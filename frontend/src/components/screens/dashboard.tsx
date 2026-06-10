// @ts-nocheck
'use client';

import React, { useState, useMemo } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import Link from '@/compat/link';
import { RISKS, MILESTONES, RISK_SOURCES } from '../../data/app-data';
import { DispatchTracker } from '../dispatch-tracker';
import Drawer from '../drawer';

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

/* 简易竖向柱状统计（问题统计 / 工程单状态统计） */
function StatBars({ bars }) {
  const max = Math.max(...bars.map(b => b.qty), 1);
  return (
    <div className="mini-bars">
      {bars.map((b, i) => (
        <div key={i} className="mini-bar-col">
          <div className="mini-bar-num">{b.qty}</div>
          <div className={`mini-bar tone-${b.tone}`} style={{ height: `${Math.max(4, (b.qty / max) * 72)}px` }} />
          <div className="mini-bar-label">{b.label}</div>
        </div>
      ))}
    </div>
  );
}

function ProblemStatsCard({ onDrill }) {
  return (
    <div className="jn-panel stat-card">
      <div className="jn-panel-head" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>问题统计</span>
        <span style={{ flex: 1 }} />
        <button className="btn sm ghost" onClick={() => onDrill?.('agent')}>Agent 问题列表 →</button>
      </div>
      <StatBars bars={[
        { label: 'high', qty: 8, tone: 'red' },
        { label: 'medium', qty: 4, tone: 'amber' },
        { label: 'low', qty: 1, tone: 'blue' },
      ]} />
    </div>
  );
}

