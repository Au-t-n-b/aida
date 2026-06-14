'use client';

import { useCallback, type MouseEvent, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { navDebug } from '@/lib/nav-debug';

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
      navigate(href, { flushSync: true });
    },
    [href, location.pathname, location.search, navigate, onClick],
  );

  return (
    <a href={href} className={className} style={style} onClick={handleClick}>
      {children}
    </a>
  );
}
