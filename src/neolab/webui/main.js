// neolab — browser UI entry point.

import { WS } from "./ws.js";
import { renderCell } from "./cell.js";
import { renderTree, setActiveFile } from "./tree.js";

function loadCollapsedCells() {
  try {
    return new Set(JSON.parse(localStorage.getItem("neolab.cells.collapsed") || "[]"));
  } catch {
    return new Set();
  }
}

const state = {
  activePath: null,
  cells: [], // [{ kind, source, outputs, status, execution_count, stale }]
  tree: null, // { root, nodes }
  activeCellIndex: null,
  kernelStatus: "idle",
  collapsed: loadCollapsedCells(),
  searchQuery: "",
};

const $path = document.getElementById("path");
const $kstat = document.getElementById("kernel-status");
const $cells = document.getElementById("cells");
const $tree = document.getElementById("tree");
const $treeRoot = document.getElementById("tree-root");
const $search = document.getElementById("output-search");

function newCell(c) {
  return {
    kind: c.kind,
    source: c.source || "",
    outputs: c.outputs || [],
    status: c.status || "idle",
    execution_count: c.execution_count ?? null,
    stale: !!c.stale,
    source_hash: c.source_hash || null,
  };
}

function ensureCell(index, kind = "code") {
  while (state.cells.length <= index) {
    state.cells.push(newCell({ kind }));
  }
}

function setKernelStatus(s) {
  state.kernelStatus = s;
  $kstat.textContent = s;
  $kstat.dataset.state = s;
}

function renderAll() {
  $path.textContent = state.activePath
    ? state.activePath.replace(/^.*\/(.{0,80})$/, "$1")
    : "(no file)";

  $cells.innerHTML = "";
  if (state.cells.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No cells yet — open a file in Neovim.";
    $cells.appendChild(empty);
  } else {
    state.cells.forEach((cell, i) => {
      const card = renderCell($cells, i, cell, {
        collapsed: isCollapsed(i),
        onToggleCollapse: toggleCollapsed,
      });
      if (state.searchQuery && !card.textContent.toLowerCase().includes(state.searchQuery)) {
        card.classList.add("search-hidden");
      }
    });
    applyActiveCellHighlight();
  }
}

function applyActiveCellHighlight() {
  $cells.querySelectorAll(".cell.active").forEach((el) => el.classList.remove("active"));
  if (state.activeCellIndex == null) return;
  const target = $cells.querySelector(`.cell[data-cell-index="${state.activeCellIndex}"]`);
  if (target) target.classList.add("active");
}

function scrollToCell(index) {
  state.activeCellIndex = index;
  applyActiveCellHighlight();
  const target = $cells.querySelector(`.cell[data-cell-index="${index}"]`);
  if (target) target.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function cellKey(index) {
  return `${state.activePath || ""}#${index}`;
}

function saveCollapsed() {
  localStorage.setItem("neolab.cells.collapsed", JSON.stringify([...state.collapsed]));
}

function isCollapsed(index) {
  return state.collapsed.has(cellKey(index));
}

function toggleCollapsed(index) {
  const key = cellKey(index);
  if (state.collapsed.has(key)) state.collapsed.delete(key);
  else state.collapsed.add(key);
  saveCollapsed();
  renderAll();
}

function renderTreeNow() {
  if (!state.tree) {
    $tree.innerHTML = "";
    $treeRoot.textContent = "";
    return;
  }
  $treeRoot.textContent = state.tree.root || "";
  renderTree($tree, state.tree, {
    activePath: state.activePath,
    onSelect: (p) => ws.send({ type: "select", path: p }),
  });
}

function mergeIncomingCells(incoming) {
  // Preserve prior outputs/status for cells whose kind+source still match;
  // markdown cells refresh their source verbatim.
  const next = incoming.map((c, i) => {
    const prior = state.cells[i];
    if (
      prior &&
      prior.kind === c.kind &&
      (prior.source_hash == null || prior.source_hash === (c.source_hash || null))
    ) {
      return {
        kind: c.kind,
        source: c.source || prior.source || "",
        outputs: c.outputs || prior.outputs,
        status: c.status || prior.status,
        execution_count: c.execution_count ?? prior.execution_count,
        stale: !!c.stale,
        source_hash: c.source_hash || prior.source_hash || null,
      };
    }
    return newCell(c);
  });
  state.cells = next;
}

function applyEvent(ev) {
  switch (ev.type) {
    case "state": {
      state.activePath = ev.path;
      state.cells = (ev.cells || []).map(newCell);
      setKernelStatus(ev.kernel_status || "idle");
      renderAll();
      setActiveFile($tree, state.activePath);
      return;
    }
    case "file_synced": {
      if (state.activePath !== ev.path) {
        state.activePath = ev.path;
        state.cells = (ev.cells || []).map(newCell);
      } else {
        mergeIncomingCells(ev.cells || []);
      }
      renderAll();
      setActiveFile($tree, state.activePath);
      return;
    }
    case "cell_started": {
      if (state.activePath !== ev.path) state.activePath = ev.path;
      ensureCell(ev.cell_index);
      const c = state.cells[ev.cell_index];
      c.outputs = [];
      c.status = "running";
      c.stale = false;
      renderAll();
      return;
    }
    case "cell_output": {
      if (ev.path && state.activePath !== ev.path) return;
      ensureCell(ev.cell_index);
      state.cells[ev.cell_index].outputs.push(ev.output);
      renderAll();
      return;
    }
    case "cell_finished": {
      ensureCell(ev.cell_index);
      const c = state.cells[ev.cell_index];
      c.status = ev.status === "ok" ? "done" : "error";
      c.execution_count = ev.execution_count;
      renderAll();
      return;
    }
    case "outputs_cleared": {
      state.cells.forEach((c) => {
        c.outputs = [];
        c.status = "idle";
        c.execution_count = null;
      });
      renderAll();
      return;
    }
    case "kernel_status": {
      setKernelStatus(ev.state);
      return;
    }
    case "cursor": {
      if (ev.path && ev.path !== state.activePath) return;
      scrollToCell(ev.cell_index);
      return;
    }
    case "tree": {
      state.tree = { root: ev.root, nodes: ev.nodes };
      renderTreeNow();
      return;
    }
  }
}

const ws = new WS(`ws://${location.host}/api/browser`, {
  onOpen: () => ws.send({ type: "hello" }),
  onMessage: applyEvent,
});

$search.addEventListener("input", () => {
  state.searchQuery = $search.value.trim().toLowerCase();
  renderAll();
});

document.addEventListener("keydown", (e) => {
  const tag = document.activeElement?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    if (e.key === "Escape") document.activeElement.blur();
    return;
  }
  if (e.key === "/") {
    e.preventDefault();
    $search.focus();
    return;
  }
  if (state.cells.length === 0) return;
  const current = state.activeCellIndex ?? 0;
  if (e.key === "j") {
    e.preventDefault();
    scrollToCell(Math.min(state.cells.length - 1, current + 1));
  } else if (e.key === "k") {
    e.preventDefault();
    scrollToCell(Math.max(0, current - 1));
  } else if (e.key === "c") {
    e.preventDefault();
    toggleCollapsed(current);
  }
});
