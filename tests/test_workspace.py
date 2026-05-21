from pathlib import Path

from neolab.workspace import Workspace


def _cells(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"kind": k, "source": s} for k, s in pairs]


def test_sync_creates_cells():
    ws = Workspace()
    ws.sync_cells(Path("/t.py"), _cells(("code", "x = 1"), ("code", "x")))
    fr = ws.file(Path("/t.py"))
    assert len(fr.cells) == 2
    assert fr.cells[0].source == "x = 1"
    assert fr.cells[1].source == "x"


def test_sync_preserves_outputs_for_unchanged():
    ws = Workspace()
    p = Path("/t.py")
    ws.sync_cells(p, _cells(("code", "x = 1")))
    ws.append_output(p, 0, {"type": "stream", "name": "stdout", "text": "out\n"})
    ws.sync_cells(p, _cells(("code", "x = 1")))
    assert ws.file(p).cells[0].outputs == [{"type": "stream", "name": "stdout", "text": "out\n"}]
    assert ws.file(p).cells[0].stale is False


def test_sync_marks_changed_cells_stale():
    ws = Workspace()
    p = Path("/t.py")
    ws.sync_cells(p, _cells(("code", "x = 1")))
    ws.append_output(p, 0, {"type": "stream", "name": "stdout", "text": "old\n"})
    ws.sync_cells(p, _cells(("code", "x = 2")))
    assert ws.file(p).cells[0].stale is True
    assert ws.file(p).cells[0].outputs[0]["text"] == "old\n"


def test_sync_drops_trailing_cells():
    ws = Workspace()
    p = Path("/t.py")
    ws.sync_cells(p, _cells(("code", "a"), ("code", "b")))
    ws.sync_cells(p, _cells(("code", "a")))
    assert ws.cell_count(p) == 1


def test_clear_outputs_resets_state():
    ws = Workspace()
    p = Path("/t.py")
    ws.sync_cells(p, _cells(("code", "x = 1")))
    ws.append_output(p, 0, {"type": "stream", "name": "stdout", "text": "x\n"})
    ws.set_cell_status(p, 0, "done")
    ws.set_cell_execution_count(p, 0, 3)
    ws.clear_outputs(p)
    c = ws.file(p).cells[0]
    assert c.outputs == []
    assert c.execution_count is None
    assert c.status == "idle"


def test_get_cell_source_returns_none_for_out_of_range():
    ws = Workspace()
    p = Path("/t.py")
    ws.sync_cells(p, _cells(("code", "x")))
    assert ws.get_cell_source(p, 5) is None
    assert ws.get_cell_source(Path("/missing.py"), 0) is None


def test_snapshot_shape():
    ws = Workspace()
    p = Path("/t.py")
    ws.sync_cells(p, _cells(("code", "x"), ("markdown", "hi")))
    snap = ws.snapshot(p)
    assert snap["path"] == str(p)
    assert [c["kind"] for c in snap["cells"]] == ["code", "markdown"]
