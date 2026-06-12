/**
 * SduiIoConfirmPanel — 确认执行计划 · 将读取 → 将生成（对齐设计稿 cv-io）
 */
import { useState } from 'react';
import { useSduiRuntime } from './SduiContext';
import type { SduiIoConfirmPanelNode } from '@/lib/sdui';

type Props = Omit<SduiIoConfirmPanelNode, 'type' | 'id'>;

export function SduiIoConfirmPanel({
  commandTitle,
  reads,
  writes,
  confirmLabel = '确认执行',
  cancelLabel = '重新选择',
  confirmValue = 'confirm',
  cancelValue = 'cancel',
  stepId,
}: Props) {
  const { onChoiceSubmit } = useSduiRuntime();
  const [submitted, setSubmitted] = useState(false);

  const handleChoice = (value: string) => {
    if (submitted) return;
    setSubmitted(true);
    onChoiceSubmit(value, stepId);
  };

  return (
    <div className={`cv-io-confirm${submitted ? ' is-submitted' : ''}`}>
      <div className="cv-io-confirm-title">{commandTitle}</div>
      <div className="cv-io-panel">
        <div className="cv-io-col">
          <div className="cv-io-col-label">将读取</div>
          <ul className="cv-io-list">
            {reads.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="cv-io-arrow" aria-hidden>→</div>
        <div className="cv-io-col">
          <div className="cv-io-col-label">将生成</div>
          <ul className="cv-io-list">
            {writes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="cv-io-actions">
        <button
          type="button"
          className="cv-io-btn secondary"
          disabled={submitted}
          onClick={() => handleChoice(cancelValue)}
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          className="cv-io-btn primary"
          disabled={submitted}
          onClick={() => handleChoice(confirmValue)}
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  );
}
