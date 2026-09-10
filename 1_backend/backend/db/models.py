"""Modelos ORM de Ticket Distribution.

Convenciones:
- `users`        → dispatchers que inician sesión (login + auditoría).
- `team_members` → colegas a los que se asignan tickets (distinto de users).
- `skills`       → matriz de habilidades (member × dimensión × categoría → nivel 0-5).
- `work_sessions`→ una sesión de distribución (p.ej. un día).
- `load_batches` → cada carga de Excel dentro de una sesión.
- `tickets`      → tickets normalizados del Excel.
- `assignments`  → resultado de la asignación de cada ticket.
- `audit_log`    → quién hizo qué.
- `email_config` → plantilla de correo (global, fila única).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(40), default="dispatcher")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), default="")
    base_cap: Mapped[int] = mapped_column(Integer, default=100)
    daily_cap: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    skills: Mapped[list["Skill"]] = relationship(
        back_populates="member", cascade="all, delete-orphan"
    )


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("member_id", "dimension", "category", name="uq_skill_cell"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), index=True
    )
    dimension: Mapped[str] = mapped_column(String(40))  # ticketType|systemRole|serviceArea
    category: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer, default=0)  # 0-5

    member: Mapped["TeamMember"] = relationship(back_populates="skills")


class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LoadBatch(Base):
    __tablename__ = "load_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="CASCADE"), index=True
    )
    num: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(400), default="")
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("session_id", "ticket_id", name="uq_ticket_per_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[int] = mapped_column(ForeignKey("load_batches.id", ondelete="CASCADE"))
    ticket_id: Mapped[str] = mapped_column(String(120), index=True)
    ticket_type: Mapped[str] = mapped_column(String(200), default="")
    priority: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(120), default="")
    queue_status: Mapped[str] = mapped_column(String(120), default="")
    waiting_reason: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(Text, default="")
    processor: Mapped[str] = mapped_column(String(200), default="")
    processing_queue: Mapped[str] = mapped_column(Text, default="")
    system_role: Mapped[str] = mapped_column(String(200), default="")
    service_area: Mapped[str] = mapped_column(String(200), default="")
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    reported_at: Mapped[str] = mapped_column(String(80), default="")
    metric: Mapped[str] = mapped_column(String(200), default="")
    metric_due_at: Mapped[str] = mapped_column(String(80), default="")
    cycle_due_at: Mapped[str] = mapped_column(String(80), default="")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[int] = mapped_column(ForeignKey("load_batches.id", ondelete="CASCADE"))
    ticket_pk: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), unique=True
    )
    assignee_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("team_members.id", ondelete="SET NULL"), nullable=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(40), default="ok")
    overloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    # lista de sugeridos: [{"id":int,"name":str,"score":float}, ...]
    alternatives: Mapped[list] = mapped_column(JSONB, default=list)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(120), default="")
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EmailConfig(Base):
    __tablename__ = "email_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    to_addr: Mapped[str] = mapped_column(String(400), default="")
    cc_addr: Mapped[str] = mapped_column(String(400), default="")
    subject: Mapped[str] = mapped_column(String(400), default="Distribución de Tickets — {{fecha}}")
    template: Mapped[str] = mapped_column(
        Text,
        default=(
            "Equipo,\n\nA continuación la distribución de tickets {{batch_label}}:\n\n"
            "{{asignaciones}}\nTotal: {{total}} tickets asignados.{{sin_asignar}}\n\nSaludos"
        ),
    )
