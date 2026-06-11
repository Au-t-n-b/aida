// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import ProposalScreen from '@/components/screens/proposal';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function ProposalInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['早期介入 · 交付预案']}
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
      <ProposalScreen />
    </AppShell>
  );
}

export default function ProposalPage() {
  return (
    <TweaksProvider>
      <ProposalInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
