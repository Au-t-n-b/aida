// @ts-nocheck
import { useState } from 'react';
import { AppShell } from '@/components/app-shell';
import DashboardScreen from '@/components/screens/dashboard';
import ClawRail from '@/components/claw-rail';
import { useCurrentProject } from '@/lib/current-project';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function CockpitInner() {
  const { tweaks, setTweak } = useTweaks();
  const { project } = useCurrentProject();
  const projectLabel = project ? `${project.name} · ${project.id}` : '项目孪生';

  return (
    <AppShell
      breadcrumbs={[`项目孪生 · ${projectLabel}`]}
      withClaw
      clawRail={
        <ClawRail
          collapsed={tweaks.clawCollapsed}
          onToggle={() => setTweak('clawCollapsed', !tweaks.clawCollapsed)}
          width={tweaks.clawWidth}
          onResize={w => setTweak('clawWidth', w)}
        />
      }
    >
      <DashboardScreen />
    </AppShell>
  );
}

export default function CockpitPage() {
  return (
    // 孪生世界分组：进入时 LLM 对话框默认收起（与 /twin、/twin/survey 一致）
    <TweaksProvider overrides={{ clawCollapsed: true }}>
      <CockpitInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
