/**
 * skillStepFeed — 部署调测等 Skill 在左侧会话按节点逐步「发卡」
 *
 * survey-agent 检测 SDUI 当前步骤变化 → emitSkillStep / emitSkillStepDone
 * ClawRail 监听后往 appendMsgs 追加/更新气泡，每步一张卡（非单框替换）。
 */
import type { SduiDocument, SduiNode, SduiFlowStepCard } from '@/lib/sdui';
import { walkSduiNodes } from '@/lib/sdui';

export type SkillStepPhase = 'running' | 'hitl';

export interface WorkflowStepSnap {
  stepKey: string;
  stepTitle: string;
  stepNum: number;
  phase: SkillStepPhase;
}

export interface SkillStepMsg {
  skillId: string;
  runId: string;
  stepKey: string;
  stepTitle: string;
  stepNum: number;
  phase: SkillStepPhase;
  status: 'active' | 'done' | 'failed';
  /** 失败时展示在左侧步骤卡上的原因摘要 */
  errorMessage?: string;
}

/** 左侧步骤卡「重试本步」→ 右侧 survey-agent.handleAction */
export const SD_ACTION_EVENT = 'aida:sd-action';

export function dispatchSdAction(action: { kind: 'post_user_message'; text: string }): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(SD_ACTION_EVENT, { detail: action }));
}

function nowTs(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** 从 SDUI 提取当前流程节点（FlowSteps + HITL 优先）。*/
export function extractWorkflowStep(doc: SduiDocument): WorkflowStepSnap | null {
  let steps: SduiFlowStepCard[] = [];
  let hitlStepKey = '';
  let hasHitl = false;

  walkSduiNodes(doc.root, (node) => {
    if (node.type === 'FlowSteps' && steps.length === 0) steps = node.steps;
    if (
      node.type === 'ChoiceCard'
      || node.type === 'FilePicker'
      || node.type === 'HitlTextInput'
      || node.type === 'HitlForm'
    ) {
      hasHitl = true;
      const raw = node as { stepId?: string; hitlRequestId?: string; purpose?: string };
      hitlStepKey = String(raw.stepId || raw.hitlRequestId || raw.purpose || '').trim();
    }
    if (node.type === 'DataTable' && node.editable && (node.submitMode ?? 'resume') === 'resume') {
      hasHitl = true;
      hitlStepKey = String(node.stepId || 'edit').trim();
    }
  });

  const current = steps.find(s => s.status === 'current');
  if (hasHitl) {
    if (hitlStepKey === 'commission_scope') {
      return {
        stepKey: 'commission_scope',
        stepTitle: '设备范围确认',
        stepNum: 0,
        phase: 'hitl',
      };
    }
    const flowStepKey = hitlStepKey || String(current?.stepKey || current?.id || 'hitl');
    return {
      stepKey: flowStepKey,
      stepTitle: current?.title ?? (hitlStepKey === 'commission_scope' ? '设备范围确认' : '待确认'),
      stepNum: current?.num ?? 0,
      phase: 'hitl',
    };
  }
  if (current) {
    return {
      stepKey: String(current.stepKey || current.id),
      stepTitle: current.title,
      stepNum: current.num,
      phase: 'running',
    };
  }
  return null;
}

export function emitSkillStep(payload: Omit<SkillStepMsg, 'status'>): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('aida:skill-step', {
    detail: { ...payload, status: 'active' as const, ts: nowTs() },
  }));
}

export function emitSkillStepDone(skillId: string, stepKey: string): void {
  if (typeof window === 'undefined' || !stepKey) return;
  window.dispatchEvent(new CustomEvent('aida:skill-step-done', {
    detail: { skillId, stepKey, ts: nowTs() },
  }));
}

export function emitSkillStepFailed(
  skillId: string,
  stepKey: string,
  errorMessage?: string,
): void {
  if (typeof window === 'undefined' || !stepKey) return;
  window.dispatchEvent(new CustomEvent('aida:skill-step-failed', {
    detail: { skillId, stepKey, errorMessage: errorMessage?.trim() || '', ts: nowTs() },
  }));
}

/** 从 hitl-card 子树解析 stepKey（写入 skillHitlStore 供左栏卡对齐）。*/
export function extractHitlStepKey(card: SduiNode): string {
  let key = '';
  walkSduiNodes(card, (node) => {
    if (key) return;
    if (
      node.type === 'ChoiceCard'
      || node.type === 'FilePicker'
      || node.type === 'HitlTextInput'
      || node.type === 'HitlForm'
    ) {
      const raw = node as { stepId?: string; hitlRequestId?: string; purpose?: string };
      key = String(raw.stepId || raw.hitlRequestId || raw.purpose || '').trim();
    }
  });
  return key;
}
