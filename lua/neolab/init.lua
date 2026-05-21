local M = {}

local cellmarks = require("neolab.cellmarks")
local client = require("neolab.client")
local commands = require("neolab.commands")
local config = require("neolab.config")
local keymaps = require("neolab.keymaps")
local sync = require("neolab.sync")

local _attached = {} ---@type table<integer, boolean>

local function attach(buf)
  if _attached[buf] then
    return
  end
  _attached[buf] = true
  keymaps.apply(buf)
  sync.attach(buf)
  cellmarks.attach(buf)
end

---@param opts table|nil
function M.setup(opts)
  config.apply(opts or {})
  commands.register()
  cellmarks.setup()

  vim.api.nvim_create_autocmd("FileType", {
    pattern = "python",
    callback = function(args)
      attach(args.buf)
    end,
  })

  vim.api.nvim_create_autocmd("DirChanged", {
    callback = function()
      sync.send_tree()
    end,
  })

  -- After connect handshake, push the file tree to the server.
  client.on("hello_ack", function()
    sync.send_tree()
  end)

  client.connect()
end

return M
