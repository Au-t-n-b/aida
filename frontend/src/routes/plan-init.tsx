import { AppShell } from '@/components/app-shell';
import { TweaksProvider } from '@/lib/tweaks-context';
import PlanInitScreen from '@/components/screens/plan-init';

// 阶段一：独立新路由，与 jintao 的「计划」(/plan?view=plan) 并存、互不影响。
// 排期页自带 ScheduleClawRail —— 它在 PlanBoard 内随 .planinit 一起布局（沿用源 C 的
// `.planinit{display:flex}` > [.claw-rail 312px, .main flex:1] 设计），点「发送·开始初排」
// 派发 aida:claw-send 驱动推演。故不走 AppShell 的 clawRail 槽（B 的通用 Claw 不派发该事件，
// 且 C 的 claw 样式 scope 在 .planinit 内）；阶段三再收敛到统一 Claw。
export default function PlanInitPage() {
  return (
    <TweaksProvider>
      <AppShell breadcrumbs={['项目管理 · 计划排期（初始化）']}>
        <PlanInitScreen />
      </AppShell>
    </TweaksProvider>
  );
}
