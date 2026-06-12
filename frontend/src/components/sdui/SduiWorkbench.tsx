/**
 * SduiWorkbench — 交付台专用节点：ContextBar + FlowSteps
 * 对齐 UI设计/UI/app.jsx · ctx-bar / flow-steps
 */
import { useEffect, useState } from 'react';
import type { SduiNode } from '@/lib/sdui';

type ContextBarNode = Extract<SduiNode, { type: 'ContextBar' }>;
type FlowStepsNode = Extract<SduiNode, { type: 'FlowSteps' }>;

function CheckIcon() {
  return (
    <svg width="8" height="8" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8.5l3.2 3.2L13 5" />
    </svg>
  );
}

function DotIcon() {
  return (
    <svg width="6" height="6" viewBox="0 0 8 8" fill="currentColor">
      <circle cx="4" cy="4" r="3" />
    </svg>
  );
}

function FlowArrow({ done }: { done?: boolean }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', flexShrink: 0,
      color: done ? '#0f9d58' : 'var(--text-tertiary)', padding: '0 2px', marginTop: 18,
    }}>
      <svg width="18" height="14" viewBox="0 0 18 14" fill="none">
        <path
          d="M1 7 H14 M10 3 L14 7 L10 11"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

function CtxGroup({ label, value, badge }: { label: string; value: string; badge?: string }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 7, flexShrink: 0 }}>
      <span style={{
        fontSize: 10.5, fontWeight: 600, letterSpacing: '.06em',
        textTransform: 'uppercase', color: 'var(--text-tertiary)',
      }}>
        {label}
      </span>
      <span style={{
        fontSize: 13, color: 'var(--text-primary)', fontWeight: 500,
        fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </span>
      {badge ? (
        <span style={{
          fontSize: 11, fontWeight: 500, padding: '1px 8px', borderRadius: 999,
          background: '#fdf2dd', color: '#b45309',
        }}>
          {badge}
        </span>
      ) : null}
    </div>
  );
}

export function SduiContextBar({ node }: { node: ContextBarNode }) {
  const groups = node.groups ?? [];
  const showArrow = node.showTimelineArrow !== false;
  const main = groups.length > 1 ? groups.slice(0, -1) : groups;
  const trailing = groups.length > 1 ? groups[groups.length - 1] : null;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      padding: '10px 16px',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
        {main.map((g, i) => {
          const isEnd = g.label === '预计截止';
          const sep = i > 0 && !(showArrow && isEnd);
          return (
            <div key={`${g.label}-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              {sep ? <span style={{ width: 1, height: 18, background: 'var(--border)', flexShrink: 0 }} /> : null}
              {showArrow && isEnd ? (
                <span style={{ color: 'var(--text-tertiary)', fontSize: 13, margin: '0 -4px' }}>→</span>
              ) : null}
              <CtxGroup label={g.label} value={g.value} badge={g.badge} />
            </div>
          );
        })}
      </div>
      {trailing ? <CtxGroup label={trailing.label} value={trailing.value} badge={trailing.badge} /> : null}
    </div>
  );
}

const CHIP_STYLE: Record<string, { icoBg: string; icoColor: string; textColor: string; border?: string }> = {
  ok:      { icoBg: '#e6f6ee', icoColor: '#0f9d58', textColor: 'var(--text-primary)' },
  pending: { icoBg: 'transparent', icoColor: '#3551d8', textColor: '#1e34a8', border: '1.5px solid #3551d8' },
  running: { icoBg: 'transparent', icoColor: '#3551d8', textColor: '#1e34a8', border: '1.5px solid #3551d8' },
  idle:    { icoBg: 'var(--c-bg-soft, #eef2f7)', icoColor: 'var(--text-tertiary)', textColor: 'var(--text-tertiary)' },
};

export function SduiFlowSteps({ node }: { node: FlowStepsNode }) {
  const steps = node.steps ?? [];
  const backendCurrent = node.currentId ?? '';
  const [selected, setSelected] = useState(backendCurrent || steps[0]?.id || '');

  useEffect(() => {
    if (backendCurrent) setSelected(backendCurrent);
  }, [backendCurrent]);

  const activeId = selected || backendCurrent;

  return (
    <div
      className="sdui-flow-steps"
      style={{
        display: 'flex',
        alignItems: 'stretch',
        gap: 0,
        padding: '12px 12px 14px',
        overflowX: 'auto',
        scrollbarWidth: 'thin',
      }}
    >
      {steps.map((st, idx) => {
        const status = st.status ?? 'future';
        const isSelected = st.id === activeId;
        const visual = isSelected ? 'current' : status;
        const isDone = visual === 'done';
        const isCurrent = visual === 'current';
        const bg = isCurrent
          ? 'linear-gradient(180deg, #eef1fc 0%, #fff 70%)'
          : isDone
            ? 'linear-gradient(180deg, #f4faf6 0%, #fff 70%)'
            : 'var(--surface)';
        const border = isCurrent ? '1.5px solid #3551d8' : '1.5px solid transparent';
        const boxShadow = isCurrent ? '0 0 0 3px rgba(53,81,216,.08), 0 1px 2px rgba(15,23,42,.04)' : 'none';

        return (
          <span key={st.id} style={{ display: 'contents' }}>
            <button
              type="button"
              onClick={() => setSelected(st.id)}
              style={{
                flex: '0 0 200px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                padding: '12px 14px',
                background: bg,
                border,
                borderRadius: 'var(--radius-lg)',
                textAlign: 'left',
                cursor: 'pointer',
                position: 'relative',
                minHeight: 104,
                boxShadow,
                transition: 'border-color .15s, box-shadow .15s, background .15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{
                  width: 26, height: 26, borderRadius: 7, flexShrink: 0,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
                  background: isDone ? '#0f9d58' : isCurrent ? '#3551d8' : 'var(--c-bg-soft, #eef2f7)',
                  color: isDone || isCurrent ? '#fff' : 'var(--text-tertiary)',
                  boxShadow: isCurrent ? '0 0 0 4px rgba(53,81,216,.18)' : 'none',
                }}>
                  {isDone ? '✓' : st.num}
                </span>
                <span style={{
                  fontSize: 13.5,
                  fontWeight: isCurrent ? 600 : 500,
                  color: isCurrent ? '#1e34a8' : visual === 'future' ? 'var(--text-secondary)' : 'var(--text-primary)',
                  lineHeight: 1.25,
                  letterSpacing: '-.005em',
                  wordBreak: 'break-word',
                }}>
                  {st.title}
                </span>
              </div>
              {(st.chips ?? []).length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3, paddingLeft: 2 }}>
                  {(st.chips ?? []).map((chip, ci) => {
                    const cs = CHIP_STYLE[chip.status ?? 'idle'] ?? CHIP_STYLE.idle!;
                    return (
                      <div key={ci} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, lineHeight: 1.3 }}>
                        <span style={{
                          width: 13, height: 13, borderRadius: '50%', flexShrink: 0,
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          background: cs.icoBg, color: cs.icoColor, border: cs.border,
                        }}>
                          {chip.status === 'ok' ? <CheckIcon /> : (chip.status === 'pending' || chip.status === 'running') ? <DotIcon /> : null}
                        </span>
                        <span style={{ color: cs.textColor, fontWeight: chip.status === 'pending' ? 500 : 400 }}>
                          {chip.text}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </button>
            {idx < steps.length - 1 && <FlowArrow done={isDone} />}
          </span>
        );
      })}
    </div>
  );
}
