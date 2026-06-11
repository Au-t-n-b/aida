import { PlanBoard } from './plan-board/plan-board';

/** 计划排期（计划调整）· 复用 PlanBoard 的 mode 机制（沿用源 C 写法，不另起一套）。 */
export default function PlanAdjustScreen() {
  return <PlanBoard mode="adjust" />;
}
