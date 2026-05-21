-- Minimal RFC 6455 WebSocket client over vim.uv (libuv).
--
-- Supports text frames in both directions, ping->pong, and graceful close.
-- No fragmentation, no extensions, no permessage-deflate. Client always
-- masks outgoing payloads as required by the spec.

local bit = require("bit")
local uv = vim.uv or vim.loop

-- Seed math.random once at module load. Not crypto-strong; for masking only.
math.randomseed(uv.hrtime() % 2 ^ 31)

local M = {}

---@param s string
---@return string
local function base64_encode(s)
  if vim.base64 and vim.base64.encode then
    return vim.base64.encode(s)
  end
  local alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
  local pad = (3 - #s % 3) % 3
  local padded = s .. string.rep("\0", pad)
  local out = {}
  for i = 1, #padded, 3 do
    local n = padded:byte(i) * 65536 + padded:byte(i + 1) * 256 + padded:byte(i + 2)
    local a = math.floor(n / 262144)
    local b = math.floor(n / 4096) % 64
    local c = math.floor(n / 64) % 64
    local d = n % 64
    out[#out + 1] = alphabet:sub(a + 1, a + 1)
    out[#out + 1] = alphabet:sub(b + 1, b + 1)
    out[#out + 1] = alphabet:sub(c + 1, c + 1)
    out[#out + 1] = alphabet:sub(d + 1, d + 1)
  end
  local enc = table.concat(out)
  return enc:sub(1, #enc - pad) .. string.rep("=", pad)
end

local function random_key_b64()
  local bytes = {}
  for i = 1, 16 do
    bytes[i] = string.char(math.random(0, 255))
  end
  return base64_encode(table.concat(bytes))
end

local function mask_payload(payload, key)
  local out = {}
  for i = 1, #payload do
    local k = key:byte(((i - 1) % 4) + 1)
    out[i] = string.char(bit.bxor(payload:byte(i), k))
  end
  return table.concat(out)
end

---@param opcode integer 0x1=text, 0x8=close, 0x9=ping, 0xA=pong
---@param payload string
---@return string
local function build_frame(opcode, payload)
  local len = #payload
  local b1 = 0x80 + opcode -- FIN=1
  local hdr
  if len < 126 then
    hdr = string.char(b1, 0x80 + len)
  elseif len < 65536 then
    hdr = string.char(b1, 0x80 + 126, math.floor(len / 256), len % 256)
  else
    -- 64-bit length: 8 length bytes (we top out at 32-bit values).
    local bytes = { string.char(b1, 0x80 + 127) }
    for i = 7, 0, -1 do
      local b = math.floor(len / 2 ^ (i * 8)) % 256
      bytes[#bytes + 1] = string.char(b)
    end
    hdr = table.concat(bytes)
  end
  local mask =
    string.char(math.random(0, 255), math.random(0, 255), math.random(0, 255), math.random(0, 255))
  return hdr .. mask .. mask_payload(payload, mask)
end

---Parse a single frame from the buffer.
---@param buf string
---@return table|nil frame {fin, opcode, payload}, or nil if buf incomplete
---@return string remaining buf with the consumed bytes stripped
local function try_parse_frame(buf)
  if #buf < 2 then
    return nil, buf
  end
  local b1 = buf:byte(1)
  local b2 = buf:byte(2)
  local fin = bit.band(b1, 0x80) ~= 0
  local opcode = bit.band(b1, 0x0F)
  local masked = bit.band(b2, 0x80) ~= 0
  local len = bit.band(b2, 0x7F)
  local idx = 3
  if len == 126 then
    if #buf < idx + 1 then
      return nil, buf
    end
    len = buf:byte(idx) * 256 + buf:byte(idx + 1)
    idx = idx + 2
  elseif len == 127 then
    if #buf < idx + 7 then
      return nil, buf
    end
    len = 0
    for i = 0, 7 do
      len = len * 256 + buf:byte(idx + i)
    end
    idx = idx + 8
  end
  local mask_key
  if masked then
    if #buf < idx + 3 then
      return nil, buf
    end
    mask_key = buf:sub(idx, idx + 3)
    idx = idx + 4
  end
  if #buf < idx + len - 1 then
    return nil, buf
  end
  local payload = buf:sub(idx, idx + len - 1)
  if mask_key then
    payload = mask_payload(payload, mask_key)
  end
  return { fin = fin, opcode = opcode, payload = payload }, buf:sub(idx + len)
end

---@class neolab.ws.Handlers
---@field on_open? fun()
---@field on_message? fun(text: string)
---@field on_close? fun()
---@field on_error? fun(err: string)

---@class neolab.ws.Client
---@field send_text fun(self, text: string)
---@field close fun(self)
---@field is_open fun(self): boolean

---@param host string
---@param port integer
---@param path string
---@param handlers neolab.ws.Handlers
---@return neolab.ws.Client
function M.connect(host, port, path, handlers)
  local sock = uv.new_tcp()
  local self = {}
  local handshake_done = false
  local handshake_buf = ""
  local frame_buf = ""
  local closed = false

  local function fire_error(reason)
    if handlers.on_error then
      vim.schedule(function()
        handlers.on_error(reason)
      end)
    end
  end

  local function close_socket(reason)
    if closed then
      return
    end
    closed = true
    if sock then
      pcall(function()
        sock:read_stop()
      end)
      pcall(function()
        sock:close()
      end)
    end
    if reason then
      fire_error(reason)
    end
    if handlers.on_close then
      vim.schedule(handlers.on_close)
    end
  end

  function self:send_text(text)
    if closed or not handshake_done then
      return
    end
    local frame = build_frame(0x1, text)
    sock:write(frame, function(err)
      if err then
        close_socket("write: " .. tostring(err))
      end
    end)
  end

  function self:close()
    if closed then
      return
    end
    if handshake_done then
      local payload = string.char(math.floor(1000 / 256), 1000 % 256)
      pcall(function()
        sock:write(build_frame(0x8, payload))
      end)
    end
    close_socket()
  end

  function self:is_open()
    return handshake_done and not closed
  end

  local function on_frame(frame)
    if frame.opcode == 0x1 then -- text
      if handlers.on_message then
        local text = frame.payload
        vim.schedule(function()
          handlers.on_message(text)
        end)
      end
    elseif frame.opcode == 0x9 then -- ping → pong
      pcall(function()
        sock:write(build_frame(0xA, frame.payload))
      end)
    elseif frame.opcode == 0x8 then -- close
      close_socket()
    end
  end

  local function on_read(err, chunk)
    if err then
      return close_socket("read: " .. tostring(err))
    end
    if not chunk then
      return close_socket()
    end

    if not handshake_done then
      handshake_buf = handshake_buf .. chunk
      local eoh = handshake_buf:find("\r\n\r\n", 1, true)
      if not eoh then
        return
      end
      local header = handshake_buf:sub(1, eoh - 1)
      frame_buf = handshake_buf:sub(eoh + 4)
      handshake_buf = ""
      if not header:match("^HTTP/1%.1 101") then
        return close_socket("ws upgrade rejected: " .. header:sub(1, 200))
      end
      handshake_done = true
      if handlers.on_open then
        vim.schedule(handlers.on_open)
      end
    else
      frame_buf = frame_buf .. chunk
    end

    while true do
      local f, rest = try_parse_frame(frame_buf)
      if not f then
        break
      end
      frame_buf = rest
      on_frame(f)
    end
  end

  local function do_connect(addr)
    sock:connect(addr, port, function(err)
      if err then
        return close_socket("connect: " .. tostring(err))
      end
      local key = random_key_b64()
      local req = table.concat({
        "GET " .. path .. " HTTP/1.1",
        "Host: " .. host .. ":" .. tostring(port),
        "Upgrade: websocket",
        "Connection: Upgrade",
        "Sec-WebSocket-Key: " .. key,
        "Sec-WebSocket-Version: 13",
        "",
        "",
      }, "\r\n")
      sock:write(req, function(werr)
        if werr then
          return close_socket("write upgrade: " .. tostring(werr))
        end
        sock:read_start(on_read)
      end)
    end)
  end

  -- libuv's tcp:connect requires a numeric IP — resolve hostnames first.
  -- getaddrinfo accepts IP literals too, so this works uniformly for both.
  uv.getaddrinfo(host, nil, { family = "inet", socktype = "stream" }, function(err, addrs)
    if err or not addrs or #addrs == 0 then
      return close_socket("dns: " .. tostring(err or ("no address for " .. host)))
    end
    do_connect(addrs[1].addr)
  end)

  return self
end

return M
