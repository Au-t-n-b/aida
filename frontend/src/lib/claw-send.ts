/** ClawRail / AIDA 助手 · 统一发送指令（全页面共用） */

export const CLAW_SEND_EVENT = 'aida:send';
/** 右侧 skill 作业区 → 左侧 ClawRail 技能会话（直连 /agent/chat/stream）。
 *  与 CLAW_SEND_EVENT（走 manager 助手）区分，由 ClawRail 单独监听，避免双发。 */
export const RAIL_SEND_EVENT = 'aida:rail-send';
export const CLAW_REPLY_START_EVENT = 'aida:reply-start';
export const CLAW_REPLY_DELTA_EVENT = 'aida:reply-delta';
export const CLAW_REPLY_DONE_EVENT = 'aida:reply-done';
export const CLAW_REPLY_ERROR_EVENT = 'aida:reply-error';

export type ClawSendDetail = {
  text: string;
  pathname?: string;
  source?: string;
};

export type ClawReplyDetail = {
  id: string;
  body?: string;
  delta?: string;
  error?: string;
};

export function formatClawTimestamp(d = new Date()): string {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** 移除流式回复前的占位文案（历史兼容） */
export function stripReplyPlaceholder(body: string): string {
  return body.replace(/^正在连接 AIDA 容器[….]{0,2}/, '').trimStart();
}

/** 等待模型回复时左侧气泡展示的思考态文案 */
export const CLAW_REPLY_THINKING_TEXT = '....';

/** 统一发送入口：所有助手发送按钮均调用此函数 */
export function dispatchClawSend(text: string, extra: Partial<ClawSendDetail> = {}): boolean {
  const trimmed = text.trim();
  if (!trimmed || typeof window === 'undefined') return false;
  window.dispatchEvent(
    new CustomEvent<ClawSendDetail>(CLAW_SEND_EVENT, {
      detail: { text: trimmed, ...extra },
    }),
  );
  return true;
}

/** 右侧 skill 作业区向左侧 ClawRail 技能会话投递一条用户消息（如 3D 机房入口下钻）。 */
export function dispatchRailSend(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed || typeof window === 'undefined') return false;
  window.dispatchEvent(
    new CustomEvent<ClawSendDetail>(RAIL_SEND_EVENT, { detail: { text: trimmed } }),
  );
  return true;
}
