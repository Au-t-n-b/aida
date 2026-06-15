/**
 * SduiDataTable — DataTable 节点渲染器（两形态）。
 *
 *  ① 旧只读位置型：columns=string[]、rows=(string|number)[][] —— 直接渲染只读表（兼容 zhgk 等）。
 *  ② 新类型化 / 可编辑：columns=SduiDataTableColumn[]、rows=Record<string,unknown>[]。
 *     - 列按 type 渲染：text=文本/输入框、status=徽标、progress=进度条；col.editable → 输入框。
 *     - checkKey → 前置勾选列；groupKey → 分组表头；groupAsTabs → 按 groupKey 分页签；pageSize → 分页。
 *     - editable=true 时表头右上角出「backLabel 返回上一步」（run-patch go_back）+「fillLabel 一键填充」+「submitLabel 提交」；提交前按 requiredKeys 校验。
 *     - submitMode='resume' → onRowsSubmit（/resume）；'run-patch' → onRowsSubmit（/run-patch）。
 */
import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import type { SduiDataTableNode, SduiDataTableColumn } from '@/lib/sdui';
import { useSduiRuntime } from './SduiContext';
import { useSduiTabBarActions } from './SduiTabBarActionsContext';
import { taskProgressFill } from './taskProgressColors';
import { principalDisplayName } from './principalDisplayName';

type Row = Record<string, unknown>;

/** 归一化为 <input type="date"> 需要的 YYYY-MM-DD；解析失败返回空串（不报错）。 */
function toDateInputValue(v: unknown): string {
  const s = String(v ?? '').trim();
  if (!s) return '';
  const m = s.match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
  if (m) {
    const y = m[1] ?? '';
    const mo = (m[2] ?? '').padStart(2, '0');
    const d = (m[3] ?? '').padStart(2, '0');
    return `${y}-${mo}-${d}`;
  }
  const dt = new Date(s);
  if (!Number.isNaN(dt.getTime())) {
    const y = dt.getFullYear();
    const mo = String(dt.getMonth() + 1).padStart(2, '0');
    const d = String(dt.getDate()).padStart(2, '0');
    return `${y}-${mo}-${d}`;
  }
  return '';
}

function isRowChecked(v: unknown): boolean {
  if (typeof v === 'boolean') return v;
  if (typeof v === 'string') return ['true', '1', 'yes', 'on'].includes(v.toLowerCase());
  return Boolean(v);
}

function isTypedColumns(cols: SduiDataTableNode['columns']): cols is SduiDataTableColumn[] {
  return cols.length > 0 && typeof cols[0] === 'object' && cols[0] !== null;
}

/** 与 DataTable 卡片标题（如「责任矩阵」）一致的字体 */
const tableTitleFont: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
};

const th: React.CSSProperties = {
  padding: '9px 12px', textAlign: 'left',
  ...tableTitleFont,
  color: 'var(--text-primary)',
  background: 'var(--c-surface-2)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
};
const td: React.CSSProperties = { padding: '9px 12px', color: 'var(--text-secondary)', verticalAlign: 'middle' };

/** 列单元格样式：支持 paddingLeft 右移列内容 */
function colCellStyle(col: SduiDataTableColumn, base: React.CSSProperties): React.CSSProperties {
  let s = col.paddingLeft != null ? { ...base, paddingLeft: col.paddingLeft } : base;
  if (col.nowrap) s = { ...s, whiteSpace: 'nowrap' as const, overflow: 'hidden', textOverflow: 'ellipsis' };
  return s;
}

/** 可编辑单元格输入框：有列宽则定宽；无列宽则 100% 撑满（如 ESN 末列吃剩余空间） */
function editableInputStyle(col: SduiDataTableColumn): React.CSSProperties {
  const w = col.width ?? (col.type === 'date' ? 118 : undefined);
  return {
    width: w ?? '100%',
    maxWidth: '100%',
    boxSizing: 'border-box',
    padding: '5px 8px',
    fontSize: 13,
    borderRadius: 4,
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    color: 'var(--text-primary)',
    outline: 'none',
  };
}

