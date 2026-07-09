import asyncio
import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger('api')


class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.add(websocket)
        logger.info(f"WebSocket baglandi | aktif={len(self.active)}")

    def disconnect(self, websocket: WebSocket):
        self.active.discard(websocket)
        logger.info(f"WebSocket kapandi | aktif={len(self.active)}")

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
