"""Siembra inicial: crea las tablas y un usuario admin si no existe.

Se llama desde el lifespan de main.py al arrancar.
"""

import logging

from sqlalchemy import select

from config import settings
from db.models import EmailConfig, User
from db.session import Base, SessionLocal, engine
from services.security import hash_password

logger = logging.getLogger("backend")


async def init_db() -> None:
    # Crea todas las tablas (para v1; en producción se migraría con Alembic).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # Usuario admin
        result = await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        if result.scalar_one_or_none() is None:
            db.add(
                User(
                    email=settings.ADMIN_EMAIL,
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    role="admin",
                    is_active=True,
                )
            )
            logger.info("Usuario admin sembrado: %s", settings.ADMIN_EMAIL)

        # Config de correo (fila única id=1)
        if await db.get(EmailConfig, 1) is None:
            db.add(EmailConfig(id=1))

        await db.commit()
