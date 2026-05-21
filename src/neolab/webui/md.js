// Minimal markdown renderer for jupytext markdown cells and text/markdown
// outputs. Handles headings, bold/italic/code, links, lists, blockquotes,
// code fences, hr, paragraphs. Text is HTML-escaped first; replacements then
// emit a fixed set of safe tags.

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escape = (s) => s.replace(/[&<>"']/g, (ch) => ESC[ch]);

function inline(text) {
  let s = escape(text);
  s = s.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  s = s.replace(/(^|[^\w])_([^_\n]+)_(?=[^\w]|$)/g, "$1<em>$2</em>");
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (whole, t, u) => {
    if (!/^(https?:\/\/|\/|#|\.)/.test(u)) return whole;
    return `<a href="${u}" target="_blank" rel="noopener">${t}</a>`;
  });
  return s;
}

export function renderMarkdown(src) {
  const lines = (src || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  const para = [];

  const flushParagraph = () => {
    if (!para.length) return;
    const text = para.join(" ");
    if (text.trim()) out.push(`<p>${inline(text)}</p>`);
    para.length = 0;
  };

  while (i < lines.length) {
    const line = lines[i];

    if (/^```/.test(line)) {
      flushParagraph();
      const lang = line.replace(/^```/, "").trim();
      i++;
      const codeLines = [];
      while (i < lines.length && !/^```/.test(lines[i])) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // closing fence
      const langAttr = lang ? ` data-lang="${escape(lang)}"` : "";
      out.push(`<pre class="md-code"${langAttr}><code>${escape(codeLines.join("\n"))}</code></pre>`);
      continue;
    }

    if (/^\s*(---+|\*\*\*+|___+)\s*$/.test(line)) {
      flushParagraph();
      out.push("<hr>");
      i++;
      continue;
    }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushParagraph();
      out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);
      i++;
      continue;
    }

    if (/^>\s?/.test(line)) {
      flushParagraph();
      const bq = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        bq.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      out.push(`<blockquote>${renderMarkdown(bq.join("\n"))}</blockquote>`);
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      flushParagraph();
      const items = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ""));
        i++;
      }
      out.push("<ul>" + items.map((t) => `<li>${inline(t)}</li>`).join("") + "</ul>");
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      flushParagraph();
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      out.push("<ol>" + items.map((t) => `<li>${inline(t)}</li>`).join("") + "</ol>");
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      i++;
      continue;
    }

    para.push(line);
    i++;
  }
  flushParagraph();
  return out.join("\n");
}
