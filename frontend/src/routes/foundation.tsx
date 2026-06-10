// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import FoundationScreen from '@/components/screens/foundation';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function FoundationInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['孪生世界 · K1903', '算力底座孪生']}
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
      <FoundationScreen />
    </AppShell>
  );
}

export default function FoundationPage() {
  return (
    <TweaksProvider>
      <FoundationInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
