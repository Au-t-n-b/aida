/** 剥离模型输出中的 thinking / redacted_thinking 块（含流式未闭合标签）。 */

const THINKING_BLOCK_RE =
  /<(?:redacted_thinking|think|thinking)>[\s\S]*?<\/(?:redacted_thinking|think|thinking)>\s*/gi;

const OPEN_TAG_RE = /<(?:redacted_thinking|think|thinking)>/i;

/** 流式尾部可能截断在未闭合的 `<redacted_thin...` */
const PARTIAL_OPEN_RE =
  /<(?:\/(?:redacted_thinking|think|thinking)?|redacted_thin(?:king)?|think(?:ing)?)?$/i;

export function stripThinkingContent(text: string): string {
  if (!text) return '';
  let s = text.replace(THINKING_BLOCK_RE, '');
  const open = OPEN_TAG_RE.exec(s);
  if (open && open.index !== undefined) {
    s = s.slice(0, open.index);
  }
  s = s.replace(PARTIAL_OPEN_RE, '');
  return s;
}
