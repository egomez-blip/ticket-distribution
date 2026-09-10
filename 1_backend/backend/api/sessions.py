"""Router de sesiones de distribución: crear/listar sesiones, cargar Excel
(asignación parcial de tickets nuevos) y listar asignaciones."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Assignment, LoadBatch, Ticket, User, WorkSession
from db.session import get_db
from services.assignment_engine import TicketView, assign_batch
from services.audit import log_action
from services.broadcast import manager
from services.excel_parser import parse_tickets
from services.security import get_current_user
from services.serializers import (
    has_dim_data,
    load_member_views,
    serialize_assignments,
)

router = APIRouter(prefix="/sessions", tags=["Sesiones"])


class SessionCreate(BaseModel):
    name: str | None = None


class SessionOut(BaseModel):
    id: int
    name: str
    status: str
    created_at: str
    total_tickets: int = 0
    loads: int = 0

    model_config = {"from_attributes": True}


async def _session_stats(db: AsyncSession, session_id: int) -> tuple[int, int]:
    total = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.session_id == session_id)
    )).scalar_one()
    loads = (await db.execute(
        select(func.count(LoadBatch.id)).where(LoadBatch.session_id == session_id)
    )).scalar_one()
    return total, loads


@router.get("", response_model=list[SessionOut], summary="Listar sesiones")
async def list_sessions(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> list[SessionOut]:
    sessions = (await db.execute(select(WorkSession).order_by(WorkSession.created_at.desc()))).scalars().all()
    out = []
    for s in sessions:
        total, loads = await _session_stats(db, s.id)
        out.append(SessionOut(
            id=s.id, name=s.name, status=s.status,
            created_at=s.created_at.isoformat(), total_tickets=total, loads=loads,
        ))
    return out


@router.post("", response_model=SessionOut, summary="Crear sesión de distribución")
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    from datetime import datetime
    name = body.name or f"Sesión {datetime.now():%Y-%m-%d %H:%M}"
    s = WorkSession(name=name, created_by=user.id, status="open")
    db.add(s)
    log_action(db, user, "create_session", "work_session", name)
    await db.commit()
    await db.refresh(s)
    await manager.broadcast_all({"type": "session_created", "session_id": s.id})
    return SessionOut(id=s.id, name=s.name, status=s.status, created_at=s.created_at.isoformat())


@router.get("/{session_id}/assignments", summary="Asignaciones de la sesión")
async def get_assignments(
    session_id: int,
    batch: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    stmt = select(Assignment).where(Assignment.session_id == session_id).order_by(Assignment.id)
    if batch is not None:
        b = (await db.execute(
            select(LoadBatch).where(LoadBatch.session_id == session_id, LoadBatch.num == batch)
        )).scalar_one_or_none()
        if b is None:
            return []
        stmt = stmt.where(Assignment.batch_id == b.id)
    assignments = (await db.execute(stmt)).scalars().all()
    return await serialize_assignments(db, list(assignments))


@router.get("/{session_id}/batches", summary="Cargas (batches) de la sesión")
async def get_batches(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    batches = (await db.execute(
        select(LoadBatch).where(LoadBatch.session_id == session_id).order_by(LoadBatch.num)
    )).scalars().all()
    return [
        {"num": b.num, "filename": b.filename, "new_count": b.new_count,
         "created_at": b.created_at.isoformat()}
        for b in batches
    ]


@router.post("/{session_id}/loads", summary="Cargar Excel → asignación parcial de tickets nuevos")
async def upload_load(
    session_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    session = await db.get(WorkSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    content = await file.read()
    try:
        parsed = parse_tickets(content)
    except Exception as exc:  # openpyxl lanza distintos errores según el archivo
        raise HTTPException(status_code=400, detail=f"No se pudo leer el Excel: {exc}") from exc
    if not parsed:
        raise HTTPException(status_code=400, detail="El archivo no tiene tickets válidos (falta Ticket ID).")

    # Dedupe por ticket_id contra los ya guardados en la sesión
    existing = set((await db.execute(
        select(Ticket.ticket_id).where(Ticket.session_id == session_id)
    )).scalars().all())
    fresh = [p for p in parsed if p["ticket_id"] not in existing]
    if not fresh:
        raise HTTPException(
            status_code=409,
            detail="No hay tickets nuevos en este archivo (todos ya procesados en la sesión).",
        )

    # Nuevo batch
    max_num = (await db.execute(
        select(func.coalesce(func.max(LoadBatch.num), 0)).where(LoadBatch.session_id == session_id)
    )).scalar_one()
    batch = LoadBatch(
        session_id=session_id, num=max_num + 1, filename=file.filename or "", new_count=len(fresh)
    )
    db.add(batch)
    await db.flush()  # obtener batch.id

    # Cargas actuales por colega (para el load factor)
    counts: dict[int, int] = {}
    for mid in (await db.execute(
        select(Assignment.assignee_member_id).where(Assignment.session_id == session_id)
    )).scalars().all():
        if mid is not None:
            counts[mid] = counts.get(mid, 0) + 1

    members = await load_member_views(db)
    dim_data = await has_dim_data(db)

    ticket_views = [
        TicketView(ticket_type=p["ticket_type"], system_role=p["system_role"], service_area=p["service_area"])
        for p in fresh
    ]
    results = assign_batch(ticket_views, members, counts, dim_data)

    new_assignments: list[Assignment] = []
    for p, r in zip(fresh, results):
        t = Ticket(session_id=session_id, batch_id=batch.id, **p)
        db.add(t)
        await db.flush()
        a = Assignment(
            session_id=session_id, batch_id=batch.id, ticket_pk=t.id,
            assignee_member_id=r.assignee_id, score=r.score, reason=r.reason,
            overloaded=r.overloaded, alternatives=r.alternatives,
        )
        db.add(a)
        new_assignments.append(a)

    log_action(db, user, "load_excel", "load_batch", f"sesión {session_id} carga #{batch.num}: {len(fresh)} nuevos")
    await db.commit()
    for a in new_assignments:
        await db.refresh(a)

    serialized = await serialize_assignments(db, new_assignments)
    await manager.broadcast(session_id, {
        "type": "batch_loaded",
        "session_id": session_id,
        "batch_num": batch.num,
        "new_count": len(fresh),
    })
    return {"batch_num": batch.num, "new_count": len(fresh), "assignments": serialized}
