# neolab

A Neovim plugin for jupytext-style Python files with a live browser view.
Edit cells in your editor; outputs (plots, DataFrames, errors, markdown)
stream to a browser tab as you run them.

- Multi-file, kernel-backed, fully local.
- Cells follow the [jupytext](https://jupytext.readthedocs.io/) "percent"
  format (`# %%`, `# %% [markdown]`).
- External edits — coding agents, `git pull`, another editor — auto-reload
  in both Neovim and the browser.
- No pandas dependency; uses polars for any tabular rendering.

---

## Install

You need two pieces: the **Neovim plugin** (this repo) and the **Python
server** (`neolab` command).

### 1. Install the Python server

Pick one. The plugin will spawn the server for you, so it just needs to be
on `$PATH`:

```sh
uv tool install neolab          # recommended
# or
pipx install neolab
```

Building from a local checkout:

```sh
uv tool install --force .       # or: pipx install --force .
```

### 2. Add to your lazy.nvim config

Drop this in `~/.config/nvim/lua/plugins/neolab.lua` (or wherever your lazy
specs live):

```lua
return {
  "<your-gh-user>/neolab",
  ft = "python",
  cmd = { "NeolabPing", "NeolabRun", "NeolabClear", "NeolabSync" },
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
  "<your-gh-user>/neolab",
  ft = "python",
  build = "uv tool install --force .",   -- or: pipx install --force .
  cmd = { "NeolabPing", "NeolabRun", "NeolabClear", "NeolabSync" },
  config = function() require("neolab").setup({}) end,
}
```

### 3. Start the server

```sh
neolab                              # binds 127.0.0.1:9494
neolab --host 0.0.0.0 --port 9494   # remote-reachable
```

Open <http://127.0.0.1:9494> in your browser. Then open any `.py` file in
Neovim — the plugin attaches automatically.

---

## Default keymaps

Buffer-local, applied to Python files only. All are normal-mode.

| Key          | Command         | What it does                                 |
| ------------ | --------------- | -------------------------------------------- |
| `<leader>r`  | `:NeolabRun`    | Execute the cell under the cursor            |
| `<leader>R`  | `:NeolabClear`  | Clear all cell outputs for the current file  |

Override or disable per keymap:

```lua
opts = {
  keymaps = {
    execute_cell = "<leader>jr",   -- remap
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
| `:NeolabClear`              | Clear all outputs for the current buffer.           |
| `:NeolabSync`               | Force a cell re-sync to the server.                 |
| `:NeolabCellmarksToggle`    | Toggle visual cell delimiters in the current buffer. |

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
    clear_outputs = "<leader>R",
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

Jupytext percent format. Code before the first header is an implicit first
cell.

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

---

## License

MIT — see [LICENSE](./LICENSE).
