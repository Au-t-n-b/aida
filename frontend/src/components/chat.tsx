// @ts-nocheck
'use client';

import { useRef, useState, useEffect } from 'react';
import { IconClaw, IconCheck, IconChevron, IconUpload } from './icons';
import { FileChip, Button, Skeleton } from './primitives';

/* ── Avatar ── */
export function Avatar({ name = '', kind = 'user', size = 26 }) {
  const isAI = kind === 'ai';
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: isAI ? 'var(--slate-900)' : 'var(--accent-muted)',
      color: isAI ? '#fff' : 'var(--accent)',
      fontSize: size * 0.42, fontWeight: 700,
    }}>
      {isAI ? <IconClaw size={size * 0.55} color="#fff" /> : name.charAt(0).toUpperCase()}
    </div>
  );
}

/* ── ChatMessage ── */
export function ChatMessage({ author, kind = 'ai', timestamp, status, children }) {
  const isUser = kind === 'user';
  return (
    <div style={{
      display: 'flex', gap: 8, alignItems: 'flex-start',
      flexDirection: isUser ? 'row-reverse' : 'row',
      animation: 'clawRise .2s ease',
    }}>
      <Avatar name={author} kind={kind} />
      <div style={{ maxWidth: '80%', display: 'flex', flexDirection: 'column', gap: 3, alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        <div style={{
          padding: '8px 10px',
          background: isUser ? 'var(--slate-900)' : 'var(--surface)',
          color: isUser ? '#fff' : 'var(--text-primary)',
          border: isUser ? 'none' : '1px solid var(--border)',
          borderRadius: isUser ? '12px 12px 3px 12px' : '3px 12px 12px 12px',
          fontSize: 'var(--text-sm)', lineHeight: 1.6,
        }}>
          {children}
        </div>
        {timestamp && (
          <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 4 }}>
            {timestamp}
            {status === 'sent' && <IconCheck size={10} color="var(--text-tertiary)" />}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── ThoughtTrace ── */
export function ThoughtTrace({ items = [], active = false }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      background: 'var(--surface-raised)',
      fontSize: 'var(--text-xs)',
      overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, width: '100%',
          padding: '5px 8px', textAlign: 'left', cursor: 'pointer',
          background: 'none', border: 'none',
          color: active ? 'var(--accent)' : 'var(--text-secondary)',
        }}
      >
        {active && <span className="claw-dot claw-dot--running" />}
        <span style={{ fontWeight: 500 }}>思考过程</span>
        <span style={{ marginLeft: 'auto' }}>
          <IconChevron size={12} direction={open ? 'up' : 'down'} />
        </span>
      </button>
      {open && (
        <div style={{ padding: '4px 8px 8px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {items.map((item, i) => (
            <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <span style={{ color: 'var(--text-secondary)' }}>{item}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── HITLOptions ── */
export function HITLOptions({ title, hint, options = [], multi = false, onSubmit, selected: externalSelected, locked = false }) {
  const [selected, setSelected] = useState(externalSelected || (multi ? [] : null));

  function toggle(val) {
    if (locked) return;
    if (multi) {
      setSelected(s => s.includes(val) ? s.filter(x => x !== val) : [...s, val]);
    } else {
      setSelected(val);
    }
  }

  const isSelected = val => multi ? selected.includes(val) : selected === val;
  const hasSelection = multi ? selected.length > 0 : selected != null;

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
      background: 'var(--surface)', overflow: 'hidden',
      animation: 'clawEnter .2s ease',
    }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>
        {hint && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 2 }}>{hint}</div>}
      </div>
      <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {options.map((opt, i) => {
          const sel = isSelected(opt.value ?? opt.label);
          return (
            <button
              key={i}
              onClick={() => toggle(opt.value ?? opt.label)}
              disabled={locked}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px',
                borderRadius: 'var(--radius-md)', textAlign: 'left', width: '100%',
                background: sel ? 'var(--accent-muted)' : 'var(--zinc-50)',
                border: `1px solid ${sel ? 'var(--accent)' : 'var(--border)'}`,
                cursor: locked ? 'default' : 'pointer',
                transition: 'all .12s',
              }}
            >
              <div style={{
                width: multi ? 14 : 14, height: multi ? 14 : 14, flexShrink: 0, marginTop: 1,
                borderRadius: multi ? 3 : '50%',
                border: `2px solid ${sel ? 'var(--accent)' : 'var(--zinc-300)'}`,
                background: sel ? 'var(--accent)' : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {sel && <span style={{ color: '#fff', fontSize: 8, lineHeight: 1 }}>✓</span>}
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: sel ? 'var(--accent)' : 'var(--text-primary)' }}>
                  {opt.label}
                </div>
                {opt.desc && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 1 }}>{opt.desc}</div>}
              </div>
              {opt.badge && (
                <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--text-tertiary)', flexShrink: 0 }}>{opt.badge}</span>
              )}
            </button>
          );
        })}
      </div>
      {!locked && (
        <div style={{ padding: '0 12px 10px' }}>
          <Button
            variant="primary" size="sm" style={{ width: '100%' }}
            disabled={!hasSelection}
            onClick={() => onSubmit?.(selected)}
          >
            确认选择
          </Button>
        </div>
      )}
    </div>
  );
}

