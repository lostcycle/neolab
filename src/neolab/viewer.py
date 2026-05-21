"""Read-only renderers for non-Python files (CSV, Parquet, Markdown, ipynb, …).

The output shape mirrors ``Workspace.snapshot`` so the browser handles
viewer cells identically to executed cells. Cells produced here have
``status = "done"`` and no execution count — they're not kernel-backed.

Tabular formats use polars; pandas is intentionally not used. The polars
import is deferred so neolab works without it; viewers that need it return
a clear error cell when it's missing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MAX_TEXT_BYTES = 200_000
MAX_TABULAR_ROWS = 1000


def render(path: Path) -> dict[str, Any]:
    """Return a snapshot dict for a non-Python file path."""
    suffix = path.suffix.lower()
    if not path.exists():
        return _err_snapshot(path, "FileNotFound", f"{path} does not exist")
    try:
        if suffix in (".md", ".markdown"):
            return _markdown(path)
        if suffix in (".csv", ".tsv"):
            return _csv(path, separator="\t" if suffix == ".tsv" else ",")
        if suffix == ".parquet":
            return _parquet(path)
        if suffix == ".ipynb":
            return _ipynb(path)
        if suffix == ".json":
            return _json(path)
        return _text(path)
    except Exception as e:
        log.exception("viewer: failed to render %s", path)
        return _err_snapshot(path, type(e).__name__, str(e))


# ---------- format-specific ----------


def _markdown(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    cell = _viewer_cell(kind="markdown", source=text, outputs=[])
    return _wrap(path, [cell])


def _csv(path: Path, separator: str = ",") -> dict[str, Any]:
    pl = _try_polars()
    if pl is None:
        return _polars_missing(path, f"{path.suffix} viewer")
    df = pl.read_csv(path, separator=separator, n_rows=MAX_TABULAR_ROWS)
    return _wrap(path, [_df_cell(df, path)])


def _parquet(path: Path) -> dict[str, Any]:
    pl = _try_polars()
    if pl is None:
        return _polars_missing(path, "parquet viewer")
    df = pl.read_parquet(path, n_rows=MAX_TABULAR_ROWS)
    return _wrap(path, [_df_cell(df, path)])


def _json(path: Path) -> dict[str, Any]:
    raw = _read_text(path)
    try:
        parsed = json.loads(raw)
        pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        cell = _viewer_cell(
            kind="code",
            outputs=[{"type": "display", "data": {"application/json": pretty}, "metadata": {}}],
        )
    except json.JSONDecodeError:
        cell = _viewer_cell(
            kind="code",
            outputs=[{"type": "stream", "name": "stdout", "text": raw}],
        )
    return _wrap(path, [cell])


def _ipynb(path: Path) -> dict[str, Any]:
    nb = json.loads(_read_text(path))
    cells: list[dict[str, Any]] = []
    for c in nb.get("cells", []):
        ct = c.get("cell_type")
        src = "".join(c.get("source", []))
        if ct == "markdown":
            cells.append(_viewer_cell(kind="markdown", source=src, outputs=[]))
        elif ct == "code":
            outs = _convert_ipynb_outputs(c.get("outputs", []))
            cells.append(
                _viewer_cell(
                    kind="code",
                    outputs=outs,
                    execution_count=c.get("execution_count"),
                )
            )
        # raw cells are skipped — they have no clean output mapping
    return _wrap(path, cells)


def _text(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    cell = _viewer_cell(
        kind="code",
        outputs=[{"type": "stream", "name": "stdout", "text": text}],
    )
    return _wrap(path, [cell])


# ---------- helpers ----------


def _try_polars():
    try:
        import polars as pl

        return pl
    except ImportError:
        return None


def _df_cell(df: Any, path: Path) -> dict[str, Any]:
    # polars frames implement _repr_html_ directly; fall back to plain repr.
    html = getattr(df, "_repr_html_", None)
    body = html() if callable(html) else f"<pre>{repr(df)}</pre>"
    rows, cols = df.shape
    note_html = (
        f"<div style='color:#8b8e98;font-size:0.75rem;margin-bottom:0.4rem'>"
        f"{path.name} — showing {rows:,} rows × {cols:,} cols"
        + (f" (capped at {MAX_TABULAR_ROWS:,})" if rows >= MAX_TABULAR_ROWS else "")
        + "</div>"
    )
    return _viewer_cell(
        kind="code",
        outputs=[{"type": "display", "data": {"text/html": note_html + body}, "metadata": {}}],
    )


def _convert_ipynb_outputs(out_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for o in out_list:
        ot = o.get("output_type")
        if ot == "stream":
            txt = o.get("text", "")
            if isinstance(txt, list):
                txt = "".join(txt)
            converted.append({"type": "stream", "name": o.get("name", "stdout"), "text": txt})
        elif ot in ("execute_result", "display_data"):
            converted.append(
                {
                    "type": "display",
                    "data": o.get("data", {}),
                    "metadata": o.get("metadata", {}),
                }
            )
        elif ot == "error":
            converted.append(
                {
                    "type": "error",
                    "ename": o.get("ename", ""),
                    "evalue": o.get("evalue", ""),
                    "traceback": list(o.get("traceback", [])),
                }
            )
    return converted


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_TEXT_BYTES:
        data = data[:MAX_TEXT_BYTES] + b"\n\n... (truncated)"
    return data.decode("utf-8", errors="replace")


def _viewer_cell(
    *,
    kind: str,
    outputs: list[dict[str, Any]],
    source: str | None = None,
    execution_count: int | None = None,
) -> dict[str, Any]:
    if any(o.get("type") == "error" for o in outputs):
        status = "error"
    elif outputs:
        status = "done"
    else:
        status = "idle"
    cell: dict[str, Any] = {
        "kind": kind,
        "outputs": outputs,
        "stale": False,
        "execution_count": execution_count,
        "status": status,
    }
    if kind == "markdown" and source is not None:
        cell["source"] = source
    return cell


def _wrap(path: Path, cells: list[dict[str, Any]]) -> dict[str, Any]:
    return {"path": str(path), "kernel_status": "idle", "cells": cells}


def _err_snapshot(path: Path, ename: str, evalue: str) -> dict[str, Any]:
    return _wrap(
        path,
        [
            _viewer_cell(
                kind="code",
                outputs=[
                    {
                        "type": "error",
                        "ename": ename,
                        "evalue": evalue,
                        "traceback": [],
                    }
                ],
            )
        ],
    )


def _polars_missing(path: Path, what: str) -> dict[str, Any]:
    return _err_snapshot(
        path,
        "MissingDependency",
        f"polars is required for the {what}. "
        "Install with `pip install neolab[data]` or `uv pip install polars`.",
    )
