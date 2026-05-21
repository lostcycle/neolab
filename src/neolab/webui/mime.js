// Render a mime bundle ({mimetype: content}) into a parent element.
// Preference matches Jupyter / IPython conventions: richest renderable first.

import { renderMarkdown } from "./md.js";

const MIME_PREFERENCE = [
  "text/html",
  "image/svg+xml",
  "image/png",
  "image/jpeg",
  "text/markdown",
  "application/json",
  "text/latex",
  "text/plain",
];

export function renderMime(container, data, _metadata) {
  for (const mime of MIME_PREFERENCE) {
    if (mime in data) {
      const el = renderOne(mime, data[mime]);
      if (el) {
        container.appendChild(el);
        return;
      }
    }
  }
  const pre = document.createElement("pre");
  pre.className = "mime-unknown";
  pre.textContent = JSON.stringify(data, null, 2);
  container.appendChild(pre);
}

function renderOne(mime, content) {
  switch (mime) {
    case "text/html": {
      // Self-hosted single-user assumption — pandas/IPython HTML reprs are
      // injected as-is. CSS in style.css neutralises pandas' inline border/
      // class noise.
      const wrap = document.createElement("div");
      wrap.className = "rich-html";
      wrap.innerHTML = content;
      enhanceTables(wrap);
      return wrap;
    }
    case "image/svg+xml": {
      return mediaFrame({
        mime,
        content,
        className: "rich-svg",
        render: (body) => {
          body.innerHTML = content;
        },
      });
    }
    case "image/png":
    case "image/jpeg": {
      const img = document.createElement("img");
      img.className = "rich-img";
      img.src = `data:${mime};base64,${content}`;
      return mediaFrame({
        mime,
        content,
        className: "rich-image-frame",
        render: (body) => body.appendChild(img),
        dataUrl: img.src,
      });
    }
    case "text/markdown": {
      const div = document.createElement("div");
      div.className = "md";
      div.innerHTML = renderMarkdown(typeof content === "string" ? content : String(content));
      return div;
    }
    case "application/json": {
      const pre = document.createElement("pre");
      pre.className = "mime-json";
      pre.textContent =
        typeof content === "string" ? content : JSON.stringify(content, null, 2);
      return pre;
    }
    case "text/latex": {
      const pre = document.createElement("pre");
      pre.className = "mime-latex";
      pre.textContent = content;
      return pre;
    }
    case "text/plain": {
      const pre = document.createElement("pre");
      pre.className = "mime-text-plain";
      pre.textContent = content;
      return pre;
    }
    default:
      return null;
  }
}

function mediaFrame({ mime, content, className, render, dataUrl }) {
  const frame = document.createElement("figure");
  frame.className = "media-frame " + className;
  const toolbar = document.createElement("figcaption");
  toolbar.className = "media-toolbar";
  const body = document.createElement("div");
  body.className = "media-body";
  render(body);

  const url =
    dataUrl || `data:${mime};charset=utf-8,${encodeURIComponent(String(content))}`;
  toolbar.appendChild(actionButton("zoom", () => frame.classList.toggle("zoomed")));
  toolbar.appendChild(actionButton("open", () => window.open(url, "_blank", "noopener")));
  toolbar.appendChild(actionButton("save", () => {
    const a = document.createElement("a");
    a.href = url;
    a.download = mime === "image/svg+xml" ? "neolab-output.svg" : "neolab-output.png";
    a.click();
  }));
  toolbar.appendChild(actionButton("copy", async () => {
    if (!navigator.clipboard || !window.ClipboardItem) return;
    const blob = await (await fetch(url)).blob();
    await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
  }));
  frame.appendChild(toolbar);
  frame.appendChild(body);
  return frame;
}

function actionButton(label, onClick) {
  const button = document.createElement("button");
  button.className = "mime-action";
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function enhanceTables(root) {
  root.querySelectorAll("table").forEach((table) => {
    const toolbar = document.createElement("div");
    toolbar.className = "table-toolbar";
    const filter = document.createElement("input");
    filter.type = "search";
    filter.placeholder = "filter rows";
    filter.className = "table-filter";
    toolbar.appendChild(filter);
    table.parentNode.insertBefore(toolbar, table);

    const body = table.tBodies[0];
    if (!body) return;
    const rows = () => Array.from(body.rows);
    filter.addEventListener("input", () => {
      const q = filter.value.trim().toLowerCase();
      rows().forEach((row) => {
        row.style.display = !q || row.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    });

    table.querySelectorAll("thead th").forEach((th, idx) => {
      th.tabIndex = 0;
      th.title = "Sort column";
      th.addEventListener("click", () => sortTable(body, idx, th));
      th.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          sortTable(body, idx, th);
        }
      });
    });
  });
}

function sortTable(body, idx, th) {
  const dir = th.dataset.sortDir === "asc" ? "desc" : "asc";
  th.dataset.sortDir = dir;
  const sign = dir === "asc" ? 1 : -1;
  const sorted = Array.from(body.rows).sort((a, b) => {
    const av = a.cells[idx]?.textContent.trim() || "";
    const bv = b.cells[idx]?.textContent.trim() || "";
    const an = Number(av.replaceAll(",", ""));
    const bn = Number(bv.replaceAll(",", ""));
    if (!Number.isNaN(an) && !Number.isNaN(bn)) return (an - bn) * sign;
    return av.localeCompare(bv) * sign;
  });
  sorted.forEach((row) => body.appendChild(row));
}
