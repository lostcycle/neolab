// Render one cell as a <section.cell> into the given container.
// Markdown cells render their source inline. Code/raw cells render outputs.

import { renderMime } from "./mime.js";
import { renderMarkdown } from "./md.js";

export function renderCell(container, index, cell) {
  const card = document.createElement("section");
  card.className = "cell cell-" + (cell.status || "idle");
  if (cell.stale) card.classList.add("stale");
  if (cell.kind === "markdown") card.classList.add("cell-markdown");
  card.dataset.cellIndex = String(index);

  const header = document.createElement("header");
  header.className = "cell-header";

  const dot = document.createElement("span");
  dot.className = "cell-dot";
  header.appendChild(dot);

  const num = document.createElement("span");
  num.className = "cell-num";
  if (cell.kind === "markdown") {
    num.textContent = `[md ${index}]`;
  } else if (cell.kind === "raw") {
    num.textContent = `[raw ${index}]`;
  } else {
    num.textContent =
      cell.execution_count != null ? `In [${cell.execution_count}]` : `[${index}]`;
  }
  header.appendChild(num);

  const status = document.createElement("span");
  status.className = "cell-status";
  status.textContent = cell.kind === "markdown" ? "md" : cell.status || "idle";
  header.appendChild(status);

  card.appendChild(header);

  const body = document.createElement("div");
  body.className = "cell-body";

  if (cell.kind === "markdown") {
    const div = document.createElement("div");
    div.className = "md";
    div.innerHTML = renderMarkdown(cell.source || "");
    if (!div.innerHTML.trim()) {
      div.innerHTML = '<p class="cell-empty">(empty markdown cell)</p>';
    }
    body.appendChild(div);
  } else {
    const outputs = cell.outputs || [];
    if (outputs.length === 0) {
      const empty = document.createElement("p");
      empty.className = "cell-empty";
      empty.textContent = "(no output yet)";
      body.appendChild(empty);
    } else {
      outputs.forEach((out) => renderOutput(body, out));
    }
  }
  card.appendChild(body);

  container.appendChild(card);
  return card;
}

function stripAnsi(s) {
  // eslint-disable-next-line no-control-regex
  return s.replace(/\x1b\[[0-9;]*m/g, "");
}

function renderOutput(container, output) {
  switch (output.type) {
    case "stream": {
      const last = container.lastElementChild;
      if (last && last.dataset.streamName === output.name) {
        last.textContent += output.text;
        return;
      }
      const pre = document.createElement("pre");
      pre.className = "stream stream-" + output.name;
      pre.dataset.streamName = output.name;
      pre.textContent = output.text;
      container.appendChild(pre);
      return;
    }
    case "display":
    case "result": {
      const wrap = document.createElement("div");
      wrap.className = "output-" + output.type;
      renderMime(wrap, output.data || {}, output.metadata || {});
      container.appendChild(wrap);
      return;
    }
    case "error": {
      const wrap = document.createElement("div");
      wrap.className = "output-error";
      const head = document.createElement("strong");
      head.textContent = `${output.ename || "Error"}: ${output.evalue || ""}`;
      wrap.appendChild(head);
      if (Array.isArray(output.traceback) && output.traceback.length) {
        const pre = document.createElement("pre");
        pre.textContent = stripAnsi(output.traceback.join("\n"));
        wrap.appendChild(pre);
      }
      container.appendChild(wrap);
      return;
    }
    case "clear": {
      container.innerHTML = "";
      return;
    }
  }
}
