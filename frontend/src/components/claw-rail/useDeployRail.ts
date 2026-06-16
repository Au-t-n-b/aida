/**
 * useDeployRail — 部署调测（software_deployment）左侧对话轨的「可插拔扩展」
 *
 * 设计目标：ClawRail 是全模块共用的公共组件，本钩子把 deploy 专属的左栏逻辑
 * （按节点逐步发卡、命令调测 HITL 投影、自然语言调度指令拦截）整体收敛到此，
 * ClawRail 仅在 /module/deploy 下消费它，其它模块零感知、走公共线路。
 *
 * 数据来源全部是 window 事件 + module 级 store（与右侧 SkillAgentScreen 解耦）：
 *   · 'aida:skill-step' / '-done' / '-failed' → 步骤卡（SdSkillStepCard）
 *   · parseCommissionIntent                   → 把左栏自然语言转成 'aida:commission' 意图
 */
import { useCallback, useEffect, useState } from 'react';
import type { SkillStepMsg } from '@/lib/skillStepFeed';
import { useSkillRunStore } from '@/lib/skillRunStore';
import { parseCommissionIntent } from '@/lib/commissionCommands';

const DEPLOY_PATH = '/module/deploy';

interface SkillStepEvent {
  skillId: string;
  runId: string;
  stepKey: string;
  stepTitle: string;
  stepNum: number;
  phase: SkillStepMsg['phase'];
}

export interface DeployRailState {
  /** 当前是否处于部署调测模块（其它模块为 false，调用方应整体跳过 deploy 渲染）。*/
  enabled: boolean;
  /** 按节点逐步累积的步骤卡列表（执行中 / 待确认 / 已完成 / 失败）。*/
  stepMsgs: SkillStepMsg[];
  /**
   * 发送拦截：若文本是 deploy 调度意图（开始调测 / 执行某命令），
   * 派发 'aida:commission' 事件交右侧 SkillAgentScreen 处理，返回 true 表示已消费。
   */
  interceptSend: (text: string) => boolean;
}

function upsertStep(list: SkillStepMsg[], ev: SkillStepEvent): SkillStepMsg[] {
  // 新的 active 步骤到达：把之前仍 active 的步骤收敛为 done（防止多张卡同时转圈）。
  const next = list.map(m =>
    m.status === 'active' && m.stepKey !== ev.stepKey ? { ...m, status: 'done' as const } : m,
  );
  const idx = next.findIndex(m => m.stepKey === ev.stepKey);
  const card: SkillStepMsg = {
    skillId: ev.skillId,
    runId: ev.runId,
    stepKey: ev.stepKey,
    stepTitle: ev.stepTitle,
    stepNum: ev.stepNum,
    phase: ev.phase,
    status: 'active',
  };
  if (idx >= 0) {
    next[idx] = { ...next[idx]!, ...card };
    return next;
  }
  return [...next, card];
}

export function useDeployRail(pathname: string): DeployRailState {
  const enabled = pathname.includes(DEPLOY_PATH);
  const [stepMsgs, setStepMsgs] = useState<SkillStepMsg[]>([]);

  // 进度 store —— 仅 deploy 路径下消费
  const skillRun = useSkillRunStore();

  // 离开 deploy 模块即清空本地步骤卡，避免切回来残留上一轮
  useEffect(() => {
    if (!enabled) setStepMsgs([]);
  }, [enabled]);

  // 项目重置（survey-agent 派发 aida:clear）时清空步骤卡，避免步骤 9 等历史卡残留
  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;
    const onClear = () => setStepMsgs([]);
    window.addEventListener('aida:clear', onClear);
    return () => window.removeEventListener('aida:clear', onClear);
  }, [enabled]);

  // run 切换 / 重置（runId 清空）时丢弃上一轮步骤卡
  const activeRunId = skillRun?.skillId === 'software_deployment' ? skillRun.runId : null;
  useEffect(() => {
    if (!enabled) return;
    if (!activeRunId) {
      setStepMsgs([]);
      return;
    }
    setStepMsgs(prev => {
      if (!prev.length) return prev;
      return prev.filter(m => !m.runId || m.runId === activeRunId);
    });
  }, [enabled, activeRunId]);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;

    const onStep = (e: Event) => {
      const d = (e as CustomEvent<SkillStepEvent>).detail;
      if (!d?.stepKey) return;
      setStepMsgs(prev => upsertStep(prev, d));
    };
    const onDone = (e: Event) => {
      const d = (e as CustomEvent<{ skillId: string; stepKey: string }>).detail;
      if (!d?.stepKey) return;
      setStepMsgs(prev => prev.map(m =>
        m.stepKey === d.stepKey ? { ...m, status: 'done' as const } : m,
      ));
    };
    const onFailed = (e: Event) => {
      const d = (e as CustomEvent<{ skillId: string; stepKey: string; errorMessage?: string }>).detail;
      if (!d?.stepKey) return;
      setStepMsgs(prev => prev.map(m =>
        m.stepKey === d.stepKey
          ? { ...m, status: 'failed' as const, errorMessage: d.errorMessage }
          : m,
      ));
    };

    window.addEventListener('aida:skill-step', onStep);
    window.addEventListener('aida:skill-step-done', onDone);
    window.addEventListener('aida:skill-step-failed', onFailed);
    return () => {
      window.removeEventListener('aida:skill-step', onStep);
      window.removeEventListener('aida:skill-step-done', onDone);
      window.removeEventListener('aida:skill-step-failed', onFailed);
    };
  }, [enabled]);

  const interceptSend = useCallback((text: string): boolean => {
    if (!enabled) return false;
    const intent = parseCommissionIntent(text);
    if (!intent) return false;
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('aida:commission', { detail: intent }));
    }
    return true;
  }, [enabled]);

  return { enabled, stepMsgs, interceptSend };
}
