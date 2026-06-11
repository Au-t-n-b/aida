// @ts-nocheck
'use client';

import { useState } from 'react';

/* ── TopologyView ── */
const TOPO_NODES = [
  { id: 'core1', label: 'Core-01', x: 200, y: 60, type: 'core' },
  { id: 'core2', label: 'Core-02', x: 340, y: 60, type: 'core' },
  { id: 'agg1', label: 'Agg-01', x: 100, y: 160, type: 'agg' },
  { id: 'agg2', label: 'Agg-02', x: 240, y: 160, type: 'agg' },
  { id: 'agg3', label: 'Agg-03', x: 380, y: 160, type: 'agg' },
  { id: 'acc1', label: 'Acc-01', x: 60, y: 260, type: 'acc' },
  { id: 'acc2', label: 'Acc-02', x: 160, y: 260, type: 'acc' },
  { id: 'acc3', label: 'Acc-03', x: 260, y: 260, type: 'acc', spof: true },
  { id: 'acc4', label: 'Acc-04', x: 360, y: 260, type: 'acc' },
  { id: 'acc5', label: 'Acc-05', x: 460, y: 260, type: 'acc' },
];

const TOPO_LINKS = [
  { from: 'core1', to: 'core2' },
  { from: 'core1', to: 'agg1' }, { from: 'core1', to: 'agg2' },
  { from: 'core2', to: 'agg2' }, { from: 'core2', to: 'agg3' },
  { from: 'agg1', to: 'acc1' }, { from: 'agg1', to: 'acc2' },
  { from: 'agg2', to: 'acc2' }, { from: 'agg2', to: 'acc3' },
  { from: 'agg3', to: 'acc3' }, { from: 'agg3', to: 'acc4' }, { from: 'agg3', to: 'acc5' },
];

const NODE_COLORS = {
  core: '#1d4ed8',
  agg: '#ca8a04',
  acc: '#3f3f46',
};

