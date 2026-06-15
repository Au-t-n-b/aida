// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import PlanScreen from '@/components/screens/plan';
import PlanScheduleScreen from '@/features/schedule/components/plan-schedule';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';
import { useLocation } from 'react-router-dom';

function LegacyPlanInner() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <AppShell
      breadcrumbs={['项目管理 · 人货站融合']}
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
      <PlanScreen />
    </AppShell>
  );
}

function SchedulePlanInner({ legacyStage }: { legacyStage?: 'init' | 'adjust' }) {
  return (
    <AppShell breadcrumbs={['项目管理 · 计划排期']}>
      <PlanScheduleScreen legacyStage={legacyStage} />
    </AppShell>
  );
}

export default function PlanPage() {
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const isLegacyPlanView = params.has('view');
  const stageParam = params.get('stage');
  const legacyStage = stageParam === 'init' || stageParam === 'adjust' ? stageParam : undefined;

  return (
    <TweaksProvider>
      {isLegacyPlanView ? (
        <>
          <LegacyPlanInner />
          <TweaksPanel />
        </>
      ) : (
        <SchedulePlanInner legacyStage={legacyStage} />
      )}
    </TweaksProvider>
  );
}
