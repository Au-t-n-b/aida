// @ts-nocheck
'use client';

import Link from '@/compat/link';
import { ICON_MAP } from '../icons';
import { Badge, Button, KPI, Progress, Panel } from '../primitives';
import { ALL_MODULES } from '../../data/modules-data';

const COCKPIT_KPIS = [
  { label: '项目进度', value: 38, unit: '%', tone: 'accent', sparkline: [10, 15, 22, 28, 35, 38] },
  { label: '已完成任务', value: 47, unit: '项', tone: 'green', sparkline: [5, 12, 20, 30, 42, 47] },
  { label: '进行中', value: 12, unit: '项', tone: 'amber' },
  { label: '风险预警', value: 3, unit: '条', tone: 'red' },
];

const COCKPIT_MODULES = [
  { key: 'survey', progress: 100, status: 'done', stage: '完成', next: '已生成交付基线' },
  { key: 'modeling', progress: 72, status: 'running', stage: '执行', next: '拓扑仿真进行中' },
  { key: 'job', progress: 45, status: 'running', stage: '上传', next: '等待 WBS 文件上传' },
  { key: 'design', progress: 0, status: 'pending', stage: '未开始', next: '等待工勘报告' },
  { key: 'install', progress: 0, status: 'pending', stage: '未开始', next: '等待设计评审' },
  { key: 'deploy', progress: 0, status: 'pending', stage: '未开始', next: '等待安装完成' },
];

const TIMELINE_TASKS = [
  { name: '工勘', start: 0, dur: 8, done: true },
  { name: '建模', start: 6, dur: 10, progress: 72, critical: true },
  { name: '作业规划', start: 10, dur: 8, progress: 45 },
  { name: '概要设计', start: 16, dur: 8, progress: 0 },
  { name: '安装施工', start: 22, dur: 10, progress: 0, critical: true },
  { name: '割接部署', start: 30, dur: 6, progress: 0, critical: true },
];
const TOTAL_DAYS = 40;
const TODAY_DAY = 16;

const STATUS_TONE = { done: 'green', running: 'blue', pending: 'default', warning: 'amber' };
const STATUS_LABEL = { done: '已完成', running: '进行中', pending: '待启动', warning: '有风险' };

