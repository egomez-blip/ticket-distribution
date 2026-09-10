"""Endpoint WebSocket para sincronización en vivo.

El cliente se conecta a /ws?session=<id>&token=<jwt>. Se valida el JWT,
se registra la conexión en el manager y se reenvían los eventos de broadcast.
"""

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from services.broadcast import manager
from services.security import decode_token

logger = logging.getLogger("backend")

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    session: int = Query(...),
    token: str = Query(...),
) -> None:
    # Validar token antes de aceptar
    try:
        decode_token(token)
    except Exception:
        await websocket.close(code=4401)  # unauthorized
        return

    await manager.connect(session, websocket)
    try:
        # Mantener viva la conexión; ignoramos lo que envíe el cliente (ping/keepalive).
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(session, websocket)
    except Exception as exc:  # cualquier otro fallo cierra limpio
        logger.info("WS error sesión %s: %s", session, exc)
        await manager.disconnect(session, websocket)
