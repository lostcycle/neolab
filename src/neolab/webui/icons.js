// File-tree icons. Inline SVG so we ship no fonts and have no CDN dependency.
// Colors borrow github-linguist / vscode-icons conventions so the tree feels
// like neo-tree.

const FILE_PATH = "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6";
const FOLDER_PATH = "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z";
const FOLDER_OPEN_PATH =
  "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2H3z M3 9h18l-2 9a2 2 0 0 1-2 1.6H5a2 2 0 0 1-2-1.6L3 9z";

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
  const namedHit = nameKey(name);
  const color = namedHit ? NAME_COLOR[namedHit] : (EXT_COLOR[extOf(name)] || DEFAULT_COLOR);
  return svg(FILE_PATH, color);
}

export function folderIconHTML(open) {
  const path = open ? FOLDER_OPEN_PATH : FOLDER_PATH;
  return svg(path, FOLDER_COLOR, { fill: false });
}
