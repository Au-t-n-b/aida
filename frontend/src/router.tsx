import { lazy, type ComponentType } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { GuestOnly, RequireAuth, RequireProject, RootRedirect } from '@/lib/auth-guard';
import { TweaksProvider } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';
import WorkspaceShell from '@/routes/workspace-shell';
import LoginPage from '@/routes/login';
import LandingPage from '@/routes/landing';

/** 工作台子路由：同步 import，避免 lazy + React 19 在重页（交付预案）卸载时残留 DOM */
import CockpitPage from '@/routes/cockpit';
import DesignPage from '@/routes/design';
import TwinPage from '@/routes/twin';
import TwinDigitalDemoPage from '@/routes/twin-digital-demo';
import MilestonesPage from '@/routes/milestones';
import CommissioningPage from '@/routes/commissioning';
import SandboxPage from '@/routes/sandbox';
import ProposalPage from '@/routes/proposal';
import PreviewPage from '@/routes/preview';
import JourneyPage from '@/routes/journey';
import CreatePage from '@/routes/create';
import ModuleRoutePage from '@/routes/module';

/** 非工作台路由仍 lazy 加载 */
function lazyPage(loader: () => Promise<{ default: ComponentType }>) {
  return lazy(loader);
}

const AssetsPage = lazyPage(() => import('@/routes/assets'));
const ConfigPage = lazyPage(() => import('@/routes/config'));
const AdminPage = lazyPage(() => import('@/routes/admin'));
const PlanPage = lazyPage(() => import('@/routes/plan'));
const OnboardPage = lazyPage(() => import('@/routes/onboard'));
const EvalsPage = lazyPage(() => import('@/routes/evals'));
const ChatPage = lazyPage(() => import('@/routes/chat'));
const SduiPreviewPage = lazyPage(() => import('@/routes/sdui-preview'));
const RiskReportPage = lazyPage(() => import('@/features/schedule/components/risk-report'));

/** 项目空间 · 共享 LeftNav + ClawRail 壳层（ClawRail 不随子路由卸载） */
const workspaceLayout = (
  <RequireAuth>
    <TweaksProvider>
      <WorkspaceShell />
      <TweaksPanel />
    </TweaksProvider>
  </RequireAuth>
);

export const router = createBrowserRouter([
  { path: '/', element: <RootRedirect /> },
  {
    path: '/login',
    element: (
      <GuestOnly>
        <LoginPage />
      </GuestOnly>
    ),
  },
  {
    path: '/landing',
    element: (
      <RequireAuth>
        <LandingPage />
      </RequireAuth>
    ),
  },
  {
    element: workspaceLayout,
    children: [
      {
        path: '/cockpit',
        element: (
          <RequireProject>
            <CockpitPage />
          </RequireProject>
        ),
      },
      { path: '/design', element: <DesignPage /> },
      { path: '/twin', element: <TwinPage /> },
      { path: '/twin/digital-demo', element: <TwinDigitalDemoPage /> },
      { path: '/milestones', element: <MilestonesPage /> },
      { path: '/commissioning', element: <CommissioningPage /> },
      { path: '/sandbox', element: <SandboxPage /> },
      {
        path: '/proposal',
        element: (
          <RequireProject>
            <ProposalPage />
          </RequireProject>
        ),
      },
      {
        path: '/preview',
        element: (
          <RequireProject>
            <PreviewPage />
          </RequireProject>
        ),
      },
      { path: '/journey', element: <JourneyPage /> },
      { path: '/create', element: <CreatePage /> },
      { path: '/module/:key', element: <ModuleRoutePage /> },
    ],
  },
  { path: '/foundation', element: <Navigate to="/twin" replace /> },
  {
    path: '/assets',
    element: (
      <RequireAuth>
        <AssetsPage />
      </RequireAuth>
    ),
  },
  {
    path: '/config',
    element: (
      <RequireAuth>
        <ConfigPage />
      </RequireAuth>
    ),
  },
  {
    path: '/plan-init',
    element: (
      <RequireAuth>
        <Navigate to="/plan?stage=init" replace />
      </RequireAuth>
    ),
  },
  {
    path: '/plan-adjust',
    element: (
      <RequireAuth>
        <Navigate to="/plan?stage=adjust" replace />
      </RequireAuth>
    ),
  },
  {
    path: '/admin',
    element: (
      <RequireAuth>
        <AdminPage />
      </RequireAuth>
    ),
  },
  {
    path: '/plan',
    element: (
      <RequireAuth>
        <PlanPage />
      </RequireAuth>
    ),
  },
  {
    path: '/plan-risk-report',
    element: (
      <RequireAuth>
        <RiskReportPage />
      </RequireAuth>
    ),
  },
  {
    path: '/onboard',
    element: (
      <RequireAuth>
        <OnboardPage />
      </RequireAuth>
    ),
  },
  {
    path: '/evals',
    element: (
      <RequireAuth>
        <EvalsPage />
      </RequireAuth>
    ),
  },
  {
    path: '/chat',
    element: (
      <RequireAuth>
        <ChatPage />
      </RequireAuth>
    ),
  },
  {
    path: '/sdui-preview',
    element: (
      <RequireAuth>
        <SduiPreviewPage />
      </RequireAuth>
    ),
  },
  { path: '*', element: <RootRedirect /> },
]);
