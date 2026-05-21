// Render one cell as a <section.cell> into the given container.

import { renderMime } from "./mime.js";

export function renderCell(container, index, cell) {
  const card = document.createElement("section");
  card.className = "cell cell-" + (cell.status || "idle");
  if (cell.stale) card.classList.add("stale");
  card.dataset.cellIndex = String(index);

  const header = document.createElement("header");
  header.className = "cell-header";

  const num = document.createElement("span");
  num.className = "cell-num";
  num.textContent =
    cell.execution_count != null ? `In [${cell.execution_count}]` : `[${index}]`;
  header.appendChild(num);

  const status = document.createElement("span");
  status.className = "cell-status";
  status.textContent = cell.status || "idle";
  header.appendChild(status);

  card.appendChild(header);

  const body = document.createElement("div");
  body.className = "cell-body";

  const outputs = cell.outputs || [];
  if (outputs.length === 0) {
    const empty = document.createElement("p");
    empty.className = "cell-empty";
    empty.textContent = cell.kind === "markdown" ? "(markdown)" : "(no output yet)";
    body.appendChild(empty);
  } else {
    outputs.forEach((out) => renderOutput(body, out));
  }
  card.appendChild(body);

  container.appendChild(card);
  return card;
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
        pre.textContent = output.traceback.join("\n");
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
