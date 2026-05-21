// File-tree icons. Inline SVG so we ship no fonts and have no CDN dependency.
// Colors borrow github-linguist / vscode-icons conventions so the tree feels
// like neo-tree.

const FILE_PATH = "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6";
const FOLDER_PATH = "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z";
const FOLDER_OPEN_PATH =
  "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2H3z M3 9h18l-2 9a2 2 0 0 1-2 1.6H5a2 2 0 0 1-2-1.6L3 9z";

function iconShell(bg, fg, body) {
  return (
    `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">` +
    `<rect x="3" y="2.5" width="18" height="19" rx="3.2" fill="${bg}"/>` +
    `<path d="M15 2.5v5h6" fill="rgba(255,255,255,0.24)"/>` +
    body(fg) +
    `</svg>`
  );
}

function iconText(label, bg, fg = "#fff", { size = 6.2, y = 15 } = {}) {
  return iconShell(
    bg,
    fg,
    (color) =>
      `<text x="12" y="${y}" text-anchor="middle" fill="${color}" ` +
      `font-family="ui-monospace, Menlo, Consolas, monospace" font-size="${size}" ` +
      `font-weight="800">${label}</text>`
  );
}

function pythonIcon() {
  return (
    `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">` +
    `<path fill="#3572A5" d="M11.9 2c-3.2 0-5.1.9-5.1 2.6v2.1h5.4v.8H4.6C3.1 7.5 2 9 2 12s1.1 4.5 2.6 4.5h2.1v-2.8c0-1.7 1.5-3.2 3.2-3.2h5.2c1.4 0 2.5-1.1 2.5-2.5V4.6C17.6 2.9 15.3 2 11.9 2Z"/>` +
    `<path fill="#FFD43B" d="M12.1 22c3.2 0 5.1-.9 5.1-2.6v-2.1h-5.4v-.8h7.6c1.5 0 2.6-1.5 2.6-4.5s-1.1-4.5-2.6-4.5h-2.1v2.8c0 1.7-1.5 3.2-3.2 3.2H8.9c-1.4 0-2.5 1.1-2.5 2.5v3.4c0 1.7 2.3 2.6 5.7 2.6Z"/>` +
    `<circle cx="9" cy="4.7" r="0.8" fill="#fff"/>` +
    `<circle cx="15" cy="19.3" r="0.8" fill="#1f2937"/>` +
    `</svg>`
  );
}

function markdownIcon() {
  return iconShell(
    "#519aba",
    "#fff",
    (color) =>
      `<path d="M7 9v6m0-6 2.4 3.2L11.8 9v6M14 9l2 3 2-3m-2 3v3" ` +
      `fill="none" stroke="${color}" stroke-width="1.7" stroke-linecap="round" ` +
      `stroke-linejoin="round"/>`
  );
}

function tableIcon(label, bg = "#16a34a") {
  return iconShell(
    bg,
    "#fff",
    (color) =>
      `<path d="M6.8 7.6h10.4v8.8H6.8zM6.8 10.5h10.4M6.8 13.5h10.4M10.2 7.6v8.8M13.8 7.6v8.8" ` +
      `fill="none" stroke="${color}" stroke-width="1.1" opacity="0.92"/>` +
      `<text x="12" y="20" text-anchor="middle" fill="${color}" ` +
      `font-family="ui-monospace, Menlo, Consolas, monospace" font-size="4.2" ` +
      `font-weight="800">${label}</text>`
  );
}

function jsonIcon() {
  return iconShell(
    "#cbcb41",
    "#1f2937",
    (color) =>
      `<text x="12" y="15.4" text-anchor="middle" fill="${color}" ` +
      `font-family="ui-monospace, Menlo, Consolas, monospace" font-size="9" ` +
      `font-weight="900">{}</text>`
  );
}

function yamlIcon() {
  return iconShell(
    "#cb171e",
    "#fff",
    (color) =>
      `<path d="M8 7.5h4v3H8zM12 9h4v3h-4zM8 13.5h4v3H8zM10 10.5v3M12 10.5h2" ` +
      `fill="none" stroke="${color}" stroke-width="1.2" stroke-linejoin="round"/>`
  );
}

function tomlIcon() {
  return iconShell(
    "#9c4221",
    "#fff",
    (color) =>
      `<path d="M7.5 8.2h3.2M7.5 12h3.2M7.5 15.8h3.2M13.2 8.2h3.3M13.2 12h3.3M13.2 15.8h3.3" ` +
      `stroke="${color}" stroke-width="1.4" stroke-linecap="round"/>`
  );
}

