"""Router de skills: matriz de habilidades por colega, dimensión y categoría."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Skill, TeamMember, Ticket, User
from db.session import get_db
from services.audit import log_action
from services.broadcast import manager
from services.security import get_current_user

router = APIRouter(prefix="/skills", tags=["Skills"])

DIMENSIONS = ["ticketType", "systemRole", "serviceArea"]
_DIM_COLUMN = {
    "ticketType": Ticket.ticket_type,
    "systemRole": Ticket.system_role,
    "serviceArea": Ticket.service_area,
}


class SkillSet(BaseModel):
    member_id: int
    dimension: str
    category: str
    level: int  # 0-5


class SkillMatrix(BaseModel):
    # dimensiones detectadas de los tickets cargados
    dimensions: dict[str, list[str]]
    # skills[member_id][dimension][category] = level
    skills: dict[int, dict[str, dict[str, int]]]


@router.get("/dimensions", summary="Categorías detectadas de los tickets")
async def get_dimensions(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for dim, col in _DIM_COLUMN.items():
        values = (await db.execute(select(col).distinct())).scalars().all()
        out[dim] = sorted({v for v in values if v})
    return out


@router.get("", response_model=SkillMatrix, summary="Matriz completa de skills")
async def get_matrix(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> SkillMatrix:
    dims: dict[str, list[str]] = {}
    for dim, col in _DIM_COLUMN.items():
        values = (await db.execute(select(col).distinct())).scalars().all()
        dims[dim] = sorted({v for v in values if v})

    matrix: dict[int, dict[str, dict[str, int]]] = {}
    member_ids = (await db.execute(select(TeamMember.id))).scalars().all()
    for mid in member_ids:
        matrix[mid] = {d: {} for d in DIMENSIONS}
    rows = (await db.execute(select(Skill))).scalars().all()
    for s in rows:
        matrix.setdefault(s.member_id, {d: {} for d in DIMENSIONS})
        matrix[s.member_id].setdefault(s.dimension, {})[s.category] = s.level
    return SkillMatrix(dimensions=dims, skills=matrix)


@router.put("", summary="Fijar el nivel de una celda de la matriz")
async def set_skill(
    body: SkillSet,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    level = max(0, min(5, body.level))
    result = await db.execute(
        select(Skill).where(
            Skill.member_id == body.member_id,
            Skill.dimension == body.dimension,
            Skill.category == body.category,
        )
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        skill = Skill(
            member_id=body.member_id, dimension=body.dimension,
            category=body.category, level=level,
        )
        db.add(skill)
    else:
        skill.level = level
    log_action(db, user, "set_skill", "skill", f"m{body.member_id} {body.dimension}/{body.category}={level}")
    await db.commit()
    await manager.broadcast_all({"type": "skills_changed"})
    return {"ok": True, "level": level}
