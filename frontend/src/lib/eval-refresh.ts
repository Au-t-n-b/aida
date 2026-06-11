/** 评测刷新：会话/工勘结束后自动跑 eval（60s 防抖） */
import { API_BASE } from '@/components/screens/evals/shared';

export const EVALS_REFRESH_EVENT = 'aida-evals-refreshed';

const lastRefresh = new Map<string, number>();
const DEBOUNCE_MS = 15_000;

export async function refreshEvals(
  opts: { run_id?: string; conv_id?: string; force?: boolean } = {},
): Promise<boolean> {
  const key = opts.run_id ? `run:${opts.run_id}` : opts.conv_id ? `conv:${opts.conv_id}` : 'global';
  const now = Date.now();
  const prev = lastRefresh.get(key) ?? 0;
  if (!opts.force && now - prev < DEBOUNCE_MS) return false;
  lastRefresh.set(key, now);

  const q = new URLSearchParams({ live: '1' });
  if (opts.run_id) q.set('run_id', opts.run_id);
  if (opts.conv_id) q.set('conv_id', opts.conv_id);

  try {
    const res = await fetch(`${API_BASE}/agent/evals/refresh?${q}`, { method: 'POST' });
    if (res.ok && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(EVALS_REFRESH_EVENT, { detail: opts }));
    }
    return res.ok;
  } catch {
    return false;
  }
}
