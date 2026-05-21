// File tree rendered as a neo-tree-like list:
// - All folders are expanded by default — collapses are explicit and persisted.
// - Files fire onSelect(path) and get a colored extension-aware icon.
// - The branch containing the active file is force-expanded.

import { fileIconHTML, folderIconHTML } from "./icons.js";

const STORAGE_KEY = "neolab.tree.collapsed";

function loadCollapsed() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function saveCollapsed(set) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
  } catch {
    /* ignore */
  }
}

function collectAncestorKeys(tree, activePath) {
  if (!activePath) return new Set();
  const acc = new Set();
  function walk(nodes, prefix) {
    for (const n of nodes) {
      const key = (prefix ? prefix + "/" : "") + n.name;
      if (n.type === "dir") {
        if (walk(n.children || [], key)) {
          acc.add(key);
          return true;
        }
      } else if (n.path === activePath) {
        return true;
      }
    }
    return false;
  }
  walk(tree.nodes || [], "");
  return acc;
}

export function renderTree(container, tree, { activePath, onSelect } = {}) {
  container.innerHTML = "";
  if (!tree || !tree.nodes || tree.nodes.length === 0) {
    const empty = document.createElement("div");
    empty.className = "tree-empty";
    empty.textContent = "(empty)";
    container.appendChild(empty);
    return;
  }
  const collapsed = loadCollapsed();
  // Folders containing the active file are always expanded for this render,
  // but we don't mutate the persisted collapse set — the user's preference
  // stays for the next time they navigate away.
  const forceOpen = collectAncestorKeys(tree, activePath);

  function isOpen(key) {
    return forceOpen.has(key) || !collapsed.has(key);
  }

  function renderNode(parentEl, node, depth, parentKey) {
    const key = parentKey ? parentKey + "/" + node.name : node.name;
    const row = document.createElement("div");
    row.className = "tree-row tree-row-" + node.type;
    row.style.paddingLeft = `${0.5 + depth * 0.9}rem`;

    const open = node.type === "dir" && isOpen(key);

    const chev = document.createElement("span");
    chev.className = "tree-chevron";
    if (node.type === "dir") chev.textContent = open ? "▾" : "▸";
    row.appendChild(chev);

    const icon = document.createElement("span");
    icon.className = "tree-icon";
    icon.innerHTML =
      node.type === "dir" ? folderIconHTML(open) : fileIconHTML(node.name);
    row.appendChild(icon);

    const name = document.createElement("span");
    name.className = "tree-name";
    name.textContent = node.name;
    row.appendChild(name);

    if (node.type === "dir") {
      parentEl.appendChild(row);
      const wrap = document.createElement("div");
      wrap.className = "tree-children";
      if (!open) wrap.classList.add("collapsed");
      else row.classList.add("expanded");
      (node.children || []).forEach((c) => renderNode(wrap, c, depth + 1, key));
      parentEl.appendChild(wrap);

      row.addEventListener("click", (e) => {
        e.stopPropagation();
        const nowCollapsed = wrap.classList.toggle("collapsed");
        row.classList.toggle("expanded", !nowCollapsed);
        if (nowCollapsed) {
          collapsed.add(key);
          chev.textContent = "▸";
          icon.innerHTML = folderIconHTML(false);
        } else {
          collapsed.delete(key);
          chev.textContent = "▾";
          icon.innerHTML = folderIconHTML(true);
        }
        saveCollapsed(collapsed);
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
}

export function setActiveFile(container, path) {
  container
    .querySelectorAll(".tree-row.active")
    .forEach((el) => el.classList.remove("active"));
  if (!path) return;
  const target = container.querySelector(
    `.tree-row[data-path="${CSS.escape(path)}"]`,
  );
  if (target) target.classList.add("active");
}
