"""Orchestrates kernel execution with workspace and broadcast.

All public methods are called from the asyncio loop thread.
Kernel events arrive on the loop thread via ``call_soon_threadsafe``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from neolab.broadcast import Broadcast
from neolab.disk_watcher import DiskWatcher
from neolab.jupytext import parse as parse_jupytext
from neolab.kernel import FileKernel
from neolab.workspace import Workspace

log = logging.getLogger(__name__)


class Executor:
    def __init__(
        self,
        workspace: Workspace,
        broadcast: Broadcast,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.workspace = workspace
        self.broadcast = broadcast
        self.loop = loop
        self._kernels: dict[Path, FileKernel] = {}
        self._runs: dict[str, tuple[Path, int]] = {}
        self.active_path: Path | None = None
        self._disk_watcher: DiskWatcher | None = None

    def attach_disk_watcher(self, watcher: DiskWatcher) -> None:
        self._disk_watcher = watcher
        watcher.set_callback(self._on_disk_change)

    def shutdown(self) -> None:
        for kernel in self._kernels.values():
            kernel.shutdown()
        self._kernels = {}

    # ------------ commands ------------

    def sync_file(self, path: Path, cells: list[dict[str, str]]) -> None:
        self.workspace.sync_cells(path, cells)
        self.active_path = path
        if self._disk_watcher is not None:
            self._disk_watcher.track(path)
        snap = self.workspace.snapshot(path)
        self.broadcast.publish({"type": "file_synced", **snap})

    def execute_cell(self, path: Path, cell_index: int) -> None:
        kind = self.workspace.get_cell_kind(path, cell_index)
        source = self.workspace.get_cell_source(path, cell_index)
        if source is None:
            log.warning("execute_cell: no cell at %s[%d]", path, cell_index)
            return
        if kind in ("markdown", "raw"):
            return  # non-executable cells render but don't run
        kernel = self._get_or_spawn(path)
        run_id = uuid.uuid4().hex
        self._runs[run_id] = (path, cell_index)
        self.workspace.reset_cell_outputs(path, cell_index)
        self.workspace.set_cell_status(path, cell_index, "running")
        self.broadcast.publish(
            {
                "type": "cell_started",
                "path": str(path),
                "cell_index": cell_index,
                "run_id": run_id,
            }
        )
        kernel.execute(run_id, source)

    def execute_cells(self, path: Path, cell_indices: list[int]) -> None:
        for cell_index in cell_indices:
            self.execute_cell(path, cell_index)

    def execute_source(self, path: Path, source: str, cell_index: int) -> None:
        if not source.strip():
            return
        if self.workspace.get_cell_source(path, cell_index) is None:
            log.warning("execute_source: no target cell at %s[%d]", path, cell_index)
            return
        kernel = self._get_or_spawn(path)
        run_id = uuid.uuid4().hex
        self._runs[run_id] = (path, cell_index)
        self.workspace.reset_cell_outputs(path, cell_index)
        self.workspace.set_cell_status(path, cell_index, "running")
        self.broadcast.publish(
            {
                "type": "cell_started",
                "path": str(path),
                "cell_index": cell_index,
                "run_id": run_id,
            }
        )
        kernel.execute(run_id, source)

    def clear_outputs(self, path: Path) -> None:
        self.workspace.clear_outputs(path)
        self.broadcast.publish({"type": "outputs_cleared", "path": str(path)})

    def execute_stale(self, path: Path) -> None:
        self.execute_cells(path, self.workspace.stale_code_indices(path))

    def interrupt_kernel(self, path: Path) -> None:
        kernel = self._kernels.get(path)
        if kernel is None:
            return
        kernel.interrupt()

    def restart_kernel(self, path: Path) -> None:
        kernel = self._kernels.get(path)
        if kernel is not None:
            kernel.restart()
        self.workspace.mark_code_cells_stale(path)
        self.workspace.set_kernel_status(path, "idle")
        snap = self.workspace.snapshot(path)
        self.broadcast.publish({"type": "kernel_status", "path": str(path), "state": "idle"})
        self.broadcast.publish({"type": "file_synced", **snap})

    def update_cursor(self, path: Path, cell_index: int) -> None:
        self.active_path = path
        self.broadcast.publish(
            {
                "type": "cursor",
                "path": str(path),
                "cell_index": cell_index,
            }
        )

    def update_tree(self, root: str, nodes: list[dict[str, Any]]) -> None:
        self.workspace.set_tree(root, nodes)
        self.broadcast.publish({"type": "tree", "root": root, "nodes": nodes})

    # ------------ kernel lifecycle ------------

    def _get_or_spawn(self, path: Path) -> FileKernel:
        if path not in self._kernels:
            self._kernels[path] = FileKernel(path, self._on_kernel_event, self.loop)
        return self._kernels[path]

    # ------------ disk watcher ------------

    def _on_disk_change(self, path: Path) -> None:
        """Called by the disk watcher when an externally-edited file changes.

        Re-reads from disk, re-parses cells, and broadcasts file_synced if the
        cell list differs from what we already have. Idempotent — if nvim has
        already pushed the same content (via autoread + BufReadPost), this
        becomes a no-op.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            log.debug("disk_watcher: could not read %s: %s", path, e)
            return
        parsed = parse_jupytext(text)
        new_cells = [{"kind": c.kind, "source": c.source} for c in parsed]

        fr = self.workspace.file(path)
        same = len(fr.cells) == len(new_cells) and all(
            old.kind == new["kind"] and old.source == new["source"]
            for old, new in zip(fr.cells, new_cells, strict=False)
        )
        if same:
            return
        self.sync_file(path, new_cells)

    def _on_kernel_event(self, ev: dict[str, Any]) -> None:
        et = ev["type"]
        msg_id = ev.get("msg_id")
        if et == "status":
            path_s = ev.get("path")
            path = Path(path_s) if path_s else None
            if path is not None:
                self.workspace.set_kernel_status(path, ev["state"])
                self.broadcast.publish(
                    {
                        "type": "kernel_status",
                        "path": str(path),
                        "state": ev["state"],
                    }
                )
            return
        if msg_id is None or msg_id not in self._runs:
            return
        path, cell_index = self._runs[msg_id]
        if et in ("stream", "display", "result", "error", "clear"):
            output = {k: v for k, v in ev.items() if k != "msg_id"}
            self.workspace.append_output(path, cell_index, output)
            self.broadcast.publish(
                {
                    "type": "cell_output",
                    "path": str(path),
                    "cell_index": cell_index,
                    "output": output,
                }
            )
        elif et == "done":
            status = ev["status"]
            self.workspace.set_cell_status(path, cell_index, "done" if status == "ok" else "error")
            ec = ev.get("execution_count")
            if ec is not None:
                self.workspace.set_cell_execution_count(path, cell_index, ec)
            self.broadcast.publish(
                {
                    "type": "cell_finished",
                    "path": str(path),
                    "cell_index": cell_index,
                    "status": status,
                    "execution_count": ec,
                }
            )
            del self._runs[msg_id]
