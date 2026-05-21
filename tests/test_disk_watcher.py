"""Polling disk watcher: detects mtime/size changes on tracked files."""

from __future__ import annotations

import asyncio

from neolab.disk_watcher import DiskWatcher


async def test_track_then_change_fires_callback(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("# %%\nx = 1\n")

    loop = asyncio.get_running_loop()
    seen: list = []
    w = DiskWatcher(loop, poll_interval=0.05)
    w.set_callback(seen.append)
    w.track(f)
    w.start()
    try:
        # Force a different mtime + content so the signature changes regardless
        # of filesystem clock resolution.
        await asyncio.sleep(0.1)
        f.write_text("# %%\nx = 2\n# %%\ny = 3\n")
        for _ in range(40):
            if seen:
                break
            await asyncio.sleep(0.05)
        assert seen == [f]
    finally:
        w.stop()


async def test_untracked_file_does_not_fire(tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("x = 1\n")
    b.write_text("y = 1\n")

    loop = asyncio.get_running_loop()
    seen: list = []
    w = DiskWatcher(loop, poll_interval=0.05)
    w.set_callback(seen.append)
    w.track(a)
    w.start()
    try:
        await asyncio.sleep(0.1)
        b.write_text("y = 2\n")
        await asyncio.sleep(0.25)
        assert seen == []
    finally:
        w.stop()


async def test_no_change_no_callback(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("z = 1\n")
    loop = asyncio.get_running_loop()
    seen: list = []
    w = DiskWatcher(loop, poll_interval=0.05)
    w.set_callback(seen.append)
    w.track(f)
    w.start()
    try:
        await asyncio.sleep(0.25)
        assert seen == []
    finally:
        w.stop()
