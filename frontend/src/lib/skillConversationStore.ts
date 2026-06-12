/**
 * skillConversationStore — 把 SDUI 的「AIDA 助手」会话流（id=sd-conversation）
 * 提升到左侧会话框渲染（对齐《系统设计工作台-周二版》左列 ConversationPane）。
 */
import { useSyncExternalStore } from 'react';
import type { SduiNode } from '@/lib/sdui';
import type { SduiRuntime } from '@/components/sdui/SduiContext';

export interface SkillConversationState {
  skillId: string;
  runId: string | null;
  node: SduiNode;
  runtime: SduiRuntime;
}

let _current: SkillConversationState | null = null;
const _subs = new Set<() => void>();

function _notify(): void {
  _subs.forEach(fn => fn());
}

export function setSkillConversation(state: SkillConversationState): void {
  _current = state;
  _notify();
}

export function clearSkillConversation(skillId?: string): void {
  if (!skillId || _current?.skillId === skillId) {
    if (_current === null) return;
    _current = null;
    _notify();
  }
}

export function useSkillConversationStore(): SkillConversationState | null {
  return useSyncExternalStore(
    (cb) => { _subs.add(cb); return () => { _subs.delete(cb); }; },
    () => _current,
  );
}
