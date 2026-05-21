"""Parse jupytext-format Python files into cells.

A cell header is a line starting with `# %%` at column 0, optionally followed
by `[type]` and an arbitrary title/metadata. The space between `#` and `%%`
is required per the jupytext spec; indented headers are not recognized.

Recognized types: 'markdown' (alias 'md'), 'raw'. Default is 'code'.

Markdown cells have their leading `# ` (or just `#`) stripped from each line.

A file that starts with non-empty non-header content has an implicit leading
'code' cell of those lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADER_RE = re.compile(r"^# %%(\s.*)?$")
_TYPE_RE = re.compile(r"^\s+\[(\w+)\]")


@dataclass
class Cell:
    kind: str  # "code" | "markdown" | "raw"
    start_line: int  # 0-indexed; line of the header (or 0 for preamble)
    end_line: int  # 0-indexed exclusive (next header or EOF)
    source: str


def parse(text: str) -> list[Cell]:
    lines = text.splitlines()

    headers: list[tuple[int, str]] = []  # (line_idx, kind)
    for i, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if m:
            rest = m.group(1) or ""
            tm = _TYPE_RE.match(rest)
            headers.append((i, _normalize_kind(tm.group(1) if tm else None)))

    cells: list[Cell] = []

    if not headers:
        joined = "\n".join(lines)
        if joined.strip():
            cells.append(Cell(kind="code", start_line=0, end_line=len(lines), source=joined))
        return cells

    if headers[0][0] > 0:
        preamble = "\n".join(lines[: headers[0][0]])
        if preamble.strip():
            cells.append(Cell(kind="code", start_line=0, end_line=headers[0][0], source=preamble))

    for idx, (line_idx, kind) in enumerate(headers):
        end_line = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        body = "\n".join(lines[line_idx + 1 : end_line])
        if kind == "markdown":
            body = _strip_markdown_prefix(body)
        cells.append(Cell(kind=kind, start_line=line_idx, end_line=end_line, source=body))

    return cells


def _normalize_kind(raw: str | None) -> str:
    if raw is None:
        return "code"
    lowered = raw.lower()
    if lowered in ("markdown", "md"):
        return "markdown"
    if lowered == "raw":
        return "raw"
    return "code"


def _strip_markdown_prefix(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("# "):
            out.append(line[2:])
        elif line == "#":
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)
