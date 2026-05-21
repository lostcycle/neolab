"""Snapshot shape tests for the non-py viewer."""

from __future__ import annotations

import json
from pathlib import Path

from neolab import viewer


def test_markdown_one_cell_with_source(tmp_path: Path) -> None:
    f = tmp_path / "notes.md"
    f.write_text("# Hello\n\nbody text\n")
    snap = viewer.render(f)
    assert snap["kernel_status"] == "idle"
    assert len(snap["cells"]) == 1
    c = snap["cells"][0]
    assert c["kind"] == "markdown"
    assert "Hello" in c["source"]
    assert c["outputs"] == []


def test_text_falls_back_to_stream(tmp_path: Path) -> None:
    f = tmp_path / "log.txt"
    f.write_text("line 1\nline 2\n")
    snap = viewer.render(f)
    out = snap["cells"][0]["outputs"][0]
    assert out["type"] == "stream"
    assert "line 1" in out["text"]


def test_json_renders_pretty_printed(tmp_path: Path) -> None:
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"a": 1, "b": [2, 3]}))
    snap = viewer.render(f)
    out = snap["cells"][0]["outputs"][0]
    assert out["type"] == "display"
    assert "application/json" in out["data"]
    assert '"a": 1' in out["data"]["application/json"]


def test_missing_file_returns_error_cell(tmp_path: Path) -> None:
    snap = viewer.render(tmp_path / "nope.csv")
    cell = snap["cells"][0]
    assert cell["status"] == "error"
    err = cell["outputs"][0]
    assert err["type"] == "error"
    assert err["ename"] == "FileNotFound"


def test_csv_renders_html_table_with_polars(tmp_path: Path) -> None:
    f = tmp_path / "small.csv"
    f.write_text("a,b\n1,2\n3,4\n")
    snap = viewer.render(f)
    out = snap["cells"][0]["outputs"][0]
    assert out["type"] == "display"
    assert "text/html" in out["data"]
    html = out["data"]["text/html"]
    # polars _repr_html_ embeds a <table> element
    assert "<table" in html
    # The header note we prepend should include row/col counts
    assert "2 rows" in html
    assert "2 cols" in html


def test_ipynb_walks_cells_and_keeps_outputs(tmp_path: Path) -> None:
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# title\n"]},
            {
                "cell_type": "code",
                "execution_count": 4,
                "source": ["x = 1\n"],
                "outputs": [
                    {"output_type": "stream", "name": "stdout", "text": ["hello\n"]},
                    {
                        "output_type": "execute_result",
                        "data": {"text/plain": "42"},
                        "metadata": {},
                    },
                ],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    f = tmp_path / "nb.ipynb"
    f.write_text(json.dumps(nb))
    snap = viewer.render(f)
    assert [c["kind"] for c in snap["cells"]] == ["markdown", "code"]
    code = snap["cells"][1]
    assert code["execution_count"] == 4
    types = [o["type"] for o in code["outputs"]]
    assert types == ["stream", "display"]
