/**
 * skillRunStore — 跨组件共享当前运行中的 Skill run 状态
 *
 * 使用场景：
 *   聊天侧 SkillRunBanner（chat 触发）调 /start → setSkillRun('chat')
 *   模块页 SkillAgentScreen 点启动按钮   → setSkillRun('ui')
 *     → ClawRail 监听到 source='ui' → 自动注入左侧进度卡消息
 *
 *   survey-agent.tsx 订阅 sduiDoc 变化 → extractProgressFromSdui → updateSkillRun()
 *   SkillRunBanner 只读 store，不开独立 SSE，进度由右侧 SDUI 流驱动。
 *
 * 实现：纯 module-level 单例 + useSyncExternalStore（React 18+，无额外依赖）。
 */
import { useSyncExternalStore } from 'react';

export interface SkillRunInfo {
  skillId: string;
  runId: string;
  /** 启动来源：chat = 从左侧会话触发；ui = 从右侧模块页触发 */
  source: 'chat' | 'ui';
  /** 运行阶段 */
  phase: 'starting' | 'running' | 'hitl' | 'done' | 'error';
  /** 整体进度 0–100（由 survey-agent.tsx 从 SDUI 文档解析后写入）*/
  progress: number;
  /** 当前步骤显示名（用于左侧卡展示）*/
  currentStepName: string;
  /** HITL 类型（左侧卡仅提示「去右侧面板操作」，完整 HITL UI 在右侧 SDUI）。
   *  edit = 在线填表（route_hitl_edit 契约，表格在右侧大盘提交）。*/
  hitlType: 'file' | 'choice' | 'edit' | null;
  /** 错误信息（简短，用于左侧卡展示）*/
  errorMsg: string;
}

// ── 模块级单例状态 ─────────────────────────────────────────────────────────────
let _current: SkillRunInfo | null = null;
const _subs = new Set<() => void>();

function _notify(): void {
  _subs.forEach(fn => fn());
}

// ── 写 API ────────────────────────────────────────────────────────────────────

/**
 * 记录新的 skill run。
 * source='ui'   → ClawRail 监听后在左侧注入 SkillRunBanner 消息（右侧启动场景）
 * source='chat' → 聊天 skill_launch 已渲染卡，ClawRail 跳过注入（避免重复）
 */
export function setSkillRun(
  skillId: string,
  runId: string,
  source: 'chat' | 'ui' = 'ui',
): void {
  _current = {
    skillId, runId, source,
    phase: 'starting',
    progress: 0,
    currentStepName: '',
    hitlType: null,
    errorMsg: '',
  };
  _notify();
}

/**
 * 更新当前 run 的进度信息（不改变 skillId / runId / source）。
 * 由 survey-agent.tsx 在 sduiDoc 变化时调用，SkillRunBanner 即时反映。
 */
export function updateSkillRun(
  patch: Partial<Omit<SkillRunInfo, 'skillId' | 'runId' | 'source'>>,
): void {
  if (!_current) return;
  _current = { ..._current, ...patch };
  _notify();
}

/**
 * 清除当前 run 记录（skill 运行完成 / 重置时调用）。
 * 可选 skillId 参数：只清除对应 skill 的记录，避免误清其他 skill。
 */
export function clearSkillRun(skillId?: string): void {
  if (!skillId || _current?.skillId === skillId) {
    _current = null;
    _notify();
  }
}

// ── 读 API（React hook）───────────────────────────────────────────────────────

export function useSkillRunStore(): SkillRunInfo | null {
  return useSyncExternalStore(
    (cb) => { _subs.add(cb); return () => { _subs.delete(cb); }; },
    () => _current,
  );
}
