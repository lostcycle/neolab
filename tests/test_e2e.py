"""End-to-end smoke test: real neolab server + real nvim + real browser WS.

Validates that:
- the Lua WebSocket client speaks the same protocol as the Python WS endpoints,
- the cell parser produces the same shape on both sides,
- an execute command from nvim produces ``cell_output`` events visible to a
  browser-side WebSocket subscriber.

Skipped if ``nvim`` is not on ``PATH``.
"""

from __future__ import annotations

import asyncio
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import aiohttp
import pytest

pytestmark = pytest.mark.skipif(shutil.which("nvim") is None, reason="nvim binary not available")

REPO_ROOT = Path(__file__).resolve().parent.parent


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


async def test_e2e_nvim_execute_emits_output(tmp_path):
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "neolab", "--port", str(port), "--log-level", "WARNING"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert await _wait_for_health(port), "neolab server did not come up"

        test_py = tmp_path / "e2e_test.py"
        test_py.write_text("# %%\nprint('e2e_marker_xyz')\n")

        async with (
            aiohttp.ClientSession() as session,
            session.ws_connect(f"ws://127.0.0.1:{port}/api/browser") as browser,
        ):
            await browser.send_json({"type": "hello"})
            first = await asyncio.wait_for(browser.receive_json(), timeout=2)
            assert first["type"] == "state"

            lua_setup = f"require('neolab').setup({{server={{host='127.0.0.1',port={port}}}}})"
            nvim_proc = subprocess.Popen(
                [
                    "nvim",
                    "--headless",
                    "--noplugin",
                    "--cmd",
                    f"set rtp+={REPO_ROOT}",
                    "-c",
                    "lua " + lua_setup,
                    "-c",
                    f"edit {test_py}",
                    # Give the plugin time to handshake the WS and send
                    # file_synced before we trigger the run. The first execute
                    # also pays for InteractiveShell.instance() init.
                    "-c",
                    "lua vim.defer_fn(function() vim.cmd('NeolabRun') end, 1500)",
                    "-c",
                    "lua vim.defer_fn(function() vim.cmd('qa!') end, 9000)",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            events: list[dict] = []
            deadline = asyncio.get_running_loop().time() + 12
            while asyncio.get_running_loop().time() < deadline:
                try:
                    m = await asyncio.wait_for(browser.receive_json(), timeout=0.5)
                except asyncio.TimeoutError:
                    if nvim_proc.poll() is not None:
                        await asyncio.sleep(0.3)
                        break
                    continue
                events.append(m)
                if m.get("type") == "cell_finished":
                    break

            try:
                nvim_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                nvim_proc.kill()

        types = [e["type"] for e in events]
        assert "cell_started" in types, f"never got cell_started; events={types}"
        assert "cell_finished" in types, f"never got cell_finished; events={types}"
        streams_text = "".join(
            e["output"]["text"]
            for e in events
            if e["type"] == "cell_output" and e["output"].get("type") == "stream"
        )
        assert "e2e_marker_xyz" in streams_text, (
            f"marker not in stream output: {streams_text!r}; event types: {types}"
        )

    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
