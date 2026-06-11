/**
 * SduiDataTable — DataTable 节点渲染器（两形态）。
 *
 *  ① 旧只读位置型：columns=string[]、rows=(string|number)[][] —— 直接渲染只读表（兼容 zhgk 等）。
 *  ② 新类型化 / 可编辑：columns=SduiDataTableColumn[]、rows=Record<string,unknown>[]。
 *     - 列按 type 渲染：text=文本/输入框、status=徽标、progress=进度条；col.editable → 输入框。
 *     - checkKey → 前置勾选列；groupKey → 分组表头；pageSize → 分页。
 *     - editable=true 时底部出「fillLabel 一键填充」+「submitLabel 提交」；提交前按 requiredKeys 校验。
 *     - submitMode='resume' → onRowsSubmit（/resume payload={rows}）；'run-patch' → 暂未启用（灰显）。
 */
import { useMemo, useState } from 'react';
import type { SduiDataTableNode, SduiDataTableColumn } from '@/lib/sdui';
import { useSduiRuntime } from './SduiContext';

type Row = Record<string, unknown>;

function isTypedColumns(cols: SduiDataTableNode['columns']): cols is SduiDataTableColumn[] {
  return cols.length > 0 && typeof cols[0] === 'object' && cols[0] !== null;
}

const th: React.CSSProperties = {
  padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)',
  background: 'var(--c-surface-2)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
};
const td: React.CSSProperties = { padding: '9px 12px', color: 'var(--text-secondary)', verticalAlign: 'middle' };

function StatusBadge({ value }: { value: string }) {
  const v = String(value ?? '');
  const tone =
    /完成|已下发|done|ok/i.test(v) ? { bg: 'var(--c-success-soft)', fg: 'var(--c-success-text)' } :
    /进行|running/i.test(v)       ? { bg: 'var(--c-warning-soft)', fg: 'var(--c-warning-text)' } :
    /待|pending|未/i.test(v)      ? { bg: 'var(--c-bg-soft)', fg: 'var(--c-text-muted)' } :
                                    { bg: 'var(--c-bg-soft)', fg: 'var(--c-text-2)' };
  return (
    <span style={{ fontSize: 11, fontWeight: 600, background: tone.bg, color: tone.fg, borderRadius: 999, padding: '2px 9px', whiteSpace: 'nowrap' }}>{v || '—'}</span>
  );
}

function ProgressCell({ value }: { value: unknown }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 90 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 999, background: 'var(--c-bg-soft)', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 'inherit', background: pct >= 100 ? 'var(--c-success)' : 'var(--c-brand)', transition: 'width .4s' }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--c-text-muted)', fontVariantNumeric: 'tabular-nums' }}>{pct}%</span>
    </div>
  );
}

