"""Helpers for output event dicts.

Output dicts always carry a ``type`` key:
- ``{type: "stream",  name: "stdout"|"stderr", text: str}``
- ``{type: "display", data: {<mime>: <content>}, metadata: {...}}``
- ``{type: "result",  data: {...}, metadata: {...}, execution_count: int}``
- ``{type: "error",   ename: str, evalue: str, traceback: list[str]}``
- ``{type: "clear"}``
"""

from __future__ import annotations

from typing import Any


def stream(name: str, text: str) -> dict[str, Any]:
    return {"type": "stream", "name": name, "text": text}


def display(data: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "display", "data": data, "metadata": metadata or {}}


def result(
    data: dict[str, Any],
    execution_count: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "result",
        "data": data,
        "metadata": metadata or {},
        "execution_count": execution_count,
    }


def error(ename: str, evalue: str, traceback: list[str]) -> dict[str, Any]:
    return {"type": "error", "ename": ename, "evalue": evalue, "traceback": traceback}


def clear() -> dict[str, Any]:
    return {"type": "clear"}
