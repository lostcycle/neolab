import asyncio
import signal
import socket
import subprocess
import sys
from pathlib import Path

import aiohttp
import pytest

from neolab.server import build_app

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app():
    return build_app()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_for_health(port: int, timeout: float = 8.0) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    async with aiohttp.ClientSession() as session:
        while asyncio.get_running_loop().time() < deadline:
            try:
                async with session.get(
                    f"http://127.0.0.1:{port}/api/health",
                    timeout=aiohttp.ClientTimeout(total=1),
                ) as r:
                    if r.status == 200:
                        return True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(0.1)
    return False


async def _drain_until(ws, event_type: str, timeout: float = 5.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        if msg.get("type") == event_type:
            return msg
    raise TimeoutError(f"never received {event_type}")


async def _wait_process_exit(proc: subprocess.Popen, timeout: float = 10.0) -> int:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        rc = proc.poll()
        if rc is not None:
            return rc
        await asyncio.sleep(0.1)
    raise subprocess.TimeoutExpired(proc.args, timeout)


async def test_health(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/api/health")
    assert resp.status == 200
    assert await resp.json() == {"ok": True, "service": "neolab"}


async def test_index(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/")
    assert resp.status == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = await resp.text()
    assert "neolab" in body


async def test_static_css(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/static/style.css")
    assert resp.status == 200
    assert "--bg" in await resp.text()


async def test_sigterm_gracefully_exits_with_running_kernel(tmp_path):
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "neolab", "--port", str(port), "--log-level", "WARNING"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert await _wait_for_health(port), "neolab server did not come up"
        source_path = tmp_path / "shutdown.py"
        source_path.write_text("# %%\nimport time\nwhile True:\n    time.sleep(1)\n")

        async with (
            aiohttp.ClientSession() as session,
            session.ws_connect(f"ws://127.0.0.1:{port}/api/nvim") as nvim,
        ):
            await nvim.send_json({"type": "hello"})
            await _drain_until(nvim, "hello_ack")
            await nvim.send_json(
                {
                    "type": "file_synced",
                    "path": str(source_path),
                    "cells": [
                        {
                            "kind": "code",
                            "source": "import time\nwhile True:\n    time.sleep(1)",
                        }
                    ],
                }
            )
            await nvim.send_json(
                {
                    "type": "execute_cell",
                    "path": str(source_path),
                    "cell_index": 0,
                }
            )
            await _drain_until(nvim, "cell_started")
            proc.send_signal(signal.SIGTERM)
            await _wait_process_exit(proc)

        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
