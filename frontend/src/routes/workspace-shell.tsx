'use client';

import { Suspense, useEffect, useRef } from 'react';
import { Outlet, useLocation, useNavigation } from 'react-router-dom';
import { AppShell } from '@/components/app-shell';
import ClawRail from '@/components/claw-rail';
import { useCurrentProject } from '@/lib/current-project';
import { useAidaSession } from '@/lib/aida-session';
import { useTweaks } from '@/lib/tweaks-context';
import { getWorkspaceMeta } from '@/lib/workspace-meta';
import { navDebug, navDebugDomSnapshot, navDebugHintOnce, navDebugWarn } from '@/lib/nav-debug';
import { workspaceOutletKey, workspaceRoutePathKey } from '@/lib/workspace-nav-link';

function PageSwitchFallback() {
  return (
    <div
      style={{
        flex: 1,
        display: 'grid',
        placeItems: 'center',
        padding: 32,
        color: '#64748b',
        fontSize: 14,
      }}
    >
      页面切换中…
    </div>
  );
}

/**
 * 项目空间共享壳层：LeftNav + TopBar + ClawRail 只挂载一次。
 * Outlet 使用 pathname key 强制卸载旧页。
 */
export default function WorkspaceShell() {
  const location = useLocation();
  const navigation = useNavigation();
  const { project } = useCurrentProject();
  const { session, enterProject } = useAidaSession();
  const { tweaks, setTweak } = useTweaks();
  const prevPathRef = useRef('');
  const clawBoundRef = useRef('');

  useEffect(() => {
    if (!session?.accessToken || !project?.id) return;
    const bindKey = `${session.sessionId}:${project.id}`;
    if (clawBoundRef.current === bindKey) return;
    clawBoundRef.current = bindKey;
    void enterProject(
      project.id,
      project.projectCode || (String(project.code ?? '').startsWith('PROP-') ? undefined : project.code),
    ).catch(() => {
      clawBoundRef.current = '';
    });
  }, [session?.accessToken, session?.sessionId, project?.id, project?.projectCode, project?.code, enterProject]);

  const meta = getWorkspaceMeta(location.pathname, location.search, project);
  const pathKey = workspaceRoutePathKey(location.pathname, location.search);
  const routeKey = workspaceOutletKey(location);
  const pendingPathKey = navigation.location
    ? workspaceRoutePathKey(navigation.location.pathname, navigation.location.search ?? '')
    : '';
  const isNavigating =
    navigation.state === 'loading'
    && pendingPathKey !== ''
    && pendingPathKey !== pathKey;

  useEffect(() => {
    navDebugHintOnce();
  }, []);

  useEffect(() => {
    navDebug('location', {
      pathname: location.pathname,
      search: location.search,
      navState: navigation.state,
      navLocation: navigation.location?.pathname,
    });
    navDebugDomSnapshot('location-change');
  }, [location.pathname, location.search, navigation.state, navigation.location?.pathname]);

  useEffect(() => {
    if (prevPathRef.current === location.pathname) return;
    navDebug('route commit', { from: prevPathRef.current || '(init)', to: location.pathname });
    prevPathRef.current = location.pathname;
    if (meta.clawCollapsedDefault) {
      setTweak('clawCollapsed', true);
    }
  }, [location.pathname, meta.clawCollapsedDefault, setTweak]);

  useEffect(() => {
    if (navigation.state !== 'loading') return;
    const target = navigation.location?.pathname ?? '?';
    navDebug('navigation loading', { from: location.pathname, to: target });
    const timer = window.setTimeout(() => {
      navDebugWarn('navigation still loading after 3s', {
        from: location.pathname,
        to: target,
        navState: navigation.state,
      });
      navDebugDomSnapshot('stale-3s');
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [navigation.state, navigation.location?.pathname, location.pathname]);

  return (
    <AppShell
      breadcrumbs={meta.breadcrumbs}
      withClaw
      clawRail={
        <ClawRail
          collapsed={tweaks.clawCollapsed}
          onToggle={() => setTweak('clawCollapsed', !tweaks.clawCollapsed)}
          width={tweaks.clawWidth}
          onResize={(w) => setTweak('clawWidth', w)}
          {...meta.clawProps}
        />
      }
    >
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden',
          position: 'relative',
        }}
        data-workspace-route={location.pathname}
        data-nav-state={navigation.state}
      >
        {isNavigating && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 20,
              display: 'grid',
              placeItems: 'center',
              background: 'rgba(248,250,252,0.72)',
              backdropFilter: 'blur(2px)',
              fontSize: 14,
              color: '#64748b',
              pointerEvents: 'none',
            }}
          >
            页面切换中…
          </div>
        )}
        <Suspense fallback={<PageSwitchFallback />}>
          <Outlet key={routeKey} />
        </Suspense>
      </div>
    </AppShell>
  );
}
