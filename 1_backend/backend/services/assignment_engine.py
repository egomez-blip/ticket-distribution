"""Motor de asignación de tickets.

Portado 1:1 de la lógica del prototipo 0_prototype/index.html (score1 / assignBatch):

    skillScore = ts*0.30 + rs*0.35 + as*0.35            (0-5)
    cap        = daily_cap / 100
    maxT       = max(1, round(20 * cap))
    loadFactor = max(0, 1 - load / maxT)                 (0-1)
    total      = skillScore*0.65 + loadFactor*5*0.35

Reglas:
- Sin colegas activos → sin asignar (reason="no_team").
- Si hay skills definidos y el mejor skillScore < 0.5 → sin asignar
  (reason="no_expertise") + top-3 sugeridos por skill.
- En otro caso se elige el mejor con loadFactor > 0; si todos están saturados
  se elige el mejor de todas formas y se marca overloaded (reason="overloaded").

Trabaja con dataclasses simples para no acoplarse al ORM ni a FastAPI.
"""

from dataclasses import dataclass, field


@dataclass
class MemberView:
    id: int
    name: str
    active: bool
    daily_cap: int
    # skills[dimension][category] = level (0-5)
    skills: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class TicketView:
    ticket_type: str = ""
    system_role: str = ""
    service_area: str = ""


@dataclass
class AssignmentResult:
    assignee_id: int | None
    assignee_name: str | None
    score: float
    reason: str
    overloaded: bool
    alternatives: list[dict]


def _skill(member: MemberView, dimension: str, value: str) -> int:
    if not value:
        return 0
    return member.skills.get(dimension, {}).get(value, 0)


def score_one(
    ticket: TicketView,
    members: list[MemberView],
    counts: dict[int, int],
    has_dim_data: bool,
) -> AssignmentResult:
    """Calcula la asignación de un ticket. `counts` = carga actual por member_id."""
    available = [m for m in members if m.active]
    if not available:
        return AssignmentResult(None, None, 0.0, "no_team", False, [])

    scored = []
    for m in available:
        ts = _skill(m, "ticketType", ticket.ticket_type)
        rs = _skill(m, "systemRole", ticket.system_role)
        as_ = _skill(m, "serviceArea", ticket.service_area)
        skill_score = ts * 0.30 + rs * 0.35 + as_ * 0.35
        cap = (m.daily_cap if m.daily_cap is not None else 100) / 100
        max_t = max(1, round(20 * cap))
        load = counts.get(m.id, 0)
        load_factor = max(0.0, 1 - load / max_t)
        total = skill_score * 0.65 + load_factor * 5 * 0.35
        scored.append((m, skill_score, load_factor, total))

    scored.sort(key=lambda x: x[3], reverse=True)

    alternatives = [
        {"id": s[0].id, "name": s[0].name, "score": round(s[3], 3)} for s in scored[1:4]
    ]

    if has_dim_data and scored[0][1] < 0.5:
        top3 = [
            {"id": s[0].id, "name": s[0].name, "score": round(s[1], 3)} for s in scored[:3]
        ]
        return AssignmentResult(None, None, 0.0, "no_expertise", False, top3)

    pick = next((s for s in scored if s[2] > 0), scored[0])
    overloaded = pick[2] == 0
    return AssignmentResult(
        assignee_id=pick[0].id,
        assignee_name=pick[0].name,
        score=round(pick[3], 3),
        reason="overloaded" if overloaded else "ok",
        overloaded=overloaded,
        alternatives=alternatives,
    )


def assign_batch(
    tickets: list[TicketView],
    members: list[MemberView],
    initial_counts: dict[int, int],
    has_dim_data: bool,
) -> list[AssignmentResult]:
    """Asigna una tanda de tickets, actualizando la carga a medida que avanza."""
    counts = dict(initial_counts)
    results: list[AssignmentResult] = []
    for t in tickets:
        r = score_one(t, members, counts, has_dim_data)
        if r.assignee_id is not None:
            counts[r.assignee_id] = counts.get(r.assignee_id, 0) + 1
        results.append(r)
    return results
