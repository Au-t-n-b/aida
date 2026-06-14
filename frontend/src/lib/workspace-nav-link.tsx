'use client';

import { useCallback, type MouseEvent, type ReactNode } from 'react';
import { useLocation, useNavigate, type NavigateFunction } from 'react-router-dom';
import { navDebug } from '@/lib/nav-debug';

/** 工作台内路由跳转（与侧栏一致，强制 flushSync 避免重页切换卡住）。 */
export function workspaceNavigate(navigate: NavigateFunction, href: string, from?: string) {
  navDebug('workspace navigate', { from: from ?? '(button)', to: href });
  navigate(href, { flushSync: true });
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

      const targetPath = href.split('?')[0] ?? href;
      const samePath = targetPath === location.pathname;
      const sameFull = href === `${location.pathname}${location.search}`;
      if (sameFull || (samePath && !href.includes('?'))) return;

      e.preventDefault();
      e.stopPropagation();
      navDebug('left-nav navigate', { from: location.pathname, to: href });
      workspaceNavigate(navigate, href, location.pathname);
    },
    [href, location.pathname, location.search, navigate, onClick],
  );

  return (
    <a href={href} className={className} style={style} onClick={handleClick}>
      {children}
    </a>
  );
}
