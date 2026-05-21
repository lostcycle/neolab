"""WebSocket handler for the browser UI (``/api/browser``).

Hello triggers a state snapshot of the active file (if any). Broadcast events
relevant to rendering flow back live.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from neolab import viewer
from neolab.executor import Executor
from neolab.workspace import Workspace

_EDITABLE_SUFFIXES = {".py", ".pyi"}

log = logging.getLogger(__name__)


_BROWSER_FORWARD = {
    "file_synced",
    "cell_started",
    "cell_output",
    "cell_finished",
    "outputs_cleared",
    "kernel_status",
    "cursor",
    "tree",
}


async def ws_browser_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    workspace: Workspace = request.app["workspace"]
    executor: Executor = request.app["executor"]
    broadcast = request.app["broadcast"]
    sub = broadcast.subscribe()

    async def relay() -> None:
        try:
            while True:
                ev = await sub.get()
                if ev.get("type") not in _BROWSER_FORWARD:
                    continue
                try:
                    await ws.send_json(ev)
                except (ConnectionResetError, RuntimeError):
                    return
        except asyncio.CancelledError:
            return

    relay_task = asyncio.create_task(relay())

    try:
        async for ws_msg in ws:
            if ws_msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(ws_msg.data)
                except json.JSONDecodeError:
                    log.warning("browser ws: bad JSON: %r", ws_msg.data[:80])
                    continue
                await _handle(data, workspace, executor, ws)
            elif ws_msg.type == WSMsgType.ERROR:
                log.warning("browser ws error: %s", ws.exception())
    finally:
        broadcast.unsubscribe(sub)
        relay_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay_task

    return ws


async def _handle(
    data: dict[str, Any],
    workspace: Workspace,
    executor: Executor,
    ws: web.WebSocketResponse,
) -> None:
    t = data.get("type")
    if t == "hello":
        snap = (
            workspace.snapshot(executor.active_path)
            if executor.active_path is not None
            else {"path": None, "cells": [], "kernel_status": "idle"}
        )
        await ws.send_json({"type": "state", **snap})
        if workspace.tree is not None:
            await ws.send_json(
                {
                    "type": "tree",
                    "root": workspace.tree["root"],
                    "nodes": workspace.tree["nodes"],
                }
            )
    elif t == "select":
        path = Path(data["path"])
        if path.suffix.lower() in _EDITABLE_SUFFIXES:
            snap = workspace.snapshot(path)
        else:
            snap = viewer.render(path)
        await ws.send_json({"type": "state", **snap})
    else:
        log.debug("browser ws: unknown message type: %s", t)
