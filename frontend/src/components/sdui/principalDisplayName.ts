/** 责任人列展示：去掉末尾工号（如「梁贝 WX616744」→「梁贝」） */
const PRINCIPAL_ID_TAIL = /(?:\s+[A-Za-z]*\d+[A-Za-z0-9]*|\s*[（(]\s*[A-Za-z]*\d+[A-Za-z0-9]*\s*[）)])\s*$/;

export function principalDisplayName(v: unknown): string {
  let s = String(v ?? '').trim();
  if (!s) return '';
  for (;;) {
    const n = s.replace(PRINCIPAL_ID_TAIL, '').trim();
    if (n === s) break;
    s = n;
  }
  return s;
}
