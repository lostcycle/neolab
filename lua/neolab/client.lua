-- High-level WebSocket client to the neolab server.
-- Owns the singleton WS connection; exposes send + on(event_type).

local config = require("neolab.config")
local ws_mod = require("neolab.ws")

local M = {}

local state = {
  client = nil, ---@type neolab.ws.Client|nil
  handlers = {}, ---@type table<string, fun(msg: table)[]>
  send_queue = {}, ---@type table[]
  connected = false,
  connecting = false,
}

local function dispatch(text)
  local ok, msg = pcall(vim.json.decode, text)
  if not ok or type(msg) ~= "table" then
    vim.schedule(function()
      vim.notify("neolab: bad JSON from server: " .. text:sub(1, 100), vim.log.levels.WARN)
    end)
    return
  end
  local t = msg.type
  if not t then
    return
  end
  local list = state.handlers[t]
  if list then
    for _, fn in ipairs(list) do
      pcall(fn, msg)
    end
  end
end

local function flush_queue()
  if not state.client then
    return
  end
  for _, m in ipairs(state.send_queue) do
    state.client:send_text(vim.json.encode(m))
  end
  state.send_queue = {}
end

function M.connect()
  if state.client or state.connecting then
    return
  end
  state.connecting = true
  local cfg = config.get().server
  state.client = ws_mod.connect(cfg.host, cfg.port, "/api/nvim", {
    on_open = function()
      state.connected = true
      state.connecting = false
      if state.client then
        state.client:send_text(vim.json.encode({ type = "hello" }))
      end
      flush_queue()
    end,
    on_message = dispatch,
    on_close = function()
      state.connected = false
      state.connecting = false
      state.client = nil
      vim.defer_fn(function()
        M.connect()
      end, 2000)
    end,
    on_error = function(err)
      vim.notify("neolab WS: " .. err, vim.log.levels.WARN)
    end,
  })
end

function M.send(msg)
  if state.connected and state.client then
    state.client:send_text(vim.json.encode(msg))
  else
    table.insert(state.send_queue, msg)
    if not state.client then
      M.connect()
    end
  end
end

---@param event_type string
---@param fn fun(msg: table)
function M.on(event_type, fn)
  state.handlers[event_type] = state.handlers[event_type] or {}
  table.insert(state.handlers[event_type], fn)
end

function M.is_connected()
  return state.connected
end

function M.close()
  if state.client then
    state.client:close()
    state.client = nil
    state.connected = false
  end
end

return M