/* ── ToolApprovalCard ── */
export function ToolApprovalCard({ tool, params = {}, onRun, onCancel, decided }) {
  return (
    <div style={{
      border: '1px solid var(--amber-100)', borderRadius: 'var(--radius-lg)',
      background: 'var(--amber-50)', overflow: 'hidden',
      animation: 'clawEnter .2s ease',
    }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--amber-100)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: '12px' }}>🔧</span>
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--amber-700)' }}>工具调用请求</div>
        {decided && (
          <span style={{ marginLeft: 'auto', fontSize: 'var(--text-xs)', color: decided === 'run' ? 'var(--green-600)' : 'var(--red-600)', fontWeight: 500 }}>
            {decided === 'run' ? '已批准' : '已拒绝'}
          </span>
        )}
      </div>
      <div style={{ padding: '8px 12px' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--amber-700)', fontWeight: 600, marginBottom: 6 }}>
          {tool}
        </div>
        {Object.entries(params).length > 0 && (
          <pre style={{
            fontSize: '10px', color: 'var(--text-secondary)',
            background: 'rgba(0,0,0,.04)', borderRadius: 'var(--radius-sm)',
            padding: '6px 8px', overflow: 'auto', maxHeight: 80,
            fontFamily: 'var(--font-mono)',
          }}>
            {JSON.stringify(params, null, 2)}
          </pre>
        )}
      </div>
      {!decided && (
        <div style={{ padding: '0 12px 10px', display: 'flex', gap: 6 }}>
          <Button variant="primary" size="sm" onClick={onRun} style={{ flex: 1 }}>批准运行</Button>
          <Button variant="secondary" size="sm" onClick={onCancel} style={{ flex: 1 }}>拒绝</Button>
        </div>
      )}
    </div>
  );
}

/* ── UploadSummaryCard ── */
export function UploadSummaryCard({ files = [] }) {
  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
      background: 'var(--surface)', overflow: 'hidden',
      animation: 'clawEnter .2s ease',
    }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <IconUpload size={14} color="var(--text-secondary)" />
        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>已上传文件</span>
        <span style={{ marginLeft: 'auto', fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>{files.length} 个</span>
      </div>
      <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {files.map((f, i) => (
          <FileChip key={i} file={f} justUploaded />
        ))}
      </div>
    </div>
  );
}

/* ── ChatComposer ── */
export function ChatComposer({ onSend, model = 'claude-opus-4-7', disabled = false }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleSend() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend?.(t);
    setText('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }

  useEffect(() => { autoResize(); }, [text]);

  return (
    <div style={{
      padding: '8px 10px',
      borderTop: '1px solid var(--border)',
      background: 'var(--surface)',
    }}>
      <div style={{
        display: 'flex', gap: 6, alignItems: 'flex-end',
        border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
        padding: '6px 8px',
        background: 'var(--surface-raised)',
      }}>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          disabled={disabled}
          placeholder="发送消息…"
          rows={1}
          style={{
            flex: 1, resize: 'none', border: 'none', outline: 'none',
            background: 'transparent', fontSize: 'var(--text-sm)',
            color: 'var(--text-primary)', lineHeight: 1.5,
            minHeight: 22, maxHeight: 120,
            fontFamily: 'var(--font-sans)',
          }}
        />
        <Button
          variant="primary" size="sm"
          disabled={!text.trim() || disabled}
          onClick={handleSend}
          style={{ flexShrink: 0, height: 28, padding: '0 10px' }}
        >
          发送
        </Button>
      </div>
      <div style={{ marginTop: 4, fontSize: '10px', color: 'var(--text-tertiary)', textAlign: 'center' }}>
        {model} · Enter 发送 · Shift+Enter 换行
      </div>
    </div>
  );
}

/* ── ThinkingDots (loading indicator) ── */
export function ThinkingDots() {
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', padding: '8px 0' }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          className="claw-dot claw-dot--running"
          style={{ animationDelay: `${i * 0.2}s` }}
        />
      ))}
    </div>
  );
}