function textIcon() {
  return iconShell(
    "#8b8e98",
    "#fff",
    (color) =>
      `<path d="M7 8.2h10M7 11.2h10M7 14.2h7M7 17.2h8.5" ` +
      `stroke="${color}" stroke-width="1.35" stroke-linecap="round"/>`
  );
}

function logIcon() {
  return iconShell(
    "#64748b",
    "#fff",
    (color) =>
      `<path d="M7 9.2 9.4 12 7 14.8M10.7 15h5.6" fill="none" ` +
      `stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`
  );
}

function svg(pathD, color, { fill = false } = {}) {
  const stroke = fill ? "none" : color;
  const fillAttr = fill ? color : "none";
  return (
    `<svg viewBox="0 0 24 24" width="14" height="14" fill="${fillAttr}" ` +
    `stroke="${stroke}" stroke-width="1.6" stroke-linecap="round" ` +
    `stroke-linejoin="round" aria-hidden="true"><path d="${pathD}"/></svg>`
  );
}

// extension -> color. Names follow github-linguist's defaults where reasonable.
const EXT_COLOR = {
  py: "#3572A5",
  pyi: "#3572A5",
  ipynb: "#DA5B0B",
  lua: "#51a0cf",
  js: "#f1e05a",
  mjs: "#f1e05a",
  cjs: "#f1e05a",
  ts: "#2b7489",
  tsx: "#2b7489",
  jsx: "#f1e05a",
  json: "#cbcb41",
  jsonc: "#cbcb41",
  md: "#519aba",
  markdown: "#519aba",
  rst: "#519aba",
  toml: "#9c4221",
  yaml: "#cb171e",
  yml: "#cb171e",
  html: "#e34c26",
  htm: "#e34c26",
  css: "#563d7c",
  scss: "#c6538c",
  sass: "#c6538c",
  txt: "#8b8e98",
  log: "#8b8e98",
  sh: "#4eaa25",
  bash: "#4eaa25",
  zsh: "#4eaa25",
  fish: "#4eaa25",
  rs: "#dea584",
  go: "#6ad7e5",
  c: "#555555",
  h: "#555555",
  cpp: "#f34b7d",
  hpp: "#f34b7d",
  java: "#b07219",
  rb: "#701516",
  php: "#4F5D95",
  sql: "#e38c00",
  csv: "#16a34a",
  tsv: "#16a34a",
  parquet: "#16a34a",
  xml: "#0060ac",
  svg: "#ff9800",
  png: "#a371f7",
  jpg: "#a371f7",
  jpeg: "#a371f7",
  gif: "#a371f7",
  webp: "#a371f7",
  pdf: "#dc2626",
  lock: "#8b8e98",
  env: "#fbbf24",
  gitignore: "#8b8e98",
};

// Special filenames (case-insensitive, full match) → color.
const NAME_COLOR = {
  Dockerfile: "#0db7ed",
  Makefile: "#427819",
  "pyproject.toml": "#3572A5",
  "uv.lock": "#3572A5",
  "requirements.txt": "#3572A5",
  README: "#519aba",
  LICENSE: "#cbcb41",
  CHANGELOG: "#519aba",
};

const DEFAULT_COLOR = "#9aa0a8";
const FOLDER_COLOR = "#6cc4ff";

function extOf(name) {
  const i = name.lastIndexOf(".");
  if (i < 0 || i === name.length - 1) return "";
  return name.slice(i + 1).toLowerCase();
}

function nameKey(name) {
  for (const key of Object.keys(NAME_COLOR)) {
    if (name === key || name.toLowerCase() === key.toLowerCase()) return key;
  }
  return null;
}

export function fileIconHTML(name) {
  const ext = extOf(name);
  if (ext === "py" || ext === "pyi") return pythonIcon();
  if (ext === "md" || ext === "markdown") return markdownIcon();
  if (ext === "csv") return tableIcon("CSV");
  if (ext === "tsv") return tableIcon("TSV");
  if (ext === "parquet") return tableIcon("PQ", "#0f766e");
  if (ext === "json") return jsonIcon();
  if (ext === "yaml" || ext === "yml") return yamlIcon();
  if (ext === "toml") return tomlIcon();
  if (ext === "txt") return textIcon();
  if (ext === "log") return logIcon();
  const namedHit = nameKey(name);
  const color = namedHit ? NAME_COLOR[namedHit] : (EXT_COLOR[ext] || DEFAULT_COLOR);
  return svg(FILE_PATH, color);
}

export function folderIconHTML(open) {
  const path = open ? FOLDER_OPEN_PATH : FOLDER_PATH;
  return svg(path, FOLDER_COLOR, { fill: false });
}
