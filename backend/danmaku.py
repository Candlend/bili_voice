from __future__ import annotations

import asyncio
import json
import time
from typing import Dict, Optional, Set
import logging

from fastapi import WebSocket
from bilibili_api import Credential as BiliCredential
from bilibili_api.live import LiveDanmaku as BiliLiveDanmaku
from bilibili_api.live import LiveRoom
from bilibili_api.login_v2 import QrCodeLoginEvents

from .models import Settings
from .storage import load_settings, load_credential
from .events import create_event
from . import tts_service

logger = logging.getLogger("bili-voice.danmaku")

def build_bili_credential() -> Optional[BiliCredential]:
    cred_dto = load_credential()
    if not cred_dto or not cred_dto.is_valid():
        return None
    try:
        return BiliCredential(
            sessdata=cred_dto.sessdata or "",
            bili_jct=cred_dto.bili_jct or "",
            buvid3=cred_dto.buvid3 or "",
            buvid4=cred_dto.buvid4 or "",
            dedeuserid=cred_dto.dedeuserid or "",
            ac_time_value=cred_dto.ac_time_value or "",
        )
    except Exception:
        return None


class RoomStream:
    def __init__(self, room_id: int) -> None:
        self.room_id = room_id
        self.clients: Set[WebSocket] = set()
        self.lock = asyncio.Lock()
        self.connected = False
        self.task: Optional[asyncio.Task] = None
        self.room: Optional[BiliLiveDanmaku] = None
        self._tts_seq: int = 1

    async def ensure_started(self):
        async with self.lock:
            if self.connected:
                return
            credential = build_bili_credential()
            self.room = BiliLiveDanmaku(self.room_id, credential=credential)

            # Register event handlers
            @self.room.on("ALL")
            async def _on_event(event):
                try:
                    raw = event['data']
                except Exception:
                    return
                s = load_settings()
                if not isinstance(raw, dict):
                    return
                live_event = create_event(raw)
                payload = live_event.to_payload(s)
                logger.info(f"Event: {live_event.event_type} - Allowed: {bool(payload)}")
                if not payload:
                    return
                # Attach TTS key and broadcast payload first
                try:
                    tts_key = f"{int(time.time()*1000)}-{self._tts_seq}"
                    self._tts_seq += 1
                except Exception:
                    tts_key = None
                try:
                    if isinstance(payload, dict):
                        payload["tts_key"] = tts_key
                except Exception:
                    pass
                await self.broadcast(payload)
                # Enqueue TTS using GPT-SoVITS backend service (priority aware)
                try:
                    pr = tts_service.priority_from_event_type(live_event.event_type)
                    tts_service.enqueue_text(payload.get("text", ""), pr, key=tts_key, room_id=self.room_id)
                except Exception:
                    pass

            self.connected = True
            # Start the connection in background
            self.task = asyncio.create_task(self.room.connect())

    async def stop_if_idle(self):
        async with self.lock:
            if self.connected and not self.clients:
                try:
                    if self.room:
                        await self.room.disconnect()
                except Exception:
                    pass
                if self.task:
                    self.task.cancel()
                self.connected = False
                self.room = None
                self.task = None

    async def add_client(self, ws: WebSocket):
        self.clients.add(ws)
        await self.ensure_started()

    async def remove_client(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)
        # Grace period before stopping to avoid thrashing on quick reconnects
        asyncio.create_task(self._delayed_stop())

    async def _delayed_stop(self):
        await asyncio.sleep(3)
        await self.stop_if_idle()

    async def broadcast(self, payload: dict):
        if not self.clients:
            return
        data = json.dumps(payload, ensure_ascii=False)
        dead: Set[WebSocket] = set()
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            await self.remove_client(ws)

class DanmakuHub:
    def __init__(self) -> None:
        self.rooms: Dict[int, RoomStream] = {}
        self.lock = asyncio.Lock()

    async def add_client(self, room_id: int, ws: WebSocket):
        room = await self._get_room(room_id)
        await room.add_client(ws)

    async def remove_client(self, room_id: int, ws: WebSocket):
        room = await self._get_room(room_id)
        await room.remove_client(ws)

    async def broadcast_to_room(self, room_id: int, payload: dict):
        room = await self._get_room(room_id)
        await room.broadcast(payload)

    async def _get_room(self, room_id: int) -> RoomStream:
        async with self.lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = RoomStream(room_id)
            return self.rooms[room_id]

danmaku_hub = DanmakuHub()