function ModuleCard({ mod }) {
  const data = COCKPIT_MODULES.find(m => m.key === mod.key) || {};
  const Icon = ICON_MAP[mod.iconName];
  const tone = STATUS_TONE[data.status] || 'default';

  return (
    <Link href={`/module/${mod.key}`} style={{ textDecoration: 'none' }}>
      <div style={{
        padding: 'var(--pad-panel)', borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border)', background: 'var(--surface)',
        transition: 'box-shadow .15s, border-color .15s',
        cursor: 'pointer',
      }}
        onMouseEnter={e => { e.currentTarget.style.boxShadow = 'var(--shadow-md)'; e.currentTarget.style.borderColor = 'var(--border-strong)'; }}
        onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.borderColor = 'var(--border)'; }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 30, height: 30, borderRadius: 'var(--radius-sm)', background: 'var(--accent-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {Icon && <Icon size={15} color="var(--accent)" />}
            </div>
            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>{mod.name}</span>
          </div>
          <Badge tone={tone} size="xs" dot>{STATUS_LABEL[data.status] || '未知'}</Badge>
        </div>
        <Progress value={data.progress || 0} status={data.status === 'running' ? 'running' : data.status === 'done' ? 'done' : 'default'} height={4} />
        <div style={{ marginTop: 6, fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', display: 'flex', justifyContent: 'space-between' }}>
          <span>{data.stage}</span>
          <span>{data.progress || 0}%</span>
        </div>
        {data.next && (
          <div style={{ marginTop: 4, fontSize: '10px', color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            → {data.next}
          </div>
        )}
      </div>
    </Link>
  );
}

function CockpitGantt() {
  const labelW = 72;
  const chartW = 340;
  const rowH = 22;
  const todayX = labelW + (TODAY_DAY / TOTAL_DAYS) * chartW;

  return (
    <div style={{ overflow: 'auto' }} className="claw-scroll">
      <svg width={labelW + chartW + 16} height={TIMELINE_TASKS.length * rowH + 24} style={{ display: 'block' }}>
        {/* Date ticks */}
        {[0, 10, 20, 30, 40].map(d => {
          const x = labelW + (d / TOTAL_DAYS) * chartW;
          return (
            <g key={d}>
              <line x1={x} y1={0} x2={x} y2={TIMELINE_TASKS.length * rowH + 16} stroke="var(--border)" strokeWidth={0.5} />
              <text x={x} y={12} textAnchor="middle" fontSize={8} fill="var(--text-tertiary)" fontFamily="var(--font-mono)">D{d}</text>
            </g>
          );
        })}

        {/* Today */}
        <line x1={todayX} y1={0} x2={todayX} y2={TIMELINE_TASKS.length * rowH + 16} stroke="var(--red-500)" strokeWidth={1.5} strokeDasharray="3,2" />

        {TIMELINE_TASKS.map((task, i) => {
          const y = 18 + i * rowH;
          const bx = labelW + (task.start / TOTAL_DAYS) * chartW;
          const bw = (task.dur / TOTAL_DAYS) * chartW;
          const color = task.done ? 'var(--green-600)' : task.critical ? 'var(--accent)' : 'var(--blue-600)';

          return (
            <g key={i}>
              {i % 2 === 0 && <rect x={0} y={y - 2} width={labelW + chartW + 16} height={rowH} fill="rgba(0,0,0,.015)" />}
              <text x={labelW - 4} y={y + rowH / 2 + 3} textAnchor="end" fontSize={9} fill="var(--text-secondary)" fontFamily="var(--font-sans)">{task.name}</text>
              <rect x={bx} y={y + 3} width={bw} height={rowH - 6} rx={2} fill="var(--zinc-200)" />
              {(task.done || (task.progress != null && task.progress > 0)) && (
                <rect x={bx} y={y + 3} width={bw * (task.done ? 1 : (task.progress || 0) / 100)} height={rowH - 6} rx={2} fill={color} />
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function CockpitScreen() {
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 'var(--pad-panel)' }} className="claw-scroll">
      {/* Project header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 3 }}>华南区 DC 扩容</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Badge tone="blue" size="xs" dot>进行中</Badge>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>预计完成: 2025-08-15</span>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>· 项目经理: 张伟</span>
          </div>
        </div>
        <Button variant="secondary" size="sm">导出报告</Button>
      </div>

      {/* Alert */}
      <div style={{
        padding: '8px 12px', borderRadius: 'var(--radius-md)', marginBottom: 16,
        background: 'var(--amber-50)', border: '1px solid var(--amber-100)',
        display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-xs)',
      }}>
        <span>⚠️</span>
        <span style={{ color: 'var(--amber-700)', fontWeight: 500 }}>建模仿真</span>
        <span style={{ color: 'var(--text-secondary)' }}>识别到 3 个 SPOF 节点，建议在割接前完成冗余链路配置。</span>
        <a href="/module/modeling" style={{ marginLeft: 'auto', color: 'var(--amber-700)', fontWeight: 600, fontSize: 'var(--text-xs)' }}>查看详情 →</a>
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        {COCKPIT_KPIS.map((kpi, i) => (
          <Panel key={i} padding="var(--pad-panel)">
            <KPI {...kpi} />
          </Panel>
        ))}
      </div>

      {/* Timeline */}
      <Panel title="项目时间线" subtitle={`第 ${TODAY_DAY} 天 / 共 ${TOTAL_DAYS} 天`} style={{ marginBottom: 16 }}>
        <CockpitGantt />
      </Panel>

      {/* Module cards */}
      <div style={{ marginBottom: 8 }}>
        <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 10 }}>交付模块</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          {ALL_MODULES.map(mod => <ModuleCard key={mod.key} mod={mod} />)}
        </div>
      </div>
    </div>
  );
}
