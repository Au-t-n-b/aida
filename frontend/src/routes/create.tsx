// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import CreateScreen from '@/components/screens/create';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function CreateInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['项目创建向导', '5 字段 → OCC 审批 → 激活']}
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
      <CreateScreen />
    </AppShell>
  );
}

export default function CreatePage() {
  return (
    <TweaksProvider>
      <CreateInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
