/**
 * useChatStream — POST SSE 会话流 hook。
 *
 * EventSource 不支持 POST，因此用 fetch + ReadableStream 手工解析 SSE 帧。
 * 事件类型对应 chat_engine.run_chat_async 的 yield：
 *   token / tool_call / tool_result / skill_launch / choices / heartbeat / done / error
 */
import { useCallback, useRef, useState } from 'react';

const AGENT_BASE = import.meta.env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';

// ── 消息类型 ─────────────────────────────────────────────────────────────────

export type MessageRole = 'user' | 'assistant';

export interface ToolCallInfo {
  name: string;
  args: Record<string, unknown>;
  result?: string;
}

export interface ChoicesInfo {
  question: string;
  options: Array<{ label: string; value?: string; desc?: string }>;
}

export interface SkillLaunchInfo {
  skill: string;
  run_id: string;
  project_code: string;
  scenario_run: string;
  project_name: string;
  steps: string[];
}

export interface ToolApprovalInfo {
  approval_id: string;
  name: string;
  args: Record<string, unknown>;
  decided?: 'approved' | 'denied';
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  toolCalls?: ToolCallInfo[];
  choices?: ChoicesInfo;
  skillLaunch?: SkillLaunchInfo;
  pendingApproval?: ToolApprovalInfo;
  isStreaming?: boolean;
}

export interface SendOptions {
  convId?: string;
  context?: Record<string, string>;
}

export interface ChatStreamState {
  messages: ChatMessage[];
  isLoading: boolean;
  skillLaunch: SkillLaunchInfo | null;
  error: string | null;
}

// ── SSE 帧解析 ───────────────────────────────────────────────────────────────

function parseSseFrame(raw: string): Array<{ event: string; data: string }> {
  const frames: Array<{ event: string; data: string }> = [];
  const blocks = raw.split(/\n\n/);
  for (const block of blocks) {
    if (!block.trim()) continue;
    let event = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trim();
    }
    if (data) frames.push({ event, data });
  }
  return frames;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useChatStream() {
  const [state, setState] = useState<ChatStreamState>({
    messages: [],
    isLoading: false,
    skillLaunch: null,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  // 用 ref 存当前 AI 消息 id，避免闭包过期
  const aiMsgIdRef = useRef<string>('');

  const send = useCallback(async (userText: string, opts: SendOptions = {}) => {
    // 取消上一次未完成的请求
    abortRef.current?.abort();
    const abort = new AbortController();
    abortRef.current = abort;

    const userId = `u-${Date.now()}`;
    const aiId = `a-${Date.now()}`;
    aiMsgIdRef.current = aiId;

    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      messages: [
        ...prev.messages,
        { id: userId, role: 'user', text: userText },
        { id: aiId, role: 'assistant', text: '', isStreaming: true },
      ],
    }));

    try {
      const res = await fetch(`${AGENT_BASE}/agent/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userText,
          conv_id: opts.convId ?? '',
          context: opts.context ?? {},
        }),
        signal: abort.signal,
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        // 每次积累到完整帧（以 \n\n 分隔）才处理
        const cut = buf.lastIndexOf('\n\n');
        if (cut === -1) continue;
        const chunk = buf.slice(0, cut + 2);
        buf = buf.slice(cut + 2);

        for (const frame of parseSseFrame(chunk)) {
          if (frame.event === 'heartbeat') continue;

          let ev: Record<string, unknown>;
          try {
            ev = JSON.parse(frame.data) as Record<string, unknown>;
          } catch {
            continue;
          }

          const type = ev.type as string | undefined;
          const currentAiId = aiMsgIdRef.current;

          if (type === 'token') {
            const text = (ev.text as string) ?? '';
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(m =>
                m.id === currentAiId ? { ...m, text: m.text + text } : m,
              ),
            }));
          } else if (type === 'tool_call') {
            const tc: ToolCallInfo = {
              name: (ev.name as string) ?? '',
              args: (ev.args as Record<string, unknown>) ?? {},
            };
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(m =>
                m.id === currentAiId
                  ? { ...m, toolCalls: [...(m.toolCalls ?? []), tc] }
                  : m,
              ),
            }));
          } else if (type === 'tool_result') {
            const name = (ev.name as string) ?? '';
            const result = (ev.result as string) ?? '';
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(m => {
                if (m.id !== currentAiId) return m;
                const tcs = (m.toolCalls ?? []).map(tc =>
                  tc.name === name && tc.result === undefined
                    ? { ...tc, result }
                    : tc,
                );
                return { ...m, toolCalls: tcs };
              }),
            }));
          } else if (type === 'skill_launch') {
            const info: SkillLaunchInfo = {
              skill: (ev.skill as string) ?? '',
              run_id: (ev.run_id as string) ?? '',
              project_code: (ev.project_code as string) ?? '',
              scenario_run: (ev.scenario_run as string) ?? '',
              project_name: (ev.project_name as string) ?? '',
              steps: (ev.steps as string[]) ?? [],
            };
            setState(prev => ({
              ...prev,
              skillLaunch: info,
              messages: prev.messages.map(m =>
                m.id === currentAiId ? { ...m, skillLaunch: info } : m,
              ),
            }));
          } else if (type === 'tool_approval_required') {
            const approval: ToolApprovalInfo = {
              approval_id: (ev.approval_id as string) ?? '',
              name: (ev.name as string) ?? '',
              args: (ev.args as Record<string, unknown>) ?? {},
            };
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(m =>
                m.id === currentAiId ? { ...m, pendingApproval: approval } : m,
              ),
            }));
          } else if (type === 'choices') {
            const choices: ChoicesInfo = {
              question: (ev.question as string) ?? '',
              options: (ev.options as ChoicesInfo['options']) ?? [],
            };
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(m =>
                m.id === currentAiId ? { ...m, choices } : m,
              ),
            }));
          } else if (type === 'done') {
            setState(prev => ({
              ...prev,
              isLoading: false,
              messages: prev.messages.map(m =>
                m.id === currentAiId ? { ...m, isStreaming: false } : m,
              ),
            }));
          } else if (type === 'error') {
            setState(prev => ({
              ...prev,
              isLoading: false,
              error: (ev.message as string) ?? 'unknown error',
              messages: prev.messages.map(m =>
                m.id === currentAiId ? { ...m, isStreaming: false } : m,
              ),
            }));
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      const msg = err instanceof Error ? err.message : String(err);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: msg,
        messages: prev.messages.map(m =>
          m.id === aiMsgIdRef.current ? { ...m, isStreaming: false } : m,
        ),
      }));
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ messages: [], isLoading: false, skillLaunch: null, error: null });
  }, []);

  const clearSkillLaunch = useCallback(() => {
    setState(prev => ({ ...prev, skillLaunch: null }));
  }, []);

  const decideTool = useCallback(async (approvalId: string, approved: boolean) => {
    // 乐观更新 UI（立即标记已决策）
    setState(prev => ({
      ...prev,
      messages: prev.messages.map(m => {
        if (!m.pendingApproval || m.pendingApproval.approval_id !== approvalId) return m;
        return { ...m, pendingApproval: { ...m.pendingApproval, decided: approved ? 'approved' : 'denied' } };
      }),
    }));
    // 通知后端解锁挂起的工具
    await fetch(`${AGENT_BASE}/agent/chat/approve-tool`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: approvalId, approved }),
    });
  }, []);

  return { ...state, send, reset, clearSkillLaunch, decideTool };
}
