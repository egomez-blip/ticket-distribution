"""Router de equipo: CRUD de colegas + disponibilidad/capacidad del día."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Assignment, Skill, TeamMember, User
from db.session import get_db
from services.audit import log_action
from services.broadcast import manager
from services.security import get_current_user

router = APIRouter(prefix="/team", tags=["Equipo"])


class MemberCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = ""
    base_cap: int = 100


class MemberUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    base_cap: int | None = None
    daily_cap: int | None = None
    active: bool | None = None


class MemberOut(BaseModel):
    id: int
    name: str
    email: str
    base_cap: int
    daily_cap: int
    active: bool
    assigned_today: int = 0

    model_config = {"from_attributes": True}


async def _assigned_counts(db: AsyncSession) -> dict[int, int]:
    rows = (await db.execute(select(Assignment.assignee_member_id))).scalars().all()
    counts: dict[int, int] = {}
    for mid in rows:
        if mid is not None:
            counts[mid] = counts.get(mid, 0) + 1
    return counts


async def _serialize(db: AsyncSession, members: list[TeamMember]) -> list[MemberOut]:
    counts = await _assigned_counts(db)
    return [
        MemberOut(
            id=m.id, name=m.name, email=m.email, base_cap=m.base_cap,
            daily_cap=m.daily_cap, active=m.active, assigned_today=counts.get(m.id, 0),
        )
        for m in members
    ]


@router.get("", response_model=list[MemberOut], summary="Listar equipo")
async def list_members(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> list[MemberOut]:
    members = (await db.execute(select(TeamMember).order_by(TeamMember.name))).scalars().all()
    return await _serialize(db, list(members))


@router.post("", response_model=MemberOut, summary="Añadir colega")
async def add_member(
    body: MemberCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberOut:
    m = TeamMember(
        name=body.name.strip(), email=body.email.strip(),
        base_cap=body.base_cap, daily_cap=body.base_cap, active=True,
    )
    db.add(m)
    log_action(db, user, "add_member", "team_member", body.name)
    await db.commit()
    await db.refresh(m)
    await manager.broadcast_all({"type": "team_changed"})
    return (await _serialize(db, [m]))[0]


@router.patch("/{member_id}", response_model=MemberOut, summary="Actualizar colega")
async def update_member(
    member_id: int,
    body: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberOut:
    m = await db.get(TeamMember, member_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Colega no encontrado")
    data = body.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(m, k, v.strip() if isinstance(v, str) else v)
    log_action(db, user, "update_member", "team_member", f"{m.name}: {list(data)}")
    await db.commit()
    await db.refresh(m)
    await manager.broadcast_all({"type": "team_changed"})
    return (await _serialize(db, [m]))[0]


@router.delete("/{member_id}", status_code=204, summary="Eliminar colega")
async def delete_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    m = await db.get(TeamMember, member_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Colega no encontrado")
    await db.delete(m)
    log_action(db, user, "delete_member", "team_member", m.name)
    await db.commit()
    await manager.broadcast_all({"type": "team_changed"})


@router.post("/reset-capacities", response_model=list[MemberOut], summary="Reset capacidades del día")
async def reset_capacities(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[MemberOut]:
    members = (await db.execute(select(TeamMember))).scalars().all()
    for m in members:
        m.daily_cap = m.base_cap
    log_action(db, user, "reset_capacities", "team")
    await db.commit()
    await manager.broadcast_all({"type": "team_changed"})
    members = (await db.execute(select(TeamMember).order_by(TeamMember.name))).scalars().all()
    return await _serialize(db, list(members))
