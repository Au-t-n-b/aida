export type NavExpandedState = {
  twin: boolean;
  early: boolean;
  plan: boolean;
  ops: boolean;
  docs: boolean;
};

const STORAGE_KEY = 'aida:left-nav-expanded';

const DEFAULT_EXPANDED: NavExpandedState = {
  twin: true,
  early: true,
  plan: true,
  ops: true,
  docs: false,
};

let cachedExpanded: NavExpandedState | null = null;

/** 当前路由下必须保持展开的分组（含 query 切换场景） */
export function routeRequiredExpanded(navPath: string): NavExpandedState {
  const pathname = navPath.split('?')[0] ?? navPath;
  return {
    twin: pathname === '/cockpit' || pathname.startsWith('/twin'),
    early: pathname.startsWith('/preview') || pathname.startsWith('/proposal'),
    plan:
      pathname.startsWith('/plan') ||
      pathname.startsWith('/plan-init') ||
      pathname.startsWith('/plan-adjust'),
    ops: pathname.startsWith('/module/') || pathname.startsWith('/commissioning'),
    docs: navPath.startsWith('/assets'),
  };
}

/** 路由进入某分区时自动展开对应分组，不覆盖用户已收起的状态 */
export function applyRouteRequiredExpand(manual: NavExpandedState, navPath: string): NavExpandedState {
  const required = routeRequiredExpanded(navPath);
  let changed = false;
  const next = { ...manual };
  (Object.keys(required) as (keyof NavExpandedState)[]).forEach((k) => {
    if (required[k] && !next[k]) {
      next[k] = true;
      changed = true;
    }
  });
  return changed ? next : manual;
}

export function readPersistedExpanded(): NavExpandedState {
  if (cachedExpanded) return { ...cachedExpanded };
  if (typeof sessionStorage === 'undefined') return { ...DEFAULT_EXPANDED };
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_EXPANDED };
    const parsed = JSON.parse(raw) as Partial<NavExpandedState>;
    cachedExpanded = { ...DEFAULT_EXPANDED, ...parsed };
    return { ...cachedExpanded };
  } catch {
    return { ...DEFAULT_EXPANDED };
  }
}

export function persistExpanded(state: NavExpandedState) {
  cachedExpanded = { ...state };
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(cachedExpanded));
  }
}

export function readInitialExpanded(navPath?: string): NavExpandedState {
  let path = navPath ?? '';
  if (!path && typeof window !== 'undefined') {
    const { pathname, search } = window.location;
    path = search ? `${pathname}${search}` : pathname;
  }
  const manual = readPersistedExpanded();
  return path ? applyRouteRequiredExpand(manual, path) : manual;
}
