// neolab — browser UI entry point.

import { WS } from "./ws.js";
import { renderCell } from "./cell.js";
import { renderTree, setActiveFile } from "./tree.js";

const state = {
  activePath: null,
  cells: [], // [{ kind, outputs, status, execution_count, stale }]
  tree: null, // { root, nodes }
  activeCellIndex: null,
};

const $path = document.getElementById("path");
const $kstat = document.getElementById("kernel-status");
const $cells = document.getElementById("cells");
const $tree = document.getElementById("tree");
const $treeRoot = document.getElementById("tree-root");

function ensureCell(index, kind = "code") {
  while (state.cells.length <= index) {
    state.cells.push({
      kind,
      outputs: [],
      status: "idle",
      execution_count: null,
      stale: false,
    });
  }
}

function setKernelStatus(s) {
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
    state.cells.forEach((cell, i) => renderCell($cells, i, cell));
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
  if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
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

function applyEvent(ev) {
  switch (ev.type) {
    case "state": {
      state.activePath = ev.path;
      state.cells = (ev.cells || []).map((c) => ({
        kind: c.kind,
        outputs: c.outputs || [],
        status: c.status || "idle",
        execution_count: c.execution_count ?? null,
        stale: !!c.stale,
      }));
      setKernelStatus(ev.kernel_status || "idle");
      renderAll();
      setActiveFile($tree, state.activePath);
      return;
    }
    case "file_synced": {
      if (state.activePath !== ev.path) {
        state.activePath = ev.path;
        state.cells = (ev.cells || []).map((c) => ({
          kind: c.kind,
          outputs: [],
          status: "idle",
          execution_count: null,
          stale: false,
        }));
      } else {
        const incoming = ev.cells || [];
        incoming.forEach((c, i) => {
          if (i >= state.cells.length) {
            state.cells.push({
              kind: c.kind,
              outputs: [],
              status: "idle",
              execution_count: null,
              stale: false,
            });
          } else {
            state.cells[i].kind = c.kind;
          }
        });
        state.cells.length = incoming.length;
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
