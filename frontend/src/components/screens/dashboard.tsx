// @ts-nocheck
'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import Link from '@/compat/link';
import { RISKS, MILESTONES, RISK_SOURCES } from '../../data/app-data';
import { DispatchTracker } from '../dispatch-tracker';
import Drawer from '../drawer';
import MilestoneBoard from './milestone-board/milestone-board';
import { podMilestonesFromSnapshot } from './milestone-board/data';

const commonRoomReady = {
  expectedEnd: '2025-12-01', actualEnd: '2026-03-10', progress: 100, common: true, owner: '严浩丁 00635652',
};
const deliveryMilestone = (expectedEnd, actualEnd, owner = '') => ({ expectedEnd, actualEnd, progress: actualEnd ? 100 : 0, owner });
const deliveryPod = (id, arrival, cabling, powerOn, online, handover) => ({
  pod: id,
  batch: id.split('-')[0] || id,
  stages: {
    roomReady: commonRoomReady,
    arrival: deliveryMilestone(...arrival),
    cabling: deliveryMilestone(...cabling),
    powerOn: deliveryMilestone(...powerOn),
    online: deliveryMilestone(...online),
    handover: deliveryMilestone(...handover),
  },
});

const formatLocalDate = (value) => {
  if (!value) return '';
  if (value instanceof Date) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  const match = String(value).match(/\d{4}-\d{2}-\d{2}/);
  return match?.[0] || '';
};

const parseProgress = (value, completed) => {
  if (completed) return 100;
  const parsed = Number.parseFloat(String(value || '').replace('%', ''));
  return Number.isFinite(parsed) ? Math.max(0, Math.min(99, parsed)) : 0;
};

const DELIVERY_STAGE_MATCHERS = {
  roomReady: name => name.includes('机房改造实施'),
  arrival: name => name.includes('设备到货静置') || name.includes('设备静置'),
  cabling: name => name.includes('综合布线与成端'),
  powerOn: name => name.includes('设备上电'),
  online: name => name.includes('集群性能调优'),
  handover: name => name === '移交',
};

const parseDeliveryPlanWorkbook = async (arrayBuffer, projectId) => {
  const XLSX = await import('xlsx');
  const workbook = XLSX.read(arrayBuffer, { type: 'array', cellDates: true });
  const rows = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], { defval: '', raw: false });
  const pods = Array.from(new Set(rows.flatMap(row =>
    String(row.MANAGEMENT_UNIT || '').split(',').map(unit => unit.trim()).filter(unit => /POD\d+$/i.test(unit)),
  ))).sort();
  if (!pods.length) throw new Error('Excel 中未找到 PoD');

  const podMap = new Map(pods.map(pod => [pod, { pod, batch: pod.split('-')[0] || pod, stages: {} }]));
  Object.entries(DELIVERY_STAGE_MATCHERS).forEach(([key, matcher]) => {
    const matchingRows = rows.filter(row => matcher(String(row.ACTIVITY_NAME || '').trim()));
    pods.forEach(pod => {
      const candidates = matchingRows.filter(row => {
        const units = String(row.MANAGEMENT_UNIT || '').split(',').map(unit => unit.trim()).filter(Boolean);
        return units.length === 0 || units.includes(pod);
      });
      if (!candidates.length) return;
      const completed = candidates.every(row =>
        String(row.STATUS || '').includes('已完成') || Number.parseFloat(String(row.PROCESS || '').replace('%', '')) >= 100,
      );
      const expectedEnds = candidates.map(row => formatLocalDate(row.END_DATE)).filter(Boolean).sort();
      const actualEnds = candidates.map(row => formatLocalDate(row.ACTUAL_END_DATE)).filter(Boolean).sort();
      podMap.get(pod).stages[key] = {
        expectedEnd: expectedEnds.at(-1) || '',
        actualEnd: completed ? actualEnds.at(-1) || '' : '',
        progress: Math.min(...candidates.map(row => parseProgress(row.PROCESS, String(row.STATUS || '').includes('已完成')))),
        owner: String(candidates.find(row => row.PRINCIPAL)?.PRINCIPAL || ''),
        common: candidates.some(row => !String(row.MANAGEMENT_UNIT || '').trim()),
      };
    });
  });

  const parsedPods = Array.from(podMap.values()).filter(pod =>
    DELIVERY_FLOW_STAGES.every(({ key }) => pod.stages[key]?.expectedEnd),
  );
  if (!parsedPods.length) throw new Error('Excel 中未找到完整交付里程碑');
  return { projectId, sourceLabel: '数据中心 Excel', pods: parsedPods };
};

/* 当前从交付计划表.xlsx 提取的回退快照。后续数据中心接口返回同一结构即可直接替换。 */
const DELIVERY_PLAN_FALLBACK = {
  projectId: 'K1903',
  sourceLabel: '交付计划表.xlsx（本地回退）',
  actualEndNeedsReview: true,
  pods: [
    ...['B2DH401-POD01', 'B2DH401-POD02', 'B2DH401-POD03', 'B2DH401-POD04'].map(id =>
      deliveryPod(id, ['2026-01-11', '2026-03-10'], ['2026-01-19', '2026-03-10'], ['2026-01-21', '2026-03-10'], ['2026-02-01', '2026-03-11'], ['2026-02-04', '2026-03-10'])),
    ...['B2DH402-POD05', 'B2DH402-POD06', 'B2DH402-POD07', 'B2DH402-POD08'].map(id =>
      deliveryPod(
        id,
        ['2026-03-05', '2026-03-10'],
        ['2026-03-15', '2026-03-15'],
        ['2026-03-17', '2026-03-15'],
        ['2026-04-01', id.endsWith('POD08') ? '' : '2026-04-02'],
        ['2026-04-04', id.endsWith('POD08') ? '' : '2026-04-04'],
      )),
    deliveryPod('B2DH403-POD09', ['2026-01-19', '2026-03-10'], ['2026-01-17', '2026-03-10'], ['2026-01-24', '2026-03-10'], ['2026-01-31', '2026-03-10'], ['2026-02-04', '2026-03-10']),
  ],
};

