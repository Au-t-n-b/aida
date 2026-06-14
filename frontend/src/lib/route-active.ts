import { useLocation } from 'react-router-dom';

/** 当前路由是否仍为 mount 时的目标路径（用于 stale UI 防护） */
export function useRouteActive(expectedPath: string): boolean {
  const { pathname } = useLocation();
  return pathname === expectedPath;
}
