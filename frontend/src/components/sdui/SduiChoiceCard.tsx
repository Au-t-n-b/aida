/**
 * SduiChoiceCard — HITL 单选卡（简化版）
 */
import { useState } from 'react';
import { useSduiRuntime } from './SduiContext';
import { hitlKey, getHitlOptimistic, setHitlOptimistic } from './hitlOptimistic';
import type { SduiChoiceCardNode } from '@/lib/sdui';

type Props = Omit<SduiChoiceCardNode, 'type' | 'id' | 'flex'>;

export function SduiChoiceCard({ title, options, stepId }: Props) {
  const { onChoiceSubmit, runId } = useSduiRuntime();
  // 跨重挂载回读确认态（冻结重放期间组件会重挂，避免闪回「未选」）
  const key = hitlKey(runId, stepId);
  const restored = getHitlOptimistic(key);
  const restoredSel = restored?.kind === 'choice' ? restored.selected : null;
  const [selected, setSelected] = useState<string | null>(restoredSel);
  const [submitted, setSubmitted] = useState(restoredSel != null);

  const handleSubmit = () => {
    if (!selected) return;
    setSubmitted(true);
    setHitlOptimistic(key, { kind: 'choice', selected });
    // parent 在 onChoiceSubmit 内会先 hold 再 resume，保证确认态可见一段时间
    onChoiceSubmit(selected, stepId);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)' }}>{title}</div>
      {/* 选项列表：提交后降低不透明度，禁止二次点击 */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 6,
        opacity: submitted ? 0.45 : 1,
        pointerEvents: submitted ? 'none' : 'auto',
        transition: 'opacity .2s',
      }}>
        {options.map((opt, i) => {
          const val = opt.value ?? opt.id ?? String(i);
          const isSelected = selected === val;
          return (
            <div
              key={val}
              onClick={() => !submitted && setSelected(val)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: `1px solid ${isSelected ? 'var(--blue-600)' : 'var(--border)'}`,
                background: isSelected ? 'var(--blue-50)' : 'var(--surface)',
                cursor: 'pointer',
                transition: 'all .15s',
              }}
            >
              <div style={{
                width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
                border: `2px solid ${isSelected ? 'var(--blue-600)' : 'var(--zinc-300)'}`,
                background: isSelected ? 'var(--blue-600)' : 'transparent',
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

      {!submitted && (
        <button
          onClick={handleSubmit}
          disabled={!selected}
          style={{
            alignSelf: 'flex-start',
            padding: '6px 14px',
            fontSize: 'var(--text-sm)', fontWeight: 500,
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: selected ? 'var(--blue-600)' : 'var(--zinc-200)',
            color: selected ? '#fff' : 'var(--text-tertiary)',
            cursor: selected ? 'pointer' : 'not-allowed',
            transition: 'all .15s',
          }}
        >
          确认选择
        </button>
      )}

      {/* 提交后：绿色确认横幅，显示选了什么 */}
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
            {options.find(o => (o.value ?? o.id ?? String(options.indexOf(o))) === selected)?.label ?? selected}
          </span>
          <span style={{ color: '#0a7350', fontWeight: 400, marginLeft: 4 }}>· 等待处理中…</span>
        </div>
      )}
    </div>
  );
}
