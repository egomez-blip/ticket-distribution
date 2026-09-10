"""Gestor de conexiones WebSocket y broadcast por sesión.

En memoria (monolito de un solo proceso): mantiene el conjunto de WebSockets
conectados por session_id y difunde eventos a todos los clientes de esa sesión.
"""

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger("backend")


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.setdefault(session_id, set()).add(ws)
        logger.info("WS conectado a sesión %s (total=%d)", session_id, len(self._conns[session_id]))

    async def disconnect(self, session_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._conns.get(session_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._conns.pop(session_id, None)

    async def broadcast(self, session_id: int, message: dict) -> None:
        """Envía `message` (JSON) a todos los clientes de la sesión. Ignora fallos."""
        async with self._lock:
            targets = list(self._conns.get(session_id, set()))
        await self._send_many(targets, message)

    async def broadcast_all(self, message: dict) -> None:
        """Envía `message` a TODOS los clientes conectados (eventos globales:
        equipo, skills, config de correo)."""
        async with self._lock:
            targets = [ws for conns in self._conns.values() for ws in conns]
        await self._send_many(targets, message)

    async def _send_many(self, targets: list[WebSocket], message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for conns in self._conns.values():
                    for ws in dead:
                        conns.discard(ws)


manager = ConnectionManager()
