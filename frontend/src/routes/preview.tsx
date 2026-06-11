// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import PreviewScreen from '@/components/screens/preview';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function PreviewInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['早期接入 · 合同 + 预案三快照']}
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
      <PreviewScreen />
    </AppShell>
  );
}

export default function PreviewPage() {
  return (
    <TweaksProvider>
      <PreviewInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
