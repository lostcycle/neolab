-- :Neolab* user commands, wired through the WS client.

local M = {}

local cells = require("neolab.cells")
local client = require("neolab.client")

local function buf_path(buf)
  local name = vim.api.nvim_buf_get_name(buf or 0)
  if name == "" then
    return nil
  end
  return vim.fn.fnamemodify(name, ":p")
end

local function buf_cells(buf)
  local lines = vim.api.nvim_buf_get_lines(buf or 0, 0, -1, false)
  return cells.parse(lines)
end

local function sync_and_get(buf)
  local path = buf_path(buf)
  if not path then
    vim.notify("neolab: buffer has no file path", vim.log.levels.WARN)
    return nil, nil
  end
  local cell_list = buf_cells(buf)
  client.send({
    type = "file_synced",
    path = path,
    cells = vim.tbl_map(function(c)
      return { kind = c.kind, source = c.source }
    end, cell_list),
  })
  return path, cell_list
end

local function ping()
  client.connect()
  vim.notify("neolab: connecting…", vim.log.levels.INFO)
end

local function run_current()
  local path, cell_list = sync_and_get(0)
  if not path then
    return
  end
  local cur = vim.api.nvim_win_get_cursor(0)
  local cell_idx = cells.cell_index_for_line(cell_list, cur[1] - 1)
  if cell_idx == nil then
    vim.notify("neolab: no cell at cursor", vim.log.levels.WARN)
    return
  end
  client.send({ type = "execute_cell", path = path, cell_index = cell_idx })
end

local function clear_outputs()
  local path = buf_path(0)
  if not path then
    return
  end
  client.send({ type = "clear_outputs", path = path })
end

local function sync()
  sync_and_get(0)
end

local function on_hello_ack(msg)
  vim.notify("neolab: connected (server v" .. (msg.version or "?") .. ")", vim.log.levels.INFO)
end

local function on_cell_error(msg)
  vim.notify(
    string.format("neolab cell %d: %s: %s", msg.cell_index, msg.ename or "", msg.evalue or ""),
    vim.log.levels.ERROR
  )
end

function M.register()
  client.on("hello_ack", on_hello_ack)
  client.on("cell_error", on_cell_error)

  vim.api.nvim_create_user_command("NeolabPing", ping, {
    desc = "Connect to (or re-check) the neolab server",
  })
  vim.api.nvim_create_user_command("NeolabRun", run_current, {
    desc = "Execute the cell under the cursor",
  })
  vim.api.nvim_create_user_command("NeolabClear", clear_outputs, {
    desc = "Clear all cell outputs for the current file",
  })
  vim.api.nvim_create_user_command("NeolabSync", sync, {
    desc = "Resync the current buffer's cells to the server",
  })
end

return M
