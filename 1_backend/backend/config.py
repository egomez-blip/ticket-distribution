"""Configuración del backend de Ticket Distribution.

Clase Settings que lee variables de entorno con defaults locales
(clase simple, no BaseSettings).
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _origins(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


class Settings:
    # Backend
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    CORS_ORIGINS: list[str] = _origins(
        os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
    )

    # Base de datos (asyncpg). Si DATABASE_URL no está definida, se arma desde POSTGRES_*.
    DATABASE_URL: str = os.getenv("DATABASE_URL") or (
        "postgresql+asyncpg://"
        f"{os.getenv('POSTGRES_USER', 'ticketdist')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'change-me-postgres')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'ticketdist')}"
    )

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-before-deploying")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    # Usuario admin sembrado al iniciar
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@empresa.com")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "change-me-admin")

    # SMTP (opcional)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")


settings = Settings()
