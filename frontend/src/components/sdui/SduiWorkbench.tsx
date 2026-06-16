/**
 * SduiWorkbench — 交付台专用节点：ContextBar + FlowSteps
 * 对齐 UI设计/UI/app.jsx · ctx-bar / flow-steps
 */
import { useEffect, useRef, useState } from 'react';
import type { SduiAction, SduiNode } from '@/lib/sdui';
import { useSduiRuntime } from './SduiContext';

type ContextBarNode = Extract<SduiNode, { type: 'ContextBar' }>;
type FlowStepsNode = Extract<SduiNode, { type: 'FlowSteps' }>;

(function injectFlowStepsStyles() {
  if (typeof document === 'undefined') return;
  ['sdui-flow-steps-styles', 'sdui-flow-steps-styles-v2', 'sdui-flow-steps-styles-v3', 'sdui-flow-steps-styles-v4', 'sdui-flow-steps-styles-v5'].forEach((id) => {
    document.getElementById(id)?.remove();
  });
  const styleId = 'sdui-flow-steps-styles-v5';
  const s = document.createElement('style');
  s.id = styleId;
  s.textContent = `
    .sdui-flow-steps {
      overflow-x: auto;
      scrollbar-width: none;
      -ms-overflow-style: none;
      cursor: grab;
      user-select: none;
      -webkit-user-select: none;
    }
    .sdui-flow-steps.is-dragging {
      cursor: grabbing;
    }
    .sdui-flow-steps::-webkit-scrollbar {
      display: none;
      height: 0;
    }
    .sdui-flow-step-btn {
      font-family: var(--font-sans);
    }
    .sdui-flow-step-shell {
      position: relative;
      flex-shrink: 0;
      border-radius: var(--radius-lg);
    }
  `;
  document.head.appendChild(s);
})();

const FLOW_STEP_MIN_W = 158;

function FlowArrow({ done }: { done?: boolean }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', flexShrink: 0,
      color: done ? '#0f9d58' : 'var(--text-tertiary)', padding: '0 3px', alignSelf: 'center',
    }}>
      <svg width="14" height="12" viewBox="0 0 18 14" fill="none">
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

function CtxGroup({
  label,
  value,
  badge,
  inlineAction,
  onAction,
}: {
  label: string;
  value: string;
  badge?: string;
  inlineAction?: { label: string; variant?: string; action: SduiAction };
  onAction?: (action: SduiAction) => void;
}) {
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
      {inlineAction ? (
        <button
          type="button"
          onClick={() => onAction?.(inlineAction.action)}
          style={{
            marginLeft: 2,
            padding: '2px 8px',
            fontSize: 11,
            fontWeight: 600,
            lineHeight: 1.4,
            borderRadius: 5,
            border: '1px solid var(--border)',
            background: 'var(--surface)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
            whiteSpace: 'nowrap',
          }}
        >
          {inlineAction.label}
        </button>
      ) : null}
    </div>
  );
}

function CtxBarAction({
  action,
  onAction,
}: {
  action: { label: string; variant?: string; action: SduiAction };
  onAction?: (action: SduiAction) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onAction?.(action.action)}
      style={{
        padding: '2px 8px',
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 1.4,
        borderRadius: 5,
        border: '1px solid var(--border)',
        background: 'var(--surface)',
        color: 'var(--text-secondary)',
        cursor: 'pointer',
        fontFamily: 'var(--font-sans)',
        whiteSpace: 'nowrap',
      }}
    >
      {action.label}
    </button>
  );
}