/** 只读位置型表（旧形态）。*/
function LegacyTable({ node }: { node: SduiDataTableNode }) {
  const cols = node.columns as string[];
  const rows = node.rows as (string | number)[][];
  return (
    <div className="sdui-tbl" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--surface)', boxShadow: 'var(--shadow-xs)' }}>
      {node.title && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{node.title}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', background: 'var(--c-bg-soft, #eef2f7)', borderRadius: 999, padding: '1px 8px', fontVariantNumeric: 'tabular-nums' }}>{rows.length}</span>
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead><tr>{cols.map((c, i) => <th key={i} style={th}>{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, ri) => (
          <tr key={ri} style={{ borderBottom: ri < rows.length - 1 ? '1px solid var(--border)' : 'none' }}>
            {r.map((cell, ci) => <td key={ci} style={td}>{String(cell)}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

/** 类型化 / 可编辑表（新形态）。*/
function TypedTable({ node }: { node: SduiDataTableNode }) {
  const { onRowsSubmit } = useSduiRuntime();
  const columns = node.columns as SduiDataTableColumn[];
  const [rows, setRows] = useState<Row[]>(() => (node.rows as Row[]).map(r => ({ ...r })));
  const [page, setPage] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const rowKey = node.rowKey ?? 'id';
  const editable = !!node.editable;
  const isRunPatch = node.submitMode === 'run-patch';
  const hasFill = !!(editable && node.fillLabel && node.fillRows && !isRunPatch);
  // 勾选型表（如计划下发）的「一键全选」放到表头右上角；非勾选的填值型仍留在底部工具条。
  const selectAllInHeader = hasFill && !!node.checkKey;

  const setCell = (rk: unknown, key: string, val: unknown) => {
    setRows(prev => prev.map(r => (r[rowKey] === rk ? { ...r, [key]: val } : r)));
  };

  // 分页
  const pageSize = node.pageSize && node.pageSize > 0 ? node.pageSize : 0;
  const pageCount = pageSize ? Math.max(1, Math.ceil(rows.length / pageSize)) : 1;
  const pageRows = pageSize ? rows.slice(page * pageSize, page * pageSize + pageSize) : rows;

  // 分组（仅在当前页内分组，保持顺序）
  const groups = useMemo(() => {
    if (!node.groupKey) return [{ label: '', rows: pageRows }];
    const map = new Map<string, Row[]>();
    for (const r of pageRows) {
      const g = String(r[node.groupKey!] ?? '');
      if (!map.has(g)) map.set(g, []);
      map.get(g)!.push(r);
    }
    return Array.from(map.entries()).map(([label, rs]) => ({ label, rows: rs }));
  }, [pageRows, node.groupKey]);

  const totalCols = columns.length + (node.checkKey ? 1 : 0);

  const handleFill = () => {
    if (node.fillRows) setRows((node.fillRows as Row[]).map(r => ({ ...r })));
  };

  const handleSubmit = () => {
    if (!onRowsSubmit || submitted) return;
    const required = node.requiredKeys ?? [];
    if (required.length) {
      const bad = rows.filter(r => required.some(k => !String(r[k] ?? '').trim()));
      if (bad.length) { setErr(`还有 ${bad.length} 行未填写必填项（${required.join('、')}）`); return; }
    }
    setErr(null);
    setSubmitted(true);
    onRowsSubmit(rows, node.stepId);
  };

  const renderCell = (r: Row, col: SduiDataTableColumn) => {
    const val = r[col.key];
    if (col.editable) {
      return (
        <input
          value={String(val ?? '')}
          placeholder={col.placeholder}
          onChange={e => setCell(r[rowKey], col.key, e.target.value)}
          disabled={submitted}
          style={{ width: '100%', padding: '5px 8px', fontSize: 13, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-primary)', outline: 'none' }}
        />
      );
    }
    if (col.type === 'status') return <StatusBadge value={String(val ?? '')} />;
    if (col.type === 'progress') return <ProgressCell value={val} />;
    return <span>{String(val ?? '')}</span>;
  };

  return (
    <div className={editable ? undefined : 'sdui-tbl'} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--surface)', boxShadow: 'var(--shadow-xs)' }}>
      {(node.title || selectAllInHeader) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
          {node.title && <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{node.title}</span>}
          {node.title && <span style={{ fontSize: 11, color: 'var(--text-tertiary)', background: 'var(--c-bg-soft, #eef2f7)', borderRadius: 999, padding: '1px 8px', fontVariantNumeric: 'tabular-nums' }}>{rows.length}</span>}
          {selectAllInHeader && (
            <button onClick={handleFill} disabled={submitted} style={{ ...pagerBtn(submitted), marginLeft: 'auto' }}>{node.fillLabel}</button>
          )}
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              {node.checkKey && <th style={{ ...th, width: 36 }} />}
              {columns.map((c, i) => <th key={i} style={{ ...th, width: c.width }}>{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {groups.map((g, gi) => (
              <>
                {g.label && (
                  <tr key={`g-${gi}`}>
                    <td colSpan={totalCols} style={{ padding: '6px 12px', fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', background: 'var(--c-surface-2)', textTransform: 'uppercase', letterSpacing: '.04em' }}>{g.label}</td>
                  </tr>
                )}
                {g.rows.map((r, ri) => (
                  <tr key={`${gi}-${String(r[rowKey] ?? ri)}`} style={{ borderBottom: '1px solid var(--border)' }}>
                    {node.checkKey && (
                      <td style={{ ...td, textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={!!r[node.checkKey]}
                          disabled={submitted}
                          onChange={e => setCell(r[rowKey], node.checkKey!, e.target.checked)}
                          style={{ cursor: submitted ? 'default' : 'pointer' }}
                        />
                      </td>
                    )}
                    {columns.map((c, ci) => <td key={ci} style={td}>{renderCell(r, c)}</td>)}
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {pageSize > 0 && pageCount > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10, padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={pagerBtn(page === 0)}>上一页</button>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{page + 1} / {pageCount}</span>
          <button onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} disabled={page >= pageCount - 1} style={pagerBtn(page >= pageCount - 1)}>下一页</button>
        </div>
      )}

      {editable && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderTop: '1px solid var(--border)' }}>
          {err && <span style={{ fontSize: 12, color: 'var(--red-600, #dc2626)', marginRight: 'auto' }}>{err}</span>}
          {!err && <span style={{ marginRight: 'auto' }} />}
          {hasFill && !selectAllInHeader && (
            <button onClick={handleFill} disabled={submitted} style={pagerBtn(submitted)}>{node.fillLabel}</button>
          )}
          {isRunPatch ? (
            <button disabled title="该能力暂未启用（/run-patch 端点未接入）" style={{ ...primaryBtn, opacity: 0.45, cursor: 'not-allowed' }}>{node.submitLabel ?? '提交'}（暂未启用）</button>
          ) : (
            <button onClick={handleSubmit} disabled={submitted || !onRowsSubmit} style={{ ...primaryBtn, opacity: submitted ? 0.5 : 1, cursor: submitted ? 'default' : 'pointer' }}>
              {submitted ? '已提交' : (node.submitLabel ?? '提交')}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function pagerBtn(disabled: boolean): React.CSSProperties {
  return { padding: '5px 12px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.5 : 1 };
}
const primaryBtn: React.CSSProperties = { padding: '6px 16px', fontSize: 13, fontWeight: 500, borderRadius: 'var(--r-md)', border: '1px solid var(--c-brand)', background: 'var(--c-brand)', color: '#fff' };

export function SduiDataTable({ node }: { node: SduiDataTableNode }) {
  return isTypedColumns(node.columns) ? <TypedTable node={node} /> : <LegacyTable node={node} />;
}
