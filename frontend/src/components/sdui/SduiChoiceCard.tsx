/**
 * SduiChoiceCard — HITL 单选 / 多选卡（意图消歧等多选场景对齐设计稿 cv-dis-*）
 */
import { useEffect, useState } from 'react';
import { useSduiRuntime } from './SduiContext';
import { hitlKey, getHitlOptimistic, setHitlOptimistic } from './hitlOptimistic';
import type { SduiChoiceCardNode } from '@/lib/sdui';

type Props = Omit<SduiChoiceCardNode, 'type' | 'id' | 'flex'>;

export function SduiChoiceCard({
  title,
  options,
  hitlRequestId,
  stepId,
  multiple = false,
  maxSelections,
  submitLabel,
  repeatable = false,
}: Props) {
  const { onChoiceSubmit, runId, streamEpoch } = useSduiRuntime();
  const isRefreshAction = options.length === 1 && options.some((opt) => {
    const value = String(opt.value ?? opt.id ?? '').toLowerCase();
    return value === 'refresh' || opt.label.includes('刷新检查回传');
  });
  const effectiveRepeatable = repeatable || isRefreshAction;
  const promptFingerprint = [
    hitlRequestId ?? '',
    title,
    multiple ? 'multi' : 'single',
    options.map((opt, i) => `${opt.value ?? opt.id ?? i}:${opt.label}`).join('|'),
  ].join('::');
  const key = hitlKey(runId, stepId, promptFingerprint);
  const readRestoredSelection = () => {
    const restored = effectiveRepeatable ? null : getHitlOptimistic(key);
    return restored?.kind === 'choice' ? restored.selected : null;
  };
  const restoredSel = readRestoredSelection();

  const [selected, setSelected] = useState<string[]>(
    multiple ? (restoredSel ? restoredSel.split('、') : []) : [],
  );
  const [single, setSingle] = useState<string | null>(
    multiple ? null : restoredSel,
  );
  const [submitted, setSubmitted] = useState(!effectiveRepeatable && restoredSel != null);

  useEffect(() => {
    const nextRestoredSel = readRestoredSelection();
    setSelected(multiple ? (nextRestoredSel ? nextRestoredSel.split('、') : []) : []);
    setSingle(multiple ? null : nextRestoredSel);
    setSubmitted(!effectiveRepeatable && nextRestoredSel != null);
  }, [key, multiple, effectiveRepeatable]);

  useEffect(() => {
    if (!effectiveRepeatable) return;
    setSelected([]);
    setSingle(null);
    setSubmitted(false);
  }, [effectiveRepeatable, streamEpoch]);

  const max = multiple ? (maxSelections ?? options.length) : 1;
  const picked = multiple ? selected : (single ? [single] : []);
  const canSubmit = picked.length > 0;

  const toggle = (val: string) => {
    if (submitted) return;
    if (!multiple) {
      setSingle(val);
      return;
    }
    setSelected((prev) => {
      if (prev.includes(val)) return prev.filter((x) => x !== val);
      if (prev.length >= max) return prev;
      return [...prev, val];
    });
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    const value = multiple ? picked.join('、') : picked[0];
    if (!value) return;
    setSubmitted(true);
    if (!effectiveRepeatable) {
      setHitlOptimistic(key, { kind: 'choice', selected: value });
    } else {
      window.setTimeout(() => {
        setSelected([]);
        setSingle(null);
        setSubmitted(false);
      }, 1200);
    }
    onChoiceSubmit(value, stepId);
  };

  const confirmText = submitLabel
    ?? (multiple ? `确认（${picked.length}）` : '确认选择');
  const showRefreshMissHint = isRefreshAction && !title.includes('暂未检测到回传结果');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {showRefreshMissHint && (
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--orange-600, #d97706)', whiteSpace: 'pre-line', lineHeight: 1.5 }}>
          暂未检测到回传结果
        </div>
      )}
      <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'pre-line', lineHeight: 1.5 }}>
        {title}
      </div>
      <div
        className={multiple ? 'cv-dis-list' : undefined}
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          opacity: submitted ? 0.45 : 1,
          pointerEvents: submitted ? 'none' : 'auto',
          transition: 'opacity .2s',
        }}
      >
        {options.map((opt, i) => {
          const val = opt.value ?? opt.id ?? String(i);
          const isOn = multiple ? selected.includes(val) : single === val;
          if (multiple) {
            return (
              <button
                key={val}
                type="button"
                className={`cv-dis-opt${isOn ? ' on' : ''}`}
                onClick={() => toggle(val)}
              >
                <span className="cv-dis-check">{isOn ? '✓' : ''}</span>
                <span className="cv-dis-label">{opt.label}</span>
              </button>
            );
          }
          return (
            <div
              key={val}
              onClick={() => toggle(val)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: `1px solid ${isOn ? 'var(--blue-600)' : 'var(--border)'}`,
                background: isOn ? 'var(--blue-50)' : 'var(--surface)',
                cursor: 'pointer',
                transition: 'all .15s',
              }}
            >
              <div style={{
                width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
                border: `2px solid ${isOn ? 'var(--blue-600)' : 'var(--zinc-300)'}`,
                background: isOn ? 'var(--blue-600)' : 'transparent',
              }} />
              <div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{opt.label}</div>
                {opt.description && (
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: 1 }}>{opt.description}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {multiple && !submitted && (
        <span className="cv-card-hint" style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
          已选 {picked.length} 项{max < options.length ? `（最多 ${max} 项）` : ''}
        </span>
      )}

      {!submitted && (
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={multiple ? 'btn primary sm' : undefined}
          style={multiple ? undefined : {
            alignSelf: 'flex-start',
            padding: '6px 14px',
            fontSize: 'var(--text-sm)', fontWeight: 500,
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: canSubmit ? 'var(--blue-600)' : 'var(--zinc-200)',
            color: canSubmit ? '#fff' : 'var(--text-tertiary)',
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            transition: 'all .15s',
          }}
        >
          {confirmText}
        </button>
      )}

      {submitted && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
          background: '#e6f6ee',
          border: '1px solid #bfe9d3',
          fontSize: '12px', color: '#065f46', fontWeight: 500,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/>
          </svg>
          已提交：
          <span style={{ fontWeight: 600 }}>
            {picked.map((v) => options.find((o) => (o.value ?? o.id) === v)?.label ?? v).join('、')}
          </span>
          <span style={{ color: '#0a7350', fontWeight: 400, marginLeft: 4 }}>· 等待处理中…</span>
        </div>
      )}
    </div>
  );
}
