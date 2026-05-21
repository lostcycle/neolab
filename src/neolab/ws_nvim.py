"""WebSocket handler for the Neovim plugin (``/api/nvim``).

Commands in, status events out. Cell outputs themselves are sent only to the
browser — nvim only gets cell-level lifecycle events (started / finished /
error / kernel status).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from neolab import __version__
from neolab.executor import Executor

log = logging.getLogger(__name__)


async def ws_nvim_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    executor: Executor = request.app["executor"]
    broadcast = request.app["broadcast"]
    sub = broadcast.subscribe()

    async def relay() -> None:
        try:
            while True:
                ev = await sub.get()
                payload = _to_nvim(ev)
                if payload is None:
                    continue
                try:
                    await ws.send_json(payload)
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
                    log.warning("nvim ws: bad JSON: %r", ws_msg.data[:80])
                    continue
                await _handle(data, executor, ws)
            elif ws_msg.type == WSMsgType.ERROR:
                log.warning("nvim ws error: %s", ws.exception())
    finally:
        broadcast.unsubscribe(sub)
        relay_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay_task

    return ws


def _to_nvim(ev: dict[str, Any]) -> dict[str, Any] | None:
    et = ev.get("type")
    if et in ("cell_started", "cell_finished", "kernel_status", "outputs_cleared", "file_synced"):
        return ev
    if et == "cell_output":
        out = ev.get("output", {})
        if out.get("type") == "error":
            return {
                "type": "cell_error",
                "path": ev["path"],
                "cell_index": ev["cell_index"],
                "ename": out.get("ename", ""),
                "evalue": out.get("evalue", ""),
                "traceback": out.get("traceback", []),
            }
    return None


async def _handle(data: dict[str, Any], executor: Executor, ws: web.WebSocketResponse) -> None:
    t = data.get("type")
    if t == "hello":
        await ws.send_json({"type": "hello_ack", "version": __version__})
    elif t == "file_synced":
        executor.sync_file(Path(data["path"]), data.get("cells", []))
    elif t == "execute_cell":
        executor.execute_cell(Path(data["path"]), int(data["cell_index"]))
    elif t == "execute_cells":
        executor.execute_cells(Path(data["path"]), [int(i) for i in data.get("cell_indices", [])])
    elif t == "execute_source":
        executor.execute_source(
            Path(data["path"]),
            str(data.get("source", "")),
            int(data.get("cell_index", 0)),
        )
    elif t == "execute_stale":
        executor.execute_stale(Path(data["path"]))
    elif t == "clear_outputs":
        executor.clear_outputs(Path(data["path"]))
    elif t == "interrupt_kernel":
        executor.interrupt_kernel(Path(data["path"]))
    elif t == "restart_kernel":
        executor.restart_kernel(Path(data["path"]))
    elif t == "cursor":
        executor.update_cursor(Path(data["path"]), int(data["cell_index"]))
    elif t == "tree":
        executor.update_tree(str(data.get("root", "")), data.get("nodes", []))
    elif t == "goodbye":
        await ws.close()
    else:
        log.debug("nvim ws: unknown message type: %s", t)
