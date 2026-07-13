/**
 * 字幕分块：把整段文案切成 ≤maxChars 字符的块，按标点断点切，不硬拆词。
 * 中文标点（，。！？、；：）+ 英文标点 + 换行/空格 作为短语边界。
 */

const PHRASE_BREAK = new Set([
  "，", "。", "！", "？", "、", "；", "：", "…",
  ",", ".", "!", "?", ";", ":",
  "\n", "\r", " ", "　",
  "“", "”", "‘", "’", "（", "）", "(", ")",
]);

/**
 * 先按标点切成短语（标点附着前一个短语），再贪心打包成 ≤maxChars 的块。
 * 单个短语超 maxChars 时硬切。
 */
export function splitSubtitle(text: string, maxChars = 16): string[] {
  const cleaned = (text || "").replace(/\s+/g, " ").trim();
  if (!cleaned) return [];
  if (cleaned.length <= maxChars) return [cleaned];

  // 1. 按标点切短语（标点保留在前一短语末尾）
  const phrases: string[] = [];
  let cur = "";
  for (const ch of cleaned) {
    cur += ch;
    if (PHRASE_BREAK.has(ch)) {
      phrases.push(cur);
      cur = "";
    }
  }
  if (cur) phrases.push(cur);

  // 2. 贪心打包成 ≤maxChars 的块
  const chunks: string[] = [];
  let buf = "";
  for (const p of phrases) {
    if (p.length > maxChars) {
      // 超长短语：先收尾 buf，再硬切 p
      if (buf.trim()) { chunks.push(buf.trim()); buf = ""; }
      for (let i = 0; i < p.length; i += maxChars) {
        chunks.push(p.slice(i, i + maxChars).trim());
      }
      continue;
    }
    if ((buf + p).length <= maxChars) {
      buf += p;
    } else {
      if (buf.trim()) chunks.push(buf.trim());
      buf = p;
    }
  }
  if (buf.trim()) chunks.push(buf.trim());
  return chunks.filter((c) => c.length > 0);
}
