-- Visual cell delimiters in Neovim:
--   • a horizontal separator line above each `# %%` header,
--   • a tinted background bar on the `# %%` line itself,
--   • a different tint for markdown cells.
--
-- Treesitter foreground colors are preserved (we use `line_hl_group` rather
-- than `hl_eol = true`).

local M = {}

local config = require("neolab.config")

local ns = vim.api.nvim_create_namespace("neolab.cellmarks")
local sign_ns = vim.api.nvim_create_namespace("neolab.cellmarks.signs")

---@param line string
---@return string|nil kind  'code' | 'markdown' | 'raw', or nil if not a header
local function header_kind(line)
  if line == "# %%" then
    return "code"
  end
  local rest = line:match("^# %%%%(%s.*)$")
  if not rest then
    return nil
  end
  local k = rest:match("^%s+%[([%w_]+)%]")
  if k == nil then
    return "code"
  end
  k = k:lower()
  if k == "markdown" or k == "md" then
    return "markdown"
  end
  if k == "raw" then
    return "raw"
  end
  return "code"
end

local function effective_width(bufnr)
  local cfg = config.get().cellmarks or {}
  local max_w = cfg.max_width or 120
  local win = vim.fn.bufwinid(bufnr)
  local w
  if win ~= -1 then
    w = vim.api.nvim_win_get_width(win) - vim.fn.getwininfo(win)[1].textoff
  else
    w = vim.o.columns
  end
  if w < 20 then
    w = 80
  end
  return math.min(max_w, math.max(20, w - 2))
end

local function refresh(bufnr)
  if not vim.api.nvim_buf_is_valid(bufnr) then
    return
  end
  vim.api.nvim_buf_clear_namespace(bufnr, ns, 0, -1)

  local cfg = config.get().cellmarks or {}
  local sep_char = cfg.separator or "─"
  local show_index = cfg.show_index == true

  local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  local sep = sep_char:rep(effective_width(bufnr))
  local index = 0

  for i, line in ipairs(lines) do
    local kind = header_kind(line)
    if kind then
      index = index + 1
      local line_hl = (kind == "markdown") and "NeolabCellDelimMd" or "NeolabCellDelim"

      -- Background bar on the delimiter line — non-destructive to TS fg colors.
      vim.api.nvim_buf_set_extmark(bufnr, ns, i - 1, 0, {
        line_hl_group = line_hl,
        priority = 50,
      })

      -- Separator drawn ABOVE the line (skip when the file starts with a header).
      if i > 1 then
        vim.api.nvim_buf_set_extmark(bufnr, ns, i - 1, 0, {
          virt_lines_above = true,
          virt_lines = { { { sep, "NeolabCellSep" } } },
          priority = 50,
        })
      end

      if show_index then
        vim.api.nvim_buf_set_extmark(bufnr, ns, i - 1, 0, {
          virt_text = { { "  " .. index, "Comment" } },
          virt_text_pos = "eol",
          priority = 50,
        })
      end
    end
  end
end

local function ensure_highlights()
  local function setdefault(name, spec)
    if vim.fn.hlexists(name) == 0 or vim.api.nvim_get_hl(0, { name = name }).default then
      spec.default = true
      vim.api.nvim_set_hl(0, name, spec)
    end
  end
  -- Subtle tinted bars — link-based so users can override per colorscheme.
  setdefault("NeolabCellSep", { link = "NonText" })
  setdefault("NeolabCellDelim", { link = "CursorLine" })
  setdefault("NeolabCellDelimMd", { link = "Visual" })
end

local attached = {} ---@type table<integer, boolean>

---@param bufnr integer
function M.attach(bufnr)
  bufnr = bufnr or vim.api.nvim_get_current_buf()
  if attached[bufnr] then
    refresh(bufnr)
    return
  end
  ensure_highlights()
  refresh(bufnr)
  attached[bufnr] = true

  local pending = false
  local function schedule_refresh()
    if pending then
      return
    end
    pending = true
    vim.defer_fn(function()
      pending = false
      if vim.api.nvim_buf_is_valid(bufnr) then
        refresh(bufnr)
      end
    end, 80)
  end

  vim.api.nvim_buf_attach(bufnr, false, {
    on_lines = function()
      schedule_refresh()
    end,
    on_reload = function()
      schedule_refresh()
    end,
    on_detach = function()
      attached[bufnr] = nil
      return true
    end,
  })
end

function M.detach(bufnr)
  bufnr = bufnr or vim.api.nvim_get_current_buf()
  if vim.api.nvim_buf_is_valid(bufnr) then
    vim.api.nvim_buf_clear_namespace(bufnr, ns, 0, -1)
    vim.api.nvim_buf_clear_namespace(bufnr, sign_ns, 0, -1)
  end
  attached[bufnr] = nil
end

function M.toggle(bufnr)
  bufnr = bufnr or vim.api.nvim_get_current_buf()
  if attached[bufnr] then
    M.detach(bufnr)
  else
    M.attach(bufnr)
  end
end

function M.refresh_all()
  for buf in pairs(attached) do
    if vim.api.nvim_buf_is_valid(buf) then
      refresh(buf)
    else
      attached[buf] = nil
    end
  end
end

function M.setup()
  local cfg = config.get().cellmarks or {}
  if cfg.enabled == false then
    return
  end
  ensure_highlights()

  -- Re-tint after a colorscheme swap; redraw separators after window resize.
  vim.api.nvim_create_autocmd("ColorScheme", {
    callback = function()
      ensure_highlights()
      M.refresh_all()
    end,
  })
  vim.api.nvim_create_autocmd({ "VimResized", "WinResized" }, {
    callback = function()
      M.refresh_all()
    end,
  })

  vim.api.nvim_create_user_command("NeolabCellmarksToggle", function()
    M.toggle()
  end, { desc = "neolab: toggle cell delimiters in this buffer" })

  -- Attach to any already-open python buffers (FileType autocmd in init.lua
  -- covers new ones).
  for _, b in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_loaded(b) and vim.bo[b].filetype == "python" then
      M.attach(b)
    end
  end
end

return M
