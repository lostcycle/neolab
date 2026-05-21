"""Hooks bolted onto an IPython InteractiveShell.

Two pieces:
- ``JsonDisplayPublisher`` — replaces ``shell.display_pub`` so that
  ``IPython.display.display(...)`` and rich-repr publishing emit JSON
  ``display`` / ``clear`` events.
- ``capture_streams`` — context manager that swaps ``sys.stdout`` and
  ``sys.stderr`` for line-emitting writers during a single execution.

Both accept a shared ``ref`` dict whose ``msg_id`` key is updated by
the FileKernel before each execution so emitted events carry the right id.

The cell's *result* value (last expression) is handled separately in
``kernel.py``: ``FileKernel`` no-ops IPython's built-in displayhook output
methods and instead formats ``result.result`` itself via
``shell.display_formatter.format``. This bypasses the IPython-9 quirk where
reassigning ``shell.displayhook`` does not redirect what gets called for
top-level expression values.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from IPython.core.displaypub import DisplayPublisher

EmitFn = Callable[[dict[str, Any]], None]


class _StreamCapture:
    def __init__(self, name: str, emit: EmitFn, ref: dict[str, Any]) -> None:
        self.name = name
        self.emit = emit
        self.ref = ref

    def write(self, text: str) -> int:
        if text:
            self.emit(
                {
                    "type": "stream",
                    "msg_id": self.ref.get("msg_id"),
                    "name": self.name,
                    "text": text,
                }
            )
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


@contextmanager
def capture_streams(emit: EmitFn, ref: dict[str, Any]):
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = _StreamCapture("stdout", emit, ref)
    sys.stderr = _StreamCapture("stderr", emit, ref)
    try:
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


class JsonDisplayPublisher(DisplayPublisher):
    def __init__(self, emit: EmitFn, ref: dict[str, Any]) -> None:
        super().__init__()
        self.emit = emit
        self.ref = ref

    def publish(self, data, metadata=None, source=None, *, transient=None, update=False):  # type: ignore[override]
        self.emit(
            {
                "type": "display",
                "msg_id": self.ref.get("msg_id"),
                "data": data,
                "metadata": metadata or {},
            }
        )

    def clear_output(self, wait: bool = False) -> None:  # type: ignore[override]
        self.emit({"type": "clear", "msg_id": self.ref.get("msg_id")})
