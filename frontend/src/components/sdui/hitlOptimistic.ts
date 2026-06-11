/**
 * HITL 乐观确认态 store（模块级）
 *
 * 背景：用户在 ChoiceCard 选定 / FilePicker 上传后，parent(SkillAgentScreen) 会冻结
 * 旧 SDUI 快照以避免 full_restart 重放期间闪回 0%。但冻结=用旧节点重新渲染 →
 * HITL 组件**重新挂载**，其本地 submitted/success 态丢失 → 卡片闪回「未选 / 未传」。
 *
 * 解法：把「已选什么 / 已传哪些」写进本 store（按 `${runId}:${stepId}` 键），组件
 * 挂载时回读 → 跨重挂载保住确认态，直到流程推进、卡片真正卸载。带 TTL 自动过期，
 * 避免下一轮（如复勘再进 wait_survey）误显示上一轮的旧确认。
 */
export type HitlOptimistic =
  | { kind: 'choice'; selected: string }
  | { kind: 'file'; names: string[] };

interface Entry { value: HitlOptimistic; ts: number }

const store = new Map<string, Entry>();
const TTL_MS = 8000;

export function hitlKey(runId: string | null | undefined, stepId: string | undefined): string {
  return `${runId ?? '-'}:${stepId ?? '-'}`;
}

export function setHitlOptimistic(key: string, value: HitlOptimistic): void {
  store.set(key, { value, ts: Date.now() });
}

export function getHitlOptimistic(key: string): HitlOptimistic | null {
  const e = store.get(key);
  if (!e) return null;
  if (Date.now() - e.ts > TTL_MS) {
    store.delete(key);
    return null;
  }
  return e.value;
}

/** HITL 推进前的最小确认可见时长：先稳定显示确认态，再触发后端 resume。 */
export const HITL_HOLD_MS = 1000;
