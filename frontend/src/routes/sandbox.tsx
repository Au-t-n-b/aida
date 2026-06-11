// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import SandboxScreen from '@/components/screens/sandbox';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function SandboxInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['AI 推演沙箱']}
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
      <SandboxScreen />
    </AppShell>
  );
}

export default function SandboxPage() {
  return (
    <TweaksProvider>
      <SandboxInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
