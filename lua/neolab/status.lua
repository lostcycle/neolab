-- Lightweight Neovim-side cell status: signs, virtual text, and quickfix
-- entries for traceback locations.

local M = {}

local cells = require("neolab.cells")
local client = require("neolab.client")
local config = require("neolab.config")

local ns = vim.api.nvim_create_namespace("neolab.status")

---@type table<string, table<integer, table>>
local by_path = {}

local function buf_path(buf)
  local name = vim.api.nvim_buf_get_name(buf)
  if name == "" then
    return nil
  end
  return vim.fn.fnamemodify(name, ":p")
end

local function buf_for_path(path)
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_loaded(buf) and buf_path(buf) == path then
      return buf
    end
  end
  return nil
end

local function parsed_cells(buf)
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  return cells.parse(lines)
end

local function ensure_path(path)
  by_path[path] = by_path[path] or {}
  return by_path[path]
end

local function display_state(st)
  if not st then
    return nil
  end
  if st.stale then
    return "stale", "S", "NeolabCellStale"
  end
  if st.status == "running" then
    return "running", "●", "NeolabCellRunning"
  end
  if st.status == "error" then
    return "error", "×", "NeolabCellError"
  end
  if st.status == "done" then
    return "done", "✓", "NeolabCellDone"
  end
  return nil
end

local function extmark(buf, line, label, sign, hl)
  local opts = {
    virt_text = { { "  " .. label, hl } },
    virt_text_pos = "eol",
    priority = 80,
  }
  if config.get().render.status_signs ~= false then
    opts.sign_text = sign
    opts.sign_hl_group = hl
  end
  local ok = pcall(vim.api.nvim_buf_set_extmark, buf, ns, line, 0, opts)
  if not ok then
    opts.sign_text = nil
    opts.sign_hl_group = nil
    pcall(vim.api.nvim_buf_set_extmark, buf, ns, line, 0, opts)
  end
end

local function refresh_buf(buf)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  if config.get().render.virtual_line == false then
    return
  end
  local path = buf_path(buf)
  local path_state = path and by_path[path]
  if not path_state then
    return
  end
  local cell_list = parsed_cells(buf)
  for idx, st in pairs(path_state) do
    local c = cell_list[idx + 1]
    if c then
      local name, sign, hl = display_state(st)
      if name then
        local label = name
        if st.execution_count ~= nil and name == "done" then
          label = "In [" .. st.execution_count .. "]"
        elseif st.error then
          label = label .. ": " .. st.error
        end
        extmark(buf, c.start_line, label, sign, hl)
      end
    end
  end
end

local function refresh_path(path)
  local buf = buf_for_path(path)
  if buf then
    refresh_buf(buf)
  end
end

local function set_cell(path, idx, st)
  local path_state = ensure_path(path)
  path_state[idx] = vim.tbl_extend("force", path_state[idx] or {}, st)
  refresh_path(path)
end

local function apply_file_synced(msg)
  if not msg.path then
    return
  end
  local path_state = {}
  for i, c in ipairs(msg.cells or {}) do
    path_state[i - 1] = {
      status = c.status,
      execution_count = c.execution_count,
      stale = c.stale,
    }
  end
  by_path[msg.path] = path_state
  refresh_path(msg.path)
end

local function build_quickfix(msg)
  local path = msg.path
  local buf = path and buf_for_path(path)
  if not buf then
    return
  end
  local cell_list = parsed_cells(buf)
  local cell = cell_list[(msg.cell_index or 0) + 1]
  if not cell then
    return
  end

  local items = {}
  local header_offset = 0
  local first_line = vim.api.nvim_buf_get_lines(buf, cell.start_line, cell.start_line + 1, false)[1]
    or ""
  if first_line:match("^# %%%%") then
    header_offset = 1
  end
  for _, line in ipairs(msg.traceback or {}) do
    local rel = line:match("[Ll]ine (%d+)")
    if rel then
      items[#items + 1] = {
        bufnr = buf,
        lnum = cell.start_line + header_offset + tonumber(rel),
        col = 1,
        text = line,
      }
    end
  end
  if #items == 0 then
    items[1] = {
      bufnr = buf,
      lnum = cell.start_line + 1,
      col = 1,
      text = string.format("%s: %s", msg.ename or "Error", msg.evalue or ""),
    }
  end
  vim.fn.setqflist({}, "r", { title = "neolab traceback", items = items })
end

local function short_error(msg)
  local value = tostring(msg.evalue or "")
  value = value:gsub("%s+", " ")
  if #value > 80 then
    value = value:sub(1, 77) .. "..."
  end
  if value == "" then
    return tostring(msg.ename or "Error")
  end
  return string.format("%s: %s", msg.ename or "Error", value)
end

local function ensure_highlights()
  local function setdefault(name, spec)
    if vim.fn.hlexists(name) == 0 or vim.api.nvim_get_hl(0, { name = name }).default then
      spec.default = true
      vim.api.nvim_set_hl(0, name, spec)
    end
  end
  setdefault("NeolabCellRunning", { fg = "#ffd166", bold = true })
  setdefault("NeolabCellDone", { link = "DiagnosticOk" })
  setdefault("NeolabCellError", { link = "DiagnosticError" })
  setdefault("NeolabCellStale", { link = "DiagnosticWarn" })
end

function M.attach(buf)
  refresh_buf(buf)
end

function M.setup()
  ensure_highlights()

  client.on("cell_started", function(msg)
    set_cell(msg.path, msg.cell_index, {
      status = "running",
      execution_count = nil,
      stale = false,
      error = nil,
    })
  end)

  client.on("cell_finished", function(msg)
    set_cell(msg.path, msg.cell_index, {
      status = msg.status == "ok" and "done" or "error",
      execution_count = msg.execution_count,
      stale = false,
    })
  end)

  client.on("cell_error", function(msg)
    set_cell(msg.path, msg.cell_index, {
      status = "error",
      stale = false,
      error = short_error(msg),
    })
    build_quickfix(msg)
  end)

  client.on("file_synced", apply_file_synced)

  client.on("outputs_cleared", function(msg)
    if msg.path then
      by_path[msg.path] = {}
      refresh_path(msg.path)
    end
  end)

  vim.api.nvim_create_autocmd("ColorScheme", {
    callback = ensure_highlights,
  })
end

return M
