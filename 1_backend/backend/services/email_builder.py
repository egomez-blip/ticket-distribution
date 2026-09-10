"""Construcción del cuerpo del correo de asignación.

Portado de buildEmailBody() del prototipo. Agrupa por asignado, lista tickets,
y arma un bloque de 'sin asignar' con sugerencias. Sustituye variables de plantilla.
"""

from datetime import datetime


def _today_es() -> str:
    # Fecha larga en español; datetime no depende de locale del SO.
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    now = datetime.now()
    return f"{dias[now.weekday()]}, {now.day} de {meses[now.month - 1]} de {now.year}"


def build_email_body(assignments: list[dict], template: str, batch_label: str) -> str:
    """`assignments` = lista de dicts con:
        assignee_id, assignee_name, alternatives, ticket:{ticket_id, priority,
        ticket_type, system_role, customer_name, subject}
    """
    today = _today_es()
    grouped: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    for a in assignments:
        if a.get("assignee_id"):
            grouped.setdefault(a["assignee_name"], []).append(a)
        else:
            unassigned.append(a)

    lines = ""
    for name in sorted(grouped):
        arr = grouped[name]
        lines += f"{name} ({len(arr)} ticket{'s' if len(arr) > 1 else ''}):\n"
        for a in arr:
            t = a["ticket"]
            pri = f"[{t['priority']}] " if t.get("priority") else ""
            lines += f"  • {t['ticket_id']} {pri}| {t.get('ticket_type') or '—'} | {t.get('customer_name') or '—'}\n"
            if t.get("subject"):
                subj = t["subject"]
                lines += f"    {subj[:90]}{'…' if len(subj) > 90 else ''}\n"
        lines += "\n"

    sin_block = ""
    if unassigned:
        sin_block = f"\n\n⚠ SIN ASIGNAR ({len(unassigned)} — revisión manual):\n"
        for a in unassigned:
            t = a["ticket"]
            alts = a.get("alternatives") or []
            sugs = (
                "Sugeridos: " + ", ".join(x["name"] for x in alts)
                if alts
                else "(configura skills para sugerencias)"
            )
            sin_block += f"  • {t['ticket_id']} | {t.get('ticket_type') or '—'} | {t.get('system_role') or '—'}\n    {sugs}\n"

    assigned_count = sum(len(v) for v in grouped.values())

    return (
        template.replace("{{fecha}}", today)
        .replace("{{batch_label}}", batch_label)
        .replace("{{asignaciones}}", lines.rstrip())
        .replace("{{total}}", str(assigned_count))
        .replace("{{sin_asignar}}", sin_block)
    )


def render_subject(subject: str) -> str:
    return subject.replace("{{fecha}}", _today_es())
