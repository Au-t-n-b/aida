/** 数据中心降级提示（Toast / console） */
let handler: ((warnings: string[], source?: string) => void) | null = null;

export function setDataFallbackHandler(
  fn: ((warnings: string[], source?: string) => void) | null,
): void {
  handler = fn;
}

export function notifyDataFallback(warnings: string[], source?: string): void {
  if (!warnings.length) return;
  console.warn('[AIDA 数据降级]', source ?? '', warnings);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent('aida:data-fallback', { detail: { warnings, source } }),
    );
  }
  handler?.(warnings, source);
}
