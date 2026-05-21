// Render a mime bundle ({mimetype: content}) into a parent element.
// P1 ships text/plain only; richer mimes (text/html, image/png, ...) are P3.

const MIME_PREFERENCE = [
  "image/svg+xml",
  "image/png",
  "image/jpeg",
  "text/html",
  "application/json",
  "text/markdown",
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
  // Unknown mime — pretty-print the bundle for debugging.
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(data, null, 2);
  container.appendChild(pre);
}

function renderOne(mime, content) {
  switch (mime) {
    case "text/plain": {
      const pre = document.createElement("pre");
      pre.className = "mime-text-plain";
      pre.textContent = content;
      return pre;
    }
    // Placeholder until P3 wires up sanitization/rendering for richer types.
    case "text/html":
    case "image/png":
    case "image/jpeg":
    case "image/svg+xml":
    case "application/json":
    case "text/markdown":
    case "text/latex":
    default:
      return null; // fall through to next preferred mime
  }
}
