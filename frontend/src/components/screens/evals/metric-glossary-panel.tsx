/* 可折叠的指标说明面板 */
import { useState } from 'react';
import {
  COMMON_HELP,
  metricsForView,
  PRODUCT_METRICS,
  SKILL_FOUR_DIM,
  type EvalView,
  type MetricDef,
} from './metric-glossary';

function MetricRow({ m }: { m: MetricDef }) {
  return (
    <div className="eval-metric-row">
      <div className="eval-metric-label">{m.label}</div>
      <div className="eval-metric-meaning">{m.meaning}</div>
      <div className="eval-metric-formula">
        <span className="eval-metric-tag">计算</span> {m.formula}
      </div>
      {m.interpret ? (
        <div className="eval-metric-interpret">
          <span className="eval-metric-tag">解读</span> {m.interpret}
        </div>
      ) : null}
    </div>
  );
}

export function MetricGlossaryPanel({ view }: { view: EvalView }) {
  const [open, setOpen] = useState(false);
  const items = view === 'skill'
    ? [...SKILL_FOUR_DIM, ...Object.values(PRODUCT_METRICS)]
    : metricsForView(view);

  return (
    <div className="jn-panel eval-glossary-panel" style={{ marginBottom: 14 }}>
      <button
        type="button"
        className="eval-glossary-toggle"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
      >
        <span className="eval-glossary-title">📖 指标说明（计算方法与含义）</span>
        <span className="eval-glossary-chevron">{open ? '收起 ▲' : '展开 ▼'}</span>
      </button>
      {!open ? (
        <p className="eval-glossary-teaser">
          初次使用建议展开：含四维得分、产物字段、自纠率、延迟/成本数据源及基线阈值说明。
          权威定义见仓库 <code>agent/evals/METRICS.md</code>。
        </p>
      ) : (
        <div className="eval-glossary-body">
          {view !== 'common' && (
            <div className="jn-hint" style={{ marginTop: 0, borderTop: 'none', paddingTop: 0 }}>
              当前 Tab：{view === 'skill' ? 'SKILL 测评' : view === 'tools' ? '工具测评' : 'Langfuse 大盘'}
            </div>
          )}
          {items.map(m => (
            <MetricRow key={m.label} m={m} />
          ))}
        </div>
      )}
    </div>
  );
}

/** 页顶通用说明（三 tab 共享） */
export function MetricCommonPanel() {
  const [open, setOpen] = useState(false);
  return (
    <div className="eval-glossary-inline">
      <button type="button" className="eval-glossary-link" onClick={() => setOpen(v => !v)}>
        {open ? '收起使用说明' : '如何使用评测中心？'}
      </button>
      {open && (
        <div className="eval-glossary-body eval-glossary-body--compact">
          {COMMON_HELP.map(m => (
            <MetricRow key={m.label} m={m} />
          ))}
        </div>
      )}
    </div>
  );
}
