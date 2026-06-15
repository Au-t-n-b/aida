'use client';

import { useCallback, type MouseEvent, type ReactNode } from 'react';
import {
  useLocation,
  useNavigate,
  type Location,
  type NavigateFunction,
} from 'react-router-dom';
import { navDebug } from '@/lib/nav-debug';

export const WORKSPACE_REMOUNT_STATE_KEY = '_remount';

type WorkspaceNavState = Record<string, unknown> & {
  [WORKSPACE_REMOUNT_STATE_KEY]?: number;
};

/** pathname + search，用于导航对比与 Outlet key（不含 remount 计数）。 */
export function workspaceRoutePathKey(pathname: string, search = ''): string {
  return `${pathname}${search}`;
}

export function workspaceRemountTick(state: unknown): number {
  if (!state || typeof state !== 'object') return 0;
  const tick = (state as WorkspaceNavState)[WORKSPACE_REMOUNT_STATE_KEY];
  return typeof tick === 'number' ? tick : 0;
}

/** WorkspaceShell Outlet key：同一路径再次点击侧栏时靠 remount tick 强制重挂载。 */
export function workspaceOutletKey(location: Pick<Location, 'pathname' | 'search' | 'state'>): string {
  const pathKey = workspaceRoutePathKey(location.pathname, location.search);
  const tick = workspaceRemountTick(location.state);
  return tick ? `${pathKey}@${tick}` : pathKey;
}

function hrefToPathKey(href: string): string {
  return href;
}

function mergeNavState(
  current: unknown,
  remount: boolean,
): WorkspaceNavState | undefined {
  const base =
    current && typeof current === 'object' && !Array.isArray(current)
      ? { ...(current as WorkspaceNavState) }
      : {};
  if (remount) {
    base[WORKSPACE_REMOUNT_STATE_KEY] = Date.now();
    return base;
  }
  return Object.keys(base).length > 0 ? base : undefined;
}

/** 工作台内路由跳转（与侧栏一致，强制 flushSync 避免重页切换卡住）。 */
export function workspaceNavigate(
  navigate: NavigateFunction,
  href: string,
  from?: string,
  opts?: { remount?: boolean; currentState?: unknown },
) {
  navDebug('workspace navigate', { from: from ?? '(button)', to: href, remount: !!opts?.remount });
  const navOpts: { flushSync: true; replace?: boolean; state?: WorkspaceNavState } = { flushSync: true };
  if (opts?.remount) {
    const q = href.indexOf('?');
    const pathname = q === -1 ? href : href.slice(0, q);
    const search = q === -1 ? '' : href.slice(q);
    navOpts.replace = true;
    navOpts.state = mergeNavState(opts.currentState, true);
    navigate({ pathname, search }, navOpts);
    return;
  }
  navigate(href, navOpts);
}

type WorkspaceNavLinkProps = {
  href: string;
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  onClick?: (e: MouseEvent<HTMLAnchorElement>) => void;
};

/**
 * 工作台侧栏导航：flushSync 同步提交路由，避免交付预案重页加载后 startTransition 被饿死。
 */
export function WorkspaceNavLink({ href, children, className, style, onClick }: WorkspaceNavLinkProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const handleClick = useCallback(
    (e: MouseEvent<HTMLAnchorElement>) => {
      onClick?.(e);
      if (e.defaultPrevented) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;

      const currentFull = workspaceRoutePathKey(location.pathname, location.search);
      const targetFull = hrefToPathKey(href);
      const sameTarget =
        targetFull === currentFull
        || (href.split('?')[0] === location.pathname && !href.includes('?'));

      e.preventDefault();
      e.stopPropagation();
      navDebug('left-nav navigate', {
        from: location.pathname,
        to: href,
        sameTarget,
      });
      workspaceNavigate(navigate, href, location.pathname, {
        remount: sameTarget,
        currentState: location.state,
      });
    },
    [href, location.pathname, location.search, location.state, navigate, onClick],
  );

  return (
    <a href={href} className={className} style={style} onClick={handleClick}>
      {children}
    </a>
  );
}
