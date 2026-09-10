"""Router de correo: configuración de plantilla y generación del cuerpo."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Assignment, EmailConfig, LoadBatch, User, WorkSession
from db.session import get_db
from services.audit import log_action
from services.broadcast import manager
from services.email_builder import build_email_body, render_subject
from services.security import get_current_user
from services.serializers import serialize_assignments

router = APIRouter(prefix="/email", tags=["Email"])


class EmailConfigModel(BaseModel):
    to_addr: str = ""
    cc_addr: str = ""
    subject: str = "Distribución de Tickets — {{fecha}}"
    template: str = ""

    model_config = {"from_attributes": True}


async def _get_config(db: AsyncSession) -> EmailConfig:
    cfg = await db.get(EmailConfig, 1)
    if cfg is None:
        cfg = EmailConfig(id=1)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg


@router.get("/config", response_model=EmailConfigModel, summary="Obtener configuración de correo")
async def get_config(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> EmailConfigModel:
    return EmailConfigModel.model_validate(await _get_config(db))


@router.put("/config", response_model=EmailConfigModel, summary="Guardar configuración de correo")
async def put_config(
    body: EmailConfigModel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EmailConfigModel:
    cfg = await _get_config(db)
    cfg.to_addr = body.to_addr
    cfg.cc_addr = body.cc_addr
    cfg.subject = body.subject
    if body.template:
        cfg.template = body.template
    log_action(db, user, "update_email_config", "email_config")
    await db.commit()
    await db.refresh(cfg)
    await manager.broadcast_all({"type": "email_config_changed"})
    return EmailConfigModel.model_validate(cfg)


@router.get("/preview/{session_id}", summary="Generar cuerpo del correo (batch o sesión completa)")
async def preview(
    session_id: int,
    batch: str = "last",  # "last" | "all" | número de carga
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    session = await db.get(WorkSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    cfg = await _get_config(db)

    batches = (await db.execute(
        select(LoadBatch).where(LoadBatch.session_id == session_id).order_by(LoadBatch.num)
    )).scalars().all()
    if not batches:
        return {"subject": render_subject(cfg.subject), "body": "Aún no hay cargas en esta sesión."}

    stmt = select(Assignment).where(Assignment.session_id == session_id).order_by(Assignment.id)
    if batch == "all":
        target = None
        batch_label = "de la sesión completa"
    else:
        if batch == "last":
            b = batches[-1]
        else:
            b = next((x for x in batches if str(x.num) == str(batch)), None)
            if b is None:
                raise HTTPException(status_code=404, detail="Carga no encontrada")
        target = b
        stmt = stmt.where(Assignment.batch_id == b.id)
        batch_label = f"(Carga #{b.num} — {b.new_count} tickets — {b.created_at:%H:%M})"

    assignments = (await db.execute(stmt)).scalars().all()
    serialized = await serialize_assignments(db, list(assignments))
    body = build_email_body(serialized, cfg.template, batch_label)
    return {
        "subject": render_subject(cfg.subject),
        "to": cfg.to_addr,
        "cc": cfg.cc_addr,
        "body": body,
    }
