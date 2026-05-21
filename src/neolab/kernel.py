"""FileKernel: a worker-thread-driven IPython InteractiveShell.

Public methods are thread-safe. Emitted events are delivered on the asyncio
loop's thread via ``loop.call_soon_threadsafe``.

P1 caveat: ``InteractiveShell.instance()`` is a singleton. With a single file
this is fine; multi-file isolation (P2) will revisit, likely by swapping
``shell.user_ns`` per execute or switching to a subprocess-per-file model.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from IPython.core.interactiveshell import InteractiveShell

from neolab.shell_setup import JsonDisplayPublisher, capture_streams

log = logging.getLogger(__name__)


def _noop(*args, **kwargs) -> None:
    return None


class FileKernel:
    def __init__(
        self,
        path: Path,
        emit: Callable[[dict[str, Any]], None],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.path = path
        self._loop = loop
        self._emit_async = emit
        self._requests: queue.Queue[tuple[str, str | None, str | None]] = queue.Queue()
        self._ref: dict[str, Any] = {"msg_id": None}

        self.shell = InteractiveShell.instance()
        self._publisher = JsonDisplayPublisher(self._emit_from_thread, self._ref)
        self.shell.display_pub = self._publisher

        # IPython's built-in displayhook can't be cleanly replaced in IPython 9
        # (sys.displayhook is wired to it under the hood). Instead, neutralise
        # its output methods and emit the result event manually from
        # result.result after run_cell completes.
        dh = self.shell.displayhook
        dh.write_output_prompt = _noop  # type: ignore[assignment]
        dh.write_format_data = _noop  # type: ignore[assignment]
        dh.log_output = _noop  # type: ignore[assignment]

        _set_traceback_colorless(self.shell.InteractiveTB)
        # We emit our own structured 'error' event; suppress IPython's default print.
        self.shell.showtraceback = _noop  # type: ignore[assignment]

        try:
            self.shell.run_line_magic("matplotlib", "inline")
        except Exception:
            log.debug("matplotlib magic unavailable; figures fall back to repr")

        self._thread = threading.Thread(target=self._run, daemon=True, name=f"neolab-kernel:{path}")
        self._thread.start()

    # ------------ public API ------------

    def execute(self, msg_id: str, code: str) -> None:
        self._requests.put(("execute", msg_id, code))

    def shutdown(self) -> None:
        self._requests.put(("shutdown", None, None))

    # ------------ worker thread ------------

    def _run(self) -> None:
        while True:
            kind, msg_id, code = self._requests.get()
            if kind == "shutdown":
                return
            assert msg_id is not None and code is not None
            self._do_execute(msg_id, code)

    def _do_execute(self, msg_id: str, code: str) -> None:
        self._ref["msg_id"] = msg_id
        self._emit_from_thread({"type": "status", "msg_id": msg_id, "state": "busy"})
        try:
            with capture_streams(self._emit_from_thread, self._ref):
                result = self.shell.run_cell(code, store_history=True)
        except Exception as e:  # pragma: no cover - safety net
            log.exception("kernel crash for %s", self.path)
            self._emit_from_thread(
                {
                    "type": "error",
                    "msg_id": msg_id,
                    "ename": type(e).__name__,
                    "evalue": str(e),
                    "traceback": [str(e)],
                }
            )
            self._emit_from_thread(
                {
                    "type": "done",
                    "msg_id": msg_id,
                    "status": "error",
                    "execution_count": None,
                }
            )
            return

        if result.success and result.result is not None:
            try:
                data, metadata = self.shell.display_formatter.format(result.result)
            except Exception:
                data, metadata = {"text/plain": repr(result.result)}, {}
            if data:
                self._emit_from_thread(
                    {
                        "type": "result",
                        "msg_id": msg_id,
                        "data": data,
                        "metadata": metadata or {},
                        "execution_count": self.shell.execution_count,
                    }
                )

        if result.error_in_exec is not None:
            err = result.error_in_exec
            try:
                tb = self.shell.InteractiveTB.structured_traceback(
                    type(err), err, err.__traceback__
                )
            except Exception:
                tb = [f"{type(err).__name__}: {err}"]
            self._emit_from_thread(
                {
                    "type": "error",
                    "msg_id": msg_id,
                    "ename": type(err).__name__,
                    "evalue": str(err),
                    "traceback": tb,
                }
            )

        self._emit_from_thread({"type": "status", "msg_id": msg_id, "state": "idle"})
        self._emit_from_thread(
            {
                "type": "done",
                "msg_id": msg_id,
                "status": "ok" if result.success else "error",
                "execution_count": self.shell.execution_count,
            }
        )

    def _emit_from_thread(self, payload: dict[str, Any]) -> None:
        self._loop.call_soon_threadsafe(self._emit_async, payload)


def _set_traceback_colorless(itb: Any) -> None:
    """Configure InteractiveTB to emit plain (uncolored) tracebacks.

    Handles both IPython 9 (``set_theme_name('nocolor')``) and IPython 8
    (``set_colors('NoColor')``).
    """
    if hasattr(itb, "set_theme_name"):
        try:
            itb.set_theme_name("nocolor")
            return
        except Exception:
            pass
    if hasattr(itb, "set_colors"):
        try:
            itb.set_colors("NoColor")
        except Exception:
            log.debug("could not set traceback color scheme; falling back to default")
