"""Helpers compartidos: cargar colegas como MemberView y serializar asignaciones."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Assignment, Skill, TeamMember, Ticket
from services.assignment_engine import MemberView

DIMENSIONS = ["ticketType", "systemRole", "serviceArea"]


async def load_member_views(db: AsyncSession) -> list[MemberView]:
    """Carga todos los colegas con su matriz de skills anidada."""
    members = (await db.execute(select(TeamMember))).scalars().all()
    skills = (await db.execute(select(Skill))).scalars().all()
    by_member: dict[int, dict[str, dict[str, int]]] = {}
    for s in skills:
        by_member.setdefault(s.member_id, {}).setdefault(s.dimension, {})[s.category] = s.level
    return [
        MemberView(
            id=m.id, name=m.name, active=m.active, daily_cap=m.daily_cap,
            skills=by_member.get(m.id, {}),
        )
        for m in members
    ]


async def has_dim_data(db: AsyncSession) -> bool:
    """True si hay al menos una categoría en ticketType o systemRole (tickets cargados)."""
    for col in (Ticket.ticket_type, Ticket.system_role):
        row = (await db.execute(select(col).where(col != "").limit(1))).first()
        if row:
            return True
    return False


def ticket_to_dict(t: Ticket) -> dict:
    return {
        "id": t.id,
        "ticket_id": t.ticket_id,
        "ticket_type": t.ticket_type,
        "priority": t.priority,
        "status": t.status,
        "queue_status": t.queue_status,
        "waiting_reason": t.waiting_reason,
        "subject": t.subject,
        "processor": t.processor,
        "processing_queue": t.processing_queue,
        "system_role": t.system_role,
        "service_area": t.service_area,
        "customer_name": t.customer_name,
        "reported_at": t.reported_at,
        "metric": t.metric,
        "metric_due_at": t.metric_due_at,
        "cycle_due_at": t.cycle_due_at,
    }


def assignment_to_dict(a: Assignment, t: Ticket, member_name: str | None, batch_num: int) -> dict:
    return {
        "id": a.id,
        "session_id": a.session_id,
        "batch_id": a.batch_id,
        "batch_num": batch_num,
        "assignee_id": a.assignee_member_id,
        "assignee_name": member_name,
        "score": a.score,
        "reason": a.reason,
        "overloaded": a.overloaded,
        "manual_override": a.manual_override,
        "alternatives": a.alternatives or [],
        "ticket": ticket_to_dict(t),
    }


async def serialize_assignments(db: AsyncSession, assignments: list[Assignment]) -> list[dict]:
    """Serializa una lista de Assignment resolviendo ticket, nombre y batch_num."""
    if not assignments:
        return []
    ticket_ids = [a.ticket_pk for a in assignments]
    member_ids = [a.assignee_member_id for a in assignments if a.assignee_member_id]
    batch_ids = [a.batch_id for a in assignments]

    tickets = {
        t.id: t
        for t in (await db.execute(select(Ticket).where(Ticket.id.in_(ticket_ids)))).scalars()
    }
    names = {
        m.id: m.name
        for m in (await db.execute(select(TeamMember).where(TeamMember.id.in_(member_ids)))).scalars()
    } if member_ids else {}

    from db.models import LoadBatch
    batch_nums = {
        b.id: b.num
        for b in (await db.execute(select(LoadBatch).where(LoadBatch.id.in_(batch_ids)))).scalars()
    }

    out = []
    for a in assignments:
        t = tickets.get(a.ticket_pk)
        if t is None:
            continue
        out.append(
            assignment_to_dict(a, t, names.get(a.assignee_member_id), batch_nums.get(a.batch_id, 0))
        )
    return out
