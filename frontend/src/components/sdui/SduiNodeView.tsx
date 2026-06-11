/**
 * SduiNodeView — SDUI 树递归渲染器
 *
 * 分发策略：
 *  - 布局节点（Stack/Card/Row）：inline 实现
 *  - 复杂节点（Stepper/DonutChart/ArtifactGrid/HITL）：独立组件
 *  - 简单叶节点（Text/Badge/Button/Statistic）：inline 实现
 *  - 未知节点：降级提示
 */
import React, { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { SduiNode, SduiStatisticRowItem } from '@/lib/sdui';
import { stableChildKey } from '@/lib/sduiKeys';
import { Badge, Button, Panel } from '@/components/primitives';
import { SduiStepper } from './SduiStepper';
import { SduiDonutChart } from './SduiDonutChart';
import { SduiArtifactGrid } from './SduiArtifactGrid';
import { SduiFilePicker } from './SduiFilePicker';
import { SduiChoiceCard } from './SduiChoiceCard';
import { SduiDataTable } from './SduiDataTable';
import { useSduiRuntime } from './SduiContext';

// ── Sub-components (must be real components for hook rules) ────────────────────

function UnknownNode({ type }: { type: string }) {
  return (
    <div style={{
      padding: '6px 10px', borderRadius: 'var(--radius-md)',
      border: '1px solid var(--amber-100)', background: 'var(--amber-50)',
      fontSize: 'var(--text-xs)', color: 'var(--amber-700)',
    }}>
      未知节点：<code style={{ fontFamily: 'var(--font-mono)' }}>{type}</code>
    </div>
  );
}

// StatusIntent → left 3px bar accent color (single color outlet; hero numbers always zinc-900)
const STAT_ACCENT: Record<string, string> = {
  accent: '#3551d8',   // brand
  brand:  '#3551d8',
  success: '#10b981',
  warning: '#d97706',
  error:   '#dc2626',
  danger:  '#dc2626',
  subtle:  '#94a3b8',
};

function StatRow({ items }: { items: SduiStatisticRowItem[] }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(108px, 1fr))',
      gap: '10px',
      flex: 1,
    }}>
      {items.map((item, i) => {
        const accent = item.color ? (STAT_ACCENT[item.color] ?? '#94a3b8') : '#94a3b8';
        // 错开入场：每个 KPI 卡延迟 50ms * i，让统计数字依次亮起而非整块跳出
        const staggerDelay = `${Math.min(i, 6) * 0.05}s`;
        return (
          <div key={i} style={{
            position: 'relative',
            background: 'var(--c-surface)',
            border: '1px solid var(--c-border)',
            borderRadius: 'var(--r-md)',
            boxShadow: 'var(--shadow-xs)',
            padding: '12px 16px 12px 20px',
            overflow: 'hidden',
            animation: `sdui-node-in .22s cubic-bezier(.2,.65,.4,1) ${staggerDelay} both`,
          }}>
            {/* Left 3px accent bar — sole color outlet (inset + rounded, v4 .d-stat) */}
            <div style={{ position: 'absolute', left: 0, top: 11, bottom: 11, width: 3, borderRadius: '0 999px 999px 0', background: accent }} />
            <div style={{
              fontSize: 'var(--fs-11)', color: 'var(--c-text-muted)',
              textTransform: 'uppercase', letterSpacing: '.05em', fontWeight: 500,
              lineHeight: 1.2, minHeight: 24, display: 'flex', alignItems: 'flex-start',
            }}>
              {item.title}
            </div>
            <div style={{
              fontFamily: 'var(--font-sans)', fontSize: 'var(--fs-24)', fontWeight: 600,
              color: 'var(--c-text)',
              marginTop: 5, letterSpacing: '-.01em', lineHeight: 1.1,
              fontVariantNumeric: 'tabular-nums',
              display: 'flex', alignItems: 'baseline', gap: 3,
            }}>
              {String(item.value)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** GoldenMetrics — 黄金指标卡（v4 .d-gm）：顶部 2px 状态色边 + 状态色数值 + 星标 eyebrow。
 *  区别于 StatRow（中性 KPI），黄金指标用状态色强调「健康度」。 */
const GM_STATUS: Record<string, { top: string; val: string }> = {
  success: { top: 'var(--c-success)', val: 'var(--c-success-text)' },
  warning: { top: 'var(--c-warning)', val: 'var(--c-warning-text)' },
  danger:  { top: 'var(--c-danger)',  val: 'var(--c-danger-text)' },
  error:   { top: 'var(--c-danger)',  val: 'var(--c-danger-text)' },
  accent:  { top: 'var(--c-brand)',   val: 'var(--c-text)' },
  brand:   { top: 'var(--c-brand)',   val: 'var(--c-text)' },
};
function GoldenMetricsCards({ items }: { items: SduiStatisticRowItem[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 'var(--sp-2)' }}>
      {items.map((m, i) => {
        const st = m.color ? (GM_STATUS[m.color] ?? { top: 'var(--c-border-strong)', val: 'var(--c-text)' })
                           : { top: 'var(--c-border-strong)', val: 'var(--c-text)' };
        return (
          <div key={i} style={{
            background: 'var(--c-surface)', border: '1px solid var(--c-border)',
            borderTop: `2px solid ${st.top}`, borderRadius: 'var(--r-md)',
            padding: '13px var(--sp-3)', boxShadow: 'var(--shadow-xs)',
            animation: `sdui-node-in .22s cubic-bezier(.2,.65,.4,1) ${Math.min(i, 6) * 0.05}s both`,
          }}>
            <div style={{
              fontSize: 'var(--fs-11)', textTransform: 'uppercase', letterSpacing: '.05em',
              color: 'var(--c-text-muted)', display: 'flex', alignItems: 'center', gap: 5,
            }}>
              <span style={{ color: 'var(--c-brand)', fontSize: 10 }}>★</span>{m.title}
            </div>
            <div style={{
              fontSize: 'var(--fs-24)', fontWeight: 600, letterSpacing: '-.01em', lineHeight: 1.1,
              color: st.val, marginTop: 8, fontVariantNumeric: 'tabular-nums',
            }}>
              {String(m.value)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Risk-level dot colors (first-column semantic indicator)
const RISK_DOT: Record<string, string> = {
  '高': '#dc2626',  // danger
  '中': '#d97706',  // warning
  '低': '#10b981',  // success
};

// 数字单元格判定：纯数字 / 百分比 / 带单位数字 → 右对齐 + tabular-nums
const NUMERIC_CELL = /^[¥$]?\s*-?[\d,]+(\.\d+)?\s*(%|台|个|条|组|柜|项|kW|W|GB|TB)?$/;

function SduiTable({ headers, rows }: { headers?: string[]; rows: string[][] }) {
  return (
    <div className="sdui-tbl" style={{
      border: '1px solid var(--c-border)', borderRadius: 'var(--r-md)',
      overflow: 'hidden', background: 'var(--c-surface)', boxShadow: 'var(--shadow-xs)',
    }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--fs-13)' }}>
        {headers && (
          <thead>
            <tr>
              {headers.map((h, i) => {
                const numeric = rows.length > 0 && rows.every(r => r[i] === undefined || r[i] === '' || NUMERIC_CELL.test(r[i]));
                return (
                  <th key={i} style={{
                    padding: '10px 12px', textAlign: numeric && i > 0 ? 'right' : 'left',
                    fontSize: 'var(--fs-11)', fontWeight: 600, letterSpacing: '.05em', textTransform: 'uppercase',
                    color: 'var(--c-text-muted)', background: 'var(--c-surface-2)', whiteSpace: 'nowrap',
                    borderBottom: '1px solid var(--c-divider)',
                  }}>
                    {h}
                  </th>
                );
              })}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} style={{ borderBottom: ri < rows.length - 1 ? '1px solid var(--c-divider)' : 'none' }}>
              {row.map((cell, ci) => {
                const dotColor = ci === 0 ? RISK_DOT[cell] : undefined;
                const numeric = ci > 0 && NUMERIC_CELL.test(cell ?? '');
                return (
                  <td key={ci} style={{
                    padding: '10px 12px', verticalAlign: 'top',
                    color: numeric ? 'var(--c-text)' : 'var(--c-text-2)',
                    textAlign: numeric ? 'right' : 'left',
                    fontWeight: numeric ? 600 : 400,
                    fontVariantNumeric: numeric ? 'tabular-nums' : undefined,
                  }}>
                    {dotColor ? (
                      /* Risk level: colored dot + text, no pill badge */
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600, color: 'var(--c-text)' }}>
                        <i style={{ width: 7, height: 7, borderRadius: 2, background: dotColor, display: 'block', flexShrink: 0 }} />
                        {cell}
                      </span>
                    ) : cell}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <div style={{ padding: '14px', textAlign: 'center', color: 'var(--c-text-muted)', fontSize: 'var(--fs-12)' }}>暂无数据</div>
      )}
    </div>
  );
}

function SduiBarChart({ data, valueUnit }: { data?: Array<{ label: string; value: number; color?: string }> | null; valueUnit?: string }) {
  const items = data ?? [];
  const max = Math.max(...items.map(d => d.value), 1);
  const total = items.reduce((s, d) => s + d.value, 0) || 1;
  // Solid fills only — no gradients; brand blue unified to #3551d8
  const BAR_COLORS: Record<string, string> = {
    accent:  '#3551d8',
    brand:   '#3551d8',
    success: '#10b981',
    warning: '#d97706',
    error:   '#dc2626',
    danger:  '#dc2626',
    subtle:  '#94a3b8',
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
      {items.map((d, i) => {
        // Bar width by max ratio; share% only when total differs from max
        const barPct = max > 0 ? (d.value / max) * 100 : 0;
        const sharePct = total > 0 ? Math.round((d.value / total) * 100) : 0;
        return (
          <div key={i}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6 }}>
              {/* Label only — no leading colored dot */}
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>{d.label}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {d.value}{valueUnit ? ` ${valueUnit}` : ''}
                {total > max && (
                  <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 4 }}>({sharePct}%)</span>
                )}
              </span>
            </div>
            <div style={{ height: 8, borderRadius: 999, background: 'var(--zinc-100)', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${barPct}%`,
                background: d.color ? (BAR_COLORS[d.color] ?? d.color) : '#3551d8',
                borderRadius: 999,
                // Ease-out only — no spring overshoot to keep data representation accurate
                transition: 'width .85s cubic-bezier(.22,.61,.36,1)',
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** 将内联 Markdown token 解析为 React 节点（无外部依赖）。
 *  支持：**粗体** · *斜体* · `行内代码` · 其余原样输出 */
function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // 顺序匹配：**bold** | *em* | `code`
  const pattern = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`)/g;
  let last = 0, key = 0, m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[2] !== undefined)      parts.push(<strong key={key++}>{m[2]}</strong>);
    else if (m[3] !== undefined) parts.push(<em key={key++}>{m[3]}</em>);
    else if (m[4] !== undefined) parts.push(
      <code key={key++} style={{ background: 'var(--zinc-100)', padding: '0 3px', borderRadius: 3, fontFamily: 'var(--font-mono)', fontSize: '0.9em' }}>{m[4]}</code>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function SduiMarkdown({ content }: { content: string }) {
  // 整块代码围栏
  const isCode = content.startsWith('```') || (content.startsWith('    ') && content.includes('\n'));
  if (isCode) {
    const cleaned = content.replace(/^```[a-z]*\n?/, '').replace(/\n?```$/, '');
    return (
      <pre style={{ margin: 0, padding: '8px 10px', background: 'var(--zinc-100)', borderRadius: 'var(--radius-md)', fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {cleaned}
      </pre>
    );
  }

  // 逐行解析：有序列表 / 无序列表 / 普通段落
  const lines = content.split('\n');
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i] ?? '';

    // 空行 → 间距
    if (line.trim() === '') {
      if (nodes.length > 0) nodes.push(<div key={`br${i}`} style={{ height: 6 }} />);
      i++; continue;
    }

    // 有序列表：以 "数字." 开头的连续行
    if (/^\d+\.\s+/.test(line)) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i] ?? '')) {
        const cur = lines[i] ?? '';
        const m2 = /^\d+\.\s+(.*)$/.exec(cur);
        items.push(
          <li key={i} style={{ marginBottom: 2 }}>{parseInline(m2?.[1] ?? cur)}</li>
        );
        i++;
      }
      nodes.push(
        <ol key={`ol${i}`} style={{ margin: '2px 0', paddingLeft: 20, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {items}
        </ol>
      );
      continue;
    }

    // 无序列表：以 "- " 或 "· " 开头的连续行
    if (/^[-·•]\s+/.test(line)) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && /^[-·•]\s+/.test(lines[i] ?? '')) {
        const cur = lines[i] ?? '';
        const m2 = /^[-·•]\s+(.*)$/.exec(cur);
        items.push(
          <li key={i} style={{ marginBottom: 2 }}>{parseInline(m2?.[1] ?? cur)}</li>
        );
        i++;
      }
      nodes.push(
        <ul key={`ul${i}`} style={{ margin: '2px 0', paddingLeft: 18, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.6, listStyleType: 'disc' }}>
          {items}
        </ul>
      );
      continue;
    }

    // 普通段落行
    nodes.push(
      <div key={`p${i}`} style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {parseInline(line)}
      </div>
    );
    i++;
  }

  return <div>{nodes}</div>;
}

function SduiKeyValueList({ items }: { items: Array<{ key: string; value: string }> }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {items.map((item, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
          gap: 14, padding: '9px 0',
          borderBottom: i < items.length - 1 ? '1px dashed var(--border)' : 'none',
        }}>
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)', flexShrink: 0 }}>{item.key}</span>
          <span style={{
            fontSize: '12px', color: 'var(--text-primary)', fontWeight: 600,
            textAlign: 'right', fontFamily: 'var(--font-mono)',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// Risk level → 等级色带（对齐 v4 risk-high/mid/low）
const RISK_LEVEL: Record<string, { label: string; color: string; bg: string }> = {
  high: { label: '高', color: '#dc2626', bg: '#fde6e6' },
  mid:  { label: '中', color: '#d97706', bg: '#fdeed6' },
  low:  { label: '低', color: '#b58a0c', bg: '#fbf3d3' },
};

function SduiRiskList({ items, title }: { items: Array<{ title: string; level: string; detail?: string }>; title?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {title && (
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>
      )}
      {items.map((it, i) => {
        const lv = RISK_LEVEL[it.level] ?? { label: it.level, color: '#b58a0c', bg: '#fbf3d3' };
        return (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '11px 13px',
            border: '1px solid var(--border)',
            borderLeft: `3px solid ${lv.color}`,
            borderRadius: 6,
            background: 'var(--surface)',
            // 风险项依次左滑入（最多 8 项参与错开）
            animation: `sdui-stagger .18s ease-out ${Math.min(i, 8) * 0.04}s both`,
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{it.title}</span>
                <span style={{
                  fontSize: '10px', fontWeight: 500, color: lv.color, background: lv.bg,
                  borderRadius: 4, padding: '1px 7px',
                }}>{lv.label}</span>
              </div>
              {it.detail && (
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: 3, lineHeight: 1.5 }}>
                  {it.detail}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SduiSegmentedControl({ segments, caption }: { segments: string[]; caption?: string }) {
  const [active, setActive] = useState(0);
  return (
    <div>
      <div style={{ display: 'inline-flex', background: 'var(--c-bg-soft, #eef2f7)', borderRadius: 6, padding: 3 }}>
        {segments.map((s, i) => (
          <button key={i} onClick={() => setActive(i)} style={{
            padding: '5px 14px', fontSize: 13, border: 'none', borderRadius: 4, cursor: 'pointer',
            background: i === active ? 'var(--surface)' : 'transparent',
            color: i === active ? 'var(--text-primary)' : 'var(--text-tertiary)',
            fontWeight: i === active ? 600 : 400,
            boxShadow: i === active ? 'var(--shadow-xs, 0 1px 2px rgba(15,23,42,.04))' : 'none',
          }}>{s}</button>
        ))}
      </div>
      {caption && <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 10 }}>{caption}</div>}
    </div>
  );
}

function SduiMultiSelect({ options, title }: { options: Array<{ label: string; value?: string }>; title?: string }) {
  const [sel, setSel] = useState<Set<number>>(new Set());
  const toggle = (i: number) => { const n = new Set(sel); if (n.has(i)) n.delete(i); else n.add(i); setSel(n); };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {title && <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {options.map((o, i) => {
          const on = sel.has(i);
          return (
            <button key={i} onClick={() => toggle(i)} style={{
              padding: '6px 12px', fontSize: 13, borderRadius: 999, cursor: 'pointer',
              border: `1px solid ${on ? '#3551d8' : 'var(--border)'}`,
              background: on ? 'var(--c-brand-soft, #eef1fc)' : 'var(--surface)',
              color: on ? 'var(--c-brand-text, #1e34a8)' : 'var(--text-secondary)',
              fontWeight: on ? 600 : 400,
            }}>{on ? '✓ ' : ''}{o.label}</button>
          );
        })}
      </div>
    </div>
  );
}

function SduiSlider({ value, label, min = 0, max = 100, unit }: { value: number; label?: string; min?: number; max?: number; unit?: string }) {
  const [v, setV] = useState(value);
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 9 }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--c-brand-text, #1e34a8)', background: 'var(--c-brand-soft, #eef1fc)', padding: '2px 9px', borderRadius: 4 }}>{v}{unit ?? ''}</span>
      </div>
      <input type="range" min={min} max={max} value={v} onChange={e => setV(Number(e.target.value))} style={{ width: '100%', accentColor: '#3551d8' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-faint, #94a3b8)', marginTop: 6 }}><span>{min}</span><span>{max}</span></div>
    </div>
  );
}

function SduiTabbedTable({ tabs }: { tabs: Array<{ label: string; headers?: string[]; rows: string[][] }> }) {
  const [active, setActive] = useState(0);
  const cur = tabs[active];
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', background: 'var(--surface)' }}>
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 8px', flexWrap: 'wrap' }}>
        {tabs.map((t, i) => (
          <button key={i} onClick={() => setActive(i)} style={{
            padding: '8px 12px', fontSize: 12, border: 'none', background: 'none', cursor: 'pointer',
            color: i === active ? 'var(--c-brand-text, #1e34a8)' : 'var(--text-tertiary)',
            borderBottom: `2px solid ${i === active ? '#3551d8' : 'transparent'}`, marginBottom: -1,
            fontWeight: i === active ? 600 : 400,
          }}>
            {t.label}<span style={{ fontSize: 11, color: 'var(--text-faint, #94a3b8)', marginLeft: 3 }}>{t.rows?.length ?? 0}</span>
          </button>
        ))}
      </div>
      {cur && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          {cur.headers && (
            <thead><tr>{cur.headers.map((h, i) => (
              <th key={i} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)', background: 'var(--c-surface-2)', borderBottom: '1px solid var(--border)' }}>{h}</th>
            ))}</tr></thead>
          )}
          <tbody>{(cur.rows ?? []).map((r, ri) => (
            <tr key={ri}>{r.map((cell, ci) => <td key={ci} style={{ padding: '6px 12px', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>{cell}</td>)}</tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}

function SduiTabs({ tabs }: { tabs: Array<{ label: string; content?: string }> }) {
  const [active, setActive] = useState(0);
  return (
    <div>
      <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--border)' }}>
        {tabs.map((t, i) => (
          <button key={i} onClick={() => setActive(i)} style={{
            border: 0, background: 'transparent', padding: '8px 12px', fontSize: 13, cursor: 'pointer',
            color: i === active ? 'var(--c-brand-text, #1e34a8)' : 'var(--text-tertiary)',
            borderBottom: `2px solid ${i === active ? '#3551d8' : 'transparent'}`,
            marginBottom: -1, fontWeight: 500,
          }}>{t.label}</button>
        ))}
      </div>
      <div style={{ padding: '13px 2px 2px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {tabs[active]?.content}
      </div>
    </div>
  );
}

/** TabGroup — 子节点按页签分组切换。badge 角标 + 后端可引导 activeTab（递归渲染 children）。*/
function SduiTabGroup({ node, pathPrefix }: { node: Extract<SduiNode, { type: 'TabGroup' }>; pathPrefix: string }) {
  const tabs = node.tabs ?? [];
  const initialIdx = () => {
    const i = tabs.findIndex(t => t.id === node.activeTab);
    return i >= 0 ? i : 0;
  };
  const [active, setActive] = useState(initialIdx());
  // 后端引导：activeTab 变化时同步选中（如执行中自动切「进度」页）；
  // 用户点击在两次刷新之间接管本地选择。
  useEffect(() => {
    const i = tabs.findIndex(t => t.id === node.activeTab);
    if (i >= 0) setActive(i);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node.activeTab]);
  const idx = Math.min(active, Math.max(tabs.length - 1, 0));
  const cur = tabs[idx];
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', background: 'var(--surface)' }}>
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 8px', flexWrap: 'wrap' }}>
        {tabs.map((t, i) => {
          const on = i === idx;
          const hasBadge = t.badge != null && t.badge !== '';
          return (
            <button key={t.id ?? i} onClick={() => setActive(i)} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '9px 13px', fontSize: 13, border: 'none', background: 'none', cursor: 'pointer',
              color: on ? 'var(--c-brand-text, #1e34a8)' : 'var(--text-tertiary)',
              borderBottom: `2px solid ${on ? '#3551d8' : 'transparent'}`, marginBottom: -1,
              fontWeight: on ? 600 : 400,
            }}>
              {t.label}
              {hasBadge && (
                <span style={{
                  fontSize: 11, fontWeight: 600, lineHeight: 1.4, minWidth: 16, textAlign: 'center',
                  padding: '1px 6px', borderRadius: 999,
                  color: on ? '#fff' : 'var(--text-tertiary)',
                  background: on ? '#3551d8' : 'var(--c-bg-soft, #eef2f7)',
                }}>{String(t.badge)}</span>
              )}
            </button>
          );
        })}
      </div>
      <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 14 }}>
        {(cur?.children ?? []).map((child, i) => {
          const seg = stableChildKey(child, i, `${pathPrefix}.${cur?.id ?? idx}`);
          return <SduiNodeView key={seg} node={child} pathPrefix={seg} />;
        })}
      </div>
    </div>
  );
}

function SduiAccordion({ items }: { items: Array<{ title: string; body: string }> }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map((it, i) => {
        const isOpen = open === i;
        return (
          <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)', overflow: 'hidden' }}>
            <div onClick={() => setOpen(isOpen ? null : i)} style={{
              display: 'flex', alignItems: 'center', gap: 9, padding: '10px 12px', cursor: 'pointer',
              fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', userSelect: 'none',
            }}>
              {it.title}
              <span style={{ marginLeft: 'auto', color: 'var(--text-tertiary)', transform: isOpen ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }}>›</span>
            </div>
            {isOpen && (
              <div style={{ padding: '10px 12px 12px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, borderTop: '1px solid var(--border)' }}>
                {it.body}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** 可折叠卡（Card.collapsible）：卡头变可点击折叠开关，把次要明细（如 micro-step Stepper）收起。
 *  样式与 Panel 一致（白面板 + border + shadow-sm），单独成组件以便用 useState。 */
function CollapsibleCard({ title, defaultCollapsed, children }: {
  title: string; defaultCollapsed?: boolean; children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(!!defaultCollapsed);
  return (
    <div style={{
      background: 'var(--c-surface)', border: '1px solid var(--c-border)',
      borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-sm)', overflow: 'hidden',
      animation: 'sdui-node-in .28s cubic-bezier(.2,.65,.4,1) both',
    }}>
      <div
        onClick={() => setCollapsed(c => !c)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none',
          padding: 'var(--sp-3) var(--pad-panel)',
          borderBottom: collapsed ? 'none' : '1px solid var(--c-divider)',
        }}
      >
        <span style={{ fontWeight: 600, fontSize: 'var(--fs-13)', color: 'var(--c-text)' }}>{title}</span>
        <span style={{
          marginLeft: 'auto', color: 'var(--c-text-faint)', fontSize: 'var(--fs-12)',
          transform: collapsed ? 'none' : 'rotate(90deg)', transition: 'transform .2s',
        }}>▸</span>
      </div>
      {!collapsed && <div style={{ padding: 'var(--pad-panel)' }}>{children}</div>}
    </div>
  );
}

type HitlTextProps = {
  node: Extract<SduiNode, { type: 'HitlTextInput' }>;
  onSubmit: (value: string, stepId?: string) => void;
};
function HitlTextInput({ node, onSubmit }: HitlTextProps) {
  const [val, setVal] = useState(node.defaultValue ?? '');
  const [submitted, setSubmitted] = useState(false);
  const [focused, setFocused] = useState(false);
  const canSubmit = val.trim().length > 0;
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {/* hitl-note: brand left-bar info banner */}
      {(node.title || node.helpText) && (
        <div style={{
          display: 'flex', gap: 8, alignItems: 'flex-start',
          borderLeft: '3px solid #3551d8',
          background: 'var(--c-surface-2)',
          padding: '10px 12px',
          borderRadius: '0 6px 6px 0',
          fontSize: '11px', lineHeight: 1.5,
          marginBottom: 12,
        }}>
          <div>
            {node.title && (
              <div style={{ fontWeight: 600, fontSize: '12px', color: 'var(--text-secondary)', marginBottom: node.helpText ? 2 : 0 }}>
                {node.title}
              </div>
            )}
            {node.helpText && (
              <div style={{ color: 'var(--text-tertiary)' }}>{node.helpText}</div>
            )}
          </div>
        </div>
      )}
      <textarea
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        disabled={submitted}
        placeholder={node.placeholder}
        rows={node.rows ?? 3}
        style={{
          width: '100%', padding: '11px 12px',
          borderRadius: 'var(--radius-md)',
          border: `1.5px solid ${focused ? '#3551d8' : 'var(--border)'}`,
          boxShadow: focused ? '0 0 0 3px rgba(53,81,216,.12)' : 'none',
          outline: 'none',
          fontSize: '12.5px', resize: 'vertical', minHeight: 88,
          lineHeight: 1.55, fontFamily: 'var(--font-sans)',
          color: 'var(--text-primary)',
          background: submitted ? 'var(--zinc-50)' : 'var(--surface)',
          transition: 'border-color .15s, box-shadow .15s',
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
        {!submitted ? (
          <button
            onClick={() => { setSubmitted(true); onSubmit(val, node.stepId); }}
            disabled={!canSubmit}
            style={{
              padding: '6px 14px', fontSize: 'var(--text-sm)', fontWeight: 600,
              borderRadius: 'var(--radius-md)', border: 'none',
              background: canSubmit ? '#3551d8' : 'var(--zinc-200)',
              color: canSubmit ? '#fff' : 'var(--text-tertiary)',
              cursor: canSubmit ? 'pointer' : 'not-allowed',
            }}
          >
            {node.submitLabel ?? '提交'}
          </button>
        ) : (
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/>
            </svg>
            已提交
          </span>
        )}
        <span style={{ fontSize: '10.5px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          {val.length} 字
        </span>
      </div>
    </div>
  );
}

// ── Gap token → px ────────────────────────────────────────────────────────────

const GAP: Record<string, number> = { none: 0, xs: 6, sm: 10, md: 14, lg: 20, xl: 28 };
const COLOR_MAP: Record<string, string> = {
  success: 'var(--green-600)', warning: '#d97706',
  error: 'var(--red-600)', accent: 'var(--blue-600)', subtle: 'var(--text-tertiary)',
};
const BADGE_TONE: Record<string, 'default' | 'green' | 'amber' | 'red'> = {
  success: 'green', warning: 'amber', danger: 'red', default: 'default',
};
const BTN_VARIANT: Record<string, 'primary' | 'secondary' | 'ghost'> = {
  primary: 'primary', secondary: 'secondary', ghost: 'ghost', outline: 'secondary',
};

// ── Main dispatcher ────────────────────────────────────────────────────────────

type Props = { node: SduiNode; pathPrefix?: string };

export function SduiNodeView({ node, pathPrefix = 'root' }: Props) {
  const { onAction, onChoiceSubmit } = useSduiRuntime();

  const renderChildren = (children: SduiNode[] | undefined) =>
    children?.map((child, i) => {
      const seg = stableChildKey(child, i, pathPrefix);
      return <SduiNodeView key={seg} node={child} pathPrefix={seg} />;
    });

  const inner = (() => {
    switch (node.type) {

    // ── Layout ──

    case 'Stack':
      return (
        <div style={{
          display: 'flex', flexDirection: 'column',
          gap: GAP[node.gap ?? 'md'] ?? 14,
          justifyContent: node.justify === 'between' ? 'space-between' : node.justify === 'center' ? 'center' : node.justify === 'end' ? 'flex-end' : 'flex-start',
        }}>
          {renderChildren(node.children)}
        </div>
      );

    case 'Card': {
      const rawTone = (node as { tone?: string }).tone;
      const panelTone =
        rawTone === 'danger'  ? 'red'   :
        rawTone === 'warning' ? 'amber' :
        rawTone === 'info'    ? 'blue'  :
        rawTone === 'success' ? 'green' : 'default';
      // Card 是最主要的 section 容器：入场淡入 + 上移。
      // 依赖 React key 机制：id 稳定的 Card（header/stepper/golden-metrics）不会 remount，
      // 不会重复动画；新出现的 Card（risk-top-alert/hitl-card）会 remount → 触发动画。
      const headerAction = (node as { headerAction?: { label: string; variant?: string; action: import('@/lib/sdui').SduiAction } }).headerAction;
      // 可折叠卡：把次要明细（如 micro-step Stepper）收起，减轻信息墙（需 title）。
      if (node.collapsible && node.title) {
        return (
          <CollapsibleCard title={node.title} defaultCollapsed={node.defaultCollapsed}>
            {renderChildren(node.children)}
          </CollapsibleCard>
        );
      }
      return (
        <Panel title={node.title ?? undefined} tone={panelTone}
               style={{ animation: 'sdui-node-in .28s cubic-bezier(.2,.65,.4,1) both' }}>
          {headerAction && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              <button
                onClick={() => onAction(headerAction.action)}
                style={{ padding: '5px 12px', fontSize: 12, fontWeight: 500, borderRadius: 4, cursor: 'pointer',
                  border: headerAction.variant === 'primary' ? '1px solid #3551d8' : '1px solid var(--border)',
                  background: headerAction.variant === 'primary' ? '#3551d8' : 'var(--surface)',
                  color: headerAction.variant === 'primary' ? '#fff' : 'var(--text-secondary)' }}
              >{headerAction.label}</button>
            </div>
          )}
          {renderChildren(node.children)}
        </Panel>
      );
    }

    case 'Row': {
      const gap = GAP[node.gap ?? 'md'] ?? 14;
      const alignMap: Record<string, string> = { start: 'flex-start', end: 'flex-end', stretch: 'stretch', baseline: 'baseline', center: 'center' };
      const justMap: Record<string, string> = { between: 'space-between', end: 'flex-end', center: 'center', around: 'space-around', start: 'flex-start' };
      return (
        <div style={{
          display: 'flex', flexDirection: 'row', gap,
          alignItems: alignMap[node.align ?? 'center'] ?? 'center',
          justifyContent: justMap[node.justify ?? 'start'] ?? 'flex-start',
          flexWrap: node.wrap ? 'wrap' : 'nowrap',
        }}>
          {node.children?.map((child, i) => {
            const seg = stableChildKey(child, i, pathPrefix);
            const flex = (child as { flex?: number }).flex;
            return (
              <div key={seg} style={{ flex: typeof flex === 'number' ? `${flex} ${flex} 0%` : undefined, minWidth: 0 }}>
                <SduiNodeView node={child} pathPrefix={seg} />
              </div>
            );
          })}
        </div>
      );
    }

    case 'Divider':
      // 带 label = 分节眉题（eyebrow 大写小字 + 延伸细线），用于把同区多张卡分组。
      if (node.label) {
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', margin: 'var(--sp-1) 0 0' }}>
            <span style={{
              fontSize: 'var(--fs-11)', fontWeight: 600, letterSpacing: '.06em',
              textTransform: 'uppercase', color: 'var(--c-text-muted)', whiteSpace: 'nowrap',
            }}>{node.label}</span>
            <span style={{ flex: 1, height: 1, background: 'var(--c-divider)' }} />
          </div>
        );
      }
      return (
        <div style={
          node.orientation === 'vertical'
            ? { width: 1, alignSelf: 'stretch', background: 'var(--border)' }
            : { height: 1, background: 'var(--border)', margin: '2px 0' }
        } />
      );

    case 'Skeleton': {
      const v = node.variant ?? 'rect';
      // shimmer：左→右扫光，宽度 400px 的高光带循环移动
      const shimmer: React.CSSProperties = {
        background: 'linear-gradient(90deg, var(--zinc-100) 25%, var(--zinc-50) 50%, var(--zinc-100) 75%)',
        backgroundSize: '400px 100%',
        animation: 'sdui-shimmer 1.5s ease-in-out infinite',
      };
      if (v === 'text') {
        const n = Math.min(8, Math.max(1, node.lines ?? 3));
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Array.from({ length: n }, (_, i) => (
              // 最后一行短 30%（模拟段落末行）
              <div key={i} style={{ height: 12, borderRadius: 4, width: i === n - 1 ? '70%' : '100%', ...shimmer }} />
            ))}
          </div>
        );
      }
      return <div style={{ height: v === 'row' ? 40 : 80, borderRadius: 8, ...shimmer }} />;
    }

    // ── Text ──

    case 'Text': {
      const isHeading = node.variant === 'heading';
      return (
        <span style={{
          fontSize: isHeading ? 'var(--text-xl)' : node.variant === 'caption' ? 'var(--text-xs)' : 'var(--text-sm)',
          fontWeight: isHeading ? 700 : 400,
          fontFamily: node.variant === 'mono' ? 'var(--font-mono)' : undefined,
          color: node.color ? (COLOR_MAP[node.color] ?? 'var(--text-primary)') : 'var(--text-primary)',
          display: 'block',
        }}>
          {node.content}
        </span>
      );
    }

    case 'Markdown':
      return <SduiMarkdown content={node.content} />;

    // ── Display ──

    case 'Badge':
      return <Badge tone={BADGE_TONE[node.tone ?? 'default'] ?? 'default'}>{node.text}</Badge>;

    case 'Statistic':
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ fontSize: 'var(--fs-11)', color: 'var(--c-text-muted)', textTransform: 'uppercase', letterSpacing: '.05em' }}>{node.title}</div>
          <div style={{
            fontSize: 'var(--fs-24)', fontWeight: 600, letterSpacing: '-.01em', lineHeight: 1.1,
            fontVariantNumeric: 'tabular-nums',
            color: node.color ? (COLOR_MAP[node.color] ?? 'var(--c-text)') : 'var(--c-text)',
          }}>
            {String(node.value)}
          </div>
        </div>
      );

    case 'StatisticRow':
      return <StatRow items={node.items} />;

    case 'KeyValueList':
      return <SduiKeyValueList items={node.items} />;

    case 'Table':
      return <SduiTable headers={node.headers} rows={node.rows} />;

    // ── Interactive ──

    case 'Button': {
      const v = BTN_VARIANT[node.variant ?? 'primary'] ?? 'primary';
      return (
        <Button variant={v} size="sm" onClick={() => onAction(node.action)}>
          {node.label}
        </Button>
      );
    }

    case 'Link': {
      const href = node.href;
      return (
        <a
          href={href}
          onClick={!href && node.action ? (e) => { e.preventDefault(); onAction(node.action!); } : undefined}
          style={{ fontSize: 'var(--text-sm)', color: 'var(--blue-600)', textDecoration: 'underline', cursor: 'pointer' }}
        >
          {node.label}
        </a>
      );
    }

    // ── Charts ──

    case 'Stepper':
      return <SduiStepper steps={node.steps} orientation={node.orientation} />;

    case 'DonutChart':
      return <SduiDonutChart segments={node.segments} centerLabel={node.centerLabel} centerValue={node.centerValue} />;

    case 'BarChart':
      return <SduiBarChart data={node.data} valueUnit={node.valueUnit} />;

    case 'GoldenMetrics': {
      const items: SduiStatisticRowItem[] = (node.metrics ?? []).map(m => ({
        title: String(m.label ?? ''),
        value: String(m.value ?? ''),
        color: m.color as SduiStatisticRowItem['color'],
      }));
      return <GoldenMetricsCards items={items} />;
    }

    // ── v1.1 display nodes ──

    case 'Alert': {
      // Tone-specific semantic colors; line SVG icons replace emoji
      type AlertStyle = { bg: string; border: string; titleColor: string; textColor: string; iconColor: string };
      const ALERT_STYLE: Record<string, AlertStyle> = {
        info:    { bg: 'var(--c-info-soft)',    border: 'var(--c-brand-line)', titleColor: 'var(--c-info-text)',    textColor: 'var(--c-info-text)',    iconColor: 'var(--c-brand)' },
        success: { bg: 'var(--c-success-soft)', border: '#bfe9d3',             titleColor: 'var(--c-success-text)', textColor: 'var(--c-success-text)', iconColor: 'var(--c-success)' },
        warning: { bg: 'var(--c-warning-soft)', border: '#f1d79a',             titleColor: 'var(--c-warning-text)', textColor: 'var(--c-warning-text)', iconColor: 'var(--c-warning)' },
        error:   { bg: 'var(--c-danger-soft)',  border: '#f6c6c6',             titleColor: 'var(--c-danger-text)',  textColor: 'var(--c-danger-text)',  iconColor: 'var(--c-danger)' },
      };
      // SVG path content per tone (stroke icon, currentColor)
      const ALERT_SVG: Record<string, ReactNode> = {
        info:    (<><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></>),
        success: (<><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></>),
        warning: (<><path d="M12 4 21 19H3z"/><path d="M12 10v3.5"/><path d="M12 16.5h.01"/></>),
        error:   (<><path d="M8 3h8l5 5v8l-5 5H8l-5-5V8z"/><path d="M15 9l-6 6M9 9l6 6"/></>),
      };
      const tone = (node.tone ?? 'info') as string;
      const _alertStyle = ALERT_STYLE[tone] ?? ALERT_STYLE['info'];
      const s: AlertStyle = _alertStyle ?? { bg: 'var(--c-info-soft)', border: 'var(--c-brand-line)', titleColor: 'var(--c-info-text)', textColor: 'var(--c-info-text)', iconColor: 'var(--c-brand)' };
      return (
        <div style={{
          display: 'flex', gap: 10, alignItems: 'flex-start',
          borderRadius: 'var(--radius-lg)',
          padding: '11px 13px',
          background: s.bg,
          border: `1px solid ${s.border}`,
          // Alert 从上方落下：高风险横幅出现时更有紧迫感
          animation: 'sdui-alert-in .24s cubic-bezier(.2,.65,.4,1) both',
        }}>
          {/* Line SVG icon instead of emoji */}
          <span style={{ flexShrink: 0, color: s.iconColor, marginTop: 1, display: 'flex' }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {ALERT_SVG[tone] ?? ALERT_SVG.info}
            </svg>
          </span>
          <div>
            {node.title && (
              <div style={{ fontWeight: 600, fontSize: 'var(--fs-13)', color: s.titleColor, lineHeight: 1.4, marginBottom: 2 }}>
                {node.title}
              </div>
            )}
            <div style={{ fontSize: 'var(--fs-12)', color: s.textColor, lineHeight: 1.55 }}>
              {node.message}
            </div>
          </div>
        </div>
      );
    }

    case 'Timeline': {
      // Double-ring dot: inner fill + outer ring via box-shadow
      const TL_DOT_COLOR: Record<string, string> = {
        default: 'var(--c-text-faint)', success: 'var(--c-success)', warning: 'var(--c-warning)', error: 'var(--c-danger)',
      };
      const TL_RING_COLOR: Record<string, string> = {
        default: 'var(--c-border-strong)', success: 'var(--c-success-soft)', warning: 'var(--c-warning-soft)', error: 'var(--c-danger-soft)',
      };
      const evts = node.events ?? [];
      return (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {evts.map((ev, i) => {
            const isLast = i === evts.length - 1;
            const tone = (ev.tone ?? 'default') as string;
            const dotColor = TL_DOT_COLOR[tone] ?? TL_DOT_COLOR.default;
            const ringColor = TL_RING_COLOR[tone] ?? TL_RING_COLOR.default;
            return (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '14px 1fr', gap: 13,
                position: 'relative', paddingBottom: isLast ? 0 : 15,
                // 错开入场：事件依次从左滑入，最多 8 项参与错开
                animation: `sdui-stagger .2s ease-out ${Math.min(i, 8) * 0.05}s both`,
              }}>
                {/* Rail: double-ring dot + connector line */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div style={{
                    width: 10, height: 10, borderRadius: '50%', marginTop: 3,
                    flexShrink: 0, zIndex: 2,
                    background: dotColor,
                    boxShadow: `0 0 0 3px var(--surface), 0 0 0 4px ${ringColor}`,
                  }} />
                  {!isLast && (
                    <div style={{ width: 2, flex: 1, minHeight: 10, background: 'var(--zinc-200)', marginTop: 3, borderRadius: 1 }} />
                  )}
                </div>
                {/* Content */}
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', fontWeight: 500, lineHeight: 1.4 }}>
                    {ev.label}
                  </div>
                  {ev.time && (
                    <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>
                      {ev.time}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    case 'NumberCard': {
      // KPI 大数字弹入：轻弹簧感（scale 0.88 → 1.015 → 1）
      // Top 3px semantic gradient bar by tone; hero number always zinc-900
      // 顶部 3px 语义色条（v4 克制：实色 token，不再用渐变）
      const NC_BAR: Record<string, string> = {
        accent:  'var(--c-brand)', brand: 'var(--c-brand)',
        success: 'var(--c-success)', warning: 'var(--c-warning)',
        error:   'var(--c-danger)', danger: 'var(--c-danger)',
        subtle:  'var(--c-border-strong)',
      };
      const DELTA_COLOR: Record<string, string> = {
        up: 'var(--c-success-text)', down: 'var(--c-danger-text)', neutral: 'var(--c-text-muted)',
      };
      // SVG chevron paths for delta direction
      const DELTA_SVG: Record<string, ReactNode> = {
        up:      (<><path d="M3 17l6-6 4 4 8-8"/><path d="M16 7h5v5"/></>),
        down:    (<><path d="M3 7l6 6 4-4 8 8"/><path d="M16 17h5v-5"/></>),
        neutral: (<path d="M5 12h14"/>),
      };
      const dir = (node.deltaDir ?? 'neutral') as string;
      const barColor = NC_BAR[(node.tone ?? 'subtle') as string] ?? NC_BAR.subtle;
      return (
        <div style={{
          position: 'relative',
          padding: '15px 14px 13px',
          borderRadius: 'var(--r-md)',
          background: 'var(--c-surface)',
          border: '1px solid var(--c-border)',
          boxShadow: 'var(--shadow-xs)',
          overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
          animation: 'sdui-pop .32s cubic-bezier(.2,.65,.4,1) both',
        }}>
          {/* Top 3px semantic bar — sole color outlet */}
          <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 3, background: barColor }} />
          <div style={{ fontSize: 'var(--fs-11)', fontWeight: 500, letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--c-text-muted)' }}>
            {node.label}
          </div>
          {/* Hero value: sans + tabular-nums（与 StatRow/GoldenMetrics 一致） */}
          <div style={{
            fontFamily: 'var(--font-sans)', fontSize: 'var(--fs-30)', fontWeight: 600,
            letterSpacing: '-.01em', color: 'var(--c-text)', fontVariantNumeric: 'tabular-nums',
            margin: '8px 0 7px', lineHeight: 1,
            display: 'flex', alignItems: 'baseline', gap: 3,
          }}>
            {String(node.value)}
          </div>
          {node.delta && (
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 700,
              color: DELTA_COLOR[dir] ?? DELTA_COLOR.neutral,
            }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                {DELTA_SVG[dir] ?? DELTA_SVG.neutral}
              </svg>
              {node.delta}
            </div>
          )}
        </div>
      );
    }

    case 'PlaneMatrix': {
      // 平面矩阵：N 个网络平面 × 规划状态。按 group 聚拢，每格 = 状态点 + 平面名 + 角标。
      const PM_DOT: Record<string, string> = {
        done: 'var(--c-success)', running: 'var(--c-warning)', pending: 'var(--c-border-strong)', error: 'var(--c-danger)',
      };
      const PM_LABEL: Record<string, string> = {
        done: 'var(--c-text)', running: 'var(--c-warning-text)',
        pending: 'var(--c-text-muted)', error: 'var(--c-danger)',
      };
      const cells = node.cells ?? [];
      // 按首次出现顺序分组
      const groups: string[] = [];
      for (const c of cells) {
        const g = c.group ?? '';
        if (!groups.includes(g)) groups.push(g);
      }
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {groups.map((g) => {
            const items = cells.filter((c) => (c.group ?? '') === g);
            return (
              <div key={g || '_'}>
                {g && (
                  <div style={{
                    fontSize: '10px', fontWeight: 500, letterSpacing: '.05em',
                    textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 7,
                  }}>
                    {g}
                  </div>
                )}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: node.columns
                    ? `repeat(${node.columns}, 1fr)`
                    : 'repeat(auto-fill, minmax(150px, 1fr))',
                  gap: 8,
                }}>
                  {items.map((c, i) => {
                    const st = c.status ?? 'pending';
                    return (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '9px 11px',
                        border: '1px solid var(--border)', borderRadius: 8,
                        background: st === 'pending' ? 'var(--c-surface-2)' : 'var(--surface)',
                      }}>
                        <span style={{
                          width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                          background: PM_DOT[st] ?? PM_DOT.pending,
                          boxShadow: st === 'done' ? '0 0 0 3px rgba(16,185,129,.14)'
                            : st === 'running' ? '0 0 0 3px rgba(53,81,216,.14)' : 'none',
                          animation: st === 'running' ? 'clawStepperPulse 1.4s ease-in-out infinite' : 'none',
                        }} />
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{
                            fontSize: '12px', fontWeight: 500, lineHeight: 1.3,
                            color: PM_LABEL[st] ?? 'var(--text-primary)',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}>
                            {c.label}
                          </div>
                          {c.note && (
                            <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 1 }}>
                              {c.note}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    // ── Business ──

    case 'RiskList':
      return <SduiRiskList items={node.items} title={node.title} />;

    // ── Tier B (v4) ──

    case 'EmptyState':
      return (
        <div style={{ textAlign: 'center', padding: '18px 12px', color: 'var(--text-tertiary)' }}>
          <div style={{
            width: 42, height: 42, margin: '0 auto', borderRadius: 6,
            background: 'var(--c-bg-soft, #eef2f7)', display: 'grid', placeItems: 'center',
            fontSize: 18, color: 'var(--text-tertiary)',
          }}>
            {node.icon ?? '○'}
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginTop: 11 }}>{node.title}</div>
          {node.subtitle && <div style={{ fontSize: 12, marginTop: 4 }}>{node.subtitle}</div>}
        </div>
      );

    case 'Spinner': {
      // v4：默认 = 琥珀（进行中语义）；brand 变体 = 品牌蓝（仅当语义确为「AI 动作」时）
      const spinColor = node.tone === 'brand' ? 'var(--c-brand)' : 'var(--c-warning)';
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9, fontSize: 'var(--fs-13)', color: 'var(--c-text-2)' }}>
          <i style={{
            width: 18, height: 18, borderRadius: '50%', display: 'block',
            border: '2.5px solid var(--c-bg-soft)', borderTopColor: spinColor,
            animation: 'spin .8s linear infinite',
          }} />
          {node.label}
        </span>
      );
    }

    case 'ProgressBar': {
      const PB_FILL: Record<string, string> = {
        success: 'var(--c-success)', warning: 'var(--c-warning)', danger: 'var(--c-danger)',
      };
      const PB_TONE: Record<string, string> = {
        success: 'var(--c-success-text)', warning: 'var(--c-warning-text)', danger: 'var(--c-danger-text)',
      };
      const v = Math.max(0, Math.min(100, node.value));
      const fill = node.tone ? (PB_FILL[node.tone] ?? 'var(--c-brand)') : 'var(--c-brand)';
      const pctColor = node.tone ? (PB_TONE[node.tone] ?? 'var(--c-text)') : 'var(--c-text)';
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', fontSize: 'var(--fs-12)' }}>
            <span style={{ color: 'var(--c-text-2)' }}>{node.label}</span>
            <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: pctColor }}>{v}%</span>
          </div>
          <div style={{ height: 8, borderRadius: 'var(--r-pill)', background: 'var(--c-bg-soft)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${v}%`, background: fill, borderRadius: 'inherit', transition: 'width .5s, background-color .25s' }} />
          </div>
        </div>
      );
    }

    case 'Banner': {
      const isBrand = (node.tone ?? 'brand') === 'brand';
      return (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px',
          borderRadius: 'var(--radius-md)', fontSize: 13,
          background: isBrand ? 'var(--c-brand-soft, #eef1fc)' : 'var(--c-warning-soft, #fdf2dd)',
          color: isBrand ? 'var(--c-brand-text, #1e34a8)' : 'var(--c-warning-text, #9a5b08)',
          border: `1px solid ${isBrand ? 'var(--c-brand-line, #c7d0f5)' : '#f1d79a'}`,
        }}>
          {node.title && <strong style={{ fontWeight: 600 }}>{node.title}</strong>}
          <span>{node.message}</span>
        </div>
      );
    }

    case 'CodeBlock':
      return (
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--surface)' }}>
          {node.filename && (
            <div style={{ padding: '6px 12px', background: 'var(--c-surface-2)', borderBottom: '1px solid var(--border)', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
              {node.filename}
            </div>
          )}
          <pre style={{ margin: 0, padding: '11px 12px', fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.65, color: 'var(--text-primary)', overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {node.code}
          </pre>
        </div>
      );

    case 'LogStream': {
      const LOG_COLOR: Record<string, string> = { ok: '#0a7d46', warn: '#9a5b08', error: '#a31919', info: '#1747b8' };
      return (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '10px 12px', fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.75, maxHeight: 180, overflow: 'auto' }}>
          {(node.lines ?? []).map((ln, i) => (
            <div key={i} style={{ display: 'flex', gap: 9 }}>
              {ln.time && <span style={{ color: 'var(--text-tertiary)', fontVariantNumeric: 'tabular-nums' }}>{ln.time}</span>}
              <span style={{ color: ln.level ? (LOG_COLOR[ln.level] ?? 'var(--text-secondary)') : 'var(--text-secondary)' }}>{ln.text}</span>
            </div>
          ))}
        </div>
      );
    }

    case 'Checklist':
      return (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {(node.items ?? []).map((it, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', fontSize: 13 }}>
              <span style={{
                width: 18, height: 18, borderRadius: 5, flexShrink: 0, display: 'grid', placeItems: 'center', color: '#fff',
                border: `1.5px solid ${it.done ? '#0f9d58' : '#d97706'}`,
                background: it.done ? '#0f9d58' : '#fdf2dd',
              }}>
                {it.done && <svg width="11" height="11" viewBox="0 0 16 16" fill="none"><path d="M3 8.5l3.2 3.2L13 5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>}
              </span>
              <span style={{ color: it.done ? 'var(--text-tertiary)' : 'var(--text-secondary)', textDecoration: it.done ? 'line-through' : 'none' }}>{it.label}</span>
            </div>
          ))}
        </div>
      );

    case 'FileTree':
      return (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5, lineHeight: 2, color: 'var(--text-secondary)' }}>
          {(node.items ?? []).map((it, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, paddingLeft: (it.depth ?? 0) * 16 }}>
              <span style={{ color: it.type === 'dir' ? '#3551d8' : 'var(--text-tertiary)' }}>{it.type === 'dir' ? '▸' : '·'}</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: it.type === 'dir' ? 600 : 400 }}>{it.name}</span>
              {it.tag && <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>{it.tag}</span>}
            </div>
          ))}
        </div>
      );

    case 'Tabs':
      return <SduiTabs tabs={node.tabs} />;

    case 'Accordion':
      return <SduiAccordion items={node.items} />;

    case 'DataTable':
      return <SduiDataTable node={node} />;

    case 'TabbedTable':
      return <SduiTabbedTable tabs={node.tabs} />;

    case 'MultiSelect':
      return <SduiMultiSelect options={node.options} title={node.title} />;

    case 'Slider':
      return <SduiSlider value={node.value} label={node.label} min={node.min} max={node.max} unit={node.unit} />;

    case 'ConfirmDialog':
      return (
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', background: 'var(--surface)', padding: 16, boxShadow: 'var(--shadow-md, 0 4px 14px rgba(15,23,42,.06))' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{node.title}</div>
          {node.message && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 7, lineHeight: 1.55 }}>{node.message}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 14 }}>
            <button style={{ padding: '6px 13px', fontSize: 13, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', cursor: 'pointer' }}>{node.cancelLabel ?? '取消'}</button>
            <button style={{ padding: '6px 13px', fontSize: 13, borderRadius: 4, border: '1px solid #3551d8', background: '#3551d8', color: '#fff', cursor: 'pointer', fontWeight: 500 }}>{node.confirmLabel ?? '确认'}</button>
          </div>
        </div>
      );

    case 'FormGroup':
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {(node.fields ?? []).map((f, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>{f.label}</label>
              <input defaultValue={f.value} placeholder={f.placeholder} style={{ padding: '8px 11px', fontSize: 13, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-primary)', outline: 'none' }} />
            </div>
          ))}
        </div>
      );

    // ── Tier C (v4 业务扩展) ──

    case 'StatusBanner': {
      const ST: Record<string, { dot: string; bg: string }> = {
        run: { dot: '#d97706', bg: '#fdf2dd' }, pause: { dot: '#2563eb', bg: '#e6efff' },
        fail: { dot: '#dc2626', bg: '#fde8e8' }, done: { dot: '#0f9d58', bg: '#e6f6ee' },
      };
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {(node.items ?? []).map((it, i) => {
            const s = ST[it.status] ?? { dot: '#d97706', bg: '#fdf2dd' };
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '9px 12px', borderRadius: 6, background: s.bg, fontSize: 13, color: 'var(--text-secondary)' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.dot, flexShrink: 0 }} />
                {it.text}
              </div>
            );
          })}
        </div>
      );
    }

    case 'SegmentedControl':
      return <SduiSegmentedControl segments={node.segments} caption={node.caption} />;

    case 'VerticalStepper': {
      const VS: Record<string, string> = { done: '#0f9d58', running: '#d97706', pending: '#cbd5e1' };
      const items = node.items ?? [];
      return (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {items.map((it, i) => {
            const isLast = i === items.length - 1;
            const c = VS[it.status ?? 'pending'] ?? '#cbd5e1';
            const pending = (it.status ?? 'pending') === 'pending';
            return (
              <div key={i} style={{ display: 'flex', gap: 11, alignItems: 'stretch' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 22, flexShrink: 0 }}>
                  <span style={{ width: 22, height: 22, borderRadius: '50%', background: pending ? 'var(--surface)' : c, border: `2px solid ${pending ? 'var(--border-strong, #cbd5e1)' : c}`, display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 700, color: pending ? 'var(--text-tertiary)' : '#fff' }}>
                    {it.status === 'done' ? '✓' : i + 1}
                  </span>
                  {!isLast && <span style={{ width: 2, flex: 1, minHeight: 14, background: 'var(--border)', borderRadius: 1 }} />}
                </div>
                <div style={{ paddingTop: 2, paddingBottom: isLast ? 0 : 12, fontSize: 13, color: pending ? 'var(--text-tertiary)' : 'var(--text-secondary)', fontWeight: it.status === 'running' ? 600 : 400 }}>{it.label}</div>
              </div>
            );
          })}
        </div>
      );
    }

    case 'AssessmentBar': {
      const segs = node.segments ?? [];
      const total = segs.reduce((s, x) => s + x.value, 0) || 1;
      return (
        <div>
          {node.title && <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>{node.title}</div>}
          <div style={{ display: 'flex', height: 10, borderRadius: 999, overflow: 'hidden' }}>
            {segs.map((s, i) => <div key={i} style={{ width: `${(s.value / total) * 100}%`, background: s.color ?? '#3551d8' }} />)}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 9 }}>
            {segs.map((s, i) => (
              <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--text-tertiary)' }}>
                <i style={{ width: 8, height: 8, borderRadius: 2, background: s.color ?? '#3551d8' }} />
                {s.label} {Math.round((s.value / total) * 100)}%
              </span>
            ))}
          </div>
        </div>
      );
    }

    case 'RecipientList':
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {(node.items ?? []).map((r, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface)' }}>
              <span style={{ width: 30, height: 30, borderRadius: '50%', background: '#3551d8', color: '#fff', display: 'grid', placeItems: 'center', fontSize: 13, fontWeight: 600, flexShrink: 0 }}>{r.name.slice(0, 1)}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{r.name}</div>
                {r.role && <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{r.role}</div>}
              </div>
              {r.status && <span style={{ fontSize: 11, color: 'var(--text-tertiary)', background: 'var(--c-bg-soft, #eef2f7)', borderRadius: 4, padding: '2px 8px' }}>{r.status}</span>}
            </div>
          ))}
        </div>
      );

    case 'DiffView': {
      const CH: Record<string, string> = { add: '#0f9d58', del: '#dc2626', chg: '#d97706' };
      return (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', fontSize: 13 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', background: 'var(--c-surface-2)', borderBottom: '1px solid var(--border)' }}>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)' }}>{node.leftTitle ?? '左'}</div>
            <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)', borderLeft: '1px solid var(--border)' }}>{node.rightTitle ?? '右'}</div>
          </div>
          {(node.rows ?? []).map((r, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: '1px solid var(--border)' }}>
              <div style={{ padding: '8px 12px', color: r.change === 'del' ? CH.del : 'var(--text-secondary)', textDecoration: r.change === 'del' ? 'line-through' : 'none' }}>{r.left}</div>
              <div style={{ padding: '8px 12px', color: r.change ? (CH[r.change] ?? 'var(--text-secondary)') : 'var(--text-secondary)', borderLeft: '1px solid var(--border)', fontWeight: r.change ? 600 : 400 }}>{r.right}</div>
            </div>
          ))}
        </div>
      );
    }

    case 'InlinePreview':
      return (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', background: 'var(--surface)' }}>
          <div style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid var(--border)', background: 'var(--c-surface-2)' }}>
            <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{node.filename}</span>
          </div>
          <div style={{ padding: '28px 12px', textAlign: 'center', fontSize: 12, color: 'var(--text-tertiary)' }}>{node.placeholder ?? '预览区'}</div>
        </div>
      );

    case 'EmbeddedWeb': {
      // iframe 承载外部 Web UI（如 nVisual 仿真软件访问页）。内网不可达时显示 note + 新页打开兜底。
      const h = node.height ?? 520;
      return (
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', background: 'var(--surface)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border)', background: 'var(--c-surface-2)' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{node.title ?? '内嵌网页'}</span>
            {node.openInNewTab !== false && (
              <a href={node.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--c-brand-text, #1e34a8)' }}>新页打开 ↗</a>
            )}
          </div>
          {node.note && (
            <div style={{ padding: '6px 12px', fontSize: 12, color: 'var(--text-tertiary)', borderBottom: '1px solid var(--border)' }}>{node.note}</div>
          )}
          {node.offline ? (
            // 内网不可达：不渲染空白 iframe，给骨架占位 + 说明 + 「新页打开」兜底（见页眉链接）。
            <div style={{
              minHeight: Math.min(h, 300), display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 'var(--sp-3)',
              padding: 'var(--sp-6)', textAlign: 'center',
              background: 'var(--c-bg-soft)', borderTop: '1px dashed var(--c-border-strong)',
            }}>
              <svg width={40} height={40} viewBox="0 0 24 24" fill="none" style={{ color: 'var(--c-text-faint)' }}>
                <rect x="3" y="4" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
                <path d="M3 8h18M8 21h8M12 18v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <div style={{ fontSize: 'var(--fs-14)', fontWeight: 600, color: 'var(--c-text-2)' }}>
                {node.title ?? '仿真软件'} 暂未加载
              </div>
              <div style={{ fontSize: 'var(--fs-12)', color: 'var(--c-text-muted)', maxWidth: 340, lineHeight: 1.6 }}>
                当前为离线 / 内网不可达环境，落位坐标与设备数据已就绪。到内网后将自动嵌入实时拓扑，
                或点右上「新页打开」直接访问。
              </div>
              <a
                href={node.url} target="_blank" rel="noopener noreferrer"
                style={{
                  marginTop: 2, fontSize: 'var(--fs-12)', fontWeight: 600, textDecoration: 'none',
                  color: 'var(--c-text-2)', background: 'var(--c-surface)',
                  border: '1px solid var(--c-border-strong)', borderRadius: 'var(--r-md)', padding: '6px 14px',
                }}
              >在新页打开 ↗</a>
            </div>
          ) : (
            <iframe
              src={node.url}
              title={node.title ?? 'embedded-web'}
              style={{ width: '100%', height: h, border: 'none', display: 'block', background: '#fff' }}
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
            />
          )}
        </div>
      );
    }

    case 'ImageGrid':
      // 对齐 SDUI v4 设计稿 .d-imgs：3 列 · aspect-ratio 4/3 · 文件名浮层于底部
      return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          {(node.images ?? []).map((im, i) => (
            <div
              key={i}
              style={{
                aspectRatio: '4 / 3', borderRadius: 'var(--r-md, 6px)',
                border: '1px solid var(--border)', overflow: 'hidden',
                background: 'var(--c-bg-soft, #eef2f7)', position: 'relative',
                cursor: im.src ? 'pointer' : 'default',
              }}
            >
              {im.src ? (
                <img
                  src={im.src}
                  alt={im.caption}
                  loading="lazy"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />
              ) : (
                <div style={{ height: '100%', display: 'grid', placeItems: 'center', fontSize: 11, color: 'var(--text-tertiary, #94a3b8)' }}>
                  {im.label ?? '📷'}
                </div>
              )}
              <div
                style={{
                  position: 'absolute', bottom: 0, left: 0, right: 0,
                  padding: '4px 8px', background: 'rgba(15,23,42,.55)', color: '#fff',
                  fontSize: 10, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}
              >
                {im.caption}
              </div>
            </div>
          ))}
        </div>
      );

    case 'Toast': {
      // 对齐设计稿 .d-toast：状态点 + 主文案 + 副文案，inline 浮层卡
      const dotColor =
        node.tone === 'warning' ? 'var(--c-warning, #d97706)' :
        node.tone === 'error'   ? 'var(--c-danger, #dc2626)'  :
        node.tone === 'info'    ? 'var(--c-info, #2563eb)'    :
        'var(--c-success, #0f9d58)';
      return (
        <div
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 10,
            padding: '10px 13px', borderRadius: 'var(--r-md, 6px)',
            background: 'var(--surface, #fff)', border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-md, 0 4px 14px rgba(15,23,42,.06))',
            fontSize: 13, color: 'var(--text-primary)',
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: dotColor }} />
          <div>
            {node.message}
            {node.detail && (
              <>
                <br />
                <small style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>{node.detail}</small>
              </>
            )}
          </div>
        </div>
      );
    }

    case 'Sparkline': {
      const pts = node.points ?? [];
      const max = Math.max(...pts, 1), min = Math.min(...pts, 0);
      const range = max - min || 1;
      const poly = pts.map((p, i) => `${(i / Math.max(pts.length - 1, 1)) * 200},${36 - ((p - min) / range) * 30}`).join(' ');
      return (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 6 }}>
            <div>
              {node.label && <div style={{ fontSize: 11, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '.05em' }}>{node.label}</div>}
              {node.value != null && <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{String(node.value)}</div>}
            </div>
            {node.delta && <span style={{ fontSize: 12, color: '#0f9d58', fontWeight: 600 }}>{node.delta}</span>}
          </div>
          <svg width="100%" height="36" viewBox="0 0 200 36" preserveAspectRatio="none"><polyline fill="none" stroke="#3551d8" strokeWidth="2" points={poly} /></svg>
        </div>
      );
    }

    case 'DashboardLayout':
      return (
        <div style={{ display: 'grid', gridTemplateColumns: '5fr 2fr', gap: 14, alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>{renderChildren(node.main)}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>{renderChildren(node.side)}</div>
        </div>
      );

    case 'Drawer':
      return (
        <div style={{ border: '1px solid var(--border)', borderLeft: '3px solid #3551d8', borderRadius: 8, background: 'var(--surface)', padding: 14, boxShadow: 'var(--shadow-md, 0 4px 14px rgba(15,23,42,.06))' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>{node.title}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>{renderChildren(node.children)}</div>
        </div>
      );

    // ── Tier D (v5 业务扩展 · 交付台 / 系统设计) ──

    case 'TabGroup':
      return <SduiTabGroup node={node} pathPrefix={pathPrefix} />;

    case 'InputSlotList': {
      const slots = node.slots ?? [];
      const btnGhost: React.CSSProperties = { padding: '4px 11px', fontSize: 12, borderRadius: 5, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', cursor: 'pointer', whiteSpace: 'nowrap' };
      const btnPrimary: React.CSSProperties = { padding: '4px 11px', fontSize: 12, borderRadius: 5, border: '1px solid #3551d8', background: '#3551d8', color: '#fff', cursor: 'pointer', fontWeight: 500, whiteSpace: 'nowrap' };
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {node.title && <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{node.title}</div>}
          {slots.map((s, i) => {
            const ready = !!s.ready;
            const isAuto = s.source === 'auto';
            // 缺件高亮：必需缺件红，自动检查中/可选缺件琥珀，就绪绿
            const accent = ready ? '#10b981' : isAuto ? '#d97706' : s.required ? '#dc2626' : '#d97706';
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 8,
                border: '1px solid var(--border)', borderLeft: `3px solid ${accent}`,
                background: !ready && !isAuto ? 'var(--c-surface-2)' : 'var(--surface)',
                animation: `sdui-stagger .18s ease-out ${Math.min(i, 8) * 0.04}s both`,
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: accent,
                  boxShadow: ready ? '0 0 0 3px rgba(16,185,129,.14)' : 'none',
                  animation: !ready && isAuto ? 'clawStepperPulse 1.4s ease-in-out infinite' : 'none',
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{s.label}</span>
                    <span style={{ fontSize: 10, fontWeight: 500, borderRadius: 4, padding: '1px 6px', color: s.required ? '#b45309' : 'var(--text-tertiary)', background: s.required ? '#fdf2dd' : 'var(--c-bg-soft, #eef2f7)' }}>
                      {s.required ? '必需' : '可选'}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 500, borderRadius: 4, padding: '1px 6px', color: isAuto ? 'var(--c-brand-text, #1e34a8)' : 'var(--text-tertiary)', background: isAuto ? 'var(--c-brand-soft, #eef1fc)' : 'var(--c-bg-soft, #eef2f7)' }}>
                      {isAuto ? '自动 · 仿真' : '手动 · 上传'}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3, fontFamily: ready ? 'var(--font-mono)' : undefined, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {ready ? (s.fileName ?? '已就绪') : isAuto ? '检查中…（等待仿真产出）' : '缺失 · 待上传'}
                  </div>
                </div>
                <div style={{ flexShrink: 0 }}>
                  {ready ? (
                    s.previewPath ? (
                      <button onClick={() => { const p = s.previewPath; if (p) onAction({ kind: 'open_preview', path: p }); }} style={btnGhost}>预览</button>
                    ) : (
                      <span style={{ fontSize: 11, color: '#0a7350', fontWeight: 600 }}>✓ 就绪</span>
                    )
                  ) : isAuto ? (
                    <span style={{ fontSize: 11, color: '#b45309', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                      <i style={{ width: 11, height: 11, borderRadius: '50%', border: '2px solid var(--zinc-100)', borderTopColor: '#d97706', display: 'block', animation: 'spin .8s linear infinite' }} />
                      检查中
                    </span>
                  ) : (
                    <button onClick={() => onAction({ kind: 'post_user_message', text: `上传${s.label}` })} style={btnPrimary}>上传</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    case 'TaskTimelineStrip': {
      const pct = Math.max(0, Math.min(100, node.progressPct ?? 0));
      const rd = node.remainingDays;
      const overdue = typeof rd === 'number' && rd < 0;
      const fill = pct >= 100 ? '#10b981' : overdue ? '#dc2626' : '#3551d8';
      let rdText = '', rdColor = 'var(--text-tertiary)', rdBg = 'var(--c-bg-soft, #eef2f7)';
      if (typeof rd === 'number') {
        if (rd < 0) { rdText = `逾期 ${Math.abs(rd)} 天`; rdColor = '#c0322f'; rdBg = '#fde8e8'; }
        else if (rd === 0) { rdText = '今日截止'; rdColor = '#b45309'; rdBg = '#fdf2dd'; }
        else if (rd <= 3) { rdText = `剩余 ${rd} 天`; rdColor = '#b45309'; rdBg = '#fdf2dd'; }
        else { rdText = `剩余 ${rd} 天`; rdColor = 'var(--c-brand-text, #1e34a8)'; rdBg = 'var(--c-brand-soft, #eef1fc)'; }
      }
      const trackRow: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 8 };
      const track: React.CSSProperties = { flex: 1, height: 8, borderRadius: 999, background: 'var(--zinc-100)', overflow: 'hidden' };
      const railLabel: React.CSSProperties = { width: 30, fontSize: 10, color: 'var(--text-tertiary)', flexShrink: 0 };
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', fontSize: 12 }}>
              <span style={{ color: 'var(--text-tertiary)' }}>计划 <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{node.plannedStart} → {node.plannedEnd}</span></span>
              <span style={{ color: 'var(--text-tertiary)' }}>实际 <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{node.actualStart ?? '—'} → {node.actualEnd ?? '进行中'}</span></span>
            </div>
            {rdText && <span style={{ fontSize: 11, fontWeight: 600, color: rdColor, background: rdBg, borderRadius: 999, padding: '3px 10px' }}>{rdText}</span>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={trackRow}>
              <span style={railLabel}>计划</span>
              <div style={track}><div style={{ height: '100%', width: '100%', background: 'var(--zinc-200)', borderRadius: 999 }} /></div>
              <span style={{ width: 38, flexShrink: 0 }} />
            </div>
            <div style={trackRow}>
              <span style={railLabel}>实际</span>
              <div style={track}><div style={{ height: '100%', width: `${pct}%`, background: fill, borderRadius: 999, transition: 'width .85s cubic-bezier(.22,.61,.36,1)' }} /></div>
              <span style={{ width: 38, textAlign: 'right', fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', flexShrink: 0 }}>{pct}%</span>
            </div>
          </div>
        </div>
      );
    }

    case 'MacroStepRail': {
      const steps = node.steps ?? [];
      const MR: Record<string, string> = { done: '#0f9d58', running: '#3551d8', pending: '#cbd5e1' };
      return (
        <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          {steps.map((st, i) => {
            const status = st.status ?? 'pending';
            const isCurrent = node.currentId ? st.id === node.currentId : status === 'running';
            const c = MR[status] ?? '#cbd5e1';
            const dim = !!st.optional && status === 'pending';
            const isLast = i === steps.length - 1;
            const prevDone = i > 0 && steps[i - 1]?.status === 'done';
            return (
              <div key={st.id ?? i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, minWidth: 110, opacity: dim ? 0.55 : 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                  <span style={{ flex: 1, height: 2, background: i === 0 ? 'transparent' : prevDone ? '#0f9d58' : 'var(--border)' }} />
                  <span style={{
                    width: 24, height: 24, borderRadius: '50%', flexShrink: 0, display: 'grid', placeItems: 'center',
                    fontSize: 11, fontWeight: 700,
                    background: status === 'pending' ? 'var(--surface)' : c,
                    border: `2px solid ${isCurrent ? '#3551d8' : status === 'pending' ? 'var(--border-strong, #cbd5e1)' : c}`,
                    color: status === 'pending' ? 'var(--text-tertiary)' : '#fff',
                    boxShadow: isCurrent ? '0 0 0 3px rgba(53,81,216,.16)' : 'none',
                    animation: status === 'running' ? 'clawStepperPulse 1.4s ease-in-out infinite' : 'none',
                  }}>
                    {status === 'done' ? '✓' : i + 1}
                  </span>
                  <span style={{ flex: 1, height: 2, background: isLast ? 'transparent' : status === 'done' ? '#0f9d58' : 'var(--border)' }} />
                </div>
                <div style={{ textAlign: 'center', marginTop: 7, padding: '0 6px' }}>
                  <div style={{ fontSize: 12, fontWeight: isCurrent ? 700 : 500, color: isCurrent ? 'var(--c-brand-text, #1e34a8)' : 'var(--text-secondary)', lineHeight: 1.3 }}>
                    {st.title}
                  </div>
                  {st.optional && <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>可选</span>}
                  {st.hint && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2, lineHeight: 1.4 }}>{st.hint}</div>}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    // ── Artifacts ──

    case 'ArtifactGrid':
      return <SduiArtifactGrid artifacts={node.artifacts} mode={node.mode} title={node.title} />;

    // ── HITL ──

    case 'FilePicker':
      return (
        <SduiFilePicker
          purpose={node.purpose}
          label={node.label}
          helpText={node.helpText}
          accept={node.accept}
          multiple={node.multiple}
          hitlRequestId={node.hitlRequestId}
          stepId={node.stepId}
        />
      );

    case 'ChoiceCard':
      return <SduiChoiceCard title={node.title} options={node.options} hitlRequestId={node.hitlRequestId} stepId={node.stepId} />;

    case 'HitlTextInput':
      return <HitlTextInput node={node} onSubmit={onChoiceSubmit} />;

    default:
      return <UnknownNode type={(node as { type?: string }).type ?? '?'} />;
    }
  })();

  return <>{inner}</>;
}