function pagerBtn(disabled: boolean): React.CSSProperties {
  return { padding: '5px 12px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.5 : 1 };
}
const headerBtn: React.CSSProperties = {
  padding: '4px 10px', fontSize: 12, lineHeight: 1.25, borderRadius: 4,
  border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)',
  cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
};
const headerPrimaryBtn: React.CSSProperties = {
  ...headerBtn,
  border: '1px solid var(--c-brand)', background: 'var(--c-brand)', color: '#fff', fontWeight: 500,
};
const primaryBtn: React.CSSProperties = { padding: '6px 16px', fontSize: 13, fontWeight: 500, borderRadius: 'var(--r-md)', border: '1px solid var(--c-brand)', background: 'var(--c-brand)', color: '#fff' };

function StatusBadge({ value }: { value: string }) {
  const v = String(value ?? '');
  const tone =
    v === '未开始' ? { bg: 'var(--c-danger-soft)', fg: 'var(--c-danger-text)' } :
    /已完成|完成|done|ok/i.test(v) ? { bg: 'var(--c-success-soft)', fg: 'var(--c-success-text)' } :
    /进行中|running/i.test(v)       ? { bg: 'var(--c-warning-soft)', fg: 'var(--c-warning-text)' } :
    /待|pending/i.test(v)            ? { bg: 'var(--c-bg-soft)', fg: 'var(--c-text-muted)' } :
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
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 'inherit', background: taskProgressFill(pct), transition: 'width .4s, background .2s' }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--c-text-muted)', fontVariantNumeric: 'tabular-nums' }}>{pct}%</span>
    </div>
  );
}

function statusFromProgress(pct: number): string {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  if (p >= 100) return '已完成';
  if (p >= 1) return '进行中';
  return '未开始';
}

