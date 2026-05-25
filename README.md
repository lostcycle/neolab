# neolab

A Neovim plugin for Jupytext-style Python files with a live browser output
view. Edit cells in Neovim; outputs (plots, DataFrames, errors, markdown)
stream to the browser as you run them.

- Multi-file, kernel-backed, fully local.
- Cells follow the [jupytext](https://jupytext.readthedocs.io/) "percent"
  format (`# %%`, `# %% [markdown]`).
- Intentionally not an `.ipynb` workflow. The source of truth is plain `.py`.
- External edits — coding agents, `git pull`, another editor — auto-reload
  in both Neovim and the browser.
- No pandas dependency; uses polars for any tabular rendering.
- Per-file Python kernels, stale-output tracking, and browser-side search
  controls for exploratory work.

---

## Install

You need two pieces:

1. The **Python server** (`neolab` command).
2. The **Neovim plugin** (this repo).

### 1. Install the Python server

Install the server into a tool environment so `neolab` is on `$PATH`:

```sh
uv tool install neolab          # recommended
# or
pipx install neolab
```

Building from a local checkout:

```sh
uv tool install --force .       # or: pipx install --force .
```

### 2. Add the plugin with lazy.nvim

Drop this in `~/.config/nvim/lua/plugins/neolab.lua` (or wherever your lazy
specs live):

```lua
return {
  "lostcycle/neolab",
  ft = "python",
  cmd = {
    "NeolabPing",
    "NeolabRun",
    "NeolabRunAndAdvance",
    "NeolabRunAll",
    "NeolabRunAbove",
    "NeolabRunBelow",
    "NeolabRunSelection",
    "NeolabRunStale",
    "NeolabInterrupt",
    "NeolabRestart",
    "NeolabClear",
    "NeolabSync",
  },
  opts = {
    server = { host = "127.0.0.1", port = 9494 },
  },
  config = function(_, opts)
    require("neolab").setup(opts)
  end,
}
```

To pin a release: add `version = "v0.1.0"` (or `tag = "v0.1.0"`). Until you
tag, lazy tracks the default branch.

**Building the server as part of the lazy install** (skip step 1):

```lua
return {
  "lostcycle/neolab",
  ft = "python",
  build = "uv tool install --force .",   -- or: pipx install --force .
  cmd = {
    "NeolabPing",
    "NeolabRun",
    "NeolabRunAndAdvance",
    "NeolabRunAll",
    "NeolabRunAbove",
    "NeolabRunBelow",
    "NeolabRunSelection",
    "NeolabRunStale",
    "NeolabInterrupt",
    "NeolabRestart",
    "NeolabClear",
    "NeolabSync",
  },
  config = function() require("neolab").setup({}) end,
}
```

### 3. Run the Python server

Start the server in a shell before using the plugin:

```sh
neolab                              # binds 127.0.0.1:9494
neolab --host 0.0.0.0 --port 9494   # remote-reachable
neolab --port 9595 --log-level DEBUG
```

Open <http://127.0.0.1:9494> in your browser. Then open any `.py` file in
Neovim — the plugin attaches automatically, syncs the file tree, and streams
cell outputs to the browser.

If the server is not running yet, `:NeolabPing` will retry the configured
WebSocket endpoint.

---

## Default keymaps

Buffer-local, applied to Python files only. All are normal-mode.

| Key          | Command         | What it does                                 |
| ------------ | --------------- | -------------------------------------------- |
| `<leader>r`  | `:NeolabRun`    | Execute the cell under the cursor            |
| `<leader>j`  | `:NeolabRunAndAdvance` | Execute current cell and jump to next cell |
| `<leader>ra` | `:NeolabRunAll` | Execute all code cells                       |
| `<leader>rA` | `:NeolabRunAbove` | Execute code cells above the cursor        |
| `<leader>rb` | `:NeolabRunBelow` | Execute code cells from cursor to EOF      |
| `<leader>rs` | `:NeolabRunSelection` | Execute the visual selection              |
| `<leader>rt` | `:NeolabRunStale` | Execute cells with stale outputs           |
| `<leader>ri` | `:NeolabInterrupt` | Interrupt the current file kernel          |
| `<leader>rk` | `:NeolabRestart` | Restart the current file kernel             |
| `<leader>R`  | `:NeolabClear`  | Clear all cell outputs for the current file  |

Override or disable per keymap:

```lua
opts = {
  keymaps = {
    execute_cell = "<leader>jr",   -- remap
    execute_all = "<leader>ja",
    clear_outputs = false,          -- disable
  },
}
```

---

## Commands

| Command                     | Description                                         |
| --------------------------- | --------------------------------------------------- |
| `:NeolabPing`               | Connect to (or re-check) the server.                |
| `:NeolabRun`                | Execute the cell at the cursor.                     |
| `:NeolabRunAndAdvance`      | Execute the cell at the cursor and jump to next.    |
| `:NeolabRunAll`             | Execute all code cells in the current buffer.       |
| `:NeolabRunAbove`           | Execute code cells above the cursor.                |
| `:NeolabRunBelow`           | Execute code cells from the cursor to EOF.          |
| `:NeolabRunSelection`       | Execute the selected source in the file kernel.     |
| `:NeolabRunStale`           | Execute cells whose prior outputs are stale.        |
| `:NeolabInterrupt`          | Interrupt the current file kernel.                  |
| `:NeolabRestart`            | Restart the current file kernel.                    |
| `:NeolabClear`              | Clear all outputs for the current buffer.           |
| `:NeolabSync`               | Force a cell re-sync to the server.                 |
| `:NeolabCellmarksToggle`    | Toggle visual cell delimiters in the current buffer. |

Neovim shows lightweight cell status using signs and virtual text:

- `running` while a cell is executing.
- `In [n]` when a cell completed successfully.
- `error` with a quickfix traceback when execution fails.
- `stale` when an edited cell or downstream executed cell may no longer match
  the current source.

---

## Cell delimiters

`# %%` headers get a tinted background bar in the buffer plus a horizontal
separator above them. Markdown cells (`# %% [markdown]`) use a different
tint so they're visually distinct.

Override the highlight groups in your colorscheme config if needed:

- `NeolabCellDelim` (links to `CursorLine` by default) — code cells
- `NeolabCellDelimMd` (links to `Visual` by default) — markdown cells
- `NeolabCellSep` (links to `NonText` by default) — separator line

---

## Agent-friendly auto-reload

When an external process modifies a file you have open:

- **Neovim** notices via libuv's `fs_event` and runs `:checktime` — buffers
  refresh automatically (`autoread` is set on attached buffers), and the
  resulting `BufReadPost` re-syncs cells to the server.
- **The server** polls tracked-file mtimes on its own and re-broadcasts
  `file_synced` — so the browser updates even if Neovim is closed or
  unfocused.

Both paths are idempotent; if Neovim already pushed the new content, the
server-side watcher sees no diff and stays silent.

---

## Configuration

Full defaults:

```lua
require("neolab").setup({
  server = {
    host = "127.0.0.1",
    port = 9494,
  },
  keymaps = {
    execute_cell = "<leader>r",
    execute_cell_and_advance = "<leader>j",
    execute_selection = "<leader>rs",
    execute_all = "<leader>ra",
    execute_above = "<leader>rA",
    execute_below = "<leader>rb",
    execute_stale = "<leader>rt",
    interrupt_kernel = "<leader>ri",
    restart_kernel = "<leader>rk",
    clear_outputs = "<leader>R",
  },
  render = {
    virtual_line = true,
    status_signs = true,
  },
  cellmarks = {
    enabled = true,
    separator = "─",
    max_width = 120,
    show_index = false,   -- show cell number at end of `# %%` line
  },
  sync = {
    cursor_debounce_ms = 100,
    buffer_debounce_ms = 250,
  },
})
```

---

## Cell syntax

neolab uses Jupytext's percent format in plain Python files. Code before the
first header is treated as an implicit first code cell.

```python
import polars as pl

# %%
print("first explicit cell")

# %% [markdown]
# # A heading
# Some narrative. **Bold**, _italic_, `code`, [links](https://example.com).

# %%
df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
df    # repr renders as a styled HTML table in the browser
```

Supported headers:

```python
# %%              # code cell
# %% [markdown]   # markdown cell
# %% [md]         # markdown cell
# %% [raw]        # raw/non-executable cell
```

Markdown cells are written as Python comments and rendered in the browser:

```python
# %% [markdown]
# # Heading
# Narrative text with **formatting** and `inline code`.
```

Outputs are not saved into the source file. The `.py` file remains clean,
diffable, and agent-friendly.

## Browser UI

The browser is an output cockpit, not an editor:

- File tree for project files and read-only viewers for markdown, CSV, TSV,
  Parquet, JSON, YAML/TOML/text/log files.
- Collapsible cells.
- Search box for filtering rendered cells.
- Keyboard navigation: `j`/`k` moves between cells, `c` collapses/expands,
  `/` focuses search.
- Image/SVG outputs include zoom, open, save, and copy controls.
- HTML tables get row filtering and clickable column sorting.

---

## License

MIT — see [LICENSE](./LICENSE).
