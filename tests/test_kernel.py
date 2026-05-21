"""End-to-end FileKernel test.

Uses one FileKernel for several scenarios in sequence — the IPython
InteractiveShell singleton makes multiple FileKernel instances per test
session messy, and sequential scenarios mirror the actual usage pattern
(persistent state across cells).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from neolab.kernel import FileKernel


async def _wait_done(received: list[dict], msg_id: str, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        for m in received:
            if m.get("type") == "done" and m.get("msg_id") == msg_id:
                return
        await asyncio.sleep(0.01)
    raise TimeoutError(
        f"no 'done' event for {msg_id!r}; received types: {[m.get('type') for m in received]}"
    )


def _stream_text(received: list[dict], msg_id: str, name: str = "stdout") -> str:
    return "".join(
        m["text"]
        for m in received
        if m["type"] == "stream" and m.get("msg_id") == msg_id and m["name"] == name
    )


@pytest.mark.asyncio
async def test_filekernel_basic_flow():
    loop = asyncio.get_running_loop()
    received: list[dict] = []
    k = FileKernel(Path("/test.py"), received.append, loop)
    try:
        # 1. print → stream event
        k.execute("m1", "print('hello neolab')")
        await _wait_done(received, "m1")
        assert "hello neolab" in _stream_text(received, "m1")

        # 2. last-expression value → result event
        n0 = len(received)
        k.execute("m2", "2 + 2")
        await _wait_done(received, "m2")
        results = [m for m in received[n0:] if m["type"] == "result"]
        assert results, [m.get("type") for m in received[n0:]]
        assert results[0]["data"]["text/plain"].strip() == "4"
        assert results[0]["execution_count"] >= 1

        # 3. variable persists between executes
        k.execute("m3", "x = 99")
        await _wait_done(received, "m3")
        k.execute("m4", "print(x)")
        await _wait_done(received, "m4")
        assert "99" in _stream_text(received, "m4")

        # 4. exception → error event + done status=error
        n0 = len(received)
        k.execute("m5", "1 / 0")
        await _wait_done(received, "m5")
        errors = [m for m in received[n0:] if m["type"] == "error"]
        assert errors, [m.get("type") for m in received[n0:]]
        assert errors[0]["ename"] == "ZeroDivisionError"
        done = next(m for m in received[n0:] if m["type"] == "done")
        assert done["status"] == "error"

        # 5. status events bracket each execution
        statuses = [m for m in received if m["type"] == "status" and m.get("msg_id") == "m1"]
        assert [s["state"] for s in statuses] == ["busy", "idle"]
    finally:
        k.shutdown()


@pytest.mark.asyncio
async def test_filekernel_instances_are_isolated():
    loop = asyncio.get_running_loop()
    left: list[dict] = []
    right: list[dict] = []
    k1 = FileKernel(Path("/left.py"), left.append, loop)
    k2 = FileKernel(Path("/right.py"), right.append, loop)
    try:
        k1.execute("l1", "x = 'left'")
        k2.execute("r1", "x = 'right'")
        await _wait_done(left, "l1")
        await _wait_done(right, "r1")

        k1.execute("l2", "print(x)")
        k2.execute("r2", "print(x)")
        await _wait_done(left, "l2")
        await _wait_done(right, "r2")

        assert "left" in _stream_text(left, "l2")
        assert "right" in _stream_text(right, "r2")
    finally:
        k1.shutdown()
        k2.shutdown()


@pytest.mark.asyncio
async def test_filekernel_emits_inline_matplotlib_figure():
    pytest.importorskip("matplotlib")
    loop = asyncio.get_running_loop()
    received: list[dict] = []
    k = FileKernel(Path("/plot.py"), received.append, loop)
    try:
        k.execute(
            "plot1",
            "import matplotlib.pyplot as plt\n"
            "plt.figure()\n"
            "plt.plot([1, 2, 3])\n",
        )
        await _wait_done(received, "plot1")
        displays = [m for m in received if m["type"] in {"display", "result"}]
        assert any("image/png" in m.get("data", {}) for m in displays), displays
    finally:
        k.shutdown()
