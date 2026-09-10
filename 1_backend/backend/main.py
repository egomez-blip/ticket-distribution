"""Ticket Distribution — Backend (monolito modular FastAPI).

Punto de entrada único: registra los routers, expone /health y crea las tablas
+ el usuario admin al arrancar (lifespan).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.assignments import router as assignments_router
from api.auth import router as auth_router
from api.email import router as email_router
from api.sessions import router as sessions_router
from api.skills import router as skills_router
from api.team import router as team_router
from api.ws import router as ws_router
from config import settings
from db.seed import init_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Ticket Distribution API",
    description=(
        "Backend del sistema de distribución de tickets. Un solo servicio "
        "(monolito modular) con auth JWT, PostgreSQL y sincronización en vivo por WebSocket."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(team_router)
app.include_router(skills_router)
app.include_router(sessions_router)
app.include_router(assignments_router)
app.include_router(email_router)
app.include_router(ws_router)


@app.get("/health", tags=["Service"])
def health():
    return {"status": "ok", "service": "backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.BACKEND_HOST, port=settings.BACKEND_PORT, reload=True)
