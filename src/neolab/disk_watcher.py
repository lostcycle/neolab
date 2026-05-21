"""Polling file watcher for agent-friendly auto-reload.

When an external process (a coding agent, another editor, ``git pull``)
modifies one of the tracked files, the watcher fires a callback on the
asyncio loop. The Executor responds by re-reading the file, re-parsing
cells, and re-broadcasting ``file_synced`` to the browser.

We poll mtime+size rather than wire up inotify/watchfiles to keep the
dependency footprint minimal — for a handful of Python files at a 0.5s
cadence this is cheap and reliable across platforms.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

OnChange = Callable[[Path], None]


def _signature(path: Path) -> tuple[float, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime, st.st_size)


class DiskWatcher:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        poll_interval: float = 0.5,
    ) -> None:
        self._loop = loop
        self._poll = poll_interval
        self._sigs: dict[Path, tuple[float, int] | None] = {}
        self._task: asyncio.Task | None = None
        self._on_change: OnChange | None = None

    def set_callback(self, on_change: OnChange) -> None:
        self._on_change = on_change

    def track(self, path: Path) -> None:
        if path not in self._sigs:
            self._sigs[path] = _signature(path)

    def untrack(self, path: Path) -> None:
        self._sigs.pop(path, None)

    def tracked(self) -> list[Path]:
        return list(self._sigs.keys())

    def start(self) -> None:
        if self._task is None:
            self._task = self._loop.create_task(self._run(), name="neolab-disk-watcher")

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._poll)
                self._tick()
        except asyncio.CancelledError:
            return

    def _tick(self) -> None:
        for path, prev in list(self._sigs.items()):
            cur = _signature(path)
            if cur == prev:
                continue
            self._sigs[path] = cur
            if cur is None:
                # File disappeared — keep it tracked so a recreate is noticed.
                continue
            if self._on_change is None:
                continue
            try:
                self._on_change(path)
            except Exception:
                log.exception("disk watcher callback failed for %s", path)
