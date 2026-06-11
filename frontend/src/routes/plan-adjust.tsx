import { AppShell } from '@/components/app-shell';
import { TweaksProvider } from '@/lib/tweaks-context';
import PlanAdjustScreen from '@/components/screens/plan-adjust';

// 阶段一：独立新路由，与 jintao 的「计划」(/plan?view=plan) 并存（claw 布局说明见 plan-init.tsx）。
export default function PlanAdjustPage() {
  return (
    <TweaksProvider>
      <AppShell breadcrumbs={['项目管理 · 计划排期（计划调整）']}>
        <PlanAdjustScreen />
      </AppShell>
    </TweaksProvider>
  );
}
