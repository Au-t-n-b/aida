// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import DashboardScreen from '@/components/screens/dashboard';
import { useCurrentProject } from '@/lib/current-project';
import { TweaksProvider } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function CockpitInner() {
  const { project } = useCurrentProject();
  const projectLabel = project ? `${project.name} · ${project.id}` : '项目孪生';

  return (
    <AppShell breadcrumbs={[`项目孪生 · ${projectLabel}`]}>
      <DashboardScreen />
    </AppShell>
  );
}

export default function CockpitPage() {
  // 项目孪生页不展示 LLM 对话框（移除 ClawRail）
  return (
    <TweaksProvider overrides={{ clawCollapsed: true }}>
      <CockpitInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
