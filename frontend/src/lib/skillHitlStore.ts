/**
 * skillHitlStore — 把当前待交互的 HITL 卡「提升」到左侧会话框
 *
 * 背景：HITL 的 ChoiceCard / FilePicker 原本只在右侧 SkillAgentScreen 的 SDUI 里渲染。
 * 产品希望交互卡出现在左侧会话框（更顺手）。但左侧 ClawRail 与右侧 SkillAgentScreen
 * 是 AppShell 下的两棵独立组件树，无法共享 React Context。
 *
 * 方案：module 级单例 store（与 skillRunStore 同构）——
 *   · SkillAgentScreen 从 sduiDoc 抽出 hitl-card 节点 + 暴露 resume 回调 → setSkillHitl()
 *   · 左侧 SkillRunBanner 读 store，用一个本地 SduiRuntimeContext.Provider 复用同一套
 *     SduiNodeView 渲染那张卡，回调直连 store 里的 onChoiceSubmit / onUpload。
 *   · 右侧 SkillAgentScreen strip hitl-card + 顶部轻量引导条，交互在左侧会话框。
 *
 * 存函数到单例只是「持有最新回调引用」，SkillAgentScreen 在回调变化时刷新即可。
 */
import { useSyncExternalStore } from 'react';
import type { SduiNode } from '@/lib/sdui';

export interface SkillHitlState {
  skillId: string;
  runId: string | null;
  /** 待交互的 HITL 卡节点（通常是 id=hitl-card 的 Card，内含 ChoiceCard / FilePicker）。*/
  node: SduiNode;
  /** ChoiceCard 提交回调（直连 SkillAgentScreen.handleChoiceSubmit → resume）。*/
  onChoiceSubmit: (value: string, stepId?: string) => void;
  /** HitlForm 提交回调（直连 SkillAgentScreen.handleFormSubmit → resume）。*/
  onFormSubmit?: (payload: Record<string, unknown>, stepId?: string) => void;
  /** FilePicker 上传回调（直连 SkillAgentScreen.handleUpload → resume）。*/
  onUpload: (files: FileList, purpose: string, stepId?: string) => void;
}

let _current: SkillHitlState | null = null;
const _subs = new Set<() => void>();

function _notify(): void {
  _subs.forEach(fn => fn());
}

/** 写入/更新当前 HITL（SkillAgentScreen 在 sduiDoc 出现 HITL 节点时调用）。*/
export function setSkillHitl(state: SkillHitlState): void {
  _current = state;
  _notify();
}

/** 清除当前 HITL（HITL 已解决 / run 结束 / 组件卸载时调用）。
 * 传 skillId 时只清自己的，避免误清其它 skill。*/
export function clearSkillHitl(skillId?: string): void {
  if (!skillId || _current?.skillId === skillId) {
    if (_current === null) return;
    _current = null;
    _notify();
  }
}

export function useSkillHitlStore(): SkillHitlState | null {
  return useSyncExternalStore(
    (cb) => { _subs.add(cb); return () => { _subs.delete(cb); }; },
    () => _current,
  );
}