export function SduiContextBar({ node }: { node: ContextBarNode }) {
  const { onAction } = useSduiRuntime();
  const groups = node.groups ?? [];
  const showArrow = node.showTimelineArrow !== false;
  const main = groups.length > 1 ? groups.slice(0, -1) : groups;
  const trailing = groups.length > 1 ? groups[groups.length - 1] : null;
  const trailingAction = node.trailingAction;

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
              <CtxGroup
                label={g.label}
                value={g.value}
                badge={g.badge}
                inlineAction={g.inlineAction}
                onAction={onAction}
              />
            </div>
          );
        })}
      </div>
      {(trailingAction || trailing) ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexShrink: 0,
          marginLeft: 8,
        }}>
          {trailingAction ? (
            <CtxBarAction action={trailingAction} onAction={onAction} />
          ) : null}
          {trailing ? (
            <CtxGroup
              label={trailing.label}
              value={trailing.value}
              badge={trailing.badge}
              onAction={onAction}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}


function flowStepSurface(isDone: boolean, isCurrent: boolean, isFuture: boolean): { bg: string; border: string } {
  if (isCurrent) {
    return {
      bg: 'linear-gradient(180deg, var(--c-brand-soft, #eef1fc) 0%, var(--c-surface, #fff) 72%)',
      border: '1.5px solid var(--c-brand, #3551d8)',
    };
  }
  if (isDone) {
    return {
      bg: 'linear-gradient(180deg, #f3fbf6 0%, var(--c-surface, #fff) 72%)',
      border: '1px solid #d1e9d8',
    };
  }
  if (isFuture) {
    return {
      bg: 'var(--c-surface, #fff)',
      border: '1px solid var(--c-border, #e2e8f0)',
    };
  }
  return { bg: 'var(--c-surface, #fff)', border: '1px solid var(--c-border, #e2e8f0)' };
}

export function SduiFlowSteps({ node }: { node: FlowStepsNode }) {
  const { onAction } = useSduiRuntime();
  const steps = node.steps ?? [];
  const backendCurrent = node.currentId ?? '';
  const [selected, setSelected] = useState(backendCurrent || steps[0]?.id || '');
  const [dragging, setDragging] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stepRefs = useRef<Map<string, HTMLSpanElement>>(new Map());
  const dragRef = useRef({ active: false, startX: 0, scrollLeft: 0, didDrag: false });
  const lastAutoScrolled = useRef('');

  useEffect(() => {
    if (backendCurrent) setSelected(backendCurrent);
  }, [backendCurrent]);

  useEffect(() => {
    if (!backendCurrent || backendCurrent === lastAutoScrolled.current) return;
    lastAutoScrolled.current = backendCurrent;
    const shell = stepRefs.current.get(backendCurrent);
    const container = scrollRef.current;
    if (!shell || !container) return;
    const raf = requestAnimationFrame(() => {
      const left = shell.offsetLeft + shell.offsetWidth / 2 - container.clientWidth / 2;
      container.scrollTo({ left: Math.max(0, left), behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(raf);
  }, [backendCurrent, steps.length]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current.active) return;
      moveDrag(e.clientX);
    };
    const endDrag = () => {
      if (!dragRef.current.active) return;
      dragRef.current.active = false;
      setDragging(false);
      window.setTimeout(() => { dragRef.current.didDrag = false; }, 0);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', endDrag);
    window.addEventListener('touchend', endDrag);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', endDrag);
      window.removeEventListener('touchend', endDrag);
    };
  }, []);

  const beginDrag = (clientX: number) => {
    const el = scrollRef.current;
    if (!el) return;
    dragRef.current = { active: true, startX: clientX, scrollLeft: el.scrollLeft, didDrag: false };
    setDragging(true);
  };

  const moveDrag = (clientX: number) => {
    if (!dragRef.current.active || !scrollRef.current) return;
    const dx = clientX - dragRef.current.startX;
    if (Math.abs(dx) > 4) dragRef.current.didDrag = true;
    scrollRef.current.scrollLeft = dragRef.current.scrollLeft - dx;
  };

  const activeId = selected || backendCurrent;
  const headerAction = node.headerAction;

  return (
    <div style={{ width: '100%' }}>
      {headerAction ? (
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 10px 2px' }}>
          <button
            type="button"
            onClick={() => onAction?.(headerAction.action)}
            style={{
              padding: '4px 10px',
              fontSize: 12,
              fontWeight: 500,
              borderRadius: 6,
              border: '1px solid var(--c-border)',
              background: 'var(--c-surface)',
              color: 'var(--c-text-2)',
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            {headerAction.label}
          </button>
        </div>
      ) : null}
      <div
        ref={scrollRef}
        className={`sdui-flow-steps${dragging ? ' is-dragging' : ''}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          padding: '10px 10px 12px',
          width: '100%',
        }}
        onMouseDown={(e) => {
          if (e.button !== 0) return;
          beginDrag(e.clientX);
        }}
        onTouchStart={(e) => {
          if (e.touches.length !== 1) return;
          beginDrag(e.touches[0]!.clientX);
        }}
        onTouchMove={(e) => {
          if (!dragRef.current.active || e.touches.length !== 1) return;
          moveDrag(e.touches[0]!.clientX);
        }}
      >
        {steps.map((st, idx) => {
        const status = st.status ?? 'future';
        const isSelected = st.id === activeId;
        const visual = isSelected ? 'current' : status;
        const isDone = visual === 'done';
        const isCurrent = visual === 'current';
        const isFuture = visual === 'future';
        const { bg, border } = flowStepSurface(isDone, isCurrent, isFuture);

        return (
          <span
            key={st.id}
            ref={(el) => {
              if (el) stepRefs.current.set(st.id, el);
              else stepRefs.current.delete(st.id);
            }}
            style={{ display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}
          >
            <span
              className="sdui-flow-step-shell"
              style={{ width: FLOW_STEP_MIN_W, flex: `0 0 ${FLOW_STEP_MIN_W}px` }}
            >
              <button
                type="button"
                className="sdui-flow-step-btn"
                onClick={() => {
                  if (dragRef.current.didDrag) return;
                  setSelected(st.id);
                  if (st.stepKey === 'toolkit_executor') {
                    onAction?.({ kind: 'post_user_message', text: '/edit_executor' });
                  }
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 12px',
                  background: bg,
                  border,
                  borderRadius: 'var(--radius-lg)',
                  textAlign: 'left',
                  cursor: 'pointer',
                  minHeight: 46,
                  boxShadow: isCurrent
                    ? '0 0 0 3px rgba(53,81,216,.08), 0 1px 2px rgba(15,23,42,.04)'
                    : '0 1px 2px rgba(15,23,42,.03)',
                  transition: 'background .15s, border-color .15s, box-shadow .15s',
                }}
              >
                <span
                  style={{
                    width: 24, height: 24, borderRadius: 7, flexShrink: 0,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
                    background: isDone ? '#0f9d58' : isCurrent ? '#3551d8' : 'var(--c-bg-soft, #f1f5f9)',
                    color: isDone || isCurrent ? '#fff' : 'var(--c-text-muted, #94a3b8)',
                  }}>
                    {isDone ? '✓' : st.num}
                </span>
                <span
                  style={{
                    fontSize: 12.5,
                    fontWeight: isCurrent ? 600 : 500,
                    color: isCurrent ? 'var(--c-brand-text, #1e34a8)' : isFuture ? 'var(--c-text-muted, #64748b)' : 'var(--c-text-1, #0f172a)',
                    lineHeight: 1.3,
                    letterSpacing: '-.005em',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    flex: 1,
                    minWidth: 0,
                  }}>
                    {st.title}
                </span>
              </button>
            </span>
            {idx < steps.length - 1 && <FlowArrow done={isDone} />}
          </span>
        );
        })}
      </div>
    </div>
  );
}