export function TopologyView({ height = 280 }) {
  const [hovered, setHovered] = useState(null);
  const nodeMap = Object.fromEntries(TOPO_NODES.map(n => [n.id, n]));

  return (
    <div style={{ position: 'relative', height, background: 'var(--zinc-50)', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border)' }}>
      <svg width="100%" height="100%" viewBox="0 0 540 300" preserveAspectRatio="xMidYMid meet">
        {/* Links */}
        {TOPO_LINKS.map((link, i) => {
          const a = nodeMap[link.from], b = nodeMap[link.to];
          const isActive = hovered === link.from || hovered === link.to;
          return (
            <line
              key={i}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={isActive ? 'var(--accent)' : 'var(--zinc-300)'}
              strokeWidth={isActive ? 2 : 1.5}
              strokeDasharray={isActive ? 'none' : 'none'}
              style={{ transition: 'stroke .2s, stroke-width .2s' }}
            />
          );
        })}

        {/* Nodes */}
        {TOPO_NODES.map(node => {
          const isHovered = hovered === node.id;
          const r = node.type === 'core' ? 18 : node.type === 'agg' ? 14 : 11;
          return (
            <g key={node.id} onMouseEnter={() => setHovered(node.id)} onMouseLeave={() => setHovered(null)}>
              {node.spof && (
                <circle cx={node.x} cy={node.y} r={r + 6} fill="var(--red-50)" stroke="var(--red-200)" strokeWidth={1} />
              )}
              <circle
                cx={node.x} cy={node.y} r={r}
                fill={isHovered ? 'var(--accent)' : NODE_COLORS[node.type]}
                stroke="#fff" strokeWidth={2}
                style={{ cursor: 'pointer', transition: 'fill .15s' }}
              />
              <text
                x={node.x} y={node.y + r + 12}
                textAnchor="middle" fontSize={9} fill="var(--text-secondary)"
                fontFamily="var(--font-mono)"
              >
                {node.label}
              </text>
              {node.spof && (
                <text x={node.x + r} y={node.y - r} fontSize={10} fill="var(--red-600)">!</text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ position: 'absolute', bottom: 8, left: 8, display: 'flex', gap: 10, fontSize: '10px', color: 'var(--text-secondary)' }}>
        {[['core', '核心层', '#1d4ed8'], ['agg', '汇聚层', '#ca8a04'], ['acc', '接入层', '#3f3f46']].map(([, label, color]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
            {label}
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--red-50)', border: '1px solid var(--red-300)' }} />
          SPOF
        </div>
      </div>

      {/* Tooltip */}
      {hovered && (() => {
        const node = nodeMap[hovered];
        return (
          <div style={{
            position: 'absolute', top: 8, right: 8,
            background: 'var(--slate-900)', color: '#e4e4e7',
            padding: '6px 10px', borderRadius: 'var(--radius-md)',
            fontSize: '11px', fontFamily: 'var(--font-mono)',
          }}>
            <div style={{ fontWeight: 600 }}>{node.label}</div>
            <div style={{ color: '#71717a' }}>{node.type.toUpperCase()} · {node.x},{node.y}</div>
            {node.spof && <div style={{ color: 'var(--red-400)' }}>⚠ SPOF 节点</div>}
          </div>
        );
      })()}
    </div>
  );
}

/* ── GanttView ── */
const GANTT_TASKS = [
  { id: 1, name: '需求确认', start: 0, dur: 3, type: 'milestone', done: true },
  { id: 2, name: '工勘执行', start: 2, dur: 8, type: 'task', done: true },
  { id: 3, name: '设计评审', start: 9, dur: 5, type: 'task', done: true },
  { id: 4, name: '设备采购', start: 10, dur: 12, type: 'task', progress: 60, critical: true },
  { id: 5, name: '环境准备', start: 14, dur: 6, type: 'task', progress: 30 },
  { id: 6, name: '硬件安装', start: 22, dur: 8, type: 'task', progress: 0, critical: true },
  { id: 7, name: '系统配置', start: 28, dur: 10, type: 'task', progress: 0, critical: true },
  { id: 8, name: '联调测试', start: 36, dur: 7, type: 'task', progress: 0, critical: true },
  { id: 9, name: '验收交付', start: 42, dur: 3, type: 'milestone', progress: 0 },
];
const TOTAL_DAYS = 47;
const TODAY = 15;

export function GanttView({ height = 280 }) {
  const [hovered, setHovered] = useState(null);
  const rowH = 24;
  const labelW = 80;
  const chartW = 440;
  const todayX = labelW + (TODAY / TOTAL_DAYS) * chartW;
  const padding = 8;

  return (
    <div style={{ height, background: 'var(--zinc-50)', borderRadius: 'var(--radius-md)', overflow: 'auto', border: '1px solid var(--border)' }} className="claw-scroll">
      <svg width={labelW + chartW + padding * 2} height={GANTT_TASKS.length * rowH + 36} style={{ display: 'block' }}>
        {/* Header row — dates */}
        {[0, 10, 20, 30, 40, 47].map(day => {
          const x = labelW + (day / TOTAL_DAYS) * chartW;
          return (
            <g key={day}>
              <line x1={x} y1={0} x2={x} y2={GANTT_TASKS.length * rowH + 28} stroke="var(--border)" strokeWidth={0.5} />
              <text x={x} y={14} textAnchor="middle" fontSize={9} fill="var(--text-tertiary)" fontFamily="var(--font-mono)">D{day}</text>
            </g>
          );
        })}

        {/* Today marker */}
        <line x1={todayX} y1={0} x2={todayX} y2={GANTT_TASKS.length * rowH + 28} stroke="var(--red-500)" strokeWidth={1.5} strokeDasharray="4,2" />
        <text x={todayX + 3} y={14} fontSize={9} fill="var(--red-600)" fontFamily="var(--font-mono)" fontWeight={600}>今</text>

        {/* Tasks */}
        {GANTT_TASKS.map((task, i) => {
          const y = 24 + i * rowH;
          const barX = labelW + (task.start / TOTAL_DAYS) * chartW;
          const barW = (task.dur / TOTAL_DAYS) * chartW;
          const isHovered = hovered === task.id;
          const barColor = task.done ? 'var(--green-600)' : task.critical ? 'var(--accent)' : 'var(--blue-600)';

          return (
            <g key={task.id} onMouseEnter={() => setHovered(task.id)} onMouseLeave={() => setHovered(null)}>
              {/* Zebra stripe */}
              {i % 2 === 0 && <rect x={0} y={y - 2} width={labelW + chartW + padding * 2} height={rowH} fill="rgba(0,0,0,.02)" />}
              {/* Label */}
              <text x={labelW - 6} y={y + rowH / 2 + 3} textAnchor="end" fontSize={10} fill={isHovered ? 'var(--accent)' : 'var(--text-secondary)'} fontFamily="var(--font-sans)">
                {task.name}
              </text>
              {/* Bar background */}
              <rect x={barX} y={y + 3} width={barW} height={rowH - 6} rx={3} fill={task.done ? 'var(--green-100)' : 'var(--zinc-200)'} />
              {/* Progress fill */}
              {(task.done || (task.progress != null && task.progress > 0)) && (
                <rect x={barX} y={y + 3} width={barW * (task.done ? 1 : task.progress / 100)} height={rowH - 6} rx={3} fill={barColor} />
              )}
              {/* Label on bar */}
              {barW > 30 && (
                <text x={barX + 4} y={y + rowH / 2 + 3} fontSize={9} fill={task.done ? 'var(--green-700)' : task.progress > 50 ? '#fff' : 'var(--text-secondary)'} fontFamily="var(--font-mono)">
                  {task.done ? '✓' : task.progress != null ? `${task.progress}%` : ''}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* ── EmbedView router ── */
export function EmbedView({ kind, height = 280 }) {
  if (kind === 'topology') return <TopologyView height={height} />;
  if (kind === 'gantt') return <GanttView height={height} />;
  return null;
}
