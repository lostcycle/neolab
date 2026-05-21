local M = {}

local defaults = {
  server = {
    host = "127.0.0.1",
    port = 9494,
  },
  keymaps = {
    execute_cell = "<leader>r",
    execute_above = "<leader>a",
    execute_below = "<leader>b",
    execute_all = "<leader>A",
    clear_outputs = "<leader>R",
  },
  render = {
    virtual_line = true,
    status_signs = true,
  },
  sync = {
    cursor_debounce_ms = 100,
    buffer_debounce_ms = 250,
  },
}

local current = vim.deepcopy(defaults)

---@param opts table
function M.apply(opts)
  current = vim.tbl_deep_extend("force", defaults, opts or {})
end

---@return table
function M.get()
  return current
end

return M
