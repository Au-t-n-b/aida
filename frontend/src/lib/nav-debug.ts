/**
 * 路由切换诊断日志
 * 开启：localStorage.setItem('aida:nav-debug', '1') 后刷新
 * 关闭：localStorage.removeItem('aida:nav-debug')
 */
const PREFIX = '[AIDA Nav]';

export function isNavDebugEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem('aida:nav-debug') === '1';
  } catch {
    return false;
  }
}

export function navDebug(event: string, detail?: Record<string, unknown>): void {
  if (!isNavDebugEnabled()) return;
  const ts = new Date().toISOString().slice(11, 23);
  if (detail) {
    console.info(`${PREFIX} ${ts} ${event}`, detail);
  } else {
    console.info(`${PREFIX} ${ts} ${event}`);
  }
}

export function navDebugWarn(event: string, detail?: Record<string, unknown>): void {
  if (!isNavDebugEnabled()) return;
  const ts = new Date().toISOString().slice(11, 23);
  console.warn(`${PREFIX} ${ts} ${event}`, detail ?? '');
}

/** 首次进入页面时在控制台提示如何开启诊断 */
export function navDebugHintOnce(): void {
  if (typeof window === 'undefined') return;
  if (isNavDebugEnabled()) return;
  const key = 'aida:nav-debug-hint';
  try {
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, '1');
  } catch {
    return;
  }
  console.info(
    `${PREFIX} 若遇「URL 已变但页面不切换」，可执行 localStorage.setItem('aida:nav-debug','1') 后刷新，查看导航日志`,
  );
}

/** 记录 app-main 内实际 DOM，便于对比 URL 与可见内容 */
export function navDebugDomSnapshot(label: string): void {
  if (!isNavDebugEnabled() || typeof document === 'undefined') return;
  const main = document.querySelector('.app-main');
  const workspace = document.querySelector('[data-workspace-route]');
  const proposal = document.querySelector('.proposal-main-canvas');
  const twin = document.querySelector('[data-twin-survey]');
  navDebug(`dom ${label}`, {
    workspaceRoute: workspace?.getAttribute('data-workspace-route'),
    navState: workspace?.getAttribute('data-nav-state'),
    mainChildCount: main?.childElementCount ?? 0,
    mainFirstClass: main?.firstElementChild?.className?.slice?.(0, 80),
    hasProposalCanvas: !!proposal,
    hasTwinSurvey: !!twin,
  });
}
