"""Async pub/sub hub. Each subscriber owns a bounded queue.

Slow consumers get dropped messages rather than blocking the publisher.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)


class Broadcast:
    def __init__(self, max_queue: int = 256) -> None:
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()
        self._max = max_queue

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._max)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subs.discard(q)

    def publish(self, msg: dict[str, Any]) -> None:
        for q in self._subs:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                log.warning("dropping message for slow subscriber: type=%s", msg.get("type"))
