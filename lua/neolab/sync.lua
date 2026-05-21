-- Debounced buffer/cursor sync + initial file_synced on attach.

local M = {}

local cells = require("neolab.cells")
local client = require("neolab.client")
local config = require("neolab.config")
local filetree = require("neolab.filetree")

local uv = vim.uv or vim.loop

---@type table<integer, userdata>
local buffer_timers = {}
---@type userdata|nil
local cursor_timer = nil

local function buf_path(buf)
  local name = vim.api.nvim_buf_get_name(buf)
  if name == "" then
    return nil
  end
  return vim.fn.fnamemodify(name, ":p")
end

local function send_sync(buf)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  local path = buf_path(buf)
  if not path then
    return
  end
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local cell_list = cells.parse(lines)
  client.send({
    type = "file_synced",
    path = path,
    cells = vim.tbl_map(function(c)
      return { kind = c.kind, source = c.source }
    end, cell_list),
  })
end

local function send_cursor(buf)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  local path = buf_path(buf)
  if not path then
    return
  end
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local cell_list = cells.parse(lines)
  local cur = vim.api.nvim_win_get_cursor(0)
  local idx = cells.cell_index_for_line(cell_list, cur[1] - 1)
  if idx == nil then
    return
  end
  client.send({ type = "cursor", path = path, cell_index = idx })
end

local function debounce_buffer(buf)
  local ms = config.get().sync.buffer_debounce_ms or 250
  if buffer_timers[buf] then
    pcall(function()
      buffer_timers[buf]:stop()
    end)
  else
    buffer_timers[buf] = uv.new_timer()
  end
  buffer_timers[buf]:start(
    ms,
    0,
    vim.schedule_wrap(function()
      send_sync(buf)
    end)
  )
end

local function debounce_cursor(buf)
  local ms = config.get().sync.cursor_debounce_ms or 100
  if cursor_timer then
    pcall(function()
      cursor_timer:stop()
    end)
  else
    cursor_timer = uv.new_timer()
  end
  cursor_timer:start(
    ms,
    0,
    vim.schedule_wrap(function()
      send_cursor(buf)
    end)
  )
end

function M.send_tree()
  local snap = filetree.snapshot()
  client.send({ type = "tree", root = snap.root, nodes = snap.nodes })
end

---@param buf integer
function M.attach(buf)
  local group = vim.api.nvim_create_augroup("neolab-sync-" .. buf, { clear = true })

  vim.api.nvim_create_autocmd("BufReadPost", {
    group = group,
    buffer = buf,
    callback = function()
      send_sync(buf)
    end,
  })

  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI" }, {
    group = group,
    buffer = buf,
    callback = function()
      debounce_buffer(buf)
    end,
  })

  vim.api.nvim_create_autocmd("CursorMoved", {
    group = group,
    buffer = buf,
    callback = function()
      debounce_cursor(buf)
    end,
  })

  vim.api.nvim_create_autocmd("BufWipeout", {
    group = group,
    buffer = buf,
    callback = function()
      local t = buffer_timers[buf]
      if t then
        pcall(function()
          t:stop()
        end)
        pcall(function()
          t:close()
        end)
        buffer_timers[buf] = nil
      end
    end,
  })

  vim.schedule(function()
    send_sync(buf)
    send_cursor(buf)
  end)
end

return M
