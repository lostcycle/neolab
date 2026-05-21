"""In-memory workspace state: per-file cells and outputs.

All mutations happen on the asyncio loop thread. Kernel worker threads post
events back via ``loop.call_soon_threadsafe`` and never touch this directly.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _hash_source(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


@dataclass
class CellRecord:
    kind: str
    source: str
    outputs: list[dict[str, Any]] = field(default_factory=list)
    stale: bool = False
    execution_count: int | None = None
    status: str = "idle"  # "idle" | "running" | "done" | "error"

    @property
    def source_hash(self) -> str:
        return _hash_source(self.source)


@dataclass
class FileRecord:
    path: Path
    cells: list[CellRecord] = field(default_factory=list)
    kernel_status: str = "idle"  # "idle" | "busy" | "dead"


class Workspace:
    def __init__(self) -> None:
        self._files: dict[Path, FileRecord] = {}
        self.tree: dict[str, Any] | None = None  # {root, nodes}

    def set_tree(self, root: str, nodes: list[dict[str, Any]]) -> None:
        self.tree = {"root": root, "nodes": nodes}

    def file(self, path: Path) -> FileRecord:
        if path not in self._files:
            self._files[path] = FileRecord(path=path)
        return self._files[path]

    def sync_cells(self, path: Path, cells: list[dict[str, str]]) -> None:
        """Replace the cell list for ``path``.

        For each new cell at index ``i``, if the prior cell at ``i`` has the
        same ``kind`` and source hash, its outputs and status carry over.
        Otherwise outputs at index ``i`` are kept but marked ``stale``.
        Cells beyond the new length are dropped.
        """
        fr = self.file(path)
        old = fr.cells
        new: list[CellRecord] = []
        for i, c in enumerate(cells):
            kind = c["kind"]
            source = c["source"]
            record = CellRecord(kind=kind, source=source)
            if i < len(old) and old[i].kind == kind and old[i].source_hash == record.source_hash:
                record.outputs = old[i].outputs
                record.execution_count = old[i].execution_count
                record.status = old[i].status
                record.stale = False
            elif i < len(old):
                record.outputs = old[i].outputs
                record.stale = True
            new.append(record)
        fr.cells = new

    def get_cell_source(self, path: Path, cell_index: int) -> str | None:
        fr = self._files.get(path)
        if fr is None or not (0 <= cell_index < len(fr.cells)):
            return None
        return fr.cells[cell_index].source

    def get_cell_kind(self, path: Path, cell_index: int) -> str | None:
        fr = self._files.get(path)
        if fr is None or not (0 <= cell_index < len(fr.cells)):
            return None
        return fr.cells[cell_index].kind

    def cell_count(self, path: Path) -> int:
        fr = self._files.get(path)
        return 0 if fr is None else len(fr.cells)

    def append_output(self, path: Path, cell_index: int, output: dict[str, Any]) -> None:
        fr = self._files.get(path)
        if fr is None or not (0 <= cell_index < len(fr.cells)):
            return
        fr.cells[cell_index].outputs.append(output)
        fr.cells[cell_index].stale = False

    def reset_cell_outputs(self, path: Path, cell_index: int) -> None:
        fr = self._files.get(path)
        if fr is None or not (0 <= cell_index < len(fr.cells)):
            return
        fr.cells[cell_index].outputs = []
        fr.cells[cell_index].stale = False

    def clear_outputs(self, path: Path) -> None:
        fr = self._files.get(path)
        if fr is None:
            return
        for c in fr.cells:
            c.outputs = []
            c.execution_count = None
            c.status = "idle"
            c.stale = False

    def set_cell_status(self, path: Path, cell_index: int, status: str) -> None:
        fr = self._files.get(path)
        if fr is None or not (0 <= cell_index < len(fr.cells)):
            return
        fr.cells[cell_index].status = status

    def set_cell_execution_count(self, path: Path, cell_index: int, count: int) -> None:
        fr = self._files.get(path)
        if fr is None or not (0 <= cell_index < len(fr.cells)):
            return
        fr.cells[cell_index].execution_count = count

    def set_kernel_status(self, path: Path, status: str) -> None:
        self.file(path).kernel_status = status

    def snapshot(self, path: Path) -> dict[str, Any]:
        fr = self._files.get(path)
        if fr is None:
            return {"path": str(path), "cells": [], "kernel_status": "idle"}
        return {
            "path": str(path),
            "kernel_status": fr.kernel_status,
            "cells": [
                {
                    "kind": c.kind,
                    "outputs": c.outputs,
                    "stale": c.stale,
                    "execution_count": c.execution_count,
                    "status": c.status,
                }
                for c in fr.cells
            ],
        }
