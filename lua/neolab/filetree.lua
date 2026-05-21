-- Walk the project directory and produce a tree of viewable files for the
-- UI sidebar. Python files are editable; the others are read-only viewers
-- served by the server's viewer module.

local M = {}

local uv = vim.uv or vim.loop

local DEFAULT_EXCLUDE = {
  ".venv",
  "venv",
  ".git",
  "__pycache__",
  "node_modules",
  ".pytest_cache",
  ".ruff_cache",
  ".mypy_cache",
  "dist",
  "build",
}

-- Extensions surfaced in the tree. Python files are first-class (editable);
-- everything else is rendered by the viewer module on the server.
local VIEWABLE_EXTS = {
  "py",
  "md",
  "markdown",
  "csv",
  "tsv",
  "parquet",
  "json",
  "yaml",
  "yml",
  "toml",
  "txt",
  "log",
}

local function ext_of(name)
  return name:match("%.([%w]+)$")
end

local function is_viewable(name)
  local ext = ext_of(name)
  if not ext then
    return false
  end
  ext = ext:lower()
  for _, e in ipairs(VIEWABLE_EXTS) do
    if e == ext then
      return true
    end
  end
  return false
end

local function should_skip(name, excludes)
  if name:sub(1, 1) == "." then
    return true
  end
  for _, ex in ipairs(excludes) do
    if name == ex then
      return true
    end
  end
  return false
end

local function walk(dir, excludes, depth, max_depth)
  if depth > max_depth then
    return {}
  end
  local nodes = {}
  local ok, iter = pcall(vim.fs.dir, dir)
  if not ok then
    return nodes
  end
  for name, kind in iter do
    if not should_skip(name, excludes) then
      local full = dir .. "/" .. name
      if kind == "directory" then
        local children = walk(full, excludes, depth + 1, max_depth)
        if #children > 0 then
          nodes[#nodes + 1] = { type = "dir", name = name, children = children }
        end
      elseif kind == "file" and is_viewable(name) then
        nodes[#nodes + 1] = { type = "file", name = name, path = full }
      end
    end
  end
  table.sort(nodes, function(a, b)
    if a.type ~= b.type then
      return a.type == "dir"
    end
    return a.name < b.name
  end)
  return nodes
end

---@return { root: string, nodes: table[] }
function M.snapshot()
  local root = uv.cwd()
  local nodes = walk(root, DEFAULT_EXCLUDE, 1, 6)
  return { root = root, nodes = nodes }
end

return M
