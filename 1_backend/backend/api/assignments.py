"""Router de asignaciones: reasignación manual de un ticket."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Assignment, TeamMember, User
from db.session import get_db
from services.audit import log_action
from services.broadcast import manager
from services.security import get_current_user
from services.serializers import serialize_assignments

router = APIRouter(prefix="/assignments", tags=["Asignaciones"])


class Reassign(BaseModel):
    assignee_member_id: int | None  # None = dejar sin asignar


@router.patch("/{assignment_id}", summary="Reasignar manualmente un ticket")
async def reassign(
    assignment_id: int,
    body: Reassign,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    a = await db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")

    if body.assignee_member_id is not None:
        member = await db.get(TeamMember, body.assignee_member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Colega no encontrado")
        a.assignee_member_id = member.id
        a.overloaded = False
        a.reason = "manual"
    else:
        a.assignee_member_id = None
        a.reason = "manual_unassigned"
    a.manual_override = True

    log_action(db, user, "reassign", "assignment", f"a{assignment_id} → {body.assignee_member_id}")
    await db.commit()
    await db.refresh(a)

    await manager.broadcast(a.session_id, {
        "type": "assignment_changed",
        "session_id": a.session_id,
        "assignment_id": a.id,
    })
    result = await serialize_assignments(db, [a])
    return result[0]
