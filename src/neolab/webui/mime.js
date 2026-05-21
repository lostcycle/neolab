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
      return wrap;
    }
    case "image/svg+xml": {
      const wrap = document.createElement("div");
      wrap.className = "rich-svg";
      wrap.innerHTML = content;
      return wrap;
    }
    case "image/png":
    case "image/jpeg": {
      const img = document.createElement("img");
      img.className = "rich-img";
      img.src = `data:${mime};base64,${content}`;
      return img;
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
