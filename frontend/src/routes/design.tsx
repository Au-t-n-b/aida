// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import DesignScreen from '@/components/screens/design';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function DesignInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['交付方案 · LLD 主版本']}
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
      <DesignScreen />
    </AppShell>
  );
}

export default function DesignPage() {
  return (
    <TweaksProvider>
      <DesignInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