async function fetchDeliveryPlan(projectId = 'K1903') {
  const endpoint = import.meta.env.VITE_DELIVERY_PLAN_API
    || `/api/v1/projects/${encodeURIComponent(projectId)}/delivery-plan/milestones`;
  const excelEndpoint = import.meta.env.VITE_DELIVERY_PLAN_XLSX_URL
    || `/api/v1/projects/${encodeURIComponent(projectId)}/delivery-plan.xlsx`;
  try {
    const response = await fetch(endpoint, { cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const snapshot = payload.data || payload;
    return { ...snapshot, sourceLabel: snapshot.sourceLabel || '数据中心' };
  } catch {
    try {
      const response = await fetch(excelEndpoint, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await parseDeliveryPlanWorkbook(await response.arrayBuffer(), projectId);
    } catch {
      return DELIVERY_PLAN_FALLBACK;
    }
  }
}

/* ── tiny icons ── */
const IcSparkle = () => (
  <svg width={9} height={9} viewBox="0 0 11 11" fill="none">
    <path d="M5.5 0.5 L6.4 4.6 L10.5 5.5 L6.4 6.4 L5.5 10.5 L4.6 6.4 L0.5 5.5 L4.6 4.6 Z" fill="currentColor" />
  </svg>
);
const IcArrowRight = ({ size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none">
    <path d="M3 9 L14 9 M10 5 L14 9 L10 13" stroke="currentColor" strokeWidth="1.2" strokeLinecap="square" fill="none" />
  </svg>
);
const IcChevron = ({ size = 9 }) => (
  <svg width={size} height={size} viewBox="0 0 9 9" fill="none">
    <path d="M3 1 L6 4.5 L3 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="square" fill="none" />
  </svg>
);
const IcSite = ({ size = 11 }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none">
    <path d="M2 7 L9 3 L16 7 L16 15 L2 15 Z" stroke="currentColor" strokeWidth="1.2" fill="none" />
    <rect x="5" y="9" width="2" height="2" stroke="currentColor" strokeWidth="0.9" fill="none" />
    <rect x="8" y="9" width="2" height="2" stroke="currentColor" strokeWidth="0.9" fill="none" />
    <rect x="11" y="9" width="2" height="2" stroke="currentColor" strokeWidth="0.9" fill="none" />
  </svg>
);
const IcBlock = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.2" fill="none" />
    <path d="M3.5 3.5 L10.5 10.5" stroke="currentColor" strokeWidth="1.4" />
  </svg>
);
const IcWarn = ({ size = 13 }) => (
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
    <path d="M7 1.5 L13 12.5 L1 12.5 Z" stroke="currentColor" strokeWidth="1.2" fill="none" />
    <path d="M7 5.5 L7 9" stroke="currentColor" strokeWidth="1.2" />
    <circle cx="7" cy="10.8" r="0.6" fill="currentColor" />
  </svg>
);
const IcEye = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <path d="M1 6 C2.5 3 4 2 6 2 C8 2 9.5 3 11 6 C9.5 9 8 10 6 10 C4 10 2.5 9 1 6 Z" stroke="currentColor" strokeWidth="1" fill="none" />
    <circle cx="6" cy="6" r="1.6" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);
const IcSandbox = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <rect x="1" y="2" width="10" height="8" stroke="currentColor" strokeWidth="1" fill="none" strokeDasharray="2 1.5" />
    <path d="M3 6 L5 6 L5.5 4.5 L7 7.5 L7.5 6 L9 6" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);

/* ── Risk Alerts ── */
function RiskAlerts({ onDrill }) {
  const [tab, setTab] = useState('unmeet');
  /* 5.27 M-111 · 风险来源筛选；null = 全部 */
  const [sourceFilter, setSourceFilter] = useState(null);
  const unmeet = RISKS.filter(r => r.cat === 'unmeet');
  const atrisk = RISKS.filter(r => r.cat === 'atrisk');
  const base = tab === 'unmeet' ? unmeet : atrisk;
  const list = sourceFilter ? base.filter(r => r.source === sourceFilter) : base;
  /* 当前 tab 下每个来源的计数（用于 chip 显示） */
  const sourceCount = Object.keys(RISK_SOURCES).reduce((acc, k) => {
    acc[k] = base.filter(r => r.source === k).length;
    return acc;
  }, {});

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>风险预警</h3>
        <span className="ph-meta">按严重度 · 实时</span>
        <div className="ph-actions"><button className="btn-ghost" onClick={() => onDrill?.('risk')}>风险详情 →</button></div>
      </div>
      <div className="risk-tabs">
        <button className={`risk-tab${tab === 'unmeet' ? ' active' : ''}`} onClick={() => setTab('unmeet')}>
          不可满足 <span className="cnt">{unmeet.length}</span>
        </button>
        <button className={`risk-tab${tab === 'atrisk' ? ' active' : ''}`} onClick={() => setTab('atrisk')}>
          可满足 · 有风险 <span className="cnt">{atrisk.length}</span>
        </button>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--c-text-faint)', padding: '0 12px 4px' }}>
          <span>已处理: 21</span>
        </div>
      </div>

      {/* 5.27 M-111 · 来源筛选 chip 行 */}
      <div className="risk-source-bar">
        <button
          className={`risk-source-chip${sourceFilter === null ? ' on' : ''}`}
          onClick={() => setSourceFilter(null)}
        >
          全部 <span className="cnt">{base.length}</span>
        </button>
        {Object.entries(RISK_SOURCES).map(([k, meta]) => (
          <button
            key={k}
            className={`risk-source-chip tone-${meta.tone}${sourceFilter === k ? ' on' : ''}`}
            onClick={() => setSourceFilter(s => s === k ? null : k)}
            disabled={sourceCount[k] === 0}
          >
            <span className="risk-source-dot" />
            {meta.label} <span className="cnt">{sourceCount[k]}</span>
          </button>
        ))}
      </div>

      <div className="risk-list">
        {list.map((r, i) => (
          <div key={i} className={`risk-row ${r.sev}`}>
            <div className="sev-glyph">
              {r.sev === 'red' ? <IcBlock /> : <IcWarn />}
            </div>
            <div className="rr-body">
              <div className="rr-title">
                {r.source && RISK_SOURCES[r.source] && (
                  <span className={`risk-source-tag tone-${RISK_SOURCES[r.source].tone}`}>
                    {RISK_SOURCES[r.source].label}
                  </span>
                )}
                {r.title}
              </div>
              <div className="rr-meta">
                <span><span className="k">项目</span><span className="v">{r.project}</span></span>
                <span><span className="k">范围</span><span className="v">{r.pod}</span></span>
                <span><span className="k">归属</span><span className="v">{r.owner}</span></span>
              </div>
              <div className="rr-impact">
                影响 <span className="delay">{r.delay}</span> · SLA <span style={{ color: 'var(--c-text-2)', fontVariantNumeric: 'tabular-nums' }}>{r.sla}</span>
              </div>
            </div>
            <div className="rr-right">
              <div className={`rr-cat ${r.cat}`}>{r.cat === 'unmeet' ? '不可满足' : '有风险'}</div>
              <div>{r.age} ago</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Milestones ── */
function Milestones() {
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>合同里程碑 · 达成态势</h3>
        <span className="ph-meta">未来 90 天 · 5 项关键节点</span>
        <div className="ph-actions">
          <button className="btn-ghost">月视图</button>
          <button className="btn-ghost">季度视图</button>
          <Link href="/milestones" className="btn-ghost" style={{ color: 'var(--c-brand)', fontWeight: 700 }}>
            PoD 级下钻 →
          </Link>
        </div>
      </div>
      <div className="ms-strip">
        <div className="ms-head">
          <div style={{ display: 'flex', gap: 16 }}>
            {[['var(--c-success)', '按期'], ['var(--c-warning)', '有风险'], ['var(--c-danger)', '已延期']].map(([color, label]) => (
              <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 }}>
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: color }} />{label}
              </span>
            ))}
          </div>
          <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--c-text-muted)' }}>
            <span className="text-mono" style={{ color: 'var(--c-text)' }}>T-6</span> 至 <span className="text-mono" style={{ color: 'var(--c-text)' }}>T-80</span>
          </div>
        </div>
        <div className="ms-timeline">
          {MILESTONES.map((m, i) => (
            <div key={i} className={`ms-cell s-${m.status}`}>
              <div className="ms-date">{m.date}</div>
              <div className="ms-days">{m.days}</div>
              <div className="ms-dot" />
              <div className="ms-title">{m.title}</div>
              <div className="ms-project">{m.project} · 合同节点</div>
              <div className="ms-tag">{m.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Main Dashboard export ── */
/* 5.28 H-6 · 项目孪生顶部 4 阶段总览（设计准备 / 工程安装 / 调测 / 验收）
 * 每卡：阶段名 + 数字 + 饼图 / 进度环 + 关键活动延期数 */
const PROJECT_STAGES = [
  { key: 'design',   label: '设计准备', done: 12, total: 12, late: 0, tone: 'green', sub: '设计 + 准备 + 工程包单' },
  { key: 'install',  label: '工程安装', done: 28, total: 36, late: 3, tone: 'amber', sub: 'PoD 上架 + 综合布线' },
  { key: 'commission', label: '调测',  done: 8,  total: 36, late: 1, tone: 'blue',  sub: 'OS + 集群 + 网络' },
  { key: 'accept',   label: '验收',    done: 0,  total: 36, late: 0, tone: 'gray',  sub: '客户签收 + 移交' },
];

/* ─── Cockpit 卡片阴影 · 提权浮起 ─── */
const COCKPIT_SHADOW = 'shadow-[0_4px_12px_rgba(24,24,27,0.06)]';

/* ─── 供应计划菱形：未来 slate-300 / 已发生或进行中 blue-700 ─── */
const splDotColor = (monthIdx: number, todayIdx: number) =>
  monthIdx > todayIdx ? '#cbd5e1' : '#1d4ed8';

/* 旧组件 ProjectStageBoard 仍用彩色 tone 环 */
const TONE_RING: Record<string, string> = {
  green: '#10b981',
  amber: '#f59e0b',
  blue:  '#3b82f6',
  gray:  '#d1d5db',
};

/* ─── 全 Tailwind 版 ProjectStageBoard ─── */
function ProjectStageBoard() {
  return (
    /* 外层卡片：白底 + 极淡描边 + 圆角 + shadow-card */
    <div className="bg-white rounded-xl border border-zinc-100/80 shadow-card flex-shrink-0">

      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-zinc-50/80">
        <span className="text-xs font-semibold text-zinc-600 tracking-tight">
          项目分阶段总览
        </span>
        <span className="flex-1" />
        <span className="inline-flex items-center gap-1 text-[10px] text-zinc-400">
          <IcSparkle />
          AIDA 自动出图 · v22
        </span>
      </div>

      {/* 4 阶段卡片：等分 grid，中间加发丝分隔线 */}
      <div className="grid grid-cols-4 divide-x divide-zinc-50">
        {PROJECT_STAGES.map(s => {
          const pct   = Math.round(100 * s.done / s.total);
          const color = TONE_RING[s.tone] ?? TONE_RING.gray;
          const isLate = s.late > 0;

          return (
            <div
              key={s.key}
              className="flex flex-col items-center gap-0.5 py-2 px-3 transition-colors duration-150 hover:bg-zinc-50/60"
            >
              {/* 阶段名称 */}
              <span className="text-[10px] font-medium text-zinc-500 tracking-wide">
                {s.label}
              </span>

              {/* 进度环 + 中心数字 */}
              <div className="relative flex items-center justify-center">
                <svg viewBox="0 0 36 36" width="48" height="48">
                  {/* 轨道圆 */}
                  <circle
                    cx="18" cy="18" r="15.9"
                    fill="none" stroke="#f4f4f5" strokeWidth="2.8"
                  />
                  {/* 进度圆 */}
                  <circle
                    cx="18" cy="18" r="15.9"
                    fill="none"
                    stroke={color}
                    strokeWidth="2.8"
                    strokeLinecap="round"
                    strokeDasharray={`${pct} 100`}
                    transform="rotate(-90 18 18)"
                  />
                </svg>
                {/* 中心数字 */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-[12px] font-bold tabular-nums text-zinc-700 leading-none">
                    {s.done}
                  </span>
                  <span className="text-[9px] text-zinc-400 leading-none">
                    /{s.total}
                  </span>
                </div>
              </div>

              {/* 副标签 */}
              <span className="text-[9px] text-zinc-400 text-center leading-tight px-1">
                {s.sub}
              </span>

              {/* 延期 / 按期状态 */}
              {isLate ? (
                <span className="inline-flex items-center gap-0.5 text-[9px] font-semibold text-red-500">
                  ⚠ 延期 {s.late}
                </span>
              ) : (
                <span className="text-[9px] font-medium text-emerald-500">
                  ✓ 按期
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* 5.31 · 项目孪生 PoD 全景色块矩阵（替换 4 环总览，复用 foundation 三色块语义）
 * 白=未开工 / 黄=进行中 / 绿=完成 / 红描边=有风险 —— 点色块下钻 PoD 里程碑 */
const TWIN_POD_STATE = {
  done:    { bg: '#10b981', label: '完成' },
  doing:   { bg: '#f59e0b', label: '进行中' },
  pending: { bg: '#ffffff', label: '未开工' },
};
const TWIN_POD_ROOMS = [
  { room: 'A1·RM01', pods: [['done'],['done'],['done'],['done'],['done'],['done'],['done'],['done']] },
  { room: 'A1·RM02', pods: [['done'],['done'],['done'],['done'],['doing'],['doing'],['doing','risk'],['doing']] },
  { room: 'B2·RM01', pods: [['done'],['done'],['doing'],['doing','risk'],['doing'],['pending']] },
  { room: 'B2·RM02', pods: [['doing'],['doing'],['doing'],['pending'],['pending'],['pending'],['pending'],['pending']] },
  { room: 'C3·RM01', pods: [['pending'],['pending'],['pending'],['pending'],['pending'],['pending']] },
];

function ProjectTwinPods({ onDrill }) {
  const total = TWIN_POD_ROOMS.reduce((s, r) => s + r.pods.length, 0);
  const done  = TWIN_POD_ROOMS.reduce((s, r) => s + r.pods.filter(p => p[0] === 'done').length, 0);
  const risk  = TWIN_POD_ROOMS.reduce((s, r) => s + r.pods.filter(p => p[1] === 'risk').length, 0);
  const Swatch = ({ bg, border, ring }) => (
    <i style={{ width: 9, height: 9, borderRadius: 2, display: 'inline-block', background: bg,
      border: border || 'none', boxShadow: ring ? `0 0 0 1.5px ${ring}` : 'none' }} />
  );

  return (
    <div className="bg-white rounded-xl border border-zinc-100/80 shadow-card flex flex-col overflow-hidden flex-shrink-0">
      {/* 标题栏 + 图例 */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-zinc-50/80">
        <span className="text-xs font-semibold text-zinc-600 tracking-tight">项目孪生 · PoD 全景</span>
        <span className="text-[10px] text-zinc-400">和林格尔 · {done}/{total} 完成{risk > 0 ? ` · ${risk} 有风险` : ''}</span>
        <span className="flex-1" />
        <span className="inline-flex items-center gap-2 text-[9px] text-zinc-400">
          <span className="inline-flex items-center gap-1"><Swatch bg="#10b981" />完成</span>
          <span className="inline-flex items-center gap-1"><Swatch bg="#f59e0b" />进行中</span>
          <span className="inline-flex items-center gap-1"><Swatch bg="#fff" border="1px solid #e4e4e7" />未开工</span>
          <span className="inline-flex items-center gap-1"><Swatch bg="#fff" border="1px solid #e4e4e7" ring="#dc2626" />风险</span>
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] text-zinc-400 ml-1"><IcSparkle /> AIDA 自动出图</span>
      </div>
      {/* 机房 × PoD 色块 */}
      <div className="flex-1 px-3 py-2 flex flex-col gap-1 justify-center min-h-0">
        {TWIN_POD_ROOMS.map(r => (
          <div key={r.room} className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-14 shrink-0 text-right">{r.room}</span>
            <div className="flex gap-1 flex-wrap">
              {r.pods.map((p, i) => {
                const st = TWIN_POD_STATE[p[0]] ?? TWIN_POD_STATE.pending;
                const isRisk = p[1] === 'risk';
                return (
                  <button
                    key={i}
                    className="twin-pod-cell"
                    title={`${r.room} · PoD-${String(i + 1).padStart(2, '0')} · ${st.label}${isRisk ? ' · 有风险' : ''}`}
                    onClick={() => onDrill?.('milestone')}
                    style={{
                      width: 15, height: 15, borderRadius: 3, padding: 0, cursor: 'pointer',
                      background: st.bg,
                      border: p[0] === 'pending' ? '1px solid #e4e4e7' : 'none',
                      boxShadow: isRisk ? '0 0 0 1.5px #dc2626' : 'none',
                    }}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* 5.28 H-7 · 总体进展 + 活动延期 banner（顶部一行，关键决策信号置顶）*/
function OverallProgressBanner({ onDrill }) {
  const total = PROJECT_STAGES.reduce((s, x) => s + x.total, 0);
  const done  = PROJECT_STAGES.reduce((s, x) => s + x.done, 0);
  const late  = PROJECT_STAGES.reduce((s, x) => s + x.late, 0);
  const pct = Math.round(100 * done / total);
  return (
    <div className="overall-banner">
      <div className="overall-banner-cell">
        <div className="k">总体进展</div>
        <div className="v"><strong>{pct}</strong><i>%</i></div>
        <div className="sub">{done} / {total} 项</div>
      </div>
      <div className="overall-banner-cell">
        <div className="k">活动延期</div>
        <div className={`v ${late > 0 ? 'tone-red' : 'tone-green'}`}><strong>{late}</strong><i> 项</i></div>
        <div className="sub">{late > 0 ? '需 PD/TD 介入' : '当前无延期'}</div>
      </div>
      <div className="overall-banner-cell">
        <div className="k">本周节奏</div>
        <div className="v"><strong>D55</strong><i> / Q90</i></div>
        <div className="sub">进入工程安装中段</div>
      </div>
      <div className="overall-banner-cell">
        <div className="k">下次扫盘</div>
        <div className="v tone-blue"><strong>10:00</strong></div>
        <div className="sub">AI 自动驾驶中</div>
      </div>
      <button className="btn sm ghost overall-banner-drill" onClick={() => onDrill?.('milestone')}>里程碑 →</button>
    </div>
  );
}

/* 5.28 H-8 · DOA + 固件 / IGD + ICD 合并卡（按 SVG 标注「能否合并」）*/
function MergedQualityCards({ onDrill }) {
  return (
    <div className="merged-cards-row">
      <div className="merged-card">
        <div className="merged-card-head">
          <span>DOA + 固件版本</span>
          <span style={{ flex: 1 }} />
          <button className="btn sm ghost" onClick={() => onDrill?.('doa')}>DOA 详情 →</button>
        </div>
        <div className="merged-card-body">
          <div className="merged-cell">
            <div className="merged-cell-k">DOA 故障率</div>
            <div className="merged-cell-v tone-green">0.18%</div>
            <div className="merged-cell-sub">本月 4 起 · 同比 ↓ 60%</div>
          </div>
          <div className="merged-cell">
            <div className="merged-cell-k">固件版本一致性</div>
            <div className="merged-cell-v tone-amber">96%</div>
            <div className="merged-cell-sub">2 个 PoD 版本待对齐</div>
          </div>
        </div>
      </div>

      <div className="merged-card">
        <div className="merged-card-head">
          <span>IGD + ICD</span>
          <span className="ai-by-chip"><IcSparkle /> AI 合并</span>
        </div>
        <div className="merged-card-body">
          <div className="merged-cell">
            <div className="merged-cell-k">IGD 入场就绪</div>
            <div className="merged-cell-v tone-green">14 / 14</div>
            <div className="merged-cell-sub">机房全部 ready</div>
          </div>
          <div className="merged-cell">
            <div className="merged-cell-k">ICD 配置完成率</div>
            <div className="merged-cell-v tone-blue">82%</div>
            <div className="merged-cell-sub">网络配置主力推进中</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────────────
 * 5.28 SVG 项目孪生 · 7 个新组件
 * 顶部供应计划 timeline + PoD 级里程碑下钻 + 4 张数据表 + 1 张统计图
 * ─────────────────────────────────────────────────────────────────── */

/* 5.28 H-? · 供应计划 timeline（机房 ready / A3 到货 / A3 验收，HW/KL 已砍）
 * SVG 明确："放到最上面 · 机房、A3到货、A3验收，HW 和 KL 不要" */
const SUPPLY_PLAN_ROWS = [
  { key: 'room',     label: '机房 ready', tone: 'blue',  plans: [8, 17, 27, 37, 47, 57, 67, 77, 87, 97, 100, 100] },
  { key: 'a3-arr',   label: 'A3 到货',     tone: 'amber', plans: [0, 0, 0, 8, 18, 29, 40, 52, 65, 78, 90, 100] },
  { key: 'a3-acc',   label: 'A3 验收',     tone: 'green', plans: [0, 0, 0, 0, 2, 8, 14, 23, 33, 47, 65, 80] },
];
const SUPPLY_PLAN_MONTHS = ['12-31','01-31','02-28','03-31','04-30','05-31','06-30','07-31','08-31','09-30','10-31','11-30','12-31'];

function SupplyPlanTimeline({ embedded = false }: { embedded?: boolean }) {
  const n = SUPPLY_PLAN_MONTHS.length;
  const at = (i) => `${((i + 0.5) / n) * 100}%`;
  const TODAY_IDX = 5; // 当前节点 05-31（D+55）
  const inner = (
    <>
      <div className={`cp-hd flex items-center justify-between px-5 ${embedded ? 'pt-1 pb-1' : 'pt-4 pb-2 border-b border-zinc-100/50'}`}>
        <span className={embedded ? 'text-[12px] font-medium text-zinc-500 tracking-wide' : 'text-base font-semibold text-zinc-900'}>总计划</span>
      </div>
      <div className={`spl-body px-5 pb-3 pt-1${embedded ? ' pb-2' : ''}`}>
        {/* 月份轴 */}
        <div className="spl-row spl-axis">
          <div className="spl-label" />
          <div className="spl-track">
            {SUPPLY_PLAN_MONTHS.map((m, i) => (
              <span key={i} className="spl-month" style={{ left: at(i) }}>{m}</span>
            ))}
            <span className="spl-today-label" style={{ left: at(TODAY_IDX) }}>今天</span>
          </div>
        </div>
        {/* 数据行：灰色箭头 + 中性菱形 + 数值 */}
        {SUPPLY_PLAN_ROWS.map(row => (
          <div key={row.key} className="spl-row" style={{ height: 32, flexShrink: 0, display: 'flex', alignItems: 'center' }}>
            <div className="spl-label">
              {row.label}<span className="spl-sub">计划</span>
            </div>
            <div className="spl-track" style={{ position: 'relative', flex: 1, height: 32 }}>
              <div className="spl-arrow" />
              <span className="spl-today-line" style={{ left: at(TODAY_IDX) }} />
              {SUPPLY_PLAN_MONTHS.map((_, i) => {
                const v = row.plans[i];
                if (v === undefined) return null;
                return (
                  <div key={i} className="spl-point" style={{ left: at(i) }}>
                    <span className="spl-dot" style={{ background: splDotColor(i, TODAY_IDX) }} />
                    <span className="spl-num">{v}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </>
  );
  if (embedded) return inner;
  return (
    <div className={`supply-plan bg-white rounded-2xl ${COCKPIT_SHADOW} overflow-hidden`}>
      {inner}
    </div>
  );
}

/* 5.28 H-10/H-11/H-12 · PoD 级里程碑（参考牛博界面）
 * 每个里程碑两道杠：计划开始/结束（细）+ 实际开始/结束（粗），日期 hover 显示
 * 阶段（11）：L1机房准备/工程勘测/设计审核/排布线/设备到货/设备安装/成端排扎/上电/ZTP开局/装机&压测/验收 */
const POD_MILESTONE_STAGES = [
  'L1 机房准备', '工程勘测', '设计审核', '排布线',
  '设备到货', '设备安装', '成端排扎', '上电',
  'ZTP 开局', '装机&压测', '验收',
];

/* 演示 6 个 PoD · 每个 PoD 每阶段：计划起讫 + 实际起讫 + 完成度 */
function genPodMilestones() {
  const pods = ['POD10', 'POD11', 'POD12', 'POD13', 'POD14', 'POD15'];
  return pods.map((id, pi) => ({
    id,
    title: `L1 机房准备 · ${id}`,
    /* stage[].progress 0-100，演示用 100% green */
    stages: POD_MILESTONE_STAGES.map((s, i) => {
      /* 模拟：早期 PoD 完整完成，后期略带未完 */
      const baseDone = pi < 4 ? 100 : pi === 4 ? (i < 8 ? 100 : i === 8 ? 60 : 0) : (i < 5 ? 100 : i < 7 ? 70 : 0);
      return {
        stage: s,
        planStart: 5 + i * 3,
        planEnd:   8 + i * 3,
        actStart:  5 + i * 3 + (pi % 2),
        actEnd:    8 + i * 3 + (pi % 2),
        progress: baseDone,
      };
    }),
  }));
}

function PoDMilestoneGrid() {
  const pods = genPodMilestones();
  const [hovered, setHovered] = useState(null as null | { podId: string; stageIdx: number });

  return (
    <div className="jn-panel pod-milestone">
      <div className="jn-panel-head" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>PoD 级里程碑 · 和林格尔</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: 'var(--c-text-muted)', fontWeight: 400 }}>
          每个里程碑两道杠：计划 / 实际 · 日期悬停查看
        </span>
      </div>
      <div className="pod-milestone-body">
        <div className="pod-milestone-header">
          <div className="pod-milestone-name-col"></div>
          {POD_MILESTONE_STAGES.map((s, i) => (
            <div key={i} className="pod-milestone-stage-head" title={s}>
              {s}
            </div>
          ))}
        </div>
        {pods.map(p => (
          <div key={p.id} className="pod-milestone-row">
            <div className="pod-milestone-name-col">
              <span className="pod-milestone-dot" />
              <div>
                <div className="pod-milestone-id">{p.id}</div>
                <div className="pod-milestone-title">{p.title}</div>
              </div>
            </div>
            {p.stages.map((st, i) => {
              const tone = st.progress >= 100 ? 'green' : st.progress >= 50 ? 'amber' : 'gray';
              return (
                <div
                  key={i}
                  className={`pod-milestone-cell tone-${tone}`}
                  onMouseEnter={() => setHovered({ podId: p.id, stageIdx: i })}
                  onMouseLeave={() => setHovered(null)}
                >
                  {st.progress > 0 && (
                    <div className="pod-milestone-bars">
                      {/* 上杠：计划 */}
                      <div className="pod-milestone-bar plan" />
                      {/* 下杠：实际 */}
                      <div className="pod-milestone-bar actual" style={{ width: `${Math.min(100, st.progress)}%` }} />
                    </div>
                  )}
                  {st.progress > 0 && (
                    <span className={`pod-milestone-pct tone-${tone}`}>{st.progress.toFixed(1)}%</span>
                  )}
                  {hovered?.podId === p.id && hovered?.stageIdx === i && (
                    <div className="pod-milestone-tooltip">
                      <div><b>{st.stage}</b></div>
                      <div>计划：D+{st.planStart} → D+{st.planEnd}</div>
                      <div>实际：D+{st.actStart} → D+{st.actEnd}</div>
                      <div>进度：{st.progress}%</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

/* 5.28 SVG · 客户工程报单（NO 区域列，只要状态）*/
const WORK_ORDERS = [
  { id: '15275714', room: 'NMHLSJ_D3_203', ts: '2026-01-31', desc: 'A3 SuperPoD 上电后 2 张 NPU 未识别', cat: '硬件 · 计算', solver: '华为产品 · 计算', owner: '李伟 00603554', state: 'eCare', sla: 'Closed', planAt: '2026-02-15', doneAt: '2026-02-12' },
  { id: '15274961', room: 'NMHLSJ_D3_202', ts: '2026-01-31', desc: '100G 光模块链路抖动告警', cat: '网络 · 光模块', solver: '华为产品 · 网络', owner: '王明 00623478', state: 'eCare', sla: 'Closed', planAt: '2026-02-15', doneAt: '2026-02-15' },
  { id: '15272984', room: 'NMHLSJ_D3_203', ts: '2026-01-30', desc: 'BMC 带外管理无法登录', cat: '管理 · BMC', solver: '华为产品 · 服务器', owner: '李伟 00603554', state: 'eCare', sla: 'Closed', planAt: '2026-02-14', doneAt: '2026-02-03' },
  { id: '15267104', room: 'NMHLSJ_D3_101', ts: '2026-01-29', desc: '整机柜 ST 测试 GPU 数量与 BOQ 不符', cat: '测试 · ST', solver: '华为产品 · 计算', owner: '王明 00623478', state: 'eCare', sla: 'Closed', planAt: '2026-02-12', doneAt: '2026-02-12' },
  { id: '15265731', room: 'NMHLSJ_D3_202', ts: '2026-01-29', desc: '液冷 CDU 流量低于阈值', cat: '液冷 · CDU', solver: '华为产品 · 液冷', owner: '赵丹 00640815', state: 'eCare', sla: 'Closed', planAt: '2026-02-13', doneAt: '2026-02-03' },
  { id: '15265010', room: 'NMHLSJ_D3_202', ts: '2026-01-29', desc: 'ZTP 开局 DHCP 未分配地址', cat: '部署 · ZTP', solver: '华为产品 · 网络', owner: '王明 00623478', state: 'eCare', sla: 'Closed', planAt: '2026-02-13', doneAt: '2026-02-03' },
];

function CustomerWorkOrderTable() {
  return (
    <div className="jn-panel">
      <div className="jn-panel-head" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>客户工程报单（eCare）</span>
        <span style={{ flex: 1 }} />
        <input type="text" placeholder="按状态筛选" className="ws-filter" />
      </div>
      <div className="ws-table-wrap">
        <table className="vs-table ws-table">
          <thead>
            <tr>
              <th>eCare 单号</th>
              <th>机房</th>
              <th className="num">报单时间</th>
              <th>问题描述</th>
              <th>问题摘要</th>
              <th>处理人</th>
              <th>当前处理人</th>
              <th>状态</th>
              <th className="num">期望解决时间</th>
              <th className="num">实际解决时间</th>
            </tr>
          </thead>
          <tbody>
            {WORK_ORDERS.map(w => (
              <tr key={w.id}>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{w.id}</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>{w.room}</td>
                <td className="num">{w.ts}</td>
                <td style={{ fontSize: 11 }}>{w.desc}</td>
                <td style={{ fontSize: 11, color: 'var(--c-text-muted)' }}>{w.cat}</td>
                <td>{w.solver}</td>
                <td style={{ fontSize: 11 }}>{w.owner}</td>
                <td><span className="status-pill green">{w.sla}</span></td>
                <td className="num">{w.planAt}</td>
                <td className="num">{w.doneAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ padding: '8px 14px', fontSize: 11, color: 'var(--c-text-muted)', borderTop: '1px solid var(--c-border)', textAlign: 'right' }}>
        共 32 条 · 10条/页 · 1 / 2
      </div>
    </div>
  );
}

/* 5.28 SVG · 风险详情（NO 区域列）*/
const RISK_DETAIL_ROWS = [
  { id: 'R-2026-001', project: '智算 K1903 · 和林格尔', agent: '规划设计', risk: 'B2-RM02 配电延期 9 天', desc: '市电引入审批滞后，影响上电节点', sol: '协调甲方提前介入，临时柴发兜底', level: '高',  state: '处理中', owner: '李伟 00603554', responsible: '何博 00623478', source: 'DRB',  start: '2026-01-15', plan: '2026-02-25', done: '—' },
  { id: 'R-2026-002', project: '智算 K1903 · 和林格尔', agent: '交付方案', risk: 'ConnectX-7 数量与 HLD 不符', desc: 'BOQ 192 / HLD 384，采购未对齐', sol: '评审会拍板口径，重出 LLD', level: '高',  state: 'Closed', owner: '王明 00623478', responsible: '何博 00623478', source: 'DTRB', start: '2025-12-30', plan: '2026-01-10', done: '2026-01-09' },
  { id: 'R-2026-003', project: '智算 K1903 · 和林格尔', agent: '设备安装', risk: '液冷管路压测不达标', desc: '部分快接头渗漏，压力低于阈值', sol: '更换快接头并复测', level: '中', state: 'Closed', owner: '赵丹 00640815', responsible: '调试组 K',  source: '合同', start: '2026-01-20', plan: '2026-02-05', done: '2026-02-03' },
  { id: 'R-2026-004', project: '智算 K1903 · 和林格尔', agent: '部署调测', risk: 'PoD #04 100G 物流延期', desc: '光模块到货 ETA 5/28，影响开局', sol: '从 H 项目临时调拨补位', level: '中', state: '处理中', owner: '王明 00623478', responsible: '调试组 K',  source: 'DRB',  start: '2026-02-01', plan: '2026-02-28', done: '—' },
  { id: 'R-2026-005', project: '智算 K1903 · 和林格尔', agent: '智慧工勘', risk: '防静电地板承重不足', desc: '勘测发现局部网格承重低于设计', sol: '加固龙骨，调整机柜布局', level: 'NA', state: 'Closed', owner: '李伟 00603554', responsible: '施工队 07', source: 'DTRB', start: '2025-12-10', plan: '2025-12-25', done: '2025-12-23' },
];

function RiskDetailTable() {
  return (
    <div className="jn-panel">
      <div className="jn-panel-head" style={{ padding: '10px 14px' }}>风险详情</div>
      <div className="ws-table-wrap">
        <table className="vs-table ws-table compact">
          <thead>
            <tr>
              <th>id</th>
              <th>项目名称</th>
              <th>Agent模块</th>
              <th>风险名称</th>
              <th>风险描述</th>
              <th>解决方案描述</th>
              <th>风险等级</th>
              <th>状态</th>
              <th>提出人</th>
              <th>责任人</th>
              <th>来源</th>
              <th className="num">开始时间</th>
              <th className="num">计划完成时间</th>
              <th className="num">实际完成时间</th>
            </tr>
          </thead>
          <tbody>
            {RISK_DETAIL_ROWS.map((r, idx) => (
              <tr key={idx}>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{r.id}</td>
                <td style={{ fontSize: 11 }}>{r.project}</td>
                <td>{r.agent || '—'}</td>
                <td style={{ fontSize: 11 }}>{r.risk}</td>
                <td style={{ fontSize: 11 }}>{r.desc}</td>
                <td style={{ fontSize: 11 }}>{r.sol}</td>
                <td>
                  <span className={`status-pill ${r.level === '高' ? 'red' : r.level === 'NA' ? '' : 'amber'}`}>{r.level}</span>
                </td>
                <td><span className="status-pill green">{r.state}</span></td>
                <td>{r.owner}</td>
                <td>{r.responsible}</td>
                <td>{r.source}</td>
                <td className="num">{r.start}</td>
                <td className="num">{r.plan}</td>
                <td className="num">{r.done}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ padding: '8px 14px', fontSize: 11, color: 'var(--c-text-muted)', borderTop: '1px solid var(--c-border)', textAlign: 'right' }}>
        共 27 条 · 10条/页
      </div>
    </div>
  );
}

/* 5.28 SVG · Agent 问题列表（NO 区域列）*/
const AGENT_ISSUES = [
  { project: 'K1903 · 和林格尔', agent: 'manage_agent', desc: '智慧工勘识别机房承重网格存在隐患', cat1: '技术', cat2: '机房类', severity: 'high',   src: '客户 TD 00603554', state: 'processing', resp: '已下发加固方案，待现场复核', owner: '李广飞 00603834', planAt: '2026-05-30', doneAt: '' },
  { project: 'K1903 · 和林格尔', agent: 'manage_agent', desc: '规划设计阶段功率预算超机房上限', cat1: '技术', cat2: '机房类', severity: 'high',   src: '客户 TD 00603554', state: 'processing', resp: '已重算配电方案，等待评审', owner: '李广飞 00603834', planAt: '2026-05-31', doneAt: '' },
  { project: 'K1903 · 和林格尔', agent: 'manage_agent', desc: '整机柜压测中部分链路误码偏高', cat1: '质量', cat2: '网络类', severity: 'medium', src: '客户 TD 00603554', state: 'processing', resp: '更换光模块并复测，持续观察', owner: '龙利平 84258415', planAt: '2026-05-29', doneAt: '' },
  { project: 'K1903 · 和林格尔', agent: 'manage_agent', desc: '建模仿真与现场实测偏差待对齐', cat1: '技术', cat2: '计算类', severity: 'medium', src: '客户 TD 00603554', state: 'processing', resp: '校准模型参数，重新出图', owner: '龙利平 84258415', planAt: '2026-06-06', doneAt: '' },
  { project: 'K1903 · 和林格尔', agent: 'manage_agent', desc: '二次部署设备到货延期影响排期', cat1: '进度', cat2: '物流类', severity: 'low',    src: '客户 TD 00603554', state: 'processing', resp: '协调物流加急，调整安装窗口', owner: '孙磊 84194149', planAt: '2026-08-15', doneAt: '' },
];

function AgentIssuesTable() {
  return (
    <div className="jn-panel">
      <div className="jn-panel-head" style={{ padding: '10px 14px' }}>Agent 问题列表</div>
      <div className="ws-table-wrap">
        <table className="vs-table ws-table compact">
          <thead>
            <tr>
              <th>项目名称</th>
              <th>所属 Agent</th>
              <th>问题描述</th>
              <th>一级问题类别</th>
              <th>二级问题类别</th>
              <th>严重程度</th>
              <th>问题来源</th>
              <th>状态</th>
              <th>应急维系或者具体内容</th>
              <th>责任人</th>
              <th className="num">计划处理时间</th>
              <th className="num">实际关闭时间</th>
            </tr>
          </thead>
          <tbody>
            {AGENT_ISSUES.map((a, i) => (
              <tr key={i}>
                <td style={{ fontSize: 11 }}>{a.project}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{a.agent}</td>
                <td style={{ fontSize: 11 }}>{a.desc}</td>
                <td>{a.cat1}</td>
                <td>{a.cat2}</td>
                <td><span className="status-pill red">{a.severity}</span></td>
                <td style={{ fontSize: 11 }}>{a.src}</td>
                <td><span className="status-pill amber">{a.state}</span></td>
                <td style={{ fontSize: 11 }}>{a.resp}</td>
                <td style={{ fontSize: 11 }}>{a.owner}</td>
                <td className="num">{a.planAt}</td>
                <td className="num">{a.doneAt || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ padding: '8px 14px', fontSize: 11, color: 'var(--c-text-muted)', borderTop: '1px solid var(--c-border)', textAlign: 'right' }}>
        共 37 条 · 10条/页
      </div>
    </div>
  );
}

/* 5.28 SVG · DOA 部件统计（柱状图）* 保持一致 + 砍基地园区 */
const DOA_BARS = [
  { label: '已到货',   qty: 221, tone: 'blue' },
  { label: '未到货',   qty: 130, tone: 'amber' },
  { label: '已返修',   qty: 12,  tone: 'gray' },
  { label: '外件返送', qty: 8,   tone: 'gray' },
  { label: '已换货',   qty: 4,   tone: 'gray' },
  { label: '待返修',   qty: 3,   tone: 'gray' },
];

function DOAStatsChart() {
  const max = Math.max(...DOA_BARS.map(b => b.qty));
  return (
    <div className="jn-panel">
      <div className="jn-panel-head" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>DOA 部件统计</span>
        <span style={{ flex: 1 }} />
        <select className="ws-filter">
          <option>收货地点：请选择物流地点</option>
        </select>
      </div>
      <div className="doa-chart-body">
        <div className="doa-chart">
          {DOA_BARS.map((b, i) => (
            <div key={i} className="doa-chart-col">
              <div className="doa-chart-num">{b.qty}</div>
              <div
                className={`doa-chart-bar tone-${b.tone}`}
                style={{ height: `${(b.qty / max) * 220}px` }}
              />
              <div className="doa-chart-label">{b.label}</div>
            </div>
          ))}
        </div>
        <div className="doa-chart-tooltip">
          <strong>未到货</strong>
          <div>· 数量合计 <b>130</b></div>
        </div>
      </div>
    </div>
  );
}

/* 5.28 SVG · DOA 详情（保持一致）*/
const DOA_DETAIL = [
  { idx: 1, no: 'DOA-2026-0145', project: '智算 K1903 · 和林格尔', city: '和林格尔 D3-203', status: 'HWA', owner: 'HW-CALC', terminal: '193035251007', model: 'A3 SuperPoD · NPU 卡识别异常', desc: 'ST 测试 NPU 未达标，已返修闭环', workno: '华为',  dep: 'Atlas 900', who: '2026-01-30', startAt: '2026-01-28', endAt: '补货', closeAt: '2026-02-01' },
  { idx: 2, no: 'DOA-2026-0146', project: '智算 K1903 · 和林格尔', city: '和林格尔 D3-202', status: 'HWA', owner: 'HW-CALC', terminal: '193025251007', model: 'A3 SuperPoD · GPU 数量不符', desc: '整机校验 GPU 数量与 BOQ 不符，已换货', workno: '华为',  dep: 'Atlas 900', who: '2026-01-30', startAt: '2026-01-27', endAt: '换货', closeAt: '2026-02-01' },
  { idx: 3, no: 'DOA-2026-0147', project: '智算 K1903 · 和林格尔', city: '和林格尔 D3-203', status: 'HWB', owner: 'HW-NET',  terminal: '193035251007', model: '100G 光模块 · 链路误码', desc: '链路误码偏高，更换光模块后恢复', workno: '华为',  dep: 'Atlas 900', who: '2025-12-19', startAt: '2025-12-17', endAt: '换货', closeAt: '2025-12-22' },
  { idx: 4, no: 'DOA-2026-0148', project: '智算 K1903 · 和林格尔', city: '和林格尔 D3-101', status: 'HWB', owner: 'HW-SVR',  terminal: '193025251007', model: 'BMC · 带外管理异常',     desc: 'BMC 固件升级后恢复正常',        workno: '华为',  dep: 'Atlas 900', who: '2025-12-19', startAt: '2025-12-16', endAt: '补货', closeAt: '2025-12-22' },
  { idx: 5, no: 'DOA-2026-0149', project: '智算 K1903 · 和林格尔', city: '和林格尔 D3-101', status: 'HWA', owner: 'HW-COOL', terminal: '193025251008', model: '液冷快接头 · 渗漏',       desc: '更换快接头并压测通过',          workno: '华为',  dep: 'Atlas 900', who: '2025-12-19', startAt: '2025-12-15', endAt: '换货', closeAt: '2025-12-22' },
];

function DOADetailTable() {
  return (
    <div className="jn-panel">
      <div className="jn-panel-head" style={{ padding: '10px 14px' }}>DOA 详情</div>
      <div className="ws-table-wrap">
        <table className="vs-table ws-table compact">
          <thead>
            <tr>
              <th>序号</th>
              <th>问题单号</th>
              <th>项目名称</th>
              <th>收货地址</th>
              <th>退到中心</th>
              <th>厂家ID</th>
              <th>物料号</th>
              <th>问题描述</th>
              <th>原因分析</th>
              <th>物料厂家</th>
              <th>物料品牌</th>
              <th>创建时间</th>
              <th>异常时间</th>
              <th>补/退正常单</th>
              <th>合同单入时间</th>
            </tr>
          </thead>
          <tbody>
            {DOA_DETAIL.map(d => (
              <tr key={d.idx}>
                <td className="num">{d.idx}</td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{d.no}</td>
                <td style={{ fontSize: 11 }}>{d.project}</td>
                <td>{d.city}</td>
                <td><span className="status-pill green">{d.status}</span></td>
                <td>{d.owner}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{d.terminal}</td>
                <td style={{ fontSize: 11 }}>{d.model}</td>
                <td style={{ fontSize: 11 }}>{d.desc}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{d.workno}</td>
                <td>{d.dep}</td>
                <td>{d.who}</td>
                <td className="num">{d.startAt}</td>
                <td className="num">{d.endAt}</td>
                <td className="num">{d.closeAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


/* 5.28 下钻 · 主页面块点击 → 整页替换到对应详情页（← 返回看板） */
const DRILL_TITLES = {
  milestone: 'PoD 级里程碑',
  workorder: '客户工程报单',
  risk: '风险详情',
  agent: 'Agent 问题列表',
  doa: 'DOA 部件统计 + 详情',
  dispatch: '下发追踪 · 决策闭环',
};

/* 下钻内容 · 挂入右侧抽屉 slide-over（看板留原位，上下文零损失）*/
function DrillContent({ kind }) {
  return (
    <div className="drill-content p-4 flex flex-col gap-3">
      {kind === 'milestone' && <PoDMilestoneGrid />}
      {kind === 'workorder' && <CustomerWorkOrderTable />}
      {kind === 'risk' && <RiskDetailTable />}
      {kind === 'agent' && <AgentIssuesTable />}
      {kind === 'doa' && (<><DOAStatsChart /><DOADetailTable /></>)}
      {kind === 'dispatch' && <DispatchTracker />}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
 * 工程进度矩阵（参考图1：3 阶段 × 11 工序，总计 + 本月进展）
 * 数据驱动 POD_MILESTONE_STAGES，下钻到 PoDMilestoneGrid
 * ──────────────────────────────────────────────────────────── */
const PHASE_GROUPS = [
  { label: '设计 & 准备', stages: ['L1 机房准备', '工程勘测', '设计审核'] },
  { label: '工程安装',   stages: ['排布线', '设备到货', '设备安装', '成端排扎', '上电'] },
  { label: '调测验收',   stages: ['ZTP 开局', '装机&压测', '验收'] },
];

const STAGE_TOTAL = [
  { done: 45, total: 260 }, { done: 61, total: 260 }, { done: 53, total: 260 },
  { done: 37, total: 260 }, { done: 37, total: 260 }, { done: 37, total: 260 },
  { done: 37, total: 260 }, { done: 32, total: 260 },
  { done: 21, total: 260 }, { done: 8,  total: 260 }, { done: 8,  total: 260 },
];
const STAGE_MONTHLY = [
  { done: 0,  total: 28 }, { done: 16, total: 36 }, { done: 16, total: 36 },
  { done: 21, total: 27 }, { done: 29, total: 29 }, { done: 29, total: 29 },
  { done: 29, total: 33 }, { done: 24, total: 29 },
  { done: 13, total: 16 }, { done: 0,  total: 20 }, { done: 0,  total: 0 },
];

function StageProgressTable({ onDrill, embedded = false }: { onDrill?: (k: string) => void; embedded?: boolean }) {
  const allStages = PHASE_GROUPS.flatMap(g => g.stages);

  const pct = (done, total) => total > 0 ? (done / total * 100).toFixed(1) : '0.0';

  const inner = (
    <>
      <div className={`cp-hd flex items-center justify-between px-5 ${embedded ? 'pt-3 pb-1 mt-1 border-t border-zinc-100/50' : 'pt-3 pb-2'}`}>
        <span className={embedded ? 'text-[12px] font-medium text-zinc-500 tracking-wide' : 'text-base font-semibold text-zinc-900'}>作业进展</span>
      </div>
      <div style={{ overflowX: 'auto', padding: embedded ? '0 20px 12px' : '0 20px 16px' }}>
        <table className="spt-table cockpit-data-table">
          <thead>
            <tr className="spt-phase-row">
              <th className="spt-row-label" rowSpan={2} />
              {PHASE_GROUPS.map(g => (
                <th key={g.label} colSpan={g.stages.length} className="spt-phase-head">
                  {g.label}
                </th>
              ))}
            </tr>
            <tr className="spt-stage-row">
              {allStages.map(s => (
                <th key={s} className="spt-stage-head">{s}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {/* 总计：累计完成率低是项目早期常态，一律蓝色「健康推进」，不标红 */}
            <tr className="group hover:bg-zinc-50/40 cursor-pointer transition-colors" onClick={() => onDrill?.('milestone')}>
              <td className="spt-row-label">总计</td>
              {STAGE_TOTAL.map((d, i) => {
                const p = pct(d.done, d.total);
                const pNum = parseFloat(p);
                return (
                  <td key={i} className="spt-cell tone-gray">
                    <div className="spt-fraction">{d.done} / {d.total}</div>
                    <div className="spt-pct">{p}%</div>
                    <div className="spt-sparkline">
                      <div
                        className="spt-sparkline-fill"
                        style={{ width: `${Math.min(100, pNum)}%` }}
                      />
                    </div>
                  </td>
                );
              })}
            </tr>
            {/* 本月进展：红色仅标记「本应推进却完全停滞」（total>0 但 done=0）的真正异常 */}
            <tr className="group hover:bg-zinc-50/40 cursor-pointer transition-colors" onClick={() => onDrill?.('milestone')}>
              <td className="spt-row-label">本月进展</td>
              {STAGE_MONTHLY.map((d, i) => {
                const p = pct(d.done, d.total);
                const pNum = parseFloat(p);
                const isStalled = d.total > 0 && d.done === 0;
                return (
                  <td key={i} className="spt-cell tone-gray">
                    {d.total > 0 ? (
                      <>
                        <div className="spt-fraction">{d.done} / {d.total}</div>
                        <div className="spt-pct">{p}%</div>
                        <div className="spt-sparkline">
                          <div
                            className={`spt-sparkline-fill${isStalled ? ' danger' : ''}`}
                            style={{ width: `${isStalled ? 100 : Math.min(100, pNum)}%` }}
                          />
                        </div>
                      </>
                    ) : <span className="spt-na">—</span>}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
  if (embedded) return inner;
  return (
    <div className={`bg-white rounded-2xl ${COCKPIT_SHADOW} overflow-hidden stage-progress-table`}>
      {inner}
    </div>
  );
}

const DELIVERY_FLOW_STAGES = [
  { key: 'roomReady', label: '机房 ready' },
  { key: 'arrival', label: '到货' },
  { key: 'cabling', label: '综合布线' },
  { key: 'powerOn', label: '设备上电' },
  { key: 'online', label: '上线' },
  { key: 'handover', label: '移交' },
];

const deliveryDateLabel = (date) => {
  if (!date) return '待回填';
  const [, month, day] = date.split('-');
  return `${Number(month)}/${Number(day)}`;
};

const deliveryPodLabel = (pod) => {
  const match = pod.match(/POD(\d+)$/i);
  return match ? `PoD${match[1]}` : pod;
};

/* ────────────────────────────────────────────────────────────
 * 总体进展文字摘要（4 条时序：当前 / 上周 / 本周 / 昨日进展）
 * ──────────────────────────────────────────────────────────── */
const PROGRESS_LINES = [
  { label: '当前进展', text: '完成预布线 37PoD、完成到货 37PoD、完成成端&理线 37PoD、完成加电 32PoD、完成压测 8PoD、完成验收 8PoD' },
  { label: '上周进展', text: '完成预布线 0PoD、完成到货 1PoD、完成成端&理线 13PoD、完成加电 15PoD、完成压测 0PoD、完成验收 0PoD' },
  { label: '本周进展', text: '完成预布线 0PoD、完成到货 0PoD、完成成端&理线 1PoD、完成加电 4PoD、完成压测 0PoD、完成验收 0PoD' },
  { label: '昨日进展', text: '完成预布线 0PoD、完成到货 0PoD、完成成端&理线 1PoD、完成加电 0PoD、完成压测 0PoD、完成验收 0PoD' },
];

const PROGRESS_SUMMARY = [
  { label: '本周完成', text: '完成 1 个 PoD 的综合布线与成端，并完成 4 个 PoD 的设备上电。' },
  { label: '上周完成', text: '完成 1 个 PoD 的设备到货、13 个 PoD 的综合布线与成端，以及 15 个 PoD 的设备上电。' },
  { label: '本月完成', text: '交付工作集中推进至设备上电阶段，累计完成 37 个 PoD 的到货与综合布线、32 个 PoD 的设备上电。' },
];

/* 时间线按时近着色：本周(靛蓝) / 上周(灰) / 本月(浅灰)，与里程碑看板配色统一 */
const PROGRESS_PERIODS = [
  { dot: '#5165F0', spine: 'linear-gradient(#5165F0,#C7CEDB)', pillBg: '#5165F0', pillFg: '#ffffff', textCls: 'text-zinc-600', num: '#3447C9' },
  { dot: '#8A95AC', spine: '#DCE1EB', pillBg: '#EEF0F5', pillFg: '#43506A', textCls: 'text-zinc-600', num: '#1C2640' },
  { dot: '#B4BDD0', spine: 'transparent', pillBg: '#F3F5F9', pillFg: '#8A95AC', textCls: 'text-zinc-400', num: '#5F6B7E' },
] as const;

/* 加重正文里的「N 个」关键数字 */
const emphasizeNums = (text: string, color: string) =>
  text.split(/(\d+\s*个)/g).map((p, i) =>
    /\d+\s*个/.test(p)
      ? <b key={i} style={{ fontWeight: 600, color }}>{p}</b>
      : <span key={i}>{p}</span>,
  );

const getDelayedActivities = (snapshot) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return snapshot.pods.flatMap(pod => DELIVERY_FLOW_STAGES.flatMap(meta => {
    const stage = pod.stages[meta.key];
    if (!stage || stage.actualEnd || stage.progress <= 0 || stage.expectedEnd >= formatLocalDate(today)) return [];
    const delayDays = Math.max(1, Math.floor((today.getTime() - new Date(`${stage.expectedEnd}T00:00:00`).getTime()) / 86400000));
    const item = {
      pod: deliveryPodLabel(pod.pod),
      activity: meta.label,
      owner: stage.owner || '待明确',
      delayDays,
      progress: stage.progress,
      expectedEnd: stage.expectedEnd,
    };
    return [item];
  }));
};

function ProgressSummaryRow({ delayItems }) {
  return (
    /* 两列 grid：总体进展(3fr) + 活动延期(2fr) */
    <div className="grid grid-cols-[3fr_2fr] gap-6">

      {/* 左：总体进展 —— 时间线，按时近着色 + 关键数字加重 */}
      <div className={`bg-white rounded-2xl ${COCKPIT_SHADOW} overflow-hidden p-5`}>
        <div className="flex items-center gap-2 pb-4 mb-4 border-b border-zinc-100/60">
          <span className="text-base font-semibold text-zinc-900">总体进展</span>
          <span className="text-[11px] text-zinc-400">交付节奏</span>
        </div>
        <div>
          {PROGRESS_SUMMARY.map((item, i) => {
            const t = PROGRESS_PERIODS[i] ?? PROGRESS_PERIODS[PROGRESS_PERIODS.length - 1]!;
            const last = i === PROGRESS_SUMMARY.length - 1;
            return (
              <div key={item.label} className="flex gap-3">
                <div className="flex flex-col items-center pt-1">
                  <span className="shrink-0 rounded-full" style={{ width: 11, height: 11, background: t.dot }} />
                  {!last && <span className="w-0.5 flex-1" style={{ background: t.spine, minHeight: 16 }} />}
                </div>
                <div className={last ? 'pb-0.5' : 'pb-4'}>
                  <span className="inline-block rounded-md px-2.5 py-0.5 text-[11px] font-medium" style={{ background: t.pillBg, color: t.pillFg }}>{item.label}</span>
                  <p className={`mt-2 text-xs leading-relaxed ${t.textCls}`}>{emphasizeNums(item.text, t.num)}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 右：活动延期 —— 左侧严重度色条 + 进度条 */}
      <div className={`bg-white rounded-2xl ${COCKPIT_SHADOW} overflow-hidden p-5`}>
        <div className="flex items-center gap-2 pb-4 mb-4 border-b border-zinc-100/60">
          <span className="text-base font-semibold text-zinc-900">活动延期</span>
          {delayItems.length > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium" style={{ background: '#FCE3E9', color: '#B22647' }}>
              <span className="rounded-full" style={{ width: 6, height: 6, background: '#E23A5E' }} />
              {delayItems.length} 项待关注
            </span>
          )}
        </div>
        <div className="flex flex-col gap-2.5">
          {delayItems.map(d => {
            const severe = d.delayDays >= 5;
            const accent = severe ? '#E23A5E' : '#C2820F';
            const chipBg = severe ? '#FCE3E9' : '#FBEFD9';
            const chipFg = severe ? '#B22647' : '#9A5B08';
            return (
              <div
                key={`${d.pod}-${d.activity}`}
                className="relative overflow-hidden rounded-xl px-4 py-3"
                style={{ border: '0.5px solid #EAEDF3', background: '#FBFCFE' }}
              >
                <span className="absolute left-0 top-0 bottom-0" style={{ width: 3, background: accent }} />
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-semibold text-zinc-800">{d.pod}</span>
                    <span className="h-3 w-px bg-zinc-200" />
                    <span className="truncate text-xs text-zinc-600">{d.activity}</span>
                  </div>
                  <span className="shrink-0 rounded-md px-2 py-1 text-[11px] font-semibold" style={{ background: chipBg, color: chipFg }}>
                    延期 {d.delayDays} 天
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-2.5 mb-1.5">
                  <div className="flex-1 rounded-full overflow-hidden" style={{ height: 5, background: '#EEF0F5' }}>
                    <span className="block h-full rounded-full" style={{ width: `${d.progress}%`, background: '#C2820F' }} />
                  </div>
                  <span className="text-[11px] font-medium tabular-nums" style={{ color: '#C2820F' }}>{d.progress}%</span>
                </div>
                <p className="text-[11px] text-zinc-400">计划 {deliveryDateLabel(d.expectedEnd)} 完成 · {d.owner} 负责跟进</p>
              </div>
            );
          })}
          {delayItems.length === 0 && (
            <div className="rounded-xl px-4 py-3 text-xs" style={{ border: '0.5px solid #DCEFE6', background: '#EAF7F1', color: '#0B7A53' }}>
              当前没有未完成的延期活动，交付节奏正常。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
 * 带4 / 带5 数据 + 组件（参考图1 严格对齐，不加不减）
 * ═══════════════════════════════════════════════════════════ */

/* 客户工程报单：关闭/非关闭 × 提前/按期/延期（时效） */
const WORK_ORDER_STATS = {
  closed: { early: 6, onTime: 14, delayed: 4 },
  open:   { early: 0, onTime: 5,  delayed: 3 },
};
const RISK_STATS_AGG = { closed: 30, active: 6, overdue: 2, total: 38 };
const PROB_MULTI = [
  { status: '待处理', high: 7, medium: 0, low: 0 },
  { status: '处理中', high: 6, medium: 4, low: 1 },
  { status: '已关闭', high: 4, medium: 4, low: 0 },
];
/* DOA：4 类（未到货 / 已到货 / 已更换 / 好件退还），各一独立语义色 */
const DOA_STATS = [
  { label: '未到货',   value: 130, color: '#F2A03C' },
  { label: '已到货',   value: 221, color: '#0FA371' },
  { label: '已更换',   value: 4,   color: '#5165F0' },
  { label: '好件退还', value: 8,   color: '#8A95AC' },
];
/* 交付 ITO：6 道工序（冷→暖渐进色），按图2 各项目周期 */
type ItoRow = { name: string; pods: number; arrive: number | null; cable: number | null; bundle: number | null; power: number | null; mount: number | null; tree: number | null };
const ITO_STAGES: { key: keyof ItoRow; name: string; color: string }[] = [
  { key: 'arrive', name: '到货-通液',    color: '#2DBE9F' },
  { key: 'cable',  name: '通液-绑扎',    color: '#3E8FE0' },
  { key: 'bundle', name: '绑扎-上电',    color: '#5165F0' },
  { key: 'power',  name: '上电-ZTP开局', color: '#7C72E8' },
  { key: 'mount',  name: 'ZTP开局-装机', color: '#B07BD6' },
  { key: 'tree',   name: '装机-挂树',    color: '#E58AA6' },
];
const ITO_DELIVERY: ItoRow[] = [
  { name: '项目汇总', pods: 63, arrive: 1.9,  cable: 6.1,  bundle: 3,    power: 6.8,  mount: 4.3,  tree: 1 },
  { name: '和林格尔', pods: 16, arrive: 1.8,  cable: 6.3,  bundle: 2,    power: 7.8,  mount: 4.3,  tree: 1 },
  { name: '廊坊润泽', pods: 31, arrive: 1.7,  cable: 6.4,  bundle: 4,    power: 6,    mount: null, tree: null },
  { name: '芜湖无为', pods: 16, arrive: 2.1,  cable: 5.6,  bundle: 3,    power: 6.5,  mount: null, tree: null },
  { name: '天津',     pods: 8,  arrive: null, cable: null, bundle: null, power: null, mount: null, tree: null },
];

/* ───────── 统计卡（竖向柱状图：单系列 / 堆叠；hover 出分段详情）───────── */
type ChartSeg = { label: string; value: number; color: string };
type ChartCol = { label: string; sub?: string; segments: ChartSeg[] };

const fmtNum = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

function ColumnStatCard({ title, legend, columns, onDrill, drillKey, unit = '', height = 104 }: {
  title: string;
  legend?: { label: string; color: string }[];
  columns: ChartCol[];
  onDrill?: (k: string) => void;
  drillKey: string;
  unit?: string;
  height?: number;
}) {
  const totals = columns.map(c => c.segments.reduce((s, x) => s + x.value, 0));
  const max = Math.max(...totals, 1);
  return (
    <div className={`group bg-white rounded-2xl ${COCKPIT_SHADOW} flex flex-col overflow-hidden p-5 transition-shadow duration-200 hover:shadow-[0_8px_20px_rgba(24,24,27,0.08)]`}>
      <div className="flex items-start justify-between gap-3 pb-4 mb-4 border-b border-zinc-100/60 cursor-pointer" onClick={() => onDrill?.(drillKey)}>
        <span className="text-base font-semibold text-zinc-900 whitespace-nowrap">{title}</span>
        {legend
          ? <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1">{legend.map(l => (
              <span key={l.label} className="inline-flex items-center gap-1.5 text-[10.5px] text-zinc-400"><span className="w-2 h-2 rounded-sm" style={{ background: l.color }} />{l.label}</span>
            ))}</div>
          : <span className="text-[11px] text-zinc-300 group-hover:text-zinc-500 transition-colors leading-none" aria-hidden>↗</span>}
      </div>

      <div className="flex items-end justify-around gap-2" style={{ height: height + 48 }}>
        {columns.map((c, i) => {
          const total = totals[i];
          const multi = c.segments.length > 1;
          return (
            <div key={i} className="group/col relative flex h-full min-w-0 flex-1 flex-col items-center justify-end">
              {total > 0 && (
                <div className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-lg border border-zinc-200 bg-white px-2.5 py-2 text-[10.5px] opacity-0 shadow-[0_8px_22px_rgba(20,28,46,.16)] transition-opacity group-hover/col:opacity-100">
                  <div className="mb-1 font-medium text-zinc-800">{c.label} · {fmtNum(total)}{unit}</div>
                  {multi && (
                    <div className="flex flex-col gap-0.5">
                      {c.segments.filter(s => s.value > 0).slice().reverse().map(s => (
                        <div key={s.label} className="flex items-center gap-1.5 text-zinc-500"><span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />{s.label} {fmtNum(s.value)}{unit}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <span className="mb-1 text-[12px] font-semibold leading-none tabular-nums text-zinc-800">{total > 0 ? fmtNum(total) : ''}</span>
              <div className="flex w-full max-w-[46px] flex-col-reverse overflow-hidden rounded-t-[4px]">
                {c.segments.map((s, j) => (s.value > 0 ? <div key={j} style={{ height: Math.max(3, (s.value / max) * height), background: s.color }} /> : null))}
              </div>
              <span className="mt-2 text-center leading-tight">
                <span className="block whitespace-nowrap text-[11px] text-zinc-600">{c.label}</span>
                {c.sub && <span className="block whitespace-nowrap text-[10px] text-zinc-400">{c.sub}</span>}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* 客户工程报单：已关闭/未关闭 × 提前/按期/延期（堆叠柱，延期置柱底） */
function WorkOrderStatsCard({ onDrill }: { onDrill?: (k: string) => void }) {
  const seg = (t: { early: number; onTime: number; delayed: number }): ChartSeg[] => [
    { label: '延期', value: t.delayed, color: '#E5395B' },
    { label: '按期', value: t.onTime,  color: '#B9C2D4' },
    { label: '提前', value: t.early,   color: '#0FA371' },
  ];
  return (
    <ColumnStatCard
      title="客户工程报单"
      legend={[{ label: '提前', color: '#0FA371' }, { label: '按期', color: '#B9C2D4' }, { label: '延期', color: '#E5395B' }]}
      columns={[
        { label: '已关闭', segments: seg(WORK_ORDER_STATS.closed) },
        { label: '未关闭', segments: seg(WORK_ORDER_STATS.open) },
      ]}
      onDrill={onDrill} drillKey="workorder"
    />
  );
}

/* 风险统计：已超期 / 处理中 / 已关闭（单系列柱） */
function RiskStatsCard({ onDrill }: { onDrill?: (k: string) => void }) {
  return (
    <ColumnStatCard
      title="风险统计"
      columns={[
        { label: '已超期', segments: [{ label: '已超期', value: RISK_STATS_AGG.overdue, color: '#E23A5E' }] },
        { label: '处理中', segments: [{ label: '处理中', value: RISK_STATS_AGG.active,  color: '#5165F0' }] },
        { label: '已关闭', segments: [{ label: '已关闭', value: RISK_STATS_AGG.closed,  color: '#C7CEDB' }] },
      ]}
      onDrill={onDrill} drillKey="risk"
    />
  );
}

/* 问题统计：待处理/处理中/已关闭 × 高/中/低（堆叠柱，高危置柱底；已关闭灰阶弱化） */
function ProblemStatsCard({ onDrill }: { onDrill?: (k: string) => void }) {
  const live = { high: '#E5395B', medium: '#F2A03C', low: '#B9C2D4' };
  const closed = { high: '#B6BFCF', medium: '#CFD6E2', low: '#E0E5EC' };
  const columns: ChartCol[] = PROB_MULTI.map(g => {
    const c = g.status === '已关闭' ? closed : live;
    return {
      label: g.status,
      segments: [
        { label: '高', value: g.high,   color: c.high },
        { label: '中', value: g.medium, color: c.medium },
        { label: '低', value: g.low,    color: c.low },
      ],
    };
  });
  return (
    <ColumnStatCard
      title="问题统计"
      legend={[{ label: '高', color: '#E5395B' }, { label: '中', color: '#F2A03C' }, { label: '低', color: '#B9C2D4' }]}
      columns={columns}
      onDrill={onDrill} drillKey="agent"
    />
  );
}

/* DOA 统计：未到货 / 已到货 / 已更换 / 好件退还（单系列柱，各一色） */
function DOAStatsCard({ onDrill }: { onDrill?: (k: string) => void }) {
  return (
    <ColumnStatCard
      title="DOA 统计"
      columns={DOA_STATS.map(d => ({ label: d.label, segments: [{ label: d.label, value: d.value, color: d.color }] }))}
      onDrill={onDrill} drillKey="doa"
    />
  );
}

/* 交付 ITO 统计：每项目一根竖向堆叠柱（按 6 道工序分段），柱高=总交付周期；hover 看工序天数 */
function ITOStatsCard({ onDrill }: { onDrill?: (k: string) => void }) {
  const columns: ChartCol[] = ITO_DELIVERY.map(r => ({
    label: r.name,
    segments: ITO_STAGES.flatMap(s => {
      const raw = r[s.key];
      return typeof raw === 'number' && raw > 0 ? [{ label: s.name, value: raw, color: s.color }] : [];
    }),
  }));
  return (
    <ColumnStatCard
      title="交付 ITO 统计"
      legend={ITO_STAGES.map(s => ({ label: s.name, color: s.color }))}
      columns={columns}
      onDrill={onDrill} drillKey="workorder"
      unit="天" height={110}
    />
  );
}

/* 5.31 · 项目体检头条 + 异常聚合（P0）
 * 整体完成度 / 异常数全部用现有展示常量派生，零改 state / 业务逻辑。
 * 异常拆解可点击下钻：延期→dispatch · 超期→risk · 待处理→agent */
function ProjectHealthHeader({ onDrill, delayItems = [] }) {
  const totalDone = PROJECT_STAGES.reduce((s, x) => s + x.done, 0);
  const totalAll  = PROJECT_STAGES.reduce((s, x) => s + x.total, 0);
  const overallPct = totalAll > 0 ? Math.round((totalDone / totalAll) * 100) : 0;
  const delays  = delayItems.length;
  const overdue = RISK_STATS_AGG.overdue;
  const pendingRow = PROB_MULTI.find(x => x.status === '待处理');
  const pending = pendingRow ? pendingRow.high + pendingRow.medium + pendingRow.low : 0;
  const totalIssues = delays + overdue + pending;

  return (
    <div className="bg-white rounded-2xl border border-zinc-100/80 shadow-sm p-5 flex items-center gap-6 flex-wrap">
      {/* 左：项目标识 */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-lg font-semibold text-zinc-900">项目孪生 · 智算 K1903</span>
        <span className="text-xs text-zinc-400">第 55 天 · Q90 · 客户甲（华东）</span>
      </div>

      <div className="h-10 w-px bg-zinc-100" />

      {/* 中：整体完成度 + 4 阶段迷你进度 */}
      <div className="flex items-center gap-5">
        <div className="flex items-baseline gap-1.5">
          <span className="text-3xl font-bold text-zinc-900 tabular-nums leading-none">{overallPct}%</span>
          <span className="text-xs text-zinc-400">整体 · {totalDone}/{totalAll} 阶段项</span>
        </div>
        <div className="flex items-center gap-3">
          {PROJECT_STAGES.map(s => {
            const p = s.total > 0 ? Math.round((s.done / s.total) * 100) : 0;
            return (
              <div key={s.key} style={{ minWidth: 62 }}>
                <div className="flex items-baseline justify-between mb-1">
                  <span className="text-[10px] text-zinc-500">{s.label}</span>
                  <span className="text-[10px] text-zinc-400 tabular-nums">{s.done}/{s.total}</span>
                </div>
                <div className="h-1 rounded-full bg-zinc-100 overflow-hidden">
                  <div className="h-full rounded-full bg-zinc-900" style={{ width: `${p}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex-1" />

      {/* 右：异常聚合（红色仅此处，"需立即行动"语义）*/}
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={() => onDrill?.('risk')}
          className="inline-flex items-center gap-1.5 bg-red-50 text-red-600 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors hover:bg-red-100"
          style={{ boxShadow: 'inset 0 0 0 1px rgba(220,38,38,0.18)' }}
        >
          ⚠ {totalIssues} 项须关注
        </button>
        <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
          <button onClick={() => onDrill?.('dispatch')} className="hover:text-zinc-800 transition-colors">延期 {delays}</button>
          <span className="text-zinc-300">·</span>
          <button onClick={() => onDrill?.('risk')} className="hover:text-zinc-800 transition-colors">超期 {overdue}</button>
          <span className="text-zinc-300">·</span>
          <button onClick={() => onDrill?.('agent')} className="hover:text-zinc-800 transition-colors">待处理 {pending}</button>
        </div>
      </div>
    </div>
  );
}

export default function DashboardScreen() {
  const [searchParams] = useSearchParams();
  const [deliverySnapshot, setDeliverySnapshot] = useState(DELIVERY_PLAN_FALLBACK);
  const delayedActivities = useMemo(() => getDelayedActivities(deliverySnapshot), [deliverySnapshot]);
  const milestonePods = useMemo(() => podMilestonesFromSnapshot(deliverySnapshot), [deliverySnapshot]);

  useEffect(() => {
    let active = true;
    fetchDeliveryPlan('K1903').then(data => {
      if (active) setDeliverySnapshot(data);
    });
    return () => { active = false; };
  }, []);

  const view = searchParams.get('view');
  if (view === '底座' || view === 'foundation') {
    return <Navigate to="/twin" replace />;
  }

  const [drill, setDrill] = useState(null); // null | milestone | workorder | risk | agent | doa

  return (
    <>
    <div className="cockpit-page">
      <MilestoneBoard pods={milestonePods} />
      <ProgressSummaryRow delayItems={delayedActivities} />

      <div className="grid grid-cols-3 gap-3">
        <WorkOrderStatsCard onDrill={setDrill} />
        <RiskStatsCard onDrill={setDrill} />
        <ProblemStatsCard onDrill={setDrill} />
      </div>

      <div className="grid grid-cols-[3fr_5fr] gap-3">
        <DOAStatsCard onDrill={setDrill} />
        <ITOStatsCard onDrill={setDrill} />
      </div>
    </div>

      {/* 下钻 · 右侧抽屉 slide-over（替代整页替换，上下文零损失）*/}
      <Drawer
        isOpen={!!drill}
        onClose={() => setDrill(null)}
        title={drill ? DRILL_TITLES[drill] : ''}
        size="wide"
      >
        {drill && <DrillContent kind={drill} />}
      </Drawer>
    </>
  );
}
