"""WebSocket integration tests."""

from __future__ import annotations

import asyncio

import pytest

from neolab.server import build_app


@pytest.fixture
async def cli(aiohttp_client):
    return await aiohttp_client(build_app())


async def _drain_until(ws, predicate, timeout: float = 5.0) -> list[dict]:
    """Receive WS messages until `predicate(msg)` is True or timeout. Returns all messages seen."""
    seen: list[dict] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            m = await asyncio.wait_for(ws.receive_json(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        seen.append(m)
        if predicate(m):
            return seen
    raise TimeoutError(
        f"predicate not satisfied within {timeout}s; saw: {[s.get('type') for s in seen]}"
    )


async def test_nvim_hello_ack(cli):
    async with cli.ws_connect("/api/nvim") as ws:
        await ws.send_json({"type": "hello"})
        msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
        assert msg["type"] == "hello_ack"
        assert "version" in msg


async def test_browser_hello_empty_state(cli):
    async with cli.ws_connect("/api/browser") as ws:
        await ws.send_json({"type": "hello"})
        msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
        assert msg["type"] == "state"
        assert msg["cells"] == []


async def test_execute_cell_browser_receives_stream_output(cli):
    async with cli.ws_connect("/api/nvim") as nvim, cli.ws_connect("/api/browser") as browser:
        await nvim.send_json({"type": "hello"})
        await asyncio.wait_for(nvim.receive_json(), timeout=2)  # hello_ack
        await browser.send_json({"type": "hello"})
        await asyncio.wait_for(browser.receive_json(), timeout=2)  # state

        await nvim.send_json(
            {
                "type": "file_synced",
                "path": "/test_ws.py",
                "cells": [{"kind": "code", "source": "print('hi-from-ws-test')"}],
            }
        )
        await nvim.send_json(
            {
                "type": "execute_cell",
                "path": "/test_ws.py",
                "cell_index": 0,
            }
        )

        events = await _drain_until(browser, lambda m: m.get("type") == "cell_finished")
        types = [e["type"] for e in events]
        assert "file_synced" in types
        assert "cell_started" in types
        assert "cell_finished" in types
        streams = [
            e["output"]
            for e in events
            if e["type"] == "cell_output" and e["output"].get("type") == "stream"
        ]
        assert any("hi-from-ws-test" in s.get("text", "") for s in streams), streams


async def test_execute_cell_nvim_receives_status_events(cli):
    async with cli.ws_connect("/api/nvim") as nvim:
        await nvim.send_json({"type": "hello"})
        await asyncio.wait_for(nvim.receive_json(), timeout=2)

        await nvim.send_json(
            {
                "type": "file_synced",
                "path": "/nvim_status.py",
                "cells": [{"kind": "code", "source": "y = 7"}],
            }
        )
        await nvim.send_json(
            {
                "type": "execute_cell",
                "path": "/nvim_status.py",
                "cell_index": 0,
            }
        )

        events = await _drain_until(nvim, lambda m: m.get("type") == "cell_finished")
        types = {e["type"] for e in events}
        assert "cell_started" in types
        assert "cell_finished" in types
        # nvim must NOT see cell_output events (those go to browser only)
        assert "cell_output" not in types


async def test_execute_cells_runs_in_order(cli):
    async with cli.ws_connect("/api/nvim") as nvim, cli.ws_connect("/api/browser") as browser:
        await nvim.send_json({"type": "hello"})
        await asyncio.wait_for(nvim.receive_json(), timeout=2)
        await browser.send_json({"type": "hello"})
        await asyncio.wait_for(browser.receive_json(), timeout=2)

        await nvim.send_json(
            {
                "type": "file_synced",
                "path": "/multi.py",
                "cells": [
                    {"kind": "code", "source": "x = 40"},
                    {"kind": "code", "source": "print(x + 2)"},
                ],
            }
        )
        await nvim.send_json(
            {
                "type": "execute_cells",
                "path": "/multi.py",
                "cell_indices": [0, 1],
            }
        )

        events = await _drain_until(
            browser,
            lambda m: m.get("type") == "cell_finished" and m.get("cell_index") == 1,
        )
        streams_text = "".join(
            e["output"]["text"]
            for e in events
            if e["type"] == "cell_output" and e["output"].get("type") == "stream"
        )
        assert "42" in streams_text


async def test_clear_outputs(cli):
    async with cli.ws_connect("/api/nvim") as nvim, cli.ws_connect("/api/browser") as browser:
        await nvim.send_json({"type": "hello"})
        await asyncio.wait_for(nvim.receive_json(), timeout=2)
        await browser.send_json({"type": "hello"})
        await asyncio.wait_for(browser.receive_json(), timeout=2)

        await nvim.send_json(
            {
                "type": "file_synced",
                "path": "/clear_test.py",
                "cells": [{"kind": "code", "source": "print('first')"}],
            }
        )
        await nvim.send_json(
            {
                "type": "execute_cell",
                "path": "/clear_test.py",
                "cell_index": 0,
            }
        )
        await _drain_until(browser, lambda m: m.get("type") == "cell_finished")

        await nvim.send_json({"type": "clear_outputs", "path": "/clear_test.py"})
        seen = await _drain_until(browser, lambda m: m.get("type") == "outputs_cleared")
        assert seen[-1]["type"] == "outputs_cleared"
        assert seen[-1]["path"] == "/clear_test.py"
