import React, { useMemo } from 'react';
import type { SduiGanttRow } from '@/lib/sdui';

const STATUS_COLOR: Record<string, string> = {
  '已下发': '#10b981',
  '待下发': '#64748b',
  '进行中': '#3551d8',
};

function parseDay(s: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s.trim());
  if (!m) return null;
  const y = m[1], mo = m[2], d = m[3];
  if (y == null || mo == null || d == null) return null;
  return Date.UTC(+y, +mo - 1, +d);
}

function fmtDay(ts: number): string {
  const d = new Date(ts);
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
}

type ParsedRow = SduiGanttRow & { s: number; e: number };

export function SduiGanttChart({ rows, title }: { rows: SduiGanttRow[]; title?: string }) {
  const { grouped, minTs, maxTs, ticks } = useMemo(() => {
    const valid: ParsedRow[] = [];
    for (const r of rows) {
      const s = parseDay(r.start);
      const e = parseDay(r.end);
      if (s == null || e == null) continue;
      valid.push({ ...r, s, e: Math.max(e, s) });
    }
    if (!valid.length) {
      return { grouped: [] as Array<{ name: string; items: ParsedRow[] }>, minTs: 0, maxTs: 0, ticks: [] as number[] };
    }

    const minTs = Math.min(...valid.map(r => r.s));
    const maxTs = Math.max(...valid.map(r => r.e));
    const span = maxTs - minTs || 86400000;
    const tickCount = Math.min(8, Math.max(3, Math.ceil(span / (7 * 86400000))));
    const ticks: number[] = [];
    for (let i = 0; i <= tickCount; i++) ticks.push(minTs + (span * i) / tickCount);

    const groups = new Map<string, ParsedRow[]>();
    for (const r of valid) {
      const g = r.group?.trim() || '未分组';
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g)!.push(r);
    }
    const grouped = Array.from(groups.entries()).map(([name, items]) => ({
      name,
      items: items.sort((a, b) => a.s - b.s || a.label.localeCompare(b.label, 'zh-CN')),
    }));

    return { grouped, minTs, maxTs, ticks };
  }, [rows]);

  if (!grouped.length) {
    return (
      <div style={{ padding: 16, color: 'var(--text-tertiary)', fontSize: 13 }}>
        暂无有效日期数据，无法绘制甘特图
      </div>
    );
  }

  const span = maxTs - minTs || 86400000;
  const pct = (ts: number) => ((ts - minTs) / span) * 100;

  const barColor = (status?: string) => (status && STATUS_COLOR[status]) || '#3551d8';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {title && <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>}
      <div style={{
        overflow: 'auto', maxHeight: 520,
        border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface)',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '168px 1fr',
          position: 'sticky', top: 0, background: 'var(--surface)', zIndex: 2,
          borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ padding: '6px 10px', fontSize: 11, color: 'var(--text-tertiary)' }}>活动</div>
          <div style={{ position: 'relative', height: 28, borderLeft: '1px solid var(--border)' }}>
            {ticks.map((t, i) => (
              <span key={i} style={{
                position: 'absolute', left: `${pct(t)}%`, transform: 'translateX(-50%)',
                fontSize: 10, color: 'var(--text-tertiary)', top: 8, fontFamily: 'var(--font-mono)',
              }}>
                {fmtDay(t)}
              </span>
            ))}
          </div>
        </div>
        {grouped.map(g => (
          <div key={g.name}>
            <div style={{
              padding: '4px 10px', fontSize: 11, fontWeight: 700,
              color: 'var(--c-brand-text, #1e34a8)', background: 'var(--c-brand-soft, #eef1fc)',
              borderBottom: '1px solid var(--border)',
            }}>
              {g.name}
            </div>
            {g.items.map(r => {
              const left = pct(r.s);
              const width = Math.max(pct(r.e) - left, 0.8);
              const tip = `${r.start} → ${r.end}${r.status ? ` · ${r.status}` : ''}`;
              return (
                <div key={r.id} style={{
                  display: 'grid', gridTemplateColumns: '168px 1fr',
                  borderBottom: '1px solid var(--border)', minHeight: 32,
                }}>
                  <div style={{
                    padding: '6px 10px', fontSize: 12, color: 'var(--text-secondary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }} title={r.label}>
                    {r.label}
                  </div>
                  <div style={{
                    position: 'relative', borderLeft: '1px solid var(--border)',
                    background: 'repeating-linear-gradient(90deg, transparent, transparent calc(12.5% - 1px), rgba(148,163,184,.12) calc(12.5% - 1px), rgba(148,163,184,.12) 12.5%)',
                  }}>
                    <div title={tip} style={{
                      position: 'absolute', top: '50%', transform: 'translateY(-50%)',
                      left: `${left}%`, width: `${width}%`, height: 14,
                      borderRadius: 4, background: barColor(r.status),
                      boxShadow: '0 1px 2px rgba(15,23,42,.08)',
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 11, color: 'var(--text-tertiary)' }}>
        <span><i style={{ display: 'inline-block', width: 12, height: 8, background: '#3551d8', borderRadius: 2, marginRight: 4, verticalAlign: 'middle' }} />计划活动</span>
        <span><i style={{ display: 'inline-block', width: 12, height: 8, background: '#64748b', borderRadius: 2, marginRight: 4, verticalAlign: 'middle' }} />待下发</span>
        <span><i style={{ display: 'inline-block', width: 12, height: 8, background: '#10b981', borderRadius: 2, marginRight: 4, verticalAlign: 'middle' }} />已下发</span>
      </div>
    </div>
  );
}
