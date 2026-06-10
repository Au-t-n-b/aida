// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import PlanScreen from '@/components/screens/plan';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function PlanInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['项目管理 · 人货站融合']}
      withClaw
      clawRail={
        <ClawRail
          collapsed={tweaks.clawCollapsed}
          onToggle={() => setTweak('clawCollapsed', !tweaks.clawCollapsed)}
          width={tweaks.clawWidth}
          onResize={(w) => setTweak('clawWidth', w)}
        />
      }
    >
      <PlanScreen />
    </AppShell>
  );
}

export default function PlanPage() {
  return (
    <TweaksProvider>
      <PlanInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
