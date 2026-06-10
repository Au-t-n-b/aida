import { createBrowserRouter, Navigate } from 'react-router-dom';
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
  { path: '/', element: <Navigate to="/cockpit" replace /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/landing', element: <LandingPage /> },
  { path: '/cockpit', element: <CockpitPage /> },
  { path: '/assets', element: <AssetsPage /> },
  { path: '/config', element: <ConfigPage /> },
  { path: '/design', element: <DesignPage /> },
  { path: '/twin', element: <TwinPage /> },
  { path: '/twin/survey', element: <TwinSurveyPage /> },
  { path: '/foundation', element: <Navigate to="/twin" replace /> },
  { path: '/plan-init', element: <PlanInitPage /> },
  { path: '/plan-adjust', element: <PlanAdjustPage /> },
  { path: '/milestones', element: <MilestonesPage /> },
  { path: '/admin', element: <AdminPage /> },
  { path: '/commissioning', element: <CommissioningPage /> },
  { path: '/sandbox', element: <SandboxPage /> },
  { path: '/proposal', element: <ProposalPage /> },
  { path: '/preview', element: <PreviewPage /> },
  { path: '/plan', element: <PlanPage /> },
  { path: '/onboard', element: <OnboardPage /> },
  { path: '/journey', element: <JourneyPage /> },
  { path: '/create', element: <CreatePage /> },
  { path: '/evals', element: <EvalsPage /> },
  { path: '/chat', element: <ChatPage /> },
  { path: '/sdui-preview', element: <SduiPreviewPage /> },
  { path: '/module/:key', element: <ModuleRoutePage /> },
  { path: '*', element: <Navigate to="/cockpit" replace /> },
]);
