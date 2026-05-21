"""FileKernel: an isolated IPython worker process for one source file.

Public methods are thread-safe. Emitted events are delivered on the asyncio
loop's thread via ``loop.call_soon_threadsafe``.

Each ``FileKernel`` owns a separate process and a separate ``InteractiveShell``
instance. This avoids the state leaks caused by ``InteractiveShell.instance()``
and gives interrupt/restart a real process boundary.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import multiprocessing as mp
import os
import queue as queue_mod
import signal
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from IPython.core.interactiveshell import InteractiveShell

from neolab.shell_setup import JsonDisplayPublisher, capture_streams

log = logging.getLogger(__name__)


Request = tuple[str, str | None, str | None]
EventQueue = mp.Queue
RequestQueue = mp.Queue


def _noop(*args, **kwargs) -> None:
    return None


def _close_queue(q: mp.Queue | None) -> None:
    if q is None:
        return
    with contextlib.suppress(AttributeError, OSError, ValueError):
        q.cancel_join_thread()
    with contextlib.suppress(AttributeError, OSError, ValueError):
        q.close()


class _ShellRunner:
    def __init__(
        self,
        path: Path,
        emit: Callable[[dict[str, Any]], None],
    ) -> None:
        self.path = path
        self._emit = emit
        self._ref: dict[str, Any] = {"msg_id": None}

        user_ns: dict[str, Any] = {
            "__name__": "__main__",
            "__file__": str(path),
        }
        # Each kernel lives in its own process, so using IPython's singleton is
        # safe and necessary: IPython.display and matplotlib-inline publish via
        # InteractiveShell.instance().display_pub.
        InteractiveShell.clear_instance()
        self.shell = InteractiveShell.instance(user_ns=user_ns)
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
            self.shell.enable_matplotlib("inline")
        except Exception:
            log.debug("matplotlib inline backend unavailable; figures fall back to repr")

    def execute(self, msg_id: str, code: str) -> None:
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
        self._emit(payload)


def _kernel_worker(path_s: str, requests: RequestQueue, events: EventQueue) -> None:
    path = Path(path_s)
    parent = path.parent
    try:
        if parent.exists():
            os.chdir(parent)
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
    except OSError:
        pass

    runner = _ShellRunner(path, events.put)
    while True:
        kind, msg_id, code = requests.get()
        if kind == "shutdown":
            return
        if kind != "execute":
            continue
        assert msg_id is not None and code is not None
        runner.execute(msg_id, code)


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
        self._lock = threading.RLock()
        self._closed = False
        self._pending: list[str] = []
        self._active_msg_id: str | None = None
        self._requests: RequestQueue | None = None
        self._events: EventQueue | None = None
        self._process: mp.Process | None = None
        self._start_process()

    # ------------ public API ------------

    def execute(self, msg_id: str, code: str) -> None:
        with self._lock:
            if self._closed:
                return
            self._pending.append(msg_id)
            if self._requests is None or self._process is None or not self._process.is_alive():
                self._start_process()
            assert self._requests is not None
            self._requests.put(("execute", msg_id, code))

    def interrupt(self) -> None:
        """Interrupt the active execution.

        On POSIX this sends SIGINT so prior namespace state is usually
        preserved. If the process does not stop being busy promptly, callers
        can still use ``restart`` for a hard reset.
        """
        with self._lock:
            proc = self._process
            if proc is None or not proc.is_alive() or proc.pid is None:
                return
            if self._active_msg_id is None and not self._pending:
                return
            if os.name == "posix":
                try:
                    os.kill(proc.pid, signal.SIGINT)
                    return
                except OSError:
                    log.debug("failed to SIGINT kernel process for %s", self.path)
            self._cancel_inflight("KeyboardInterrupt", "execution interrupted")
            self._stop_process(force=True)
            self._start_process()

    def restart(self) -> None:
        with self._lock:
            self._cancel_inflight("KernelRestarted", "kernel restarted")
            self._stop_process(force=True)
            self._start_process()
            self._emit_from_parent({"type": "status", "msg_id": None, "state": "idle"})

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            self._stop_process(force=False)

    # ------------ process lifecycle ------------

    def _start_process(self) -> None:
        if self._closed:
            return
        self._requests = mp.Queue()
        self._events = mp.Queue()
        self._process = mp.Process(
            target=_kernel_worker,
            args=(str(self.path), self._requests, self._events),
            daemon=True,
            name=f"neolab-kernel:{self.path}",
        )
        self._process.start()
        threading.Thread(
            target=self._drain_events,
            args=(self._events, self._process),
            daemon=True,
            name=f"neolab-kernel-events:{self.path}",
        ).start()

    def _stop_process(self, *, force: bool) -> None:
        proc = self._process
        requests = self._requests
        events = self._events
        if proc is None:
            return
        if proc.is_alive() and requests is not None and not force:
            try:
                requests.put(("shutdown", None, None))
                proc.join(timeout=1.0)
            except (OSError, ValueError):
                pass
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
        self._process = None
        self._requests = None
        self._events = None
        self._active_msg_id = None
        self._pending = []
        _close_queue(requests)
        _close_queue(events)

    def _cancel_inflight(self, ename: str, evalue: str) -> None:
        with self._lock:
            msg_ids: list[str] = []
            if self._active_msg_id is not None:
                msg_ids.append(self._active_msg_id)
            msg_ids.extend(self._pending)
            seen: set[str] = set()
            for msg_id in msg_ids:
                if msg_id in seen:
                    continue
                seen.add(msg_id)
                self._emit_from_parent(
                    {
                        "type": "error",
                        "msg_id": msg_id,
                        "ename": ename,
                        "evalue": evalue,
                        "traceback": [],
                    }
                )
                self._emit_from_parent(
                    {
                        "type": "done",
                        "msg_id": msg_id,
                        "status": "error",
                        "execution_count": None,
                    }
                )
            self._active_msg_id = None
            self._pending = []

    def _drain_events(self, events: EventQueue, proc: mp.Process) -> None:
        while True:
            try:
                ev = events.get(timeout=0.1)
            except queue_mod.Empty:
                if self._closed:
                    return
                if not proc.is_alive():
                    time.sleep(0.05)
                    try:
                        ev = events.get_nowait()
                    except queue_mod.Empty:
                        with self._lock:
                            if not self._closed and self._process is proc:
                                self._cancel_inflight("KernelDied", "kernel process exited")
                                self._process = None
                                self._requests = None
                                self._events = None
                        return
                    self._handle_event(ev)
                continue
            self._handle_event(ev)

    def _handle_event(self, ev: dict[str, Any]) -> None:
        ev["path"] = str(self.path)
        et = ev.get("type")
        msg_id = ev.get("msg_id")
        with self._lock:
            if et == "status" and ev.get("state") == "busy" and msg_id is not None:
                self._active_msg_id = str(msg_id)
                self._pending = [m for m in self._pending if m != msg_id]
            elif et == "done" and msg_id is not None:
                if self._active_msg_id == msg_id:
                    self._active_msg_id = None
                self._pending = [m for m in self._pending if m != msg_id]
        self._emit_from_parent(ev)

    def _emit_from_parent(self, payload: dict[str, Any]) -> None:
        payload["path"] = str(self.path)
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
