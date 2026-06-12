import { createBrowserRouter, Navigate } from 'react-router-dom';
import { GuestOnly, RequireAuth, RequireProject, RootRedirect } from '@/lib/auth-guard';
import LoginPage from '@/routes/login';
import LandingPage from '@/routes/landing';
import CockpitPage from '@/routes/cockpit';
import AssetsPage from '@/routes/assets';
import ConfigPage from '@/routes/config';
import DesignPage from '@/routes/design';
import TwinPage from '@/routes/twin';
import TwinSurveyPage from '@/routes/twin-survey';
import PlanInitPage from '@/routes/plan-init';
import PlanAdjustPage from '@/routes/plan-adjust';
import MilestonesPage from '@/routes/milestones';
import AdminPage from '@/routes/admin';
import CommissioningPage from '@/routes/commissioning';
import SandboxPage from '@/routes/sandbox';
import ProposalPage from '@/routes/proposal';
import PreviewPage from '@/routes/preview';
import PlanPage from '@/routes/plan';
import OnboardPage from '@/routes/onboard';
import JourneyPage from '@/routes/journey';
import CreatePage from '@/routes/create';
import ModuleRoutePage from '@/routes/module';
import EvalsPage from '@/routes/evals';
import ChatPage from '@/routes/chat';
import SduiPreviewPage from '@/routes/sdui-preview';

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
    path: '/twin/survey',
    element: (
      <RequireAuth>
        <TwinSurveyPage />
      </RequireAuth>
    ),
  },
  { path: '/foundation', element: <Navigate to="/twin" replace /> },
  {
    path: '/plan-init',
    element: (
      <RequireAuth>
        <PlanInitPage />
      </RequireAuth>
    ),
  },
  {
    path: '/plan-adjust',
    element: (
      <RequireAuth>
        <PlanAdjustPage />
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
