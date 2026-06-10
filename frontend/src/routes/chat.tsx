/**
 * /chat 路由 — AIDA 通用会话页面
 *
 * 布局：左侧 60% 对话区（token 流式 + 工具调用卡片），右侧 40% SDUI 面板。
 * 当 skill_launch 事件到达（chat 引擎触发了 run_survey 工具），右侧自动切换为对应
 * skill 的执行状态（复用 useSduiStream + SduiNodeView，与 /module/:key 页共用同一套）。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { SduiNodeView } from '@/components/sdui/SduiNodeView';
import { SduiRuntimeContext, type SduiRuntime } from '@/components/sdui/SduiContext';
import { useSduiStream, resumeRun, uploadBatch } from '@/hooks/useSduiStream';
import { useChatStream } from '@/hooks/useChatStream';
import type { ChatMessage, SkillLaunchInfo, ToolApprovalInfo } from '@/hooks/useChatStream';
import type { SduiAction } from '@/lib/sdui';

// ── 会话消息渲染 ─────────────────────────────────────────────────────────────

function ToolCallBadge({ name, args, result }: { name: string; args: Record<string, unknown>; result?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
      background: 'var(--surface-raised)', fontSize: 'var(--text-xs)',
      overflow: 'hidden', margin: '4px 0',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px',
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-secondary)', textAlign: 'left',
        }}
      >
        <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
          ⚙ {name}
        </span>
        {result !== undefined && (
          <span style={{ marginLeft: 'auto', color: result.startsWith('Error') ? 'var(--red-600)' : 'var(--green-600)' }}>
            {result.startsWith('Error') ? '✗ 失败' : '✓ 完成'}
          </span>
        )}
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{ padding: '0 8px 8px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <pre style={{
            fontSize: '10px', color: 'var(--text-secondary)', margin: 0,
            background: 'rgba(0,0,0,.04)', borderRadius: 4, padding: '4px 6px',
            overflow: 'auto', maxHeight: 120, fontFamily: 'var(--font-mono)',
          }}>
            {JSON.stringify(args, null, 2)}
          </pre>
          {result !== undefined && (
            <pre style={{
              fontSize: '10px', color: result.startsWith('Error') ? 'var(--red-600)' : 'var(--text-secondary)',
              margin: 0, fontFamily: 'var(--font-mono)',
              background: 'rgba(0,0,0,.04)', borderRadius: 4, padding: '4px 6px',
              overflow: 'auto', maxHeight: 80,
            }}>
              {result}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function SkillLaunchBadge({ info }: { info: SkillLaunchInfo }) {
  return (
    <div style={{
      border: '1px solid var(--accent)', borderRadius: 'var(--radius-md)',
      background: 'var(--accent-muted)', padding: '6px 10px',
      fontSize: 'var(--text-xs)', color: 'var(--accent)', margin: '4px 0',
      display: 'flex', alignItems: 'center', gap: 6,
    }}>
      <span>🚀</span>
      <span style={{ fontWeight: 600 }}>
        已启动 {info.skill} · {info.project_code || info.project_name}
      </span>
      {info.run_id && (
        <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.7, marginLeft: 'auto' }}>
          {info.run_id}
        </span>
      )}
    </div>
  );
}

function ToolApprovalCard({
  info,
  onDecide,
}: {
  info: ToolApprovalInfo;
  onDecide: (approvalId: string, approved: boolean) => void;
}) {
  const decided = info.decided;
  return (
    <div style={{
      border: `1px solid ${decided === 'approved' ? 'var(--green-300,#86efac)' : decided === 'denied' ? 'var(--red-300,#fca5a5)' : 'var(--amber-300,#fcd34d)'}`,
      borderRadius: 'var(--radius-lg)', background: decided ? 'var(--surface)' : 'var(--amber-50,#fffbeb)',
      overflow: 'hidden', margin: '4px 0', animation: 'clawEnter .2s ease',
    }}>
      <div style={{
        padding: '7px 10px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 6,
        background: decided === 'approved' ? 'var(--green-50,#f0fdf4)' : decided === 'denied' ? 'var(--red-50,#fef2f2)' : 'var(--amber-50,#fffbeb)',
      }}>
        <span style={{ fontSize: 13 }}>🔧</span>
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: decided === 'approved' ? 'var(--green-700,#15803d)' : decided === 'denied' ? 'var(--red-700,#b91c1c)' : 'var(--amber-700,#b45309)' }}>
          {decided === 'approved' ? '已批准' : decided === 'denied' ? '已拒绝' : '工具调用请求'} · {info.name}
        </span>
      </div>
      {Object.keys(info.args).length > 0 && (
        <pre style={{
          margin: 0, padding: '6px 10px',
          fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
          background: 'rgba(0,0,0,.03)', overflow: 'auto', maxHeight: 100,
        }}>
          {JSON.stringify(info.args, null, 2)}
        </pre>
      )}
      {!decided && (
        <div style={{ padding: '6px 10px', display: 'flex', gap: 6 }}>
          <button
            onClick={() => onDecide(info.approval_id, true)}
            style={{
              flex: 1, height: 28, borderRadius: 'var(--radius-md)', border: 'none',
              background: 'var(--accent)', color: '#fff', fontSize: 'var(--text-xs)',
              fontWeight: 600, cursor: 'pointer',
            }}
          >批准执行</button>
          <button
            onClick={() => onDecide(info.approval_id, false)}
            style={{
              flex: 1, height: 28, borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border)', background: 'var(--surface)',
              fontSize: 'var(--text-xs)', cursor: 'pointer', color: 'var(--text-secondary)',
            }}
          >拒绝</button>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg, onDecide }: { msg: ChatMessage; onDecide: (id: string, approved: boolean) => void }) {
  const isUser = msg.role === 'user';
  return (
    <div style={{
      display: 'flex', gap: 8, alignItems: 'flex-start',
      flexDirection: isUser ? 'row-reverse' : 'row',
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: isUser ? 'var(--slate-900)' : 'var(--accent)',
        color: '#fff', fontSize: 12, fontWeight: 700,
      }}>
        {isUser ? 'U' : 'AI'}
      </div>
      <div style={{ maxWidth: '85%', display: 'flex', flexDirection: 'column', gap: 3, alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        {msg.text && (
          <div style={{
            padding: '8px 10px',
            background: isUser ? 'var(--slate-900)' : 'var(--surface)',
            color: isUser ? '#fff' : 'var(--text-primary)',
            border: isUser ? 'none' : '1px solid var(--border)',
            borderRadius: isUser ? '12px 12px 3px 12px' : '3px 12px 12px 12px',
            fontSize: 'var(--text-sm)', lineHeight: 1.6, whiteSpace: 'pre-wrap',
          }}>
            {msg.text}
            {msg.isStreaming && <span className="claw-dot claw-dot--running" style={{ marginLeft: 4 }} />}
          </div>
        )}
        {(msg.toolCalls ?? []).map((tc, i) => (
          <ToolCallBadge key={i} name={tc.name} args={tc.args} result={tc.result} />
        ))}
        {msg.pendingApproval && (
          <ToolApprovalCard info={msg.pendingApproval} onDecide={onDecide} />
        )}
        {msg.skillLaunch && <SkillLaunchBadge info={msg.skillLaunch} />}
        {msg.choices && (
          <div style={{
            border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
            background: 'var(--surface)', padding: '8px 10px',
            fontSize: 'var(--text-xs)', color: 'var(--text-secondary)',
          }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{msg.choices.question}</div>
            {msg.choices.options.map((o, i) => (
              <div key={i} style={{ padding: '2px 0' }}>· {o.label}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── SDUI 右侧面板 ─────────────────────────────────────────────────────────────

function SduiPanel({ skillId, runId }: { skillId: string; runId: string }) {
  const doc = useSduiStream(skillId, runId);

  const handleAction = useCallback((action: SduiAction) => {
    if (action.kind === 'post_user_message') {
      const text = action.text;
      if (text.startsWith('/resume_') || text.startsWith('/retry_')) {
        void resumeRun(skillId, runId, {});
      }
    }
  }, [skillId, runId]);

  const handleUpload = useCallback((files: FileList) => {
    void uploadBatch(skillId, Array.from(files));
  }, [skillId]);

  const handleChoiceSubmit = useCallback((value: string) => {
    void resumeRun(skillId, runId, { choice: value });
  }, [skillId, runId]);

  const runtime: SduiRuntime = {
    runId,
    onAction: handleAction,
    onUpload: handleUpload,
    onChoiceSubmit: handleChoiceSubmit,
  };

  if (!doc) {
    return (
      <div style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', flexDirection: 'column', gap: 8,
      }}>
        <div className="claw-dot claw-dot--running" />
        <span>正在连接 {skillId} 执行流…</span>
      </div>
    );
  }

  return (
    <SduiRuntimeContext.Provider value={runtime}>
      <div style={{ height: '100%', overflow: 'auto', padding: 12 }}>
        <SduiNodeView node={doc.root} />
      </div>
    </SduiRuntimeContext.Provider>
  );
}

// ── 输入框 ────────────────────────────────────────────────────────────────────

function Composer({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const [text, setText] = useState('');
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText('');
    if (ref.current) ref.current.style.height = 'auto';
  }

  return (
    <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div style={{
        display: 'flex', gap: 8, alignItems: 'flex-end',
        border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
        padding: '6px 8px', background: 'var(--surface-raised)',
      }}>
        <textarea
          ref={ref}
          value={text}
          onChange={e => {
            setText(e.target.value);
            if (ref.current) {
              ref.current.style.height = 'auto';
              ref.current.style.height = Math.min(ref.current.scrollHeight, 120) + 'px';
            }
          }}
          onKeyDown={handleKey}
          disabled={disabled}
          placeholder="发送消息，例如：启动智慧工勘…"
          rows={1}
          style={{
            flex: 1, resize: 'none', border: 'none', outline: 'none',
            background: 'transparent', fontSize: 'var(--text-sm)',
            color: 'var(--text-primary)', lineHeight: 1.5,
            minHeight: 24, maxHeight: 120, fontFamily: 'var(--font-sans)',
          }}
        />
        <button
          onClick={submit}
          disabled={!text.trim() || disabled}
          style={{
            height: 30, padding: '0 12px', borderRadius: 'var(--radius-md)',
            background: text.trim() && !disabled ? 'var(--accent)' : 'var(--border)',
            color: '#fff', border: 'none', cursor: text.trim() && !disabled ? 'pointer' : 'default',
            fontSize: 'var(--text-sm)', fontWeight: 600, flexShrink: 0, transition: 'background .15s',
          }}
        >
          发送
        </button>
      </div>
      <div style={{ marginTop: 3, fontSize: '10px', color: 'var(--text-tertiary)', textAlign: 'center' }}>
        Enter 发送 · Shift+Enter 换行
      </div>
    </div>
  );
}

// ── 主页面 ────────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { messages, isLoading, skillLaunch, error, send, decideTool } = useChatStream();
  const bottomRef = useRef<HTMLDivElement>(null);

  // skill panel 状态：首次 skill_launch 锁定，后续不清除（保持可见）
  const [activeSkill, setActiveSkill] = useState<SkillLaunchInfo | null>(null);

  useEffect(() => {
    if (skillLaunch && skillLaunch.run_id && !skillLaunch.run_id.startsWith('err-')) {
      setActiveSkill(skillLaunch);
    }
  }, [skillLaunch]);

  // 新消息自动滚底
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (text: string) => {
    send(text, { convId: 'chat-main' });
  };

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg)' }}>
      {/* ── 左：对话区 ── */}
      <div style={{
        flex: activeSkill ? '0 0 58%' : '1',
        display: 'flex', flexDirection: 'column',
        borderRight: activeSkill ? '1px solid var(--border)' : 'none',
        transition: 'flex .2s',
        minWidth: 0,
      }}>
        {/* 标题栏 */}
        <div style={{
          padding: '10px 16px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--surface)', flexShrink: 0,
        }}>
          <span style={{ fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--text-primary)' }}>
            AIDA 交付助手
          </span>
          {isLoading && <span className="claw-dot claw-dot--running" />}
          {error && (
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--red-600)', marginLeft: 4 }}>
              {error}
            </span>
          )}
        </div>

        {/* 消息列表 */}
        <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {messages.length === 0 && (
            <div style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', flexDirection: 'column', gap: 8,
            }}>
              <div style={{ fontSize: 32 }}>💬</div>
              <div>发送消息开始会话</div>
              <div style={{ fontSize: 'var(--text-xs)', opacity: 0.7 }}>
                可以说"启动智慧工勘 K1903"来触发作业流程
              </div>
            </div>
          )}
          {messages.map(msg => (
            <MessageBubble key={msg.id} msg={msg} onDecide={decideTool} />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* 输入框 */}
        <Composer onSend={handleSend} disabled={isLoading} />
      </div>

      {/* ── 右：SDUI 面板（skill 启动后出现）── */}
      {activeSkill && (
        <div style={{ flex: '0 0 42%', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {/* SDUI 面板标题 */}
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid var(--border)',
            background: 'var(--surface)', flexShrink: 0,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
              {activeSkill.skill}
            </span>
            {activeSkill.project_code && (
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {activeSkill.project_code}
              </span>
            )}
            <button
              onClick={() => setActiveSkill(null)}
              style={{
                marginLeft: 'auto', background: 'none', border: 'none',
                cursor: 'pointer', color: 'var(--text-tertiary)', fontSize: 14,
              }}
              title="关闭面板"
            >
              ✕
            </button>
          </div>
          {/* SDUI 内容 */}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <SduiPanel skillId={activeSkill.skill} runId={activeSkill.run_id} />
          </div>
        </div>
      )}
    </div>
  );
}
