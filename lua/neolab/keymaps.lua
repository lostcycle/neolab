-- Buffer-local keymaps for python buffers.

local config = require("neolab.config")

local M = {}

---@param buf integer
function M.apply(buf)
  local km = config.get().keymaps
  local map = function(mode, lhs, rhs, desc)
    if not lhs or lhs == false then
      return
    end
    vim.keymap.set(mode, lhs, rhs, { buffer = buf, desc = desc, silent = true })
  end
  map("n", km.execute_cell, "<cmd>NeolabRun<cr>", "neolab: run cell")
  map(
    "n",
    km.execute_cell_and_advance,
    "<cmd>NeolabRunAndAdvance<cr>",
    "neolab: run cell and advance"
  )
  map("n", km.execute_all, "<cmd>NeolabRunAll<cr>", "neolab: run all cells")
  map("n", km.execute_above, "<cmd>NeolabRunAbove<cr>", "neolab: run cells above cursor")
  map("n", km.execute_below, "<cmd>NeolabRunBelow<cr>", "neolab: run cells below cursor")
  map("n", km.execute_stale, "<cmd>NeolabRunStale<cr>", "neolab: run stale cells")
  map("n", km.interrupt_kernel, "<cmd>NeolabInterrupt<cr>", "neolab: interrupt kernel")
  map("n", km.restart_kernel, "<cmd>NeolabRestart<cr>", "neolab: restart kernel")
  map("n", km.clear_outputs, "<cmd>NeolabClear<cr>", "neolab: clear outputs")
  map("v", km.execute_selection, ":NeolabRunSelection<cr>", "neolab: run selection")
end

return M
