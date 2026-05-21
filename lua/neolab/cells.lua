-- Parse jupytext-format Python buffers into cells.
-- Mirrors src/neolab/jupytext.py — both sides must agree on cell boundaries.

local M = {}

---@param line string
---@return string|nil kind 'code'|'markdown'|'raw', or nil if not a header
local function parse_header(line)
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

---@param src string
---@return string
local function strip_markdown_prefix(src)
  local lines = vim.split(src, "\n", { plain = true })
  for i, line in ipairs(lines) do
    if line:sub(1, 2) == "# " then
      lines[i] = line:sub(3)
    elseif line == "#" then
      lines[i] = ""
    end
  end
  return table.concat(lines, "\n")
end

---@param lines string[] # 1-indexed Lua table (conceptually nvim 0-indexed lines)
---@return table[] cells # each {kind, start_line, end_line, source}; lines 0-indexed
function M.parse(lines)
  ---@type {idx: integer, kind: string}[]
  local headers = {}
  for i, line in ipairs(lines) do
    local kind = parse_header(line)
    if kind then
      headers[#headers + 1] = { idx = i, kind = kind }
    end
  end

  local cells = {}

  if #headers == 0 then
    local src = table.concat(lines, "\n")
    if src:match("%S") then
      cells[#cells + 1] = {
        kind = "code",
        start_line = 0,
        end_line = #lines,
        source = src,
      }
    end
    return cells
  end

  if headers[1].idx > 1 then
    local pre = {}
    for i = 1, headers[1].idx - 1 do
      pre[#pre + 1] = lines[i]
    end
    local src = table.concat(pre, "\n")
    if src:match("%S") then
      cells[#cells + 1] = {
        kind = "code",
        start_line = 0,
        end_line = headers[1].idx - 1,
        source = src,
      }
    end
  end

  for h_idx, h in ipairs(headers) do
    local next_idx = (headers[h_idx + 1] and headers[h_idx + 1].idx) or (#lines + 1)
    local body = {}
    for i = h.idx + 1, next_idx - 1 do
      body[#body + 1] = lines[i]
    end
    local src = table.concat(body, "\n")
    if h.kind == "markdown" then
      src = strip_markdown_prefix(src)
    end
    cells[#cells + 1] = {
      kind = h.kind,
      start_line = h.idx - 1,
      end_line = next_idx - 1,
      source = src,
    }
  end

  return cells
end

---Find the cell index (0-indexed) containing the given nvim line (0-indexed).
---@param cells table[]
---@param row integer
---@return integer|nil
function M.cell_index_for_line(cells, row)
  for i, cell in ipairs(cells) do
    if row >= cell.start_line and row < cell.end_line then
      return i - 1
    end
  end
  return nil
end

return M