/** Tier B · 展示/编辑双模式（组件库 DataTable 标准交互）。*/
function DualModeTable({ node }: { node: SduiDataTableNode }) {
  const { onRunPatch, streamEpoch } = useSduiRuntime();
  const columns = node.columns as SduiDataTableColumn[];
  const rowKey = node.rowKey ?? 'id';
  const [rows, setRows] = useState<Row[]>(() => (node.rows as Row[]).map(r => ({ ...r })));
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const snapshotRef = useRef<Row[]>([]);

  const rowsSeed = JSON.stringify(node.rows);
  useEffect(() => {
    if (editing) return;
    setRows((node.rows as Row[]).map(r => ({ ...r })));
    setPage(0);
  }, [rowsSeed, streamEpoch, editing]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r =>
      columns.some(c => String(r[c.key] ?? '').toLowerCase().includes(q)),
    );
  }, [rows, search, columns]);

  const pageSize = node.pageSize && node.pageSize > 0 ? node.pageSize : 0;
  const pageCount = pageSize ? Math.max(1, Math.ceil(filtered.length / pageSize)) : 1;
  const pageRows = pageSize ? filtered.slice(page * pageSize, page * pageSize + pageSize) : filtered;

  const setProgress = (id: unknown, raw: string) => {
    const pct = Math.max(0, Math.min(100, Math.round(Number(raw) || 0)));
    setRows(prev => prev.map(r => {
      if (r[rowKey] !== id) return r;
      return { ...r, progress: pct, status: statusFromProgress(pct) };
    }));
  };

  const startEdit = () => {
    snapshotRef.current = rows.map(r => ({ ...r }));
    setEditing(true);
    setErr(null);
  };

  const cancelEdit = () => {
    setRows(snapshotRef.current.map(r => ({ ...r })));
    setEditing(false);
    setErr(null);
  };

  const saveEdit = async () => {
    if (!onRunPatch) {
      setErr('保存未接入');
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const action = node.patchAction ?? 'task_progress';
      const payload = rows.map(r => ({ id: r[rowKey], progress: r.progress }));
      await onRunPatch({ action, stepId: action, rows: payload });
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const headerBtn: React.CSSProperties = {
    padding: '5px 12px', fontSize: 12, fontWeight: 500, borderRadius: 'var(--r-sm)', cursor: 'pointer',
  };

  const renderCell = (r: Row, col: SduiDataTableColumn) => {
    if (editing && col.type === 'progress') {
      return (
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
          <input
            type="number"
            min={0}
            max={100}
            value={Number(r[col.key]) || 0}
            onChange={e => setProgress(r[rowKey], e.target.value)}
            style={{ width: 52, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 12 }}
          />
          <span style={{ color: 'var(--text-tertiary)' }}>%</span>
        </label>
      );
    }
    if (col.type === 'status') return <StatusBadge value={String(r[col.key] ?? '')} />;
    if (col.type === 'progress') return <ProgressCell value={r[col.key]} />;
    const text = col.key === 'principal' ? principalDisplayName(r[col.key]) : String(r[col.key] ?? '');
    return <span>{text}</span>;
  };

  return (
    <div className="sdui-tbl" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--surface)', boxShadow: 'var(--shadow-xs)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
        {node.title && <span style={{ ...tableTitleFont, color: 'var(--text-primary)' }}>{node.title}</span>}
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', background: 'var(--c-bg-soft, #eef2f7)', borderRadius: 999, padding: '1px 8px', fontVariantNumeric: 'tabular-nums' }}>{filtered.length}</span>
        <span style={{
          fontSize: 11, fontWeight: 600, borderRadius: 999, padding: '2px 8px',
          background: editing ? 'var(--c-warning-soft)' : 'var(--c-success-soft)',
          color: editing ? 'var(--c-warning-text)' : 'var(--c-success-text)',
        }}>
          {editing ? '编辑模式' : '展示模式'}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0); }}
            placeholder="搜索…"
            style={{ padding: '5px 10px', fontSize: 12, borderRadius: 'var(--r-sm)', border: '1px solid var(--border)', minWidth: 120 }}
          />
          {node.backLabel && onRunPatch && !editing && (
            <button type="button" onClick={() => { void onRunPatch({ action: 'go_back', stepId: node.backStepId ?? 'go_back' }); }}
              style={{ ...headerBtn, border: '1px solid var(--c-border)', background: 'var(--c-surface)', color: 'var(--c-text-2)' }}>
              {node.backLabel}
            </button>
          )}
          {editing ? (
            <>
              <button type="button" onClick={cancelEdit} disabled={saving} style={{ ...headerBtn, border: '1px solid var(--c-border)', background: 'var(--c-surface)', color: 'var(--c-text-2)' }}>取消</button>
              <button type="button" onClick={() => { void saveEdit(); }} disabled={saving} style={{ ...headerBtn, border: '1px solid var(--c-brand)', background: 'var(--c-brand)', color: '#fff' }}>
                {saving ? '保存中…' : '保存'}
              </button>
            </>
          ) : (
            <button type="button" onClick={startEdit} style={{ ...headerBtn, border: '1px solid var(--c-border)', background: 'var(--c-surface)', color: 'var(--c-text-2)' }}>编辑</button>
          )}
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
          <thead>
            <tr>
              {columns.map((c, i) => <th key={i} style={colCellStyle(c, { ...th, width: c.width })}>{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r, ri) => (
              <tr key={String(r[rowKey] ?? ri)} style={{ borderBottom: '1px solid var(--border)' }}>
                {columns.map((c, ci) => <td key={ci} style={colCellStyle(c, td)}>{renderCell(r, c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '8px 12px', borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>共 {filtered.length} 条</span>
        {pageSize > 0 && pageCount > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button type="button" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={pagerBtn(page === 0)}>上一页</button>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{page + 1} / {pageCount}</span>
            <button type="button" onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} disabled={page >= pageCount - 1} style={pagerBtn(page >= pageCount - 1)}>下一页</button>
          </div>
        )}
      </div>
      {err && (
        <div style={{ padding: '8px 12px', fontSize: 12, color: 'var(--red-600, #dc2626)', borderTop: '1px solid var(--border)' }}>{err}</div>
      )}
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
          <span style={{ ...tableTitleFont, color: 'var(--text-primary)' }}>{node.title}</span>
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
  const { onRowsSubmit, onRunPatch, streamEpoch } = useSduiRuntime();
  const columns = node.columns as SduiDataTableColumn[];
  const [rows, setRows] = useState<Row[]>(() => (node.rows as Row[]).map(r => ({ ...r })));
  const [page, setPage] = useState(0);
  const [activeTab, setActiveTab] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  // 列筛选（如按管理单元筛选）：key → 选中值（'' = 全部）。仅影响展示，不影响填充/提交。
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  const rowKey = node.rowKey ?? 'id';
  const editable = !!node.editable;
  const groupTabMode = !!(node.groupKey && node.groupAsTabs);
  const displayColumns = useMemo(() => {
    if (groupTabMode && node.groupKey) {
      return columns.filter(c => c.key !== node.groupKey);
    }
    return columns;
  }, [columns, groupTabMode, node.groupKey]);
  const isRunPatch = node.submitMode === 'run-patch';
  const isCheckToggle = !!(editable && node.checkKey && node.fillLabel && !isRunPatch);
  const hasFill = isCheckToggle || !!(editable && node.fillLabel && node.fillRows && !isRunPatch);
  // 可编辑表（计划下发 / ESN 填写等）：表头或 TabGroup 页签栏右侧放回退 + 填充 + 提交
  const actionsInHeader = !!(editable && !isRunPatch && (node.fillLabel || node.backLabel));
  const tabBarActionsApi = useSduiTabBarActions();
  const actionsHoisted = !!(actionsInHeader && tabBarActionsApi);

  const allSelected = useMemo(() => {
    if (!node.checkKey || rows.length === 0) return false;
    return rows.every(r => isRowChecked(r[node.checkKey!]));
  }, [rows, node.checkKey]);

  const fillButtonLabel = node.checkKey && allSelected
    ? (node.deselectLabel ?? '一键取消')
    : (node.fillLabel ?? '一键全选');

  const selectedCount = useMemo(() => {
    if (!node.checkKey) return rows.length;
    return rows.filter(r => isRowChecked(r[node.checkKey!])).length;
  }, [rows, node.checkKey]);

  const requiredIncomplete = useMemo(() => {
    const required = node.requiredKeys ?? [];
    if (!required.length) return false;
    return rows.some(r => required.some(k => !String(r[k] ?? '').trim()));
  }, [rows, node.requiredKeys]);

  const submitDisabled = submitted || !onRowsSubmit
    || (!!node.checkKey && selectedCount === 0)
    || requiredIncomplete;

  // SSE 重推 HITL 时同步服务端行并解除「已提交」冻结（空勾选 resume 后仍停留本步）
  const rowsSeed = JSON.stringify(node.rows);
  useEffect(() => {
    setRows((node.rows as Row[]).map(r => ({ ...r })));
    setSubmitted(false);
    setActiveTab(0);
    setPage(0);
    setFilterValues({});
  }, [rowsSeed, streamEpoch]);

  // 可筛选列定义：{key,label,options}（去重 + 原序）
  const filterDefs = useMemo(() => {
    const keys = node.filterKeys ?? [];
    return keys.map(key => {
      const col = columns.find(c => c.key === key);
      const seen = new Set<string>();
      const options: string[] = [];
      for (const r of rows) {
        const v = String(r[key] ?? '').trim();
        if (v && !seen.has(v)) { seen.add(v); options.push(v); }
      }
      return { key, label: col?.label ?? key, options };
    }).filter(d => d.options.length > 0);
  }, [node.filterKeys, columns, rows]);

  // 应用筛选（展示用）：所有已选筛选列都需匹配
  const filteredRows = useMemo(() => {
    const active = Object.entries(filterValues).filter(([, v]) => v);
    if (!active.length) return rows;
    return rows.filter(r => active.every(([k, v]) => String(r[k] ?? '').trim() === v));
  }, [rows, filterValues]);

  const tabGroups = useMemo(() => {
    if (!groupTabMode || !node.groupKey) return [];
    const map = new Map<string, Row[]>();
    for (const r of filteredRows) {
      const g = String(r[node.groupKey!] ?? '未分类');
      if (!map.has(g)) map.set(g, []);
      map.get(g)!.push(r);
    }
    return Array.from(map.entries()).map(([label, rs]) => ({ label, rows: rs }));
  }, [filteredRows, groupTabMode, node.groupKey]);

  const activeTabIdx = tabGroups.length ? Math.min(activeTab, tabGroups.length - 1) : 0;
  const tabRows = groupTabMode ? (tabGroups[activeTabIdx]?.rows ?? []) : filteredRows;

  // 分页（页签模式下仅对当前页签内行分页）
  const pageSize = node.pageSize && node.pageSize > 0 ? node.pageSize : 0;
  const pageCount = pageSize ? Math.max(1, Math.ceil(tabRows.length / pageSize)) : 1;
  const pageRows = pageSize ? tabRows.slice(page * pageSize, page * pageSize + pageSize) : tabRows;

  // 分组（表内分组头；页签模式下不再使用）
  const groups = useMemo(() => {
    if (groupTabMode || !node.groupKey) return [{ label: '', rows: pageRows }];
    const map = new Map<string, Row[]>();
    for (const r of pageRows) {
      const g = String(r[node.groupKey!] ?? '');
      if (!map.has(g)) map.set(g, []);
      map.get(g)!.push(r);
    }
    return Array.from(map.entries()).map(([label, rs]) => ({ label, rows: rs }));
  }, [pageRows, node.groupKey, groupTabMode]);

  const totalCols = displayColumns.length + (node.checkKey ? 1 : 0);

  useEffect(() => {
    if (selectedCount > 0 && err) setErr(null);
  }, [selectedCount, err]);

  const setCell = (rk: unknown, key: string, val: unknown) => {
    setRows(prev => prev.map(r => (r[rowKey] === rk ? { ...r, [key]: val } : r)));
  };

  const switchTab = (idx: number) => {
    setActiveTab(idx);
    setPage(0);
  };

  const handleGoBack = async () => {
    if (!onRunPatch || submitted) return;
    setErr(null);
    try {
      await onRunPatch({ action: 'go_back', stepId: node.backStepId ?? 'go_back' });
    } catch (e) {
      setErr(e instanceof Error ? e.message : '返回失败，请重试');
    }
  };

  const handleFill = () => {
    if (node.checkKey) {
      const ck = node.checkKey;
      const next = !allSelected;
      setRows(prev => prev.map(r => ({ ...r, [ck]: next })));
      setErr(null);
      return;
    }
    if (!node.fillRows) return;
    const fillMap = new Map(
      (node.fillRows as Row[]).map(r => [String(r[rowKey] ?? ''), r]),
    );
    setRows(prev => prev.map(r => {
      const f = fillMap.get(String(r[rowKey] ?? ''));
      if (!f) return r;
      return { ...r, ...f };
    }));
    setErr(null);
  };

  const handleSubmit = () => {
    if (!onRowsSubmit || submitted) return;
    if (node.checkKey && selectedCount === 0) {
      setErr('请至少勾选一条计划后再下发');
      return;
    }
    const required = node.requiredKeys ?? [];
    if (required.length) {
      const bad = rows.filter(r => required.some(k => !String(r[k] ?? '').trim()));
      if (bad.length) { setErr(`还有 ${bad.length} 行未填写必填项（${required.join('、')}）`); return; }
    }
    setErr(null);
    setSubmitted(true);
    onRowsSubmit(rows, node.stepId);
  };

  const submitButton = (compact = false) => {
    const disabled = submitDisabled;
    const btnStyle: React.CSSProperties = compact
      ? (disabled
        ? { ...headerPrimaryBtn, opacity: 0.45, cursor: 'not-allowed' }
        : { ...headerPrimaryBtn, cursor: 'pointer' })
      : { ...primaryBtn, opacity: disabled ? 0.45 : 1, cursor: disabled ? 'not-allowed' : 'pointer' };
    if (isRunPatch && !onRowsSubmit) {
      return (
        <button
          disabled
          title="该能力暂未启用（/run-patch 端点未接入）"
          style={{ ...btnStyle, opacity: 0.45, cursor: 'not-allowed' }}
        >
          {node.submitLabel ?? '提交'}（暂未启用）
        </button>
      );
    }
    return (
      <button
        onClick={handleSubmit}
        disabled={disabled}
        title={
          node.checkKey && selectedCount === 0
            ? '请至少勾选一条计划'
            : requiredIncomplete
              ? `请先填完必填项（${(node.requiredKeys ?? []).join('、')}）`
              : undefined
        }
        style={{ ...btnStyle, cursor: disabled ? 'not-allowed' : 'pointer' }}
      >
        {submitted ? '已提交' : (node.submitLabel ?? '提交')}
      </button>
    );
  };

  const renderCell = (r: Row, col: SduiDataTableColumn) => {
    const val = r[col.key];
    if (col.editable) {
      const inputStyle = editableInputStyle(col);
      if (col.type === 'date') {
        return (
          <input
            type="date"
            value={toDateInputValue(val)}
            placeholder={col.placeholder}
            onChange={e => setCell(r[rowKey], col.key, e.target.value)}
            disabled={submitted}
            style={inputStyle}
          />
        );
      }
      const shown = col.key === 'principal' ? principalDisplayName(val) : String(val ?? '');
      return (
        <input
          value={shown}
          placeholder={col.placeholder}
          onChange={e => setCell(r[rowKey], col.key, e.target.value)}
          disabled={submitted}
          style={inputStyle}
        />
      );
    }
    if (col.type === 'status') return <StatusBadge value={String(val ?? '')} />;
    if (col.type === 'progress') return <ProgressCell value={val} />;
    const text = col.key === 'principal' ? principalDisplayName(val) : String(val ?? '');
    return <span>{text}</span>;
  };

  const headerActionButtons = useMemo(() => {
    if (!actionsInHeader) return null;
    return (
      <>
        {node.backLabel && onRunPatch && (
          <button
            type="button"
            onClick={() => { void handleGoBack(); }}
            disabled={submitted}
            style={{ ...headerBtn, opacity: submitted ? 0.5 : 1, cursor: submitted ? 'default' : 'pointer' }}
          >
            {node.backLabel}
          </button>
        )}
        {hasFill && (
          <button
            onClick={handleFill}
            disabled={submitted}
            style={{ ...headerBtn, opacity: submitted ? 0.5 : 1, cursor: submitted ? 'default' : 'pointer' }}
          >
            {fillButtonLabel}
          </button>
        )}
        {submitButton(true)}
      </>
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps -- sync disabled/submitted labels to tab bar
  }, [
    actionsInHeader, node.backLabel, node.submitLabel, onRunPatch, submitted,
    hasFill, fillButtonLabel, submitDisabled, selectedCount, requiredIncomplete,
  ]);

  useEffect(() => {
    if (!tabBarActionsApi || !actionsInHeader) return;
    tabBarActionsApi.setActions(headerActionButtons);
    return () => tabBarActionsApi.clearActions();
  }, [tabBarActionsApi, actionsInHeader, headerActionButtons]);

  const filterCompact = actionsInHeader && !actionsHoisted;

  return (
    <div className={editable ? undefined : 'sdui-tbl'} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--surface)', boxShadow: 'var(--shadow-xs)' }}>
      {(node.title || (actionsInHeader && !actionsHoisted) || filterDefs.length > 0) && (
        <div style={{
          display: 'flex', alignItems: 'center',
          gap: filterCompact ? 6 : 8,
          padding: filterCompact ? '7px 10px' : '10px 12px',
          borderBottom: '1px solid var(--border)', flexWrap: 'nowrap', minWidth: 0,
        }}>
          {node.title && (
            <span
              title={node.title}
              style={{
                ...tableTitleFont,
                color: 'var(--text-primary)',
                whiteSpace: 'nowrap',
                flex: filterCompact ? '0 1 auto' : '0 0 auto',
                minWidth: filterCompact ? 0 : undefined,
                overflow: filterCompact ? 'hidden' : undefined,
                textOverflow: filterCompact ? 'ellipsis' : undefined,
              }}
            >
              {node.title}
            </span>
          )}
          {node.title && (
            <span style={{
              fontSize: filterCompact ? 10 : 11,
              color: 'var(--text-tertiary)', background: 'var(--c-bg-soft, #eef2f7)',
              borderRadius: 999,
              padding: filterCompact ? '0 6px' : '1px 8px',
              lineHeight: filterCompact ? '18px' : undefined,
              fontVariantNumeric: 'tabular-nums', flexShrink: 0,
            }}>
              {filteredRows.length}
            </span>
          )}
          {filterDefs.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: filterCompact ? 6 : 8, flexShrink: 0 }}>
              {filterDefs.map(d => (
                <label key={d.key} style={{
                  display: 'flex', alignItems: 'center',
                  gap: filterCompact ? 3 : 4,
                  fontSize: filterCompact ? 11 : 12,
                  color: 'var(--text-secondary)', whiteSpace: 'nowrap', flexShrink: 0,
                }}>
                  <span>{d.label}</span>
                  <select
                    value={filterValues[d.key] ?? ''}
                    onChange={e => { setFilterValues(prev => ({ ...prev, [d.key]: e.target.value })); setPage(0); setActiveTab(0); }}
                    title={`${d.label}筛选`}
                    style={{
                      padding: filterCompact ? '2px 6px' : '4px 8px',
                      fontSize: filterCompact ? 11 : 12,
                      lineHeight: filterCompact ? 1.3 : undefined,
                      minWidth: filterCompact ? undefined : 120,
                      maxWidth: filterCompact ? 88 : 220,
                      borderRadius: 'var(--r-sm)', border: '1px solid var(--border)',
                      background: 'var(--surface)', color: 'var(--text-primary)', cursor: 'pointer',
                    }}
                  >
                    <option value="">全部</option>
                    {d.options.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </label>
              ))}
            </div>
          )}
          {actionsInHeader && !actionsHoisted && (
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
              {node.backLabel && onRunPatch && (
                <button
                  type="button"
                  onClick={() => { void handleGoBack(); }}
                  disabled={submitted}
                  style={{ ...headerBtn, opacity: submitted ? 0.5 : 1, cursor: submitted ? 'default' : 'pointer' }}
                >
                  {node.backLabel}
                </button>
              )}
              {hasFill && (
                <button
                  onClick={handleFill}
                  disabled={submitted}
                  style={{ ...headerBtn, opacity: submitted ? 0.5 : 1, cursor: submitted ? 'default' : 'pointer' }}
                >
                  {fillButtonLabel}
                </button>
              )}
              {submitButton(true)}
            </div>
          )}
        </div>
      )}
      {groupTabMode && tabGroups.length > 0 && (
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 8px', flexWrap: 'wrap', background: 'var(--c-surface-2)' }}>
          {tabGroups.map((t, i) => (
            <button
              key={t.label}
              type="button"
              onClick={() => switchTab(i)}
              style={{
                padding: '8px 12px', fontSize: 12, border: 'none', background: 'none', cursor: 'pointer',
                color: i === activeTabIdx ? 'var(--c-brand-text, #1e34a8)' : 'var(--text-tertiary)',
                borderBottom: `2px solid ${i === activeTabIdx ? 'var(--c-brand, #3551d8)' : 'transparent'}`,
                marginBottom: -1, fontWeight: i === activeTabIdx ? 600 : 400,
              }}
            >
              {t.label}
              <span style={{ fontSize: 11, color: 'var(--text-faint, #94a3b8)', marginLeft: 4, fontVariantNumeric: 'tabular-nums' }}>
                {t.rows.length}
              </span>
            </button>
          ))}
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
          <thead>
            <tr>
              {node.checkKey && <th style={{ ...th, width: 36 }} />}
              {displayColumns.map((c, i) => <th key={i} style={colCellStyle(c, { ...th, width: c.width })}>{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {groups.map((g, gi) => (
              <Fragment key={gi}>
                {g.label && (
                  <tr>
                    <td colSpan={totalCols} style={{ padding: '6px 12px', fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', background: 'var(--c-surface-2)', textTransform: 'uppercase', letterSpacing: '.04em' }}>{g.label}</td>
                  </tr>
                )}
                {g.rows.map((r, ri) => (
                  <tr key={`${gi}-${String(r[rowKey] ?? ri)}`} style={{ borderBottom: '1px solid var(--border)' }}>
                    {node.checkKey && (
                      <td style={{ ...td, textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={isRowChecked(r[node.checkKey])}
                          disabled={submitted}
                          onChange={e => setCell(r[rowKey], node.checkKey!, e.target.checked)}
                          style={{ cursor: submitted ? 'default' : 'pointer' }}
                        />
                      </td>
                    )}
                    {displayColumns.map((c, ci) => <td key={ci} style={colCellStyle(c, td)}>{renderCell(r, c)}</td>)}
                  </tr>
                ))}
              </Fragment>
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

      {editable && (!actionsInHeader || err) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderTop: '1px solid var(--border)' }}>
          {err && <span style={{ fontSize: 12, color: 'var(--red-600, #dc2626)', marginRight: 'auto' }}>{err}</span>}
          {!err && <span style={{ marginRight: 'auto' }} />}
          {hasFill && !actionsInHeader && (
            <button onClick={handleFill} disabled={submitted} style={pagerBtn(submitted)}>{fillButtonLabel}</button>
          )}
          {!actionsInHeader && submitButton()}
        </div>
      )}
    </div>
  );
}

export function SduiDataTable({ node }: { node: SduiDataTableNode }) {
  if (isTypedColumns(node.columns) && node.dualMode && !node.editable) {
    return <DualModeTable node={node} />;
  }
  return isTypedColumns(node.columns) ? <TypedTable node={node} /> : <LegacyTable node={node} />;
}
