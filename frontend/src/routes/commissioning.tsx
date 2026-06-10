// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import CommissioningScreen from '@/components/screens/commissioning';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function CommissioningInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['调测中心 · K1903']}
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
      <CommissioningScreen />
    </AppShell>
  );
}

export default function CommissioningPage() {
  return (
    <TweaksProvider>
      <CommissioningInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
