"""Helper de auditoría: registra quién hizo qué."""

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog, User


def log_action(db: AsyncSession, user: User | None, action: str, entity: str = "", detail: str = "") -> None:
    """Agrega una entrada al audit_log (no hace commit; lo hace el caller)."""
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else "",
            action=action,
            entity=entity,
            detail=detail,
        )
    )
