// Render a hierarchical file tree, neo-tree-style.
// Folder rows toggle expand/collapse on click. File rows fire onSelect(path).

const STORAGE_KEY = "neolab.tree.expanded";

function loadExpanded() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function saveExpanded(set) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
  } catch {
    /* ignore */
  }
}

export function renderTree(container, tree, { activePath, onSelect } = {}) {
  container.innerHTML = "";
  if (!tree || !tree.nodes || tree.nodes.length === 0) {
    const empty = document.createElement("div");
    empty.className = "tree-empty";
    empty.textContent = "(no .py files)";
    container.appendChild(empty);
    return;
  }
  const expanded = loadExpanded();
  // Expand the root level by default
  tree.nodes.forEach((n) => {
    if (n.type === "dir" && !expanded.has(n.name)) expanded.add(n.name);
  });

  function renderNode(parentEl, node, depth, parentKey) {
    const key = parentKey + "/" + node.name;
    const row = document.createElement("div");
    row.className = "tree-row";

    const chev = document.createElement("span");
    chev.className = "tree-chevron";
    chev.textContent = node.type === "dir" ? "›" : "";
    row.appendChild(chev);

    const icon = document.createElement("span");
    icon.className = "tree-icon";
    icon.textContent = node.type === "dir" ? "▸" : "·";
    row.appendChild(icon);

    const name = document.createElement("span");
    name.className = "tree-name";
    name.textContent = node.name;
    row.appendChild(name);

    if (node.type === "dir") {
      parentEl.appendChild(row);
      const wrap = document.createElement("div");
      wrap.className = "tree-children";
      if (!expanded.has(key)) wrap.classList.add("collapsed");
      else row.classList.add("expanded");
      (node.children || []).forEach((c) => renderNode(wrap, c, depth + 1, key));
      parentEl.appendChild(wrap);

      row.addEventListener("click", (e) => {
        e.stopPropagation();
        const isCollapsed = wrap.classList.toggle("collapsed");
        row.classList.toggle("expanded", !isCollapsed);
        if (isCollapsed) expanded.delete(key);
        else expanded.add(key);
        saveExpanded(expanded);
      });
    } else {
      row.dataset.path = node.path;
      if (activePath && node.path === activePath) row.classList.add("active");
      row.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect?.(node.path);
      });
      parentEl.appendChild(row);
    }
  }

  tree.nodes.forEach((n) => renderNode(container, n, 0, ""));
  saveExpanded(expanded);
}

export function setActiveFile(container, path) {
  container.querySelectorAll(".tree-row.active").forEach((el) => el.classList.remove("active"));
  if (!path) return;
  const target = container.querySelector(`.tree-row[data-path="${CSS.escape(path)}"]`);
  if (target) target.classList.add("active");
}
