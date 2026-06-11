import { AppShell } from '@/components/app-shell';
import ClawRail from '@/components/claw-rail';
import { SurveyTwinViewer } from '@/components/twin/survey-twin/survey-twin-viewer';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

function TwinSurveyInner() {
  const { tweaks, setTweak } = useTweaks();

  return (
    <AppShell
      breadcrumbs={['孪生世界', '工勘孪生 · 通道1']}
      withClaw
      clawRail={
        <ClawRail
          collapsed={tweaks.clawCollapsed}
          onToggle={() => setTweak('clawCollapsed', !tweaks.clawCollapsed)}
          width={tweaks.clawWidth}
          onResize={(w: number) => setTweak('clawWidth', w)}
        />
      }
    >
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <SurveyTwinViewer />
      </div>
    </AppShell>
  );
}

export default function TwinSurveyPage() {
  return (
    <TweaksProvider overrides={{ clawCollapsed: true }}>
      <TwinSurveyInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
