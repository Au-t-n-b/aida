import { lazy, Suspense, type ComponentType } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { GuestOnly, RequireAuth, RequireProject, RootRedirect } from '@/lib/auth-guard';
import LoginPage from '@/routes/login';
import LandingPage from '@/routes/landing';

function lazyPage(loader: () => Promise<{ default: ComponentType }>) {
  const Lazy = lazy(loader);
  return function LazyPage() {
    return (
      <Suspense fallback={<div style={{ padding: 32, color: '#64748b', fontSize: 14 }}>页面加载中…</div>}>
        <Lazy />
      </Suspense>
    );
  };
}

const CockpitPage = lazyPage(() => import('@/routes/cockpit'));
const AssetsPage = lazyPage(() => import('@/routes/assets'));
const ConfigPage = lazyPage(() => import('@/routes/config'));
const DesignPage = lazyPage(() => import('@/routes/design'));
const TwinPage = lazyPage(() => import('@/routes/twin'));
const TwinDigitalDemoPage = lazyPage(() => import('@/routes/twin-digital-demo'));
const MilestonesPage = lazyPage(() => import('@/routes/milestones'));
const AdminPage = lazyPage(() => import('@/routes/admin'));
const CommissioningPage = lazyPage(() => import('@/routes/commissioning'));
const SandboxPage = lazyPage(() => import('@/routes/sandbox'));
const ProposalPage = lazyPage(() => import('@/routes/proposal'));
const PreviewPage = lazyPage(() => import('@/routes/preview'));
const PlanPage = lazyPage(() => import('@/routes/plan'));
const OnboardPage = lazyPage(() => import('@/routes/onboard'));
const JourneyPage = lazyPage(() => import('@/routes/journey'));
const CreatePage = lazyPage(() => import('@/routes/create'));
const ModuleRoutePage = lazyPage(() => import('@/routes/module'));
const EvalsPage = lazyPage(() => import('@/routes/evals'));
const ChatPage = lazyPage(() => import('@/routes/chat'));
const SduiPreviewPage = lazyPage(() => import('@/routes/sdui-preview'));
const RiskReportPage = lazyPage(() => import('@/features/schedule/components/risk-report'));

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
    path: '/cockpit',
    element: (
      <RequireAuth>
        <RequireProject>
          <CockpitPage />
        </RequireProject>
      </RequireAuth>
    ),
  },
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
    path: '/design',
    element: (
      <RequireAuth>
        <DesignPage />
      </RequireAuth>
    ),
  },
  {
    path: '/twin',
    element: (
      <RequireAuth>
        <TwinPage />
      </RequireAuth>
    ),
  },
  {
    path: '/twin/digital-demo',
    element: (
      <RequireAuth>
        <TwinDigitalDemoPage />
      </RequireAuth>
    ),
  },
  { path: '/foundation', element: <Navigate to="/twin" replace /> },
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
    path: '/milestones',
    element: (
      <RequireAuth>
        <MilestonesPage />
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
    path: '/commissioning',
    element: (
      <RequireAuth>
        <CommissioningPage />
      </RequireAuth>
    ),
  },
  {
    path: '/sandbox',
    element: (
      <RequireAuth>
        <SandboxPage />
      </RequireAuth>
    ),
  },
  {
    path: '/proposal',
    element: (
      <RequireAuth>
        <ProposalPage />
      </RequireAuth>
    ),
  },
  {
    path: '/preview',
    element: (
      <RequireAuth>
        <PreviewPage />
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
    path: '/journey',
    element: (
      <RequireAuth>
        <JourneyPage />
      </RequireAuth>
    ),
  },
  {
    path: '/create',
    element: (
      <RequireAuth>
        <CreatePage />
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
  {
    path: '/module/:key',
    element: (
      <RequireAuth>
        <ModuleRoutePage />
      </RequireAuth>
    ),
  },
  { path: '*', element: <RootRedirect /> },
]);
