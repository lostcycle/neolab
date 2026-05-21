-- Buffer-local keymaps for python buffers.

local config = require("neolab.config")

local M = {}

---@param buf integer
function M.apply(buf)
  local km = config.get().keymaps
  local map = function(lhs, rhs, desc)
    if not lhs or lhs == false then
      return
    end
    vim.keymap.set("n", lhs, rhs, { buffer = buf, desc = desc, silent = true })
  end
  map(km.execute_cell, "<cmd>NeolabRun<cr>", "neolab: run cell")
  map(km.clear_outputs, "<cmd>NeolabClear<cr>", "neolab: clear outputs")
end

return M