function WorkOrderStatsCard({ onDrill }) {
  return (
    <div className="jn-panel stat-card">
      <div className="jn-panel-head" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>工程单状态统计</span>
        <span style={{ flex: 1 }} />
        <button className="btn sm ghost" onClick={() => onDrill?.('workorder')}>客户工程报单 →</button>
      </div>
      <StatBars bars={[
        { label: '已关闭', qty: 22, tone: 'green' },
        { label: '处理中', qty: 6, tone: 'amber' },
        { label: '已超期', qty: 2, tone: 'red' },
      ]} />
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

/** 总计划 + 作业进展 · 融合为单一作业流卡片 */
function PlanProgressSection({ onDrill }) {
  return (
    <div className={`cockpit-plan-flow bg-white rounded-2xl ${COCKPIT_SHADOW} overflow-hidden`}>
      <div className="flex items-center justify-between px-5 pt-4 pb-2">
        <span className="text-base font-semibold text-zinc-900">交付作业流</span>
        <span className="text-[11px] text-zinc-400">计划 · 进展 · K1903</span>
      </div>
      <SupplyPlanTimeline embedded />
      <StageProgressTable onDrill={onDrill} embedded />
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
 * 总体进展文字摘要（4 条时序：当前 / 上周 / 本周 / 昨日进展）
 * ──────────────────────────────────────────────────────────── */
const PROGRESS_LINES = [
  { label: '当前进展', text: '完成预布线 37PoD、完成到货 37PoD、完成成端&理线 37PoD、完成加电 32PoD、完成压测 8PoD、完成验收 8PoD' },
  { label: '上周进展', text: '完成预布线 0PoD、完成到货 1PoD、完成成端&理线 13PoD、完成加电 15PoD、完成压测 0PoD、完成验收 0PoD' },
  { label: '本周进展', text: '完成预布线 0PoD、完成到货 0PoD、完成成端&理线 1PoD、完成加电 4PoD、完成压测 0PoD、完成验收 0PoD' },
  { label: '昨日进展', text: '完成预布线 0PoD、完成到货 0PoD、完成成端&理线 1PoD、完成加电 0PoD、完成压测 0PoD、完成验收 0PoD' },
];

/* 总体进展结构化（5.31）：从 PROGRESS_LINES 同源的演示数据拆成「时段 × 工序」网格，
 * 取代 4 行截断长文本。纯展示 mock，不影响任何 state / 业务逻辑。 */
const PROGRESS_COLS = ['预布线', '到货', '成端&理线', '加电', '压测', '验收'];
const PROGRESS_MATRIX = [
  { label: '当前', accent: true,  vals: [37, 37, 37, 32, 8, 8] },
  { label: '上周', accent: false, vals: [0, 1, 13, 15, 0, 0] },
  { label: '本周', accent: false, vals: [0, 0, 1, 4, 0, 0] },
  { label: '昨日', accent: false, vals: [0, 0, 1, 0, 0, 0] },
];

/* 结构化：右侧提取「滞后天数」对齐展示，取代纯省略号截断（5.31，展示 mock）*/
const DELAY_ITEMS = [
  { text: 'O1 A3框架_WHYJ 5月12日PoD交付：输出工勘报告实际开始时间已延期（侯克照 00578443）', lag: '滞后 5 天' },
  { text: 'O1 A3框架_WHYJ 5月12日PoD交付：L1机房准备实际开始时间已延期（王文涛 00664696）', lag: '滞后 3 天' },
  { text: 'K1903 B2-RM02 配电节点：市电引入审批滞后 9 天，影响上电（李伟 00603554）', lag: '滞后 9 天' },
];

function ProgressSummaryRow({ onDrill }) {
  return (
    /* 两列 grid：总体进展(3fr) + 活动延期(2fr)，与原 CSS 比例一致 */
    <div className="grid grid-cols-[3fr_2fr] gap-6">

      {/* 左：总体进展文字 */}
      <div className={`bg-white rounded-2xl ${COCKPIT_SHADOW} overflow-hidden p-5`}>
        <div className="cp-hd flex items-center justify-between pb-4 mb-4 border-b border-zinc-100/50">
          <span className="text-base font-semibold text-zinc-900">总体进展</span>
          <button
            className="text-[10px] text-zinc-400 hover:text-zinc-600 transition-colors cursor-pointer"
            onClick={() => onDrill?.('milestone')}
          >
            里程碑 →
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full cockpit-data-table" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr className="border-b border-zinc-100/50 bg-zinc-50/80">
                <th className="text-left text-[11px] font-medium text-zinc-500 py-1.5 px-2.5 whitespace-nowrap">时段 · PoD</th>
                {PROGRESS_COLS.map(c => (
                  <th key={c} className="text-right text-[11px] font-medium text-zinc-500 py-1.5 px-2 whitespace-nowrap">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PROGRESS_MATRIX.map((row, i) => (
                <tr key={i} className={`border-b border-zinc-100/50 last:border-b-0${row.accent ? ' bg-blue-50/50' : ''}`}>
                  <td className={`text-[11px] py-1.5 px-2.5 whitespace-nowrap ${row.accent ? 'font-medium text-zinc-700' : 'text-zinc-600'}`}>
                    {row.label}
                  </td>
                  {row.vals.map((v, j) => (
                    <td
                      key={j}
                      className={`text-right text-[11px] py-1.5 px-2 tabular-nums ${
                        v === 0 ? 'text-zinc-300' : row.accent ? 'font-medium text-zinc-700' : 'text-zinc-600'
                      }`}
                    >
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 右：活动延期 */}
      <div className={`bg-white rounded-2xl ${COCKPIT_SHADOW} overflow-hidden p-5`}>
        <div className="cp-hd flex items-center justify-between pb-4 mb-4 border-b border-zinc-100/50">
          <span className="text-base font-semibold text-zinc-900">活动延期</span>
          <button
            className="text-[10px] text-zinc-400 hover:text-zinc-600 transition-colors cursor-pointer"
            onClick={() => onDrill?.('dispatch')}
          >
            下发追踪 →
          </button>
        </div>
        <div className="flex flex-col gap-2">
          {DELAY_ITEMS.map((d, i) => (
            <div
              key={i}
              className="flex items-center gap-2 border-l-2 border-amber-700/40 pl-2 min-w-0"
              title={d.text}
            >
              <span className="text-[11px] text-zinc-600 truncate flex-1 min-w-0">{d.text}</span>
              <span className="text-[12px] font-semibold text-amber-700 whitespace-nowrap tabular-nums shrink-0">{d.lag}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
 * 带4 / 带5 数据 + 组件（参考图1 严格对齐，不加不减）
 * ═══════════════════════════════════════════════════════════ */

const WO_MONTH_BARS = [
  { month: '1月', closed: 22 }, { month: '2月', closed: 18 },
  { month: '3月', closed: 15 }, { month: '4月', closed: 28 }, { month: '5月', closed: 12 },
];
const RISK_STATS_AGG = { closed: 30, active: 6, overdue: 2, total: 38 };
const PROB_MULTI = [
  { status: '处理中', high: 6, medium: 4, low: 1 },
  { status: '已关闭', high: 4, medium: 4, low: 0 },
  { status: '待处理', high: 7, medium: 0, low: 0 },
];
const DOA_TOTAL_BARS = [
  { label: '和林格尔', qty: 421 },
  { label: '廊坊涿泽', qty: 394 },
  { label: '芜湖无为', qty: 18 },
];
const ITO_DELIVERY = [
  { name: '项目汇总', pods: 37, arrive: 1.8, cable: 6.4, bundle: 2.8, power: 8.3, mount: 4.3, accept: 1 },
  { name: '和林格尔', pods: 16, arrive: 1.8, cable: 6.4, bundle: 2.0, power: 7.8, mount: 4.3, accept: 1 },
  { name: '廊坊涿泽', pods: 21, arrive: 1.7, cable: 6.4, bundle: 3.5, power: 8.7, mount: null, accept: null },
  { name: '芜湖无为', pods: 5,  arrive: null, cable: null, bundle: null, power: null, mount: null, accept: null },
];
const ITO_MONTHLY = [
  { name: '项目汇总', pods: 21, arrive: 1.7, cable: 6.4, bundle: 3.5, power: 8.7, mount: null, accept: null },
  { name: '廊坊涿泽', pods: 21, arrive: 1.7, cable: 6.4, bundle: 3.5, power: 8.7, mount: null, accept: null },
  { name: '芜湖无为', pods: 5,  arrive: null, cable: null, bundle: null, power: null, mount: null, accept: null },
];

/* ── 柱图色彩：主柱 slate-800 午夜分量；超期 amber-700；弱项 slate-300；已闭/历史 faint slate-200 ── */
const BAR_TONE_CLS: Record<string, string> = {
  green: 'bg-slate-800',
  blue:  'bg-slate-800',
  amber: 'bg-slate-400',
  red:   'bg-amber-700',
  gray:  'bg-slate-300',
  faint: 'bg-slate-200',
};

/* 通用小柱图面板（全 Tailwind 版）─ 复用于工程报单、风险统计 */
function CpBarPanel({ title, badge, bars, month, setMonth, onDrill, drillKey, footnote }) {
  const max = Math.max(...bars.map(b => b.qty), 1);
  return (
    <div className={`group bg-white rounded-2xl ${COCKPIT_SHADOW} flex flex-col overflow-hidden min-h-[160px] p-5 transition-shadow duration-200 hover:shadow-[0_8px_20px_rgba(24,24,27,0.08)]`}>

      {/* 标题栏 */}
      <div
        className="cp-hd flex items-center justify-between pb-4 mb-4 border-b border-zinc-100/50 cursor-pointer flex-shrink-0"
        onClick={() => onDrill?.(drillKey)}
      >
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold text-zinc-900">{title}</span>
          {badge != null && (
            <span className="text-[10px] font-mono bg-zinc-100 text-zinc-500 px-1.5 py-0.5 rounded border border-zinc-200 leading-none">
              {badge}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {month !== undefined && (
            <select
              className="text-[10px] px-1 py-0.5 border border-zinc-200 rounded bg-white text-zinc-500 outline-none"
              value={month}
              onClick={e => e.stopPropagation()}
              onChange={e => setMonth(e.target.value)}
            >
              <option value="">选择月份</option>
              {WO_MONTH_BARS.map(b => <option key={b.month} value={b.month}>{b.month}</option>)}
            </select>
          )}
          <button
            className="text-[11px] text-zinc-300 group-hover:text-zinc-500 group-hover:translate-x-0.5 transition-all duration-200 leading-none"
            onClick={() => onDrill?.(drillKey)} tabIndex={-1} aria-hidden
          >↗</button>
        </div>
      </div>

      {/* 柱图区：极淡基线承托柱体 */}
      <div className="flex items-end justify-around gap-1 flex-1 border-b border-zinc-100/70">
        {bars.map((b, i) => (
          <div key={i} className="flex flex-col items-center justify-end gap-0.5 flex-1">
            <span className={`text-[15px] font-mono font-semibold leading-none tabular-nums ${b.muted ? 'text-zinc-400' : 'text-zinc-800'}`}>
              {b.qty}
            </span>
            <div
              className={`w-full rounded-t-sm transition-all duration-300 ${BAR_TONE_CLS[b.tone] ?? 'bg-slate-300'}`}
              style={{ height: `${Math.max(4, (b.qty / max) * 30)}px`, minWidth: '14px' }}
            />
            <span className={`text-[9px] text-center leading-tight whitespace-nowrap ${b.muted ? 'text-zinc-300' : 'text-zinc-500'}`}>
              {b.label}
            </span>
          </div>
        ))}
      </div>

      {footnote && (
        <div className="flex items-center gap-1.5 pt-2 text-[10px] text-zinc-400 flex-shrink-0">
          {footnote}
        </div>
      )}
    </div>
  );
}

/* 带4·A: 客户工程报单（月份过滤） */
function WorkOrderMonthChart({ onDrill }) {
  const [month, setMonth] = useState('');
  const bars = (month ? WO_MONTH_BARS.filter(b => b.month === month) : WO_MONTH_BARS)
    .map(b => ({ label: b.month, qty: b.closed, tone: 'green' }));
  return (
    <CpBarPanel
      title="客户工程报单" bars={bars}
      month={month} setMonth={setMonth}
      onDrill={onDrill} drillKey="workorder"
      footnote={<><span className="inline-block w-2 h-2 rounded-full bg-slate-800 mr-1" />已关闭</>}
    />
  );
}

/* 带4·B: 风险统计 — 紧急在前（超期→处理中→已关闭），已关闭弱化为背景项 */
function RiskStatsBarChart({ onDrill }) {
  const bars = [
    { label: '已超期', qty: RISK_STATS_AGG.overdue, tone: 'red' },
    { label: '处理中', qty: RISK_STATS_AGG.active, tone: 'blue' },
    { label: '已关闭', qty: RISK_STATS_AGG.closed, tone: 'faint', muted: true },  /* 历史项弱化，视线聚焦超期/处理中 */
  ];
  return (
    <CpBarPanel
      title="风险统计"
      bars={bars} onDrill={onDrill} drillKey="risk"
    />
  );
}

/* 带4·C: 问题统计（多系列 · 全 Tailwind）*/
function ProblemMultiBarChart({ onDrill }) {
  const allVals = PROB_MULTI.flatMap(g => [g.high, g.medium, g.low]);
  const max = Math.max(...allVals, 1);

  /* high → 红色（异常风险），medium/low → 石板灰 */
  const MULTI_COLOR = ['bg-red-500', 'bg-slate-400', 'bg-slate-300'];

  return (
    <div className={`group bg-white rounded-2xl ${COCKPIT_SHADOW} flex flex-col overflow-hidden min-h-[160px] p-5 transition-shadow duration-200 hover:shadow-[0_8px_20px_rgba(24,24,27,0.08)]`}>

      {/* 标题栏 */}
      <div
        className="cp-hd flex items-center justify-between pb-4 mb-4 border-b border-zinc-100/50 cursor-pointer flex-shrink-0"
        onClick={() => onDrill?.('agent')}
      >
        <span className="text-base font-semibold text-zinc-900">问题统计</span>
        <button
          className="text-[11px] text-zinc-300 group-hover:text-zinc-500 group-hover:translate-x-0.5 transition-all duration-200 leading-none"
          onClick={() => onDrill?.('agent')} tabIndex={-1} aria-hidden
        >↗</button>
      </div>

      {/* 多系列柱图：极淡基线承托 */}
      <div className="flex items-end justify-around gap-2 flex-1 border-b border-zinc-100/70">
        {PROB_MULTI.map((g, i) => (
          <div key={i} className="flex flex-col items-center gap-0.5 flex-1">
            {/* 三色柱并排 */}
            <div className="flex items-end gap-0.5">
              {([
                { v: g.high,   cls: MULTI_COLOR[0] },
                { v: g.medium, cls: MULTI_COLOR[1] },
                { v: g.low,    cls: MULTI_COLOR[2] },
              ]).map((b, j) => (
                <div key={j} className="flex flex-col items-center gap-0.5" style={{ minWidth: '10px' }}>
                  {b.v > 0 && (
                    <>
                      <span className="text-[11px] font-mono font-semibold text-zinc-700 leading-none tabular-nums">
                        {b.v}
                      </span>
                      <div
                        className={`rounded-t-sm ${b.cls} transition-all duration-300`}
                        style={{ width: '10px', height: `${Math.max(4, (b.v / max) * 28)}px` }}
                      />
                    </>
                  )}
                </div>
              ))}
            </div>
            {/* 组标签 */}
            <span className="text-[9px] text-zinc-400 text-center leading-tight whitespace-nowrap mt-0.5">
              {g.status}
            </span>
          </div>
        ))}
      </div>

      {/* 图例 */}
      <div className="flex items-center gap-2.5 pt-2 text-[9px] text-zinc-400 flex-shrink-0">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-red-500" />high
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-slate-400" />medium
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-sm bg-slate-300" />low
        </span>
      </div>
    </div>
  );
}

/* 带5·A: DOA 统计 — 单图表 + 维度切换（按机房 / 按状态）*/
function DOAMergedSection({ onDrill }) {
  const [dim, setDim] = useState<'room' | 'status'>('room');
  const bars = dim === 'room' ? DOA_TOTAL_BARS : DOA_BARS;
  const maxQty = Math.max(...bars.map(b => b.qty), 1);

  return (
    <div className={`group bg-white rounded-2xl ${COCKPIT_SHADOW} flex flex-col overflow-hidden min-h-[160px] p-5 transition-shadow duration-200 hover:shadow-[0_8px_20px_rgba(24,24,27,0.08)]`}>

      {/* 标题栏 */}
      <div className="cp-hd flex items-center justify-between pb-4 mb-4 border-b border-zinc-100/50 flex-shrink-0">
        <div
          className="flex items-center gap-2 cursor-pointer"
          onClick={() => onDrill?.('doa')}
          title="查看 DOA 详情"
        >
          <span className="text-base font-semibold text-zinc-900">DOA 统计</span>
          <span className="text-[10px] font-mono bg-zinc-100 text-zinc-500 px-1.5 py-0.5 rounded border border-zinc-200 leading-none">425</span>
        </div>
        <div className="flex items-center gap-2">
          {/* 分段控制器 */}
          <div className="flex bg-zinc-100 p-1 rounded-md gap-0.5">
            {(['room', 'status'] as const).map(d => (
              <button
                key={d}
                onClick={() => setDim(d)}
                className={`px-2 py-0.5 rounded text-[10px] leading-none transition-all duration-150 ${
                  dim === d
                    ? 'bg-white shadow-sm text-zinc-900 font-medium'
                    : 'text-zinc-500 hover:text-zinc-700'
                }`}
              >
                {d === 'room' ? '按机房' : '按状态'}
              </button>
            ))}
          </div>
          <button
            className="text-[11px] text-zinc-300 group-hover:text-zinc-500 group-hover:translate-x-0.5 transition-all duration-200 leading-none"
            onClick={() => onDrill?.('doa')} tabIndex={-1} aria-hidden
          >↗</button>
        </div>
      </div>

      {/* 图表区：overflow-hidden 固定容器尺寸，切换维度不抖动；极淡基线承托 */}
      <div className="flex-1 overflow-hidden flex items-end gap-1 border-b border-zinc-100/70">
        {bars.map((b, i) => (
          <div key={i} className="flex flex-col items-center justify-end flex-1 min-w-0 gap-0.5">
            <span className="text-[14px] font-mono font-semibold text-zinc-800 leading-none tabular-nums mb-1">{b.qty}</span>
            <div
              className="w-full rounded-t-sm bg-slate-800 hover:bg-slate-900 transition-all duration-300"
              style={{ height: `${Math.max(4, (b.qty / maxQty) * 44)}px` }}
            />
            <span className="text-[9px] text-zinc-400 leading-tight truncate w-full text-center">{b.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* 带5·B/C: ITO 统计表（全 Tailwind 版，交付 / 当月复用）*/
function ITOTable({ title, subtitle, data, onDrill }) {
  const v = (x) => x != null ? x.toFixed(1) : '—';
  const HEADERS = ['项目', '短', '到货通道', '绑扎', '上电ZTP', '装机', '验收'];

  return (
    <div
      className={`group bg-white rounded-2xl ${COCKPIT_SHADOW} flex flex-col overflow-hidden min-h-[180px] cursor-pointer p-5 transition-all duration-200 hover:shadow-[0_8px_20px_rgba(24,24,27,0.08)]`}
      onClick={() => onDrill?.('workorder')}
    >

      {/* 标题栏 */}
      <div className="cp-hd flex items-center justify-between pb-4 mb-4 border-b border-zinc-100/50 flex-shrink-0">
        <span className="text-base font-semibold text-zinc-900">{title}</span>
        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 text-[11px] leading-none">→</span>
      </div>

      {/* 表格：仅表头底边 + 行底边，Data-Ink 留白对齐 */}
      <div className="overflow-hidden">
        <table className="w-full cockpit-data-table" style={{ fontSize: '10.5px', fontFamily: 'var(--font-mono)' }}>
          <thead>
            <tr className="border-b border-zinc-100/50 bg-zinc-50/80">
              {HEADERS.map((h, i) => (
                <th
                  key={h}
                  className={`py-1.5 px-1.5 text-[10.5px] font-medium text-zinc-500 whitespace-nowrap ${i === 0 ? 'text-left' : 'text-right'}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((r, i) => {
              const isSummary = i === 0;
              return (
                <tr key={i} className={`border-b border-zinc-100/50 last:border-b-0 ${isSummary ? '' : 'hover:bg-zinc-50/40'} transition-colors`}>
                  <td className={`py-1.5 px-1.5 text-left whitespace-nowrap ${isSummary ? 'font-medium text-zinc-700' : 'text-zinc-600'}`}>
                    {r.name}
                  </td>
                  {[r.pods, r.arrive, r.cable, r.bundle, r.mount, r.accept].map((val, j) => (
                    <td
                      key={j}
                      className={`py-1.5 px-1.5 text-right tabular-nums ${val == null ? 'text-zinc-300' : isSummary ? 'font-medium text-zinc-700' : 'text-zinc-600'}`}
                    >
                      {j === 0 ? val : v(val)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* 5.31 · 项目体检头条 + 异常聚合（P0）
 * 整体完成度 / 异常数全部用现有展示常量派生，零改 state / 业务逻辑。
 * 异常拆解可点击下钻：延期→dispatch · 超期→risk · 待处理→agent */
function ProjectHealthHeader({ onDrill }) {
  const totalDone = PROJECT_STAGES.reduce((s, x) => s + x.done, 0);
  const totalAll  = PROJECT_STAGES.reduce((s, x) => s + x.total, 0);
  const overallPct = totalAll > 0 ? Math.round((totalDone / totalAll) * 100) : 0;
  const delays  = DELAY_ITEMS.length;
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
  const view = searchParams.get('view');
  if (view === '底座' || view === 'foundation') {
    return <Navigate to="/twin" replace />;
  }

  const [drill, setDrill] = useState(null); // null | milestone | workorder | risk | agent | doa

  return (
    <>
    <div className="cockpit-page">
      <PlanProgressSection onDrill={setDrill} />
      <ProgressSummaryRow onDrill={setDrill} />

      <div className="grid grid-cols-3 gap-3">
        <WorkOrderMonthChart onDrill={setDrill} />
        <RiskStatsBarChart onDrill={setDrill} />
        <ProblemMultiBarChart onDrill={setDrill} />
      </div>

      <div className="grid grid-cols-[5fr_3.5fr_3.5fr] gap-3">
        <DOAMergedSection onDrill={setDrill} />
        <ITOTable title="交付ITO统计" subtitle="点击可查看全部机房" data={ITO_DELIVERY} onDrill={setDrill} />
        <ITOTable title="当月ITO统计" subtitle="点击可查看当月机房" data={ITO_MONTHLY} onDrill={setDrill} />
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
