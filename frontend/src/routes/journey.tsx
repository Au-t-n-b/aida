// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import JourneyScreen from '@/components/screens/journey';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function JourneyInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['项目全生命周期 · 故事线']}
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
      <JourneyScreen />
    </AppShell>
  );
}

export default function JourneyPage() {
  return (
    <TweaksProvider>
      <JourneyInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
