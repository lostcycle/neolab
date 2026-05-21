-- Debounced buffer/cursor sync + initial file_synced on attach.

local M = {}

local cells = require("neolab.cells")
local client = require("neolab.client")
local config = require("neolab.config")
local filetree = require("neolab.filetree")

local uv = vim.uv or vim.loop

---@type table<integer, userdata>
local buffer_timers = {}
---@type table<integer, userdata>
local fs_watchers = {}
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

local function start_fs_watcher(buf, path)
  -- Detect external edits (coding agents, git checkouts, other editors) and
  -- pull them into the buffer via :checktime so BufReadPost re-syncs cells.
  if not path then
    return
  end
  if fs_watchers[buf] then
    pcall(function()
      fs_watchers[buf]:stop()
    end)
    pcall(function()
      fs_watchers[buf]:close()
    end)
    fs_watchers[buf] = nil
  end
  local handle = uv.new_fs_event()
  if not handle then
    return
  end
  local ok = pcall(function()
    handle:start(
      path,
      {},
      vim.schedule_wrap(function(err)
        if err then
          return
        end
        if not vim.api.nvim_buf_is_valid(buf) then
          return
        end
        vim.bo[buf].autoread = true
        pcall(vim.api.nvim_buf_call, buf, function()
          vim.cmd("checktime")
        end)
      end)
    )
  end)
  if ok then
    fs_watchers[buf] = handle
  else
    pcall(function()
      handle:close()
    end)
  end
end

local function stop_fs_watcher(buf)
  local h = fs_watchers[buf]
  if h then
    pcall(function()
      h:stop()
    end)
    pcall(function()
      h:close()
    end)
    fs_watchers[buf] = nil
  end
end

---@param buf integer
function M.attach(buf)
  local group = vim.api.nvim_create_augroup("neolab-sync-" .. buf, { clear = true })

  vim.api.nvim_create_autocmd("BufReadPost", {
    group = group,
    buffer = buf,
    callback = function()
      send_sync(buf)
      start_fs_watcher(buf, buf_path(buf))
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

  -- When :checktime pulls in external changes, this fires; re-sync cells.
  vim.api.nvim_create_autocmd("FileChangedShellPost", {
    group = group,
    buffer = buf,
    callback = function()
      send_sync(buf)
    end,
  })

  -- Belt-and-suspenders: re-check on focus/idle in case fs_event missed an edit.
  vim.api.nvim_create_autocmd({ "FocusGained", "BufEnter", "CursorHold" }, {
    group = group,
    buffer = buf,
    callback = function()
      if vim.api.nvim_buf_is_valid(buf) then
        vim.bo[buf].autoread = true
        pcall(vim.api.nvim_buf_call, buf, function()
          vim.cmd("checktime")
        end)
      end
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
      stop_fs_watcher(buf)
    end,
  })

  vim.schedule(function()
    if vim.api.nvim_buf_is_valid(buf) then
      vim.bo[buf].autoread = true
    end
    send_sync(buf)
    send_cursor(buf)
    start_fs_watcher(buf, buf_path(buf))
  end)
end

return M
