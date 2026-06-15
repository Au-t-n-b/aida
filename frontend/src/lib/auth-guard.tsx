import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAidaSession } from './aida-session';
import { useCurrentProject } from './current-project';

/**
 * TEMP(local-dev) · 仅本地 `npm run dev` 调测用的免登录直达白名单。
 * 用 import.meta.env.DEV 守门：`npm run build`（即上传/部署版本）下恒为 false，
 * 自动回归正常登录，无需手动回滚。新增路径只在此白名单加前缀。
 */
const DEV_LOGIN_BYPASS_PREFIXES = ['/module/deploy'];

function isDevLoginBypass(pathname: string): boolean {
  return import.meta.env.DEV
    && DEV_LOGIN_BYPASS_PREFIXES.some(prefix => pathname.startsWith(prefix));
}

/** 已登录才可访问；否则跳转登录页并记录来源路径。 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAidaSession();
  const location = useLocation();
  if (!session) {
    if (isDevLoginBypass(location.pathname)) return children;  // 本地调测直达，生产自动失效
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return children;
}

/** 仅未登录可访问（登录页）；已登录则进项目选择页。 */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { session } = useAidaSession();
  if (session) {
    return <Navigate to="/landing" replace />;
  }
  return children;
}

/** 根路径：未登录 → /login，已登录 → /landing（会议规定的登录后第一屏）。 */
export function RootRedirect() {
  const { session } = useAidaSession();
  return <Navigate to={session ? '/landing' : '/login'} replace />;
}

/** 项目空间页：须已选项目，否则回项目列表。 */
export function RequireProject({ children }: { children: ReactNode }) {
  const { project } = useCurrentProject();
  if (!project?.id) {
    return <Navigate to="/landing" replace />;
  }
  return children;
}
