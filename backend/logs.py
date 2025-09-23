from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Deque, Optional, Set, Dict, Any

from fastapi import WebSocket


class LogsHub:
    """
    Broadcasts log records to connected WebSocket clients at /ws/logs.
    Keeps a small ring buffer of recent logs and replays them to new clients.
    """
    def __init__(self, max_recent: int = 200) -> None:
        self.clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._recent: Deque[Dict[str, Any]] = deque(maxlen=max_recent)

    async def add_client(self, ws: WebSocket):
        async with self._lock:
            self.clients.add(ws)
            # replay recent logs to the new client
            try:
                for item in list(self._recent):
                    await ws.send_text(json.dumps(item, ensure_ascii=False))
            except Exception:
                # ignore send errors here
                pass

    async def remove_client(self, ws: WebSocket):
        async with self._lock:
            if ws in self.clients:
                self.clients.remove(ws)

    async def broadcast(self, payload: Dict[str, Any]):
        # cache in recent buffer
        try:
            self._recent.append(payload)
        except Exception:
            pass
        if not self.clients:
            return
        dead: Set[WebSocket] = set()
        data = json.dumps(payload, ensure_ascii=False)
        # Make a copy to avoid set changed during iteration
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self.clients:
                        self.clients.remove(ws)


_logs_hub: Optional[LogsHub] = None


def get_logs_hub() -> LogsHub:
    global _logs_hub
    if _logs_hub is None:
        _logs_hub = LogsHub()
    return _logs_hub


class WSLogHandler(logging.Handler):
    """
    Logging handler that forwards log records to the LogsHub over the app event loop.
    """
    def __init__(self, loop_getter) -> None:
        super().__init__()
        self._loop_getter = loop_getter  # callable that returns an asyncio loop or None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Format payload
            payload = {
                "type": "LOG",
                "ts": record.created,
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "pathname": record.pathname,
                "lineno": record.lineno,
                "funcName": record.funcName,
            }
            loop = None
            try:
                loop = self._loop_getter()
            except Exception:
                loop = None
            if loop and loop.is_running():
                hub = get_logs_hub()
                fut = asyncio.run_coroutine_threadsafe(hub.broadcast(payload), loop)
                # Optionally result() to surface exceptions; we ignore to avoid blocking
            # If no loop, drop silently
        except Exception:
            # Never raise from emit
            pass


def install_log_handler(loop_getter, level: int = logging.INFO):
    """
    Install WSLogHandler on the root logger. loop_getter should return the running asyncio loop.
    """
    handler = WSLogHandler(loop_getter)
    handler.setLevel(level)
    root = logging.getLogger()
    root.addHandler(handler)
    # Ensure root level allows INFO and above
    if root.level > level:
        root.setLevel(level)
