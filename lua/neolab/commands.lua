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

local function executable_indices(cell_list, first_idx, last_idx)
  local out = {}
  first_idx = first_idx or 0
  last_idx = last_idx or (#cell_list - 1)
  for i = first_idx, last_idx do
    local c = cell_list[i + 1]
    if c and c.kind == "code" then
      out[#out + 1] = i
    end
  end
  return out
end

local function current_cell(cell_list)
  local cur = vim.api.nvim_win_get_cursor(0)
  local cell_idx = cells.cell_index_for_line(cell_list, cur[1] - 1)
  if cell_idx == nil then
    vim.notify("neolab: no cell at cursor", vim.log.levels.WARN)
    return nil
  end
  return cell_idx
end

local function send_execute_cells(path, indices)
  if #indices == 0 then
    vim.notify("neolab: no executable code cells", vim.log.levels.INFO)
    return
  end
  client.send({ type = "execute_cells", path = path, cell_indices = indices })
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
  local cell_idx = current_cell(cell_list)
  if cell_idx == nil then
    return
  end
  client.send({ type = "execute_cell", path = path, cell_index = cell_idx })
end

local function run_and_advance()
  local path, cell_list = sync_and_get(0)
  if not path then
    return
  end
  local cell_idx = current_cell(cell_list)
  if cell_idx == nil then
    return
  end
  client.send({ type = "execute_cell", path = path, cell_index = cell_idx })

  local next_cell = cell_list[cell_idx + 2]
  if next_cell then
    vim.api.nvim_win_set_cursor(0, { next_cell.start_line + 1, 0 })
  end
end

local function run_all()
  local path, cell_list = sync_and_get(0)
  if not path then
    return
  end
  send_execute_cells(path, executable_indices(cell_list))
end

local function run_above()
  local path, cell_list = sync_and_get(0)
  if not path then
    return
  end
  local cell_idx = current_cell(cell_list)
  if cell_idx == nil then
    return
  end
  send_execute_cells(path, executable_indices(cell_list, 0, cell_idx - 1))
end

local function run_below()
  local path, cell_list = sync_and_get(0)
  if not path then
    return
  end
  local cell_idx = current_cell(cell_list)
  if cell_idx == nil then
    return
  end
  send_execute_cells(path, executable_indices(cell_list, cell_idx, #cell_list - 1))
end

local function run_selection(opts)
  local path, cell_list = sync_and_get(0)
  if not path then
    return
  end
  local line1 = opts.line1 or vim.fn.line("'<")
  local line2 = opts.line2 or vim.fn.line("'>")
  if line1 > line2 then
    line1, line2 = line2, line1
  end
  local lines = vim.api.nvim_buf_get_lines(0, line1 - 1, line2, false)
  local cell_idx = current_cell(cell_list)
  if cell_idx == nil then
    return
  end
  client.send({
    type = "execute_source",
    path = path,
    cell_index = cell_idx,
    source = table.concat(lines, "\n"),
  })
end

local function interrupt_kernel()
  local path = buf_path(0)
  if not path then
    return
  end
  client.send({ type = "interrupt_kernel", path = path })
end

local function restart_kernel()
  local path = buf_path(0)
  if not path then
    return
  end
  client.send({ type = "restart_kernel", path = path })
end

local function run_stale()
  local path = buf_path(0)
  if not path then
    return
  end
  client.send({ type = "execute_stale", path = path })
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

function M.register()
  client.on("hello_ack", on_hello_ack)

  vim.api.nvim_create_user_command("NeolabPing", ping, {
    desc = "Connect to (or re-check) the neolab server",
  })
  vim.api.nvim_create_user_command("NeolabRun", run_current, {
    desc = "Execute the cell under the cursor",
  })
  vim.api.nvim_create_user_command("NeolabRunAndAdvance", run_and_advance, {
    desc = "Execute the cell under the cursor and move to the next cell",
  })
  vim.api.nvim_create_user_command("NeolabRunAll", run_all, {
    desc = "Execute all code cells in the current buffer",
  })
  vim.api.nvim_create_user_command("NeolabRunAbove", run_above, {
    desc = "Execute code cells above the cursor",
  })
  vim.api.nvim_create_user_command("NeolabRunBelow", run_below, {
    desc = "Execute code cells from the cursor through the end of the buffer",
  })
  vim.api.nvim_create_user_command("NeolabRunSelection", run_selection, {
    desc = "Execute the selected source in the current file kernel",
    range = true,
  })
  vim.api.nvim_create_user_command("NeolabInterrupt", interrupt_kernel, {
    desc = "Interrupt the current file kernel",
  })
  vim.api.nvim_create_user_command("NeolabRestart", restart_kernel, {
    desc = "Restart the current file kernel",
  })
  vim.api.nvim_create_user_command("NeolabRunStale", run_stale, {
    desc = "Execute stale code cells in the current buffer",
  })
  vim.api.nvim_create_user_command("NeolabClear", clear_outputs, {
    desc = "Clear all cell outputs for the current file",
  })
  vim.api.nvim_create_user_command("NeolabSync", sync, {
    desc = "Resync the current buffer's cells to the server",
  })
end

return M
