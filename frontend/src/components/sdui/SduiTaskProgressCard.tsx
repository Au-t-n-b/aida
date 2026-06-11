/**
 * SduiTaskProgressCard — 设备安装「任务进展」卡（id=task-table）
 * 概览环 + KPI 随表格进度实时联动；编辑模式下进度列支持拖拽。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { SduiCardNode, SduiDataTableColumn, SduiDataTableNode, SduiNode } from '@/lib/sdui';
import { Panel } from '@/components/primitives';
import { SduiDonutChart } from './SduiDonutChart';
import { SduiNodeView } from './SduiNodeView';
import { useSduiRuntime } from './SduiContext';
import { taskProgressFill } from './taskProgressColors';
import { principalDisplayName } from './principalDisplayName';

type Row = Record<string, unknown>;

const STAT_ACCENT: Record<string, string> = {
  accent: '#3551d8', success: '#0f9d58', warning: '#d97706', error: '#dc2626', subtle: '#94a3b8',
};

function isDataTable(n: SduiNode): n is SduiDataTableNode {
  return (n as SduiDataTableNode).type === 'DataTable';
}

function statusFromProgress(pct: number): string {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  if (p >= 100) return '已完成';
  if (p >= 1) return '进行中';
  return '未开始';
}

function donutTone(pct: number): string {
  if (pct >= 80) return 'success';
  if (pct >= 40) return 'warning';
  return 'error';
}

function deriveOverview(rows: Row[]) {
  const total = rows.length;
  const done = rows.filter(r => Number(r.progress) >= 100 || r.status === '已完成').length;
  const inProg = rows.filter(r => {
    const p = Number(r.progress) || 0;
    return (p > 0 && p < 100) || r.status === '进行中';
  }).length;
  const pct = total ? Math.round(done / total * 100) : 0;
  return { total, done, inProg, pct };
}

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

function ProgressReadonly({ value }: { value: unknown }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 100 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 999, background: 'var(--c-bg-soft)', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 'inherit', background: taskProgressFill(pct), transition: 'width .25s, background .2s' }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--c-text-muted)', fontVariantNumeric: 'tabular-nums', minWidth: 32 }}>{pct}%</span>
    </div>
  );
}

function ProgressEditor({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [isDragging, setIsDragging] = useState(false);

  const pctFromClientX = useCallback((clientX: number) => {
    const el = trackRef.current;
    if (!el) return value;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0) return value;
    return Math.round(Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100)));
  }, [value]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      onChange(pctFromClientX(e.clientX));
    };
    const onUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      setIsDragging(false);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [onChange, pctFromClientX]);

  const pct = Math.max(0, Math.min(100, value));
  const fill = taskProgressFill(pct);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 120 }}>
      <div
        style={{
          flex: 1,
          position: 'relative',
          height: 18,
          display: 'flex',
          alignItems: 'center',
          touchAction: 'none',
          userSelect: 'none',
        }}
      >
        <div
          ref={trackRef}
          role="slider"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          tabIndex={0}
          onMouseDown={e => {
            e.preventDefault();
            dragging.current = true;
            setIsDragging(true);
            onChange(pctFromClientX(e.clientX));
          }}
          onKeyDown={e => {
            if (e.key === 'ArrowLeft') onChange(Math.max(0, pct - 5));
            if (e.key === 'ArrowRight') onChange(Math.min(100, pct + 5));
          }}
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            height: 8,
            borderRadius: 999,
            background: 'var(--c-bg-soft)',
            border: '1px solid var(--c-border)',
            overflow: 'visible',
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: '100%',
              borderRadius: 'inherit',
              background: fill,
              pointerEvents: 'none',
              transition: isDragging ? 'none' : 'width .15s ease, background .2s ease',
            }}
          />
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: `clamp(0px, calc(${pct}% - 6px), calc(100% - 12px))`,
              width: 12,
              height: 12,
              marginTop: -6,
              borderRadius: '50%',
              background: '#fff',
              border: `2px solid ${fill}`,
              boxShadow: '0 1px 3px rgba(15,23,42,.12)',
              pointerEvents: 'none',
              transition: isDragging ? 'none' : 'left .12s ease, border-color .2s ease',
            }}
          />
        </div>
      </div>
      <span style={{ fontSize: 11, color: 'var(--c-text-muted)', fontVariantNumeric: 'tabular-nums', minWidth: 32 }}>{pct}%</span>
    </div>
  );
}

function KpiRow({ total, done, inProg }: { total: number; done: number; inProg: number }) {
  const items = [
    { title: '任务总数', value: `${total} 条`, color: 'accent' },
    { title: '已完成', value: `${done} 条`, color: 'success' },
    { title: '进行中', value: `${inProg} 条`, color: 'warning' },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, flex: 2, minWidth: 0 }}>
      {items.map((item, i) => {
        const accent = STAT_ACCENT[item.color] ?? '#94a3b8';
        return (
          <div key={i} style={{ position: 'relative', background: 'var(--c-surface)', border: '1px solid var(--c-border)', borderRadius: 'var(--r-md)', boxShadow: 'var(--shadow-xs)', padding: '12px 16px 12px 20px', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 0, top: 11, bottom: 11, width: 3, borderRadius: '0 999px 999px 0', background: accent }} />
            <div style={{ fontSize: 'var(--fs-11)', color: 'var(--c-text-muted)', textTransform: 'uppercase', letterSpacing: '.05em', fontWeight: 500 }}>{item.title}</div>
            <div style={{ fontSize: 'var(--fs-24)', fontWeight: 600, color: 'var(--c-text)', marginTop: 5, fontVariantNumeric: 'tabular-nums' }}>{item.value}</div>
          </div>
        );
      })}
    </div>
  );
}

const th: React.CSSProperties = {
  padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)',
  background: 'var(--c-surface-2)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
};
const td: React.CSSProperties = { padding: '9px 12px', color: 'var(--text-secondary)', verticalAlign: 'middle' };

export function SduiTaskProgressCard({ node }: { node: SduiCardNode }) {
  const { onRunPatch, streamEpoch } = useSduiRuntime();
  const children = node.children ?? [];

  const tableNode = useMemo(
    () => children.find(c => isDataTable(c) && c.id === 'task-table-dt') as SduiDataTableNode | undefined,
    [children],
  );
  const extras = useMemo(
    () => children.filter(c => !(isDataTable(c) && c.id === 'task-table-dt') && !(c as { id?: string }).id?.includes('task-progress-overview')),
    [children],
  );

  const columns = (tableNode?.columns ?? []) as SduiDataTableColumn[];
  const rowKey = tableNode?.rowKey ?? 'id';
  const seed = JSON.stringify(tableNode?.rows ?? []);

  const normalizeRows = useCallback((raw: Row[]) => raw.map(r => {
    const pct = Number(r.progress) || 0;
    return { ...r, progress: pct, status: statusFromProgress(pct) };
  }), []);

  const [rows, setRows] = useState<Row[]>(() => normalizeRows((tableNode?.rows ?? []) as Row[]));
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const snapshotRef = useRef<Row[]>([]);

  useEffect(() => {
    if (editing) return;
    setRows(normalizeRows((tableNode?.rows ?? []) as Row[]));
  }, [seed, streamEpoch, editing, tableNode?.rows, normalizeRows]);

  const overview = useMemo(() => deriveOverview(rows), [rows]);

  const setProgress = useCallback((id: unknown, pct: number) => {
    setRows(prev => prev.map(r => {
      if (r[rowKey] !== id) return r;
      const status = statusFromProgress(pct);
      return { ...r, progress: pct, status };
    }));
  }, [rowKey]);

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
      const payload = rows.map(r => ({ id: r[rowKey], progress: r.progress }));
      await onRunPatch({ action: 'task_progress', stepId: 'task_progress', rows: payload });
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

  const headerAction = editing ? (
    <div style={{ display: 'flex', gap: 8 }}>
      <button type="button" onClick={cancelEdit} disabled={saving} style={{ ...headerBtn, border: '1px solid var(--c-border)', background: 'var(--c-surface)', color: 'var(--c-text-2)' }}>取消</button>
      <button type="button" onClick={() => { void saveEdit(); }} disabled={saving} style={{ ...headerBtn, border: '1px solid var(--c-brand)', background: 'var(--c-brand)', color: '#fff' }}>
        {saving ? '保存中…' : '保存'}
      </button>
    </div>
  ) : (
    <button type="button" onClick={startEdit} style={{ ...headerBtn, border: '1px solid var(--c-border)', background: 'var(--c-surface)', color: 'var(--c-text-2)' }}>编辑</button>
  );

  if (!tableNode) {
    return (
      <Panel title={node.title ?? undefined} style={{ animation: 'sdui-node-in .28s cubic-bezier(.2,.65,.4,1) both' }}>
        {children.map((c, i) => <SduiNodeView key={i} node={c} />)}
      </Panel>
    );
  }

  return (
    <Panel title={node.title ?? undefined} action={headerAction} style={{ animation: 'sdui-node-in .28s cubic-bezier(.2,.65,.4,1) both' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14, flexWrap: 'wrap' }}>
        <SduiDonutChart
          segments={[
            { label: '已完成', value: overview.pct, color: donutTone(overview.pct) },
            { label: '剩余', value: Math.max(0, 100 - overview.pct), color: 'subtle' },
          ]}
          centerValue={`${overview.pct}%`}
        />
        <KpiRow total={overview.total} done={overview.done} inProg={overview.inProg} />
      </div>

      {extras.map((c, i) => (
        <div key={i} style={{ marginBottom: 10 }}>
          <SduiNodeView node={c} />
        </div>
      ))}

      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--surface)', boxShadow: 'var(--shadow-xs)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{tableNode.title}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', background: 'var(--c-bg-soft)', borderRadius: 999, padding: '1px 8px', fontVariantNumeric: 'tabular-nums' }}>{rows.length}</span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {columns.map((c, i) => <th key={i} style={{ ...th, width: c.width }}>{c.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={String(r[rowKey] ?? ri)} style={{ borderBottom: '1px solid var(--border)' }}>
                  {columns.map((c, ci) => (
                    <td key={ci} style={td}>
                      {c.key === 'progress' && editing ? (
                        <ProgressEditor value={Number(r.progress) || 0} onChange={v => setProgress(r[rowKey], v)} />
                      ) : c.type === 'status' ? (
                        <StatusBadge value={String(r[c.key] ?? '')} />
                      ) : c.type === 'progress' ? (
                        <ProgressReadonly value={r[c.key]} />
                      ) : (
                        <span>{c.key === 'principal' ? principalDisplayName(r[c.key]) : String(r[c.key] ?? '')}</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {err && (
          <div style={{ padding: '8px 12px', fontSize: 12, color: 'var(--red-600, #dc2626)', borderTop: '1px solid var(--border)' }}>{err}</div>
        )}
      </div>
    </Panel>
  );
}
