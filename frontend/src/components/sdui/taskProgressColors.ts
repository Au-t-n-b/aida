/** 任务进度条语义色：<15% 红 · 15–99% 黄 · 100% 绿 */
export function taskProgressFill(pct: number): string {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  if (p >= 100) return 'var(--c-success)';
  if (p >= 15) return 'var(--c-warning)';
  return 'var(--c-danger)';
}
