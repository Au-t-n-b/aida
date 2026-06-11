// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import MilestonesScreen from '@/components/screens/milestones';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function MilestonesInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['项目孪生 · K1903', 'PoD 级里程碑']}
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
      <MilestonesScreen />
    </AppShell>
  );
}

export default function MilestonesPage() {
  return (
    <TweaksProvider>
      <MilestonesInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
