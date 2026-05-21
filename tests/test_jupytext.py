from neolab.jupytext import parse


def test_empty():
    assert parse("") == []


def test_whitespace_only_no_cells():
    assert parse("\n\n  \n") == []


def test_no_headers_pure_code():
    cells = parse("import x\nx = 1")
    assert len(cells) == 1
    assert cells[0].kind == "code"
    assert cells[0].source == "import x\nx = 1"


def test_single_code_cell():
    cells = parse("# %%\nprint('hi')")
    assert len(cells) == 1
    assert cells[0].kind == "code"
    assert cells[0].source == "print('hi')"


def test_two_code_cells():
    cells = parse("# %%\nprint('a')\n# %%\nprint('b')")
    assert [c.kind for c in cells] == ["code", "code"]
    assert [c.source for c in cells] == ["print('a')", "print('b')"]


def test_preamble_then_cell():
    cells = parse("import x\n# %%\nx.do()")
    assert len(cells) == 2
    assert cells[0].kind == "code"
    assert cells[0].source == "import x"
    assert cells[1].source == "x.do()"


def test_markdown_cell():
    text = "# %% [markdown]\n# This is a heading\n# with two lines\n# %%\nprint('end')"
    cells = parse(text)
    assert len(cells) == 2
    assert cells[0].kind == "markdown"
    assert cells[0].source == "This is a heading\nwith two lines"
    assert cells[1].source == "print('end')"


def test_md_alias():
    cells = parse("# %% [md]\n# hi")
    assert cells[0].kind == "markdown"


def test_raw_cell():
    cells = parse("# %% [raw]\nraw text")
    assert cells[0].kind == "raw"
    assert cells[0].source == "raw text"


def test_title_after_type_ignored():
    cells = parse("# %% [markdown] Some Title\n# heading")
    assert cells[0].kind == "markdown"
    assert cells[0].source == "heading"


def test_header_with_title_is_code():
    cells = parse("# %% Title\nprint(1)")
    assert cells[0].kind == "code"
    assert cells[0].source == "print(1)"


def test_indented_header_not_recognized():
    cells = parse("  # %%\nfoo")
    assert len(cells) == 1
    assert cells[0].kind == "code"


def test_no_space_after_hash_not_recognized():
    cells = parse("#%%\nfoo")
    assert len(cells) == 1
    assert cells[0].kind == "code"


def test_consecutive_headers_empty_first():
    cells = parse("# %%\n# %%\nprint('x')")
    assert len(cells) == 2
    assert cells[0].source == ""
    assert cells[1].source == "print('x')"


def test_header_only():
    cells = parse("# %%")
    assert len(cells) == 1
    assert cells[0].source == ""


def test_unknown_bracket_falls_back_to_code():
    cells = parse("# %% [weird]\nx = 1")
    assert cells[0].kind == "code"


def test_start_end_lines():
    cells = parse("# %%\na\nb\n# %%\nc")
    assert cells[0].start_line == 0
    assert cells[0].end_line == 3
    assert cells[1].start_line == 3
    assert cells[1].end_line == 5
