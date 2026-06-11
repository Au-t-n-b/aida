/* AIDA · planinit.jsx — 方案2 组件移植（已模块化），导出 PlanInit */
import { CriticalPathTimeline } from "./critical-path-timeline";
import React from 'react';
import { ActivitiesGraph } from './activities-graph';
// 单一盘子数据源（站/货/人/批次/排期 共用）· 用户决策 2026-05-31
import { BATCH, BATCH_COLORS, GO_LIVE_BATCHES, READY_BATCHES, INITIAL_ROOMS, INITIAL_BATCHES, INITIAL_TEAMS, type PodRow, type RoomRow, type BatchRow, type TeamRow } from './data/plan';
import './plan-board.css';

declare global {
  interface Window {
    __aida?: {
      start: () => void;
      jump: (n: number) => void;
      end: () => void;
      play: () => void;
      total: number;
      layout?: (o: Partial<typeof DEFAULT_LAY>) => void;
    };
  }
}

const { useState, useEffect, useRef, useMemo, useCallback, Fragment } = React;

/* ===================== icons ===================== */
const I = {
  mark:()=>(<svg width="20" height="20" viewBox="0 0 28 28" fill="none">
    <path d="M5 24 L13 4 L15 4 L23 24" stroke="#fff" strokeWidth="1.7" strokeLinejoin="miter"/>
    <path d="M8 16.2 L20 16.2" stroke="#CE382F" strokeWidth="2.4"/></svg>),
  site:(s=16)=>(<svg width={s} height={s} viewBox="0 0 18 18" fill="none"><path d="M2 7 L9 3 L16 7 L16 15 L2 15 Z" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M2 15 L16 15" stroke="currentColor" strokeWidth="1.3"/><rect x="5" y="9" width="2" height="2" stroke="currentColor" strokeWidth=".9"/><rect x="8" y="9" width="2" height="2" stroke="currentColor" strokeWidth=".9"/><rect x="11" y="9" width="2" height="2" stroke="currentColor" strokeWidth=".9"/></svg>),
  goods:(s=16)=>(<svg width={s} height={s} viewBox="0 0 18 18" fill="none"><path d="M2.5 5 L9 2 L15.5 5 L15.5 13 L9 16 L2.5 13 Z" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M2.5 5 L9 8 L15.5 5 M9 8 L9 16" stroke="currentColor" strokeWidth="1.3"/></svg>),
  people:(s=16)=>(<svg width={s} height={s} viewBox="0 0 18 18" fill="none"><circle cx="6" cy="6" r="2" stroke="currentColor" strokeWidth="1.3"/><circle cx="12.5" cy="6.5" r="1.7" stroke="currentColor" strokeWidth="1.3"/><path d="M2 14 C2 11.2 3.8 10 6 10 C8.2 10 10 11.2 10 14" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M10 14 C10.4 12 12 11 12.5 11 C14.5 11 16 12.2 16 14" stroke="currentColor" strokeWidth="1.3" fill="none"/></svg>),
  cal:(s=16)=>(<svg width={s} height={s} viewBox="0 0 18 18" fill="none"><rect x="2.5" y="3.5" width="13" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M2.5 7 L15.5 7 M6 2 L6 5 M12 2 L12 5" stroke="currentColor" strokeWidth="1.3"/></svg>),
  doc:(s=14)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M3 1 L8.5 1 L11.5 4 L11.5 13 L3 13 Z" stroke="currentColor" strokeWidth="1.1" fill="none"/><path d="M8.5 1 L8.5 4 L11.5 4" stroke="currentColor" strokeWidth="1.1"/></svg>),
  check:(s=13)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M2.5 7.5 L5.5 10.5 L11.5 3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  send:(s=13)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M1.5 12.5 L12.5 7 L1.5 1.5 L3 7 Z" fill="currentColor"/></svg>),
  attach:(s=15)=>(<svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M10.5 4.5 L5.5 9.5 C4.5 10.5 4.5 12 5.5 13 C6.5 14 8 14 9 13 L14 8" stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round"/></svg>),
  warn:(s=15)=>(<svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M8 1.5 L15 13.5 L1 13.5 Z" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinejoin="round"/><path d="M8 6 L8 9.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/><circle cx="8" cy="11.6" r=".8" fill="currentColor"/></svg>),
  spark:(s=13)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M7 1 L8.1 5.4 L12.5 6.5 L8.1 7.6 L7 12 L5.9 7.6 L1.5 6.5 L5.9 5.4 Z" fill="currentColor"/></svg>),
  play:(s=14)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M3.5 2.5 L11 7 L3.5 11.5 Z" fill="currentColor"/></svg>),
  pause:(s=14)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><rect x="3.5" y="2.5" width="2.6" height="9" fill="currentColor"/><rect x="7.9" y="2.5" width="2.6" height="9" fill="currentColor"/></svg>),
  replay:(s=15)=>(<svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M13 8 A5 5 0 1 1 11.5 4.4" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round"/><path d="M12 1.8 L12 4.6 L9.2 4.6" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  flow:(s=15)=>(<svg width={s} height={s} viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M8 2 L8 6.4 M8 9.6 L8 14 M2 8 L6.4 8 M9.6 8 L14 8" stroke="currentColor" strokeWidth="1.2"/></svg>),
  person:(s=12)=>(<svg width={s} height={s} viewBox="0 0 12 12" fill="none"><circle cx="6" cy="3.1" r="2" fill="currentColor"/><path d="M1.4 11 C1.4 7.7 3.4 6.3 6 6.3 C8.6 6.3 10.6 7.7 10.6 11 Z" fill="currentColor"/></svg>),
  cable:(s=13)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M3 4 H12 M3 7 H12 M3 10 H12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/><circle cx="3" cy="4" r="1.1" fill="currentColor"/><circle cx="3" cy="7" r="1.1" fill="currentColor"/><circle cx="3" cy="10" r="1.1" fill="currentColor"/></svg>),
  lock:(s=12)=>(<svg width={s} height={s} viewBox="0 0 12 12" fill="none"><rect x="2.4" y="5.4" width="7.2" height="5" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M3.9 5.4 V4 C3.9 2.85 4.85 2 6 2 C7.15 2 8.1 2.85 8.1 4 V5.4" stroke="currentColor" strokeWidth="1.2"/></svg>),
  truck:(s=14)=>(<svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M1.5 4 H9 V11 H1.5 Z M9 6 H12.5 L14.5 8.5 V11 H9 Z" stroke="currentColor" strokeWidth="1.2" fill="none"/><circle cx="4" cy="11.5" r="1.3" stroke="currentColor" strokeWidth="1.2"/><circle cx="11.5" cy="11.5" r="1.3" stroke="currentColor" strokeWidth="1.2"/></svg>),
  // 排期 · 多策略方案：3 条不等长甘特条剪影 · 跟 I.site / I.goods / I.people 同 stroke 风格
  schedule:(s=18)=>(<svg width={s} height={s} viewBox="0 0 18 18" fill="none"><rect x="2.2" y="3.2" width="11" height="2.6" rx=".6" stroke="currentColor" strokeWidth="1.3"/><rect x="4"   y="7.7" width="9"  height="2.6" rx=".6" stroke="currentColor" strokeWidth="1.3"/><rect x="3"   y="12.2" width="13" height="2.6" rx=".6" stroke="currentColor" strokeWidth="1.3"/></svg>),
  // ClawTodo/UploadModal 移植自源 C chrome.tsx 所需图标（chrome 用 Icon.Chevron/Icon.Cog，本 I 里缺，按现有 stroke 风格补）
  chevron:(s=11)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M3.5 5 L7 8.5 L10.5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  cog:(s=12)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="2.1" stroke="currentColor" strokeWidth="1.2"/><path d="M7 1.5 L7 3 M7 11 L7 12.5 M1.5 7 L3 7 M11 7 L12.5 7 M3.1 3.1 L4.2 4.2 M9.8 9.8 L10.9 10.9 M10.9 3.1 L9.8 4.2 M4.2 9.8 L3.1 10.9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>),
  swap:(s=13)=>(<svg width={s} height={s} viewBox="0 0 14 14" fill="none"><path d="M2.5 4.5 L10 4.5 M8 2.5 L10.5 4.5 L8 6.5 M11.5 9.5 L4 9.5 M6 7.5 L3.5 9.5 L6 11.5" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>),
};

/* ===================== mock 盘子数据 → data/plan.ts（单一数据源，2026-05-31）=====================
 * INITIAL_ROOMS / INITIAL_BATCHES / INITIAL_TEAMS / GO_LIVE_BATCHES / READY_BATCHES / BATCH(派生) / 类型 全在那里。
 * BATCH 现为派生：rooms/pods/teams/headcount/deadline 来自盘子，杜绝旧硬编码(12队/184人)漂移。
 */

// 项目孪生 · 排期方案信息分类（Claw「从项目孪生加载方案」展示，移植自源 C chrome.tsx）
const TWIN_ITEMS = ["客户需求信息", "设备配置信息", "软件配置信息", "组网配置信息", "机房信息", "服务交付界面", "责任矩阵信息", "验收策略"];

// 上线批 GO_LIVE_BATCHES / ready批 READY_BATCHES / 批次 INITIAL_BATCHES + BATCH_COLORS / 机房+PoD INITIAL_ROOMS
// 及类型 PodRow / RoomRow / BatchRow → 全部移至 data/plan.ts（单一数据源）
// Plate（批次分框）现在在 IsoYard 内用 useMemo 基于 rooms state 动态计算，
// 加机房 → plate y1 自动扩；空批 → 不渲染 plate。
type PlateRow = { name: string; cust: string; x0: number; y0: number; x1: number; y1: number; batchId: string; color: string };
function computePlates(rooms: RoomRow[]): PlateRow[] {
  const out: PlateRow[] = [];
  for (const b of GO_LIVE_BATCHES) {
    const batchRooms = rooms.filter(r => r.goLiveBatch === b.id);
    if (batchRooms.length === 0) continue;
    const gxs = batchRooms.map(r => r.gx);
    const gys = batchRooms.map(r => r.gy);
    out.push({
      name: "批次 " + (GO_LIVE_BATCHES.indexOf(b) + 1),
      cust: batchRooms.map(r => r.code).join("+") + " · 上线 " + b.goLiveDate,
      x0: Math.min(...gxs), y0: Math.min(...gys),
      x1: Math.max(...gxs), y1: Math.max(...gys),
      batchId: b.id,
      color: b.color,
    });
  }
  return out;
}
const DEFAULT_LAY = { cx:132, cy:104, rw:128, px:96, py:74, pad:7, pod:11, pgap:3, rx:55, rz:45 };
type Lay = typeof DEFAULT_LAY;
const LAY_CTRL: { k: keyof Lay; lab: string; min: number; max: number; step: number }[] = [
  { k:"cx", lab:"机房横距", min:90,  max:220, step:2 },
  { k:"cy", lab:"机房纵距", min:78,  max:200, step:2 },
  // 项目横距/纵距(px/py) 控件已去除：当前单项目，无多项目间距 · 用户决策 2026-05-31
  { k:"rw", lab:"机房宽度", min:96,  max:180, step:2 },
  { k:"pad",lab:"卡内边距", min:3,   max:16,  step:1 },
  { k:"pod",lab:"PoD 格",  min:7,   max:18,  step:1 },
  { k:"pgap",lab:"PoD 间隙",min:1,   max:8,   step:1 },
  { k:"rx", lab:"俯仰角°",  min:30,  max:70,  step:1 },
  { k:"rz", lab:"旋转角°",  min:20,  max:60,  step:1 },
];
// 机房状态 2 态 · #3 用户决策 2026-05-28（任一段 ready 时间填了→可进场；三段全空→不可进场）
// SITE_LABEL 仍接受 3 种 site 字段值以兼容老代码：ready/fitting → 可进场；pending → 不可进场
// 但渲染请优先用 deriveSite(r) 派生 2 态
const SITE_LABEL: Record<RoomRow["site"], string> = { ready:"可进场", fitting:"可进场", pending:"不可进场" };
function hasAnyReady(r: RoomRow): boolean { return !!(r.cableReadyAt || r.equipReadyAt || r.liquidReadyAt); }
function deriveSite(r: RoomRow): "ready"|"pending" { return hasAnyReady(r) ? "ready" : "pending"; }
// 机房状态文案：倒排页 ready 未知 → 「待定」；否则按可进场/不可进场 · 用户决策 2026-05-29
function siteText(r: RoomRow): string { return (r.readyUnknown && !hasAnyReady(r)) ? "待定" : SITE_LABEL[deriveSite(r)]; }
// 初始化（倒排）页机房数据：ready 时间整列未知（站货人共用骨架，仅此页机房置为「待定」）
const INITIAL_ROOMS_BARE: RoomRow[] = INITIAL_ROOMS.map(r => ({
  ...r, site: "pending", readyUnknown: true,
  cableReadyAt: undefined, equipReadyAt: undefined, liquidReadyAt: undefined,
  // 货到货时间同样未明（只有分批上线/上电是确定的）· 用户决策 2026-05-29
  pods: r.pods.map(p => ({ ...p, arrival: "unknown" as const, etaLabel: "待定", etaDate: undefined, status: "pending" as const })),
}));

// #RRGGBB → rgba(...)，给 plate 批次色淡底用
function hexAlpha(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 0xff, g = (n >> 8) & 0xff, b = n & 0xff;
  return `rgba(${r},${g},${b},${a})`;
}

const SKILLS = [
  { k:"布线", color:"#3551D1", teams:4, hc:68 },
  { k:"安装", color:"#1B9D6B", teams:3, hc:44 },
  { k:"调测", color:"#BC7E14", teams:3, hc:38 },
  { k:"改造", color:"#8B96AC", teams:2, hc:34 },
];
// 队伍类型 TeamRow + INITIAL_TEAMS（6 机房 → 6 队）→ data/plan.ts
const CAPS = ["布线","安装","调测"];   // 每队全能，对 PoD 做全流程
// TEAM_STAT 改为基于 teams state 动态计算（见 PeopleView 内 useMemo）
// 有效产能 = full 队总人数 + junior 队总人数 × 0.7
// 队伍逐个呈现节奏：每 2 个一组、组间停顿、组内微抖动 → 3 组对应 3 个上线批
const TEAM_DELAY = [0,70, 400,460, 820,880];

const DUR_MAX = 18; // 工期条满刻度（天）
type Act = {
  dim: string; name: string; bound: boolean; wIcon: "site" | "truck" | "goods" | "cable" | "flow";
  dur?: number; durLabel?: string; work?: string; workU?: string;
  ppl?: number; pplU?: string; base?: number; cut?: number; rate?: string; reason?: string;
};
const ACTS: Act[] = [
  { dim:"站", name:"机房改造与验收", bound:false, dur:10, durLabel:"10", wIcon:"site", reason:"客户施工窗口" },
  { dim:"货", name:"设备到货齐套", bound:false, dur:8, durLabel:"ETA", wIcon:"truck", reason:"物流到货 · 外部" },
  { dim:"人", name:"机柜上架安装", bound:true, work:"36", workU:"PoD", wIcon:"goods", ppl:6, pplU:"队", base:18, cut:12, rate:"2 PoD/队·天" },
  { dim:"人", name:"综合布线", bound:true, work:"4,800", workU:"根", wIcon:"cable", ppl:12, pplU:"人", base:10, cut:6, rate:"48 根/人·天" },
  { dim:"站", name:"上电点亮", bound:false, dur:4, durLabel:"4", wIcon:"site", reason:"配电窗口" },
  { dim:"人", name:"系统联调测试", bound:true, work:"36", workU:"PoD", wIcon:"goods", ppl:8, pplU:"工程师", base:14, cut:8, rate:"按 PoD 联调" },
  { dim:"—", name:"客户验收移交", bound:false, dur:2, durLabel:"2", wIcon:"flow", reason:"合同里程碑" },
];

// gantt: [label, baseStart, baseLen, planStart, planLen, bound]  单位=天, 轴=42天
type GanttRow = [string, number, number, number, number, boolean];
const GANTT_BASE: GanttRow[] = [
  ["改造验收",0,10,0,10,false],["到货齐套",6,8,6,8,false],["上架安装",14,18,14,18,true],
  ["综合布线",20,10,20,10,true],["上电点亮",30,4,30,4,false],["联调测试",30,14,30,14,true],["验收移交",40,2,40,2,false],
];
// 方案数据与盘子口径一致（12 PoD · 上线目标 09-20 · 6 队/66 人）· 每方案给 风险(中/高/低)+建议 · 用户决策 2026-06-01 晚2
type Plan = {
  id: string; name: string; rec: boolean; ds: string;
  kpi: [string, string, string?][];
  risks: { lv: string; t: string; d: string }[];
  advice: string; gantt: GanttRow[];
};
const PLANS: Plan[] = [
  { id:"even", name:"方案A · 均匀分配", rec:false,
    ds:"把需压缩的 10 天平均摊到 3 个受人数约束的活动上，各加少量人力。",
    kpi:[["12","PoD"],["32","总工期/天"],["-10","压缩/天","cut"],["+24","新增/人","add"]],
    risks:[
      { lv:"中", t:"协调面广 · 三处并行", d:"三个活动同时加人，班组协调与现场管理成本高。" },
      { lv:"低", t:"单点压力小", d:"人力分散投放，单一活动资源与依赖风险低。" },
    ],
    advice:"人力充裕、求稳时选用；先对齐三处班组排班再开工。",
    gantt:[["改造验收",0,10,0,10,false],["到货齐套",6,8,6,8,false],["上架安装",14,18,13,14,true],["综合布线",18,10,16,7,true],["上电点亮",28,4,26,4,false],["联调测试",28,14,26,9,true],["验收移交",40,2,30,2,false]] },
  { id:"single", name:"方案B · TopK极限压缩", rec:true,
    ds:"按可压缩空间 (SLA−极限工期) 排序，集中压缩联调与上架两个最大空间活动。",
    kpi:[["12","PoD"],["32","总工期/天"],["-10","压缩/天","cut"],["+16","新增/人","add"]],
    risks:[
      { lv:"中", t:"集中依赖 · 联调/上架", d:"资源集中投联调与上架，对批次3到货准时与班组稳定性要求高。" },
      { lv:"低", t:"增员可控", d:"增员最少、单位效率最高。" },
    ],
    advice:"到货可控时首选，增员最少、达成 09-20 概率最高。",
    gantt:[["改造验收",0,10,0,10,false],["到货齐套",6,8,6,8,false],["上架安装",14,18,14,12,true],["综合布线",20,10,18,9,true],["上电点亮",30,4,27,4,false],["联调测试",30,14,27,8,true],["验收移交",40,2,30,2,false]] },
  { id:"pull", name:"方案C · 货期提拉", rec:false,
    ds:"对到货未明 / 在途较晚的 7 个 PoD 提前催货（含空运），整体左移、仅少量加人。",
    kpi:[["12","PoD"],["32","总工期/天"],["-10","压缩/天","cut"],["+8","新增/人","add"]],
    risks:[
      { lv:"高", t:"外部依赖 · 供应商/空运", d:"依赖供应商配合催货与空运成本，需客户侧确认承诺。" },
      { lv:"低", t:"增员最少", d:"靠提前到货为后段腾窗口，仅少量加人。" },
    ],
    advice:"供应商可配合、预算允许空运时选用；先锁定催货承诺再启动。",
    gantt:[["改造验收",0,10,0,10,false],["到货齐套",3,7,3,7,false],["上架安装",11,18,11,15,true],["综合布线",18,10,17,9,true],["上电点亮",27,4,26,4,false],["联调测试",27,14,26,9,true],["验收移交",40,2,30,2,false]] },
];


/* ===================== 项目时间范围 & PoD 状态推演 · #10 ===================== */
const PROJECT_START = "2026-05-28";  // 轴原点 / 已到货纪元（"可上架"→此日）；非进度"今天"，见 SCHED_NOW
const PROJECT_END   = "2026-09-30";  // mock：项目终点（最后一批上线 + 缓冲）
// 演示进度基准「今天」· 用户决策 2026-06-01：用于货步 PoD 按到货进展着色（早到的转绿）。
// 独立于 PROJECT_START（后者兼轴原点/纪元，动它会把"可上架"货物日期塌错）。注：用户反馈暂不在排期图/看板标注"今天"，故仅货步用。
const SCHED_NOW = "2026-08-01";

// "在途 06-18" → "2026-06-18"；"可上架"（已到货）→ PROJECT_START；"待定" → null
function parseEtaToDate(etaLabel: string): string | null {
  const m = etaLabel.match(/(\d{1,2})-(\d{1,2})/);
  if (m) return `2026-${m[1]!.padStart(2,"0")}-${m[2]!.padStart(2,"0")}`;
  if (etaLabel === "可上架") return PROJECT_START;
  return null;
}

// PoD 三态：未开始 / 进行中 / 完成，由"上线日 - 到货日 - 指针"三者决定
function podStatusAt(pod: { goLiveBatch: string; etaLabel: string }, pointerDate: string): "pending" | "in_progress" | "done" {
  const batch = GO_LIVE_BATCHES.find(b => b.id === pod.goLiveBatch);
  if (!batch) return "pending";
  if (pointerDate >= batch.goLiveDate) return "done";
  const arrival = parseEtaToDate(pod.etaLabel);
  if (arrival && pointerDate >= arrival) return "in_progress";
  return "pending";
}

// 把 ISO 日期字符串和总天数互转，用于指针滑块
function dateToDays(date: string, start = PROJECT_START){
  return Math.round((new Date(date).getTime() - new Date(start).getTime()) / 86400000);
}
function daysToDate(days: number, start = PROJECT_START){
  const d = new Date(new Date(start).getTime() + days * 86400000);
  return d.toISOString().slice(0,10);
}

/* ===================== timeline ===================== */
// clock 0..TOTAL，setTimeout 推进；阶段边界决定 step 三态与各视觉揭示
const STEPS = [
  { n:1, key:"site",   lbl:"站 · 机房就绪", en:"SITE",     start:1,  end:5,  icon: I.site },
  { n:2, key:"goods",  lbl:"货 · PoD 到货", en:"GOODS",    start:6,  end:10, icon: I.goods },
  { n:3, key:"people", lbl:"人 · 队伍与活动", en:"PEOPLE",  start:11, end:15, icon: I.people },
  { n:4, key:"plan",   lbl:"排期 · 多策略方案", en:"SCHEDULE",start:16, end:21, icon: I.schedule },
];
const TOTAL = 21;
const clamp=(v: number, a: number, b: number)=>Math.max(a,Math.min(b,v));
const stepStatus=(n: number, clk: number)=>{ const s=STEPS[n-1]!; if(clk<s.start) return "pending"; if(clk<=s.end) return "active"; return "done"; };

/* ===================== Claw rail ===================== */
// 「计划调整」自适应卡（init/adjust 共用，置顶于 Claw 线程上方）· 移植自源 C chrome.tsx · 用户决策 2026-05-31
// 漏斗入口：①上传变更表(onUpload→UploadModal→aida:plan-ingest 回灌) / ②点缺口行(aida:plan-goto 跳步) / ③面板批量调整(aida:plan-open-panel)
// 三入口都 → 累计变更 → 主区跨步飘红条确认 → Agent 推演
function ClawTodo({ state, onUpload }: { state: { site: number; goods: number; people: number; changes: number; mode: string } | null; onUpload?: () => void }) {
  const [open, setOpen] = useState(true);
  const raw = [
    { k: "site",   step: 1, dim: "站", n: state ? state.site : 0,   label: "机房 ready 待确认" },
    { k: "goods",  step: 2, dim: "货", n: state ? state.goods : 0,  label: "PoD 到货待补 ETA" },
    { k: "people", step: 3, dim: "人", n: state ? state.people : 0, label: "支队伍待分配" },
  ];
  const items = raw.filter(it => it.n > 0);
  if (items.length === 0) return null;
  const goTo = (step: number) => window.dispatchEvent(new CustomEvent('aida:plan-goto', { detail: { step } }));
  const openPanel = () => window.dispatchEvent(new Event('aida:plan-open-panel'));
  // 确认重排已收敛为主区跨步飘红条（.resched-banner）· 本卡只做漏斗入口（缺口跳转 + 面板批量调整）· 用户决策 2026-05-31
  const hint = "点某项跳到对应步就地改，或开「面板批量调整」集中改 站 / 货 / 人";
  return (
    <div className={`claw-todo ${open ? 'open' : ''}`}>
      <button className="ct-head" onClick={() => setOpen(o => !o)}>
        <span className="ct-spark">{I.spark(12)}</span>
        <span className="ct-title">计划调整</span>
        <span className="ct-count">{items.length}</span>
        <span className="ct-caret">{I.chevron(11)}</span>
      </button>
      {open && (
        <div className="ct-body">
          <div className="ct-hint">{hint}</div>
          {items.map((it) => (
            <div className={`ct-item d-${it.k}`} key={it.k} onClick={() => goTo(it.step)} title={`去「${it.dim}」步就地修改`}>
              <span className="ct-dim">{it.dim}</span>
              <span className="ct-n">{it.n}</span>
              <span className="ct-label">{it.label}</span>
              <span className="ct-act">调整 →</span>
            </div>
          ))}
          <div className="ct-entries">
            <button className="ct-entry" onClick={onUpload}>{I.attach(11)} 上传变更表</button>
            <button className="ct-entry" onClick={openPanel}>{I.cog(11)} 面板批量调整</button>
          </div>
        </div>
      )}
    </div>
  );
}

// 附文档上传弹窗（演示态）：拖拽/选择文件 → 列出 → 「解析并加入」把文件加进 Claw 资料清单 · 移植自源 C chrome.tsx
// 仅读取文件名/大小（metadata），不解析内容，无 prompt-injection 风险
function UploadModal({ onClose, onParse }: { onClose: () => void; onParse: (files: string[][]) => void }) {
  const [files, setFiles] = useState<{ name: string; size: string }[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const fmtSize = (n: number) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB");
  const addFiles = (list: FileList | null) => {
    if (!list || !list.length) return;
    setFiles(prev => [...prev, ...Array.from(list).map(f => ({ name: f.name, size: fmtSize(f.size) }))]);
  };
  const parse = () => { if (!files.length) return; const names = files.map(f => f.name); onParse(files.map(f => [f.name, f.size])); window.dispatchEvent(new CustomEvent('aida:plan-ingest', { detail: { names } })); onClose(); };
  return (
    <div className="up-mask" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="up-modal" role="dialog" aria-modal="true">
        <div className="up-head">
          <span className="up-title">{I.attach(14)} 上传交付资料</span>
          <button className="up-close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className={"up-drop" + (dragOver ? " over" : "")}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
          onClick={() => inputRef.current?.click()}>
          {I.doc(22)}
          <div className="up-drop-main">拖拽文件到此，或 <span className="up-link">点击选择</span></div>
          <div className="up-drop-sub">合同 / HLD / BOQ / 到货表 / 排班表 · PDF · Word · Excel</div>
          <input ref={inputRef} type="file" multiple hidden
            onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
        </div>
        {files.length > 0 && (
          <div className="up-list">
            {files.map((f, i) => (
              <div className="up-item" key={i}>
                {I.doc(12)}
                <span className="up-name">{f.name}</span>
                <span className="up-size">{f.size}</span>
                <button className="up-del" onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))} aria-label="移除">×</button>
              </div>
            ))}
          </div>
        )}
        <div className="up-foot">
          <div className="up-actions">
            <button className="up-btn" onClick={onClose}>取消</button>
            <button className="up-btn pri" disabled={!files.length} onClick={parse}>{I.spark(11)} 解析并加入</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// 「计划调整」卡的实时状态（监听 PlanBoard 派发的 aida:plan-state：缺口 + 待推演变更数 + 模式；ready=clk 到末才出卡）
type PlanState = { ready: boolean; site: number; goods: number; people: number; changes: number; mode: string };
function ScheduleClawRail({ width, side, onResize, onSwap }: { width: number; side: 'left' | 'right'; onResize: (w: number) => void; onSwap: () => void }){
  const [sent, setSent] = useState(false);
  const onSend = () => { if (sent) return; setSent(true); window.dispatchEvent(new CustomEvent('aida:claw-send')); };
  // 拖拽调整 claw 宽度（手柄在朝主区那侧的边缘；左/右互换时拖动方向相反）
  const onResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX, startW = width, MIN = 280, MAX = 560;
    const onMove = (ev: MouseEvent) => { const delta = side === 'left' ? ev.clientX - startX : startX - ev.clientX; onResize(Math.max(MIN, Math.min(MAX, startW + delta))); };
    const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); document.body.style.userSelect = ''; document.body.style.cursor = ''; };
    document.body.style.userSelect = 'none'; document.body.style.cursor = 'col-resize';
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp);
  };
  // 「计划调整」卡实时状态 + 上传弹窗（移植自源 C chrome.tsx 的 ClawRail）
  const [planState, setPlanState] = useState<PlanState | null>(null);
  useEffect(() => { const h = (e: Event) => { const d = (e as CustomEvent<PlanState>).detail; if (d) setPlanState(d); }; window.addEventListener('aida:plan-state', h); return () => window.removeEventListener('aida:plan-state', h); }, []);
  const [uploadOpen, setUploadOpen] = useState(false);
  // 从项目孪生加载方案（8 类信息）：点按钮 → 逐条加载动画 → 完成（移植自源 C chrome.tsx）
  const [twinPhase, setTwinPhase] = useState<'idle' | 'loading' | 'done'>('idle');
  const [twinN, setTwinN] = useState(0);
  useEffect(() => {
    if (twinPhase !== 'loading') return;
    if (twinN >= TWIN_ITEMS.length) { const t = setTimeout(() => setTwinPhase('done'), 280); return () => clearTimeout(t); }
    const t = setTimeout(() => setTwinN(n => n + 1), 240);
    return () => clearTimeout(t);
  }, [twinPhase, twinN]);
  const startTwinLoad = () => { setTwinN(0); setTwinPhase('loading'); };
  return (
    <>
    <aside className="claw-rail" style={{ flexBasis: width, width }}>
      <div className="claw-resize" onMouseDown={onResizeStart} title="拖拽调整宽度" />
      <button className="claw-swap" onClick={onSwap} title="左右互换 Claw 与主区" aria-label="左右互换 Claw 与主区">{I.swap(13)}</button>
      <div className="cr-head">
        <div className="cr-brand">
          <div className="cr-mark">{I.mark()}</div>
          <div><div className="nm">AIDA-排期助手</div><div className="sub">{twinPhase === 'done' ? '孪生方案已加载 · 待发送开始排期' : '排期初始化 · 从项目孪生加载方案'}</div></div>
        </div>
        <div className="cr-scope">{I.flow(13)}<span>交付盘子 · <b>{BATCH.group}</b></span></div>
      </div>
      <div className="cr-body">
        {planState?.ready && <ClawTodo state={planState} onUpload={() => setUploadOpen(true)} />}
        <div className="twin-card">
          <div className="twin-meta">
            <span className="twin-cap-ic">{I.spark(12)}</span>
            <span className="twin-info-t">AIDA · 孪生数据加载</span>
            {twinPhase !== 'idle' && <span className={"twin-prog" + (twinPhase === 'done' ? ' done' : '')}>{twinPhase === 'done' ? TWIN_ITEMS.length : twinN}/{TWIN_ITEMS.length}</span>}
          </div>
          <div className="twin-body">
            {twinPhase === 'idle' ? (
              <button className="twin-load-btn" onClick={startTwinLoad}>{I.spark(12)} 从项目孪生加载方案</button>
            ) : (
              <div className="twin-grid">
                {TWIN_ITEMS.map((it, i) => {
                  const st = (twinPhase === 'done' || i < twinN) ? 'done' : (i === twinN ? 'loading' : 'wait');
                  return (
                    <div className={`twin-item ${st}`} key={i}>
                      <span className="twin-no">{i + 1}</span>
                      <span className="twin-name">{it}</span>
                      <span className="twin-st">{st === 'done' ? <span className="twin-ok">✓</span> : st === 'loading' ? <i className="twin-spin" /> : <span className="twin-dot" />}</span>
                    </div>
                  );
                })}
              </div>
            )}
            {twinPhase === 'done' && <div className="twin-done">{I.spark(10)} 已加载 8 类方案信息 · 点下方「发送」开始排期</div>}
          </div>
        </div>
        {sent && (<>
          <div className="msg fade"><div className="who">PD · 你</div>
            <div className="bubble me">开始排期初始化，先理解人货站。</div></div>
          <div className="msg fade"><div className="who">Claw</div>
            <div className="bubble ai">已接收 5 份资料，识别 <span className="num hi">{BATCH.rooms}</span> 机房 / <span className="num hi">{BATCH.pods}</span> PoD / <span className="num hi">{BATCH.teams}</span> 队伍 · <span className="num hi">{BATCH.headcount}</span> 人。正在按 <b>站 → 货 → 人</b> 解析，并构建初排方案…</div></div>
        </>)}
      </div>
      <div className="cr-foot">
        <div className="composer">
          <textarea placeholder="向 Claw 追问，或补充约束条件…" defaultValue=""></textarea>
          <div className="comp-row">
            <div className="comp-tools"><span className="t">{I.attach()}</span></div>
            <button className="send-btn" onClick={onSend} disabled={sent}>
              {I.send()} {sent? "解析中…" : "发送 · 开始初排"}</button>
          </div>
        </div>
      </div>
    </aside>
    {uploadOpen && <UploadModal onClose={() => setUploadOpen(false)} onParse={() => {}} />}
    </>
  );
}

/* ===================== stepper ===================== */
// 每个 step 的"待补项数"——从 rooms state 实时推导（#3 / #1 起改成接收 rooms 参数）
function stepPending(n: number, clk: number, rooms: RoomRow[]){
  if (n === 1) return rooms.filter(r=>r.site!=="ready").length;           // 站：非可进场的机房
  if (n === 2) {                                                          // 货：到货未明的 PoD
    let c = 0; rooms.forEach(r=>r.pods.forEach(p=>{ if(p.arrival==="unknown") c++; })); return c;
  }
  if (n === 3) return 0;                                                  // 人：mock 默认完整
  if (n === 4) return clk < STEPS[3]!.end ? 1 : 0;                         // 排期：未推完 = 1 件待生成
  return 0;
}
function Stepper({ clk, view, onPick, rooms, isAdjust }: { clk: number; view: number; onPick: (n: number)=>void; rooms: RoomRow[]; isAdjust?: boolean }){
  return (
    <div className="stepper">
      {STEPS.map((s,i)=>{
        const st = stepStatus(s.n, clk);
        const cls = "step "+(st==="active"?"active ":st==="done"?"done ":"")+(view===s.n?"sel":"");
        const pCount = stepPending(s.n, clk, rooms);
        const showBadge = pCount > 0 && st !== "done";
        return (
          <Fragment key={s.n}>
            <div className={cls} onClick={()=>onPick(s.n)} title={st==="done"?"已完成 · 点击可重新编辑":"点击切换 / 进入编辑"}>
              <div className="step-ind">
                {st==="done"? I.check(20) : s.icon(20)}
                {st==="active" && <div className="a-ring"/>}
                {showBadge && <span className="step-badge" aria-label={pCount+" 项待补"}>{pCount}</span>}
                {st==="done" && <span className="step-redo" aria-label="可重新编辑">✎</span>}
              </div>
              <div className="lbl">{(s.key==="plan" && !isAdjust) ? "排期 · 到货 / 机房就位" : s.lbl}</div>
              {/* .en 英文描述 SITE/GOODS/... 已去除 · 用户决策 2026-05-28 */}
              {showBadge && <div className="step-hint">{pCount} 项待补</div>}
              {st==="done" && <div className="step-hint done">可重新编辑</div>}
            </div>
            {i<STEPS.length-1 && <div className={"step-line "+(stepStatus(s.n,clk)==="done"?"fill":"")}/>}
          </Fragment>
        );
      })}
    </div>
  );
}

/* ===================== TimeAxis · 滑动窗口（双点区间）· #10 ===================== */
// 区间内（PoD 所属上线批的 goLiveDate ∈ [start, end]）→ 高亮
// 区间外 → 淡化
function TimeAxis({ pointerStart, pointerEnd, setPointerStart, setPointerEnd, rooms }: {
  pointerStart: string; pointerEnd: string;
  setPointerStart: (d: string)=>void; setPointerEnd: (d: string)=>void;
  rooms: RoomRow[];
}){
  const totalDays = dateToDays(PROJECT_END);
  const pct = (d: string) => (dateToDays(d) / totalDays) * 100;
  const sPct = pct(pointerStart), ePct = pct(pointerEnd);

  // 红旗节点：3 个 ready 日（次要）+ 3 个上线日（核心）
  const milestones = useMemo(() => {
    const list: { date: string; label: string; sub: string; color: string; type: "ready"|"go-live" }[] = [];
    READY_BATCHES.forEach(b => list.push({
      date: b.readyDate, label: `${b.rooms.join("+")} ready`, sub: "机房就绪",
      color: b.color, type: "ready",
    }));
    GO_LIVE_BATCHES.forEach((b,i) => list.push({
      date: b.goLiveDate, label: `批次 ${i+1} 上线`, sub: `${b.rooms.length*2} PoD`,
      color: b.color, type: "go-live",
    }));
    list.sort((a,b) => a.date.localeCompare(b.date));
    return list;
  }, []);

  // 区间内统计：goLiveDate ∈ [start, end] 的 PoD 数 + 关联机房数 + 涉及批次
  const stat = useMemo(() => {
    let inPods = 0, outPods = 0;
    const inBatches = new Set<string>();
    const inRooms = new Set<string>();
    rooms.forEach(r => {
      const goBatch = GO_LIVE_BATCHES.find(b => b.id === r.goLiveBatch);
      if (!goBatch) return;
      const inR = goBatch.goLiveDate >= pointerStart && goBatch.goLiveDate <= pointerEnd;
      if (inR) { inRooms.add(r.code); inBatches.add(goBatch.id); }
      r.pods.forEach(p => {
        if (inR) inPods++; else outPods++;
      });
    });
    return { inPods, outPods, inBatches: inBatches.size, inRooms: inRooms.size };
  }, [pointerStart, pointerEnd, rooms]);

  const days = (d: string) => dateToDays(d);
  // 滑块约束：start 不能 >= end；保持至少 1 天间隔
  const onStartChange = (n: number) => {
    const d = daysToDate(Math.max(0, Math.min(n, days(pointerEnd) - 1)));
    setPointerStart(d);
  };
  const onEndChange = (n: number) => {
    const d = daysToDate(Math.max(days(pointerStart) + 1, Math.min(totalDays, n)));
    setPointerEnd(d);
  };

  return (
    <div className="time-axis">
      <div className="ta-head">
        <span className="ta-title">⏱ 时间窗口 · 拖动两端看区间内完成情况</span>
        <span className="ta-cursor">
          📅 <b>{pointerStart}</b> → <b>{pointerEnd}</b>
          <span className="ta-cursor-sem">· {days(pointerEnd) - days(pointerStart)} 天</span>
        </span>
        <span className="ta-stat">
          区间内完成 <b className="hi">{stat.inPods}</b> PoD ·
          <span className="muted">{stat.inRooms} 机房 / {stat.inBatches} 批次</span> ·
          区间外 <b>{stat.outPods}</b>
        </span>
        <div className="ta-ctrl">
          <button onClick={() => { setPointerStart(PROJECT_START); setPointerEnd(PROJECT_END); }} title="全区间">全部</button>
          <button onClick={() => { setPointerStart(PROJECT_START); setPointerEnd(GO_LIVE_BATCHES[0]!.goLiveDate); }} title="截至首批上线">至首批</button>
        </div>
      </div>
      <div className="ta-track">
        {/* 默认底条 */}
        <div className="ta-base-rail"/>
        {/* 区间高亮带 */}
        <div className="ta-range" style={{left: sPct + "%", width: (ePct - sPct) + "%"}}/>
        {/* milestone 红旗 */}
        {milestones.map((m, i) => {
          const inR = m.date >= pointerStart && m.date <= pointerEnd;
          return (
            <button key={i} className={"ta-flag "+m.type+(inR?" in-range":"")}
              style={{left: pct(m.date)+"%", borderColor: m.color}}
              onClick={(e) => {
                // 点红旗：根据修饰键决定调左还是调右端
                if (e.shiftKey) onEndChange(dateToDays(m.date));
                else onStartChange(dateToDays(m.date));
              }}
              title={m.label+" · "+m.date+"（点击设区间起点；Shift+点设终点）"}>
              <span className="ta-flag-stick" style={{background: m.color}}/>
              <span className="ta-flag-card" style={{borderColor: m.color, background: inR ? m.color : "var(--surface)", color: inR ? "var(--on-brand)" : m.color}}>
                <span className="ta-flag-emoji">{m.type==="go-live"?"🚀":"🏗"}</span>
                <span className="ta-flag-text">
                  <span className="ta-flag-label">{m.label}</span>
                  <span className="ta-flag-date">{m.date.slice(5)} · {m.sub}</span>
                </span>
              </span>
            </button>
          );
        })}
        {/* 左滑块：起点 */}
        <input type="range" className="ta-pointer ta-pointer-start" min={0} max={totalDays}
          value={days(pointerStart)} onChange={e => onStartChange(+e.target.value)}
          title={"区间起点 "+pointerStart}/>
        {/* 右滑块：终点 */}
        <input type="range" className="ta-pointer ta-pointer-end" min={0} max={totalDays}
          value={days(pointerEnd)} onChange={e => onEndChange(+e.target.value)}
          title={"区间终点 "+pointerEnd}/>
      </div>
      <div className="ta-axis-lbl">
        <span>{PROJECT_START}</span>
        <span>{PROJECT_END}</span>
      </div>
    </div>
  );
}

/* ===================== iso yard (站 + 货) ===================== */
function LayoutPanel({ lay, setLay, open, onToggle }: {
  lay: Lay; setLay: React.Dispatch<React.SetStateAction<Lay>>; open: boolean; onToggle: () => void;
}){
  const stop=(e: React.SyntheticEvent)=>e.stopPropagation();
  return (
    <div className="lay-panel" onMouseDown={stop} onWheel={stop} onClick={stop}>
      <button className="lay-gear" onClick={onToggle}>⚙ 布局参数</button>
      {open && <div className="lay-body">
        <div className="lay-h">布局参数 · 实时拖动调整</div>
        {LAY_CTRL.map(c=>(
          <label className="lay-row" key={c.k}>
            <span className="ll">{c.lab}</span>
            <input type="range" min={c.min} max={c.max} step={c.step} value={lay[c.k]}
              onChange={e=>setLay(v=>({...v,[c.k]:+e.target.value}))}/>
            <span className="lv">{lay[c.k]}</span>
          </label>
        ))}
        <div className="lay-foot">
          <button onClick={()=>setLay(DEFAULT_LAY)}>复位默认</button>
          <button onClick={()=>{ navigator.clipboard&&navigator.clipboard.writeText(JSON.stringify(lay)); }}>复制参数</button>
        </div>
      </div>}
    </div>
  );
}
// 3D ↔ 2D 视图切换：复用 lay.rx/lay.rz，3D=(55,45) 2D=(0,0)，配合 CSS transition 做相机转角动画
function ViewModeToggle({ mode, onPick }: { mode: "3d" | "2d"; onPick: (m: "3d" | "2d") => void }){
  const stop=(e: React.SyntheticEvent)=>e.stopPropagation();
  return (
    <div className="view-toggle" onMouseDown={stop} onClick={stop} title="3D 等距 / 2D 平铺切换">
      <button className={mode==="3d"?"on":""} onClick={()=>onPick("3d")}>3D</button>
      <button className={mode==="2d"?"on":""} onClick={()=>onPick("2d")}>2D</button>
    </div>
  );
}
/* #1 零状态引导：rooms 为空时盖在 stage 中央，引导用户从添加第一个机房开始 */
function ZeroStateOverlay({ onAddBatch }: { onAddBatch: (batchId: string) => void }){
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();
  return (
    <div className="zero-state" onMouseDown={stop} onClick={stop} onWheel={stop}>
      <div className="zs-banner">
        <div className="zs-step zs-active"><span className="zs-num">1</span><span>站 · 添加机房</span></div>
        <span className="zs-arrow">→</span>
        <div className="zs-step"><span className="zs-num">2</span><span>货 · 补 PoD 到货</span></div>
        <span className="zs-arrow">→</span>
        <div className="zs-step"><span className="zs-num">3</span><span>人 · 配队伍</span></div>
        <span className="zs-arrow">→</span>
        <div className="zs-step"><span className="zs-num">4</span><span>排期 · 生成</span></div>
      </div>
      <div className="zs-card">
        <div className="zs-title">从添加第一个机房开始</div>
        <div className="zs-desc">选所属上线批，PoD 默认 2 个待补充</div>
        <div className="zs-batches">
          {GO_LIVE_BATCHES.map((b,i) => (
            <button key={b.id} className="zs-batch-btn" style={{borderColor: b.color}}
              onClick={() => onAddBatch(b.id)}>
              <i style={{background: b.color}}/>
              <span className="zs-bb-lab">+ 机房 · 批次 {i+1}</span>
              <span className="zs-bb-meta">上线 {b.goLiveDate.slice(5)}</span>
            </button>
          ))}
        </div>
        <div className="zs-hint">或点顶部 <b>+ 加机房</b> 按钮</div>
      </div>
    </div>
  );
}

/* #1 添加机房：按钮 + popover · 选所属上线批后追加新机房（带 2 个 unknown PoD） */
function AddRoomBtn({ rooms, onAdd }: { rooms: RoomRow[]; onAdd: (batchId: string) => void }){
  const [open, setOpen] = useState(false);
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();
  return (
    <div className="add-room-wrap" onMouseDown={stop} onClick={stop}>
      <button className="add-room-btn" onClick={() => setOpen(o => !o)} title="添加新机房">+ 加机房</button>
      {open && (
        <div className="add-room-pop">
          <div className="pop-h">
            <span>新机房归属哪批上线</span>
            <button className="pop-close" onClick={() => setOpen(false)}>×</button>
          </div>
          <div className="pop-batches">
            {GO_LIVE_BATCHES.map((b,i) => {
              const cnt = rooms.filter(r => r.goLiveBatch === b.id).length;
              return (
                <button key={b.id} className="batch-pick" style={{borderColor: b.color}}
                  onClick={() => { onAdd(b.id); setOpen(false); }}>
                  <i style={{background: b.color}}/>
                  <span className="bp-lab">批次 {i+1}</span>
                  <span className="bp-meta">{cnt} 机房 · 上线 {b.goLiveDate.slice(5)}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
function Room({ r, idx, total, clk, step, picked, faint, onPick, onDrill, cx, cy, px, py, pointerStart, pointerEnd, onRemove, onUpdatePod, onUpdateRoom }: {
  r: RoomRow; idx: number; total: number; clk: number; step: number; picked: boolean; faint: boolean;
  onPick: (c: string)=>void; onDrill: (c: string)=>void;
  cx: number; cy: number; px: number; py: number;
  pointerStart: string; pointerEnd: string;
  onRemove: (code: string)=>void;
  onUpdatePod: (roomCode: string, podId: string, patch: Partial<PodRow>)=>void;
  onUpdateRoom: (roomCode: string, patch: Partial<RoomRow>)=>void;
}){
  const revealed = clk>=5 ? total : clamp(clk*3,0,total);
  const inView = idx < revealed;
  const placed = clk>=6;            // PoD 落位
  // PoD 三态色 · 用户决策 2026-06-01：演示「今天」(SCHED_NOW=8/1) 后重新启用，货步按进度推演着色（见下 pods.map）
  const goBatch = GO_LIVE_BATCHES.find(b => b.id === r.goLiveBatch);
  const inRange = goBatch ? (goBatch.goLiveDate >= pointerStart && goBatch.goLiveDate <= pointerEnd) : true;
  // ready 时间编辑 + PoD 编辑均已迁出到右侧 .detail 面板内联 · 用户决策 2026-05-28
  // Room 卡内只保留 rstat 文字 + PoD 形态，点 rstat / pod-btn 都触发 onPick 选中机房
  const ds = deriveSite(r);
  return (
    <div className={"room "+(inView?"in ":"")+(picked?"picked ":"")+(faint?"faint ":"")+(inRange?"":"out-of-range")}
      style={{left:(r.gx<3?r.gx*cx:r.gx*cx-cx+px), top:(r.gy<3?r.gy*cy:r.gy*cy-cy+py), transitionDelay:(idx*45)+"ms"}}
      onClick={(e)=>{e.stopPropagation(); onPick(r.code);}}>
      <button className="drill-btn" title="下钻查看 PoD" onClick={(e)=>{e.stopPropagation(); onDrill(r.code);}}>⤢</button>
      {/* #1 删除按钮 · hover 显示 */}
      <button className="room-del" title={"删除 "+r.code}
        onClick={(e)=>{ e.stopPropagation(); if (confirm("确认删除 "+r.code+"？(其 "+r.pods.length+" 个 PoD 一并移除)")) onRemove(r.code); }}>✕</button>
      <div className={"bar "+ds}/>
      {/* 机房卡头一行：机房图标 + 「机房N」可读名 + 状态（同一行）· 用户决策 2026-05-29 */}
      <div className="rname">
        <span className="rname-ico" aria-hidden="true">{I.site(13)}</span>
        <span className="rname-txt">机房{r.code.replace(/\D/g,"") || r.code}</span>
        <button className={"rstat rstat-btn rstat-ready "+ds}
          title="可布线 / 可装设备 / 可通液 ready 时间 · 点击在右侧详情面板编辑"
          onClick={(e)=>{ e.stopPropagation(); onPick(r.code); }}>
          {hasAnyReady(r)
            ? [r.cableReadyAt, r.equipReadyAt, r.liquidReadyAt].map((d,i)=>(
                <span className={"rs-d"+(d?"":" tbd")} key={i}>{d ? d.slice(5) : "待定"}</span>))
            : <span className="rs-d tbd">待定</span>}
        </button>
      </div>
      <div className="pods">
        {r.pods.map((p,j)=>{
          // 货步(step 2) PoD 着色 · 用户决策 2026-06-01：按"今天"(SCHED_NOW) 推演到货进展——已到货(含 eta≤今天)=绿 /
          // 在途=琥珀 / 未明=灰，与本步图例(已到货/在途/未明)一致；早到的 PoD 随"今天"推进转绿，直观看到货进展。站步(step1)保持中性。
          const arr = step===2
            ? (p.arrival === "unknown" ? "unknown" : (p.arrival === "arrived" || (p.etaDate && p.etaDate <= SCHED_NOW) ? "arrived" : "eta"))
            : null;
          const cls = "pod "+(placed?"placed ":"")+(arr?arr:"");
          return (
            <button key={j} className={cls + " pod-btn"}
              style={{transitionDelay:((idx*4+j)*34)+"ms"}}
              title={`${p.id} · ${p.etaLabel} · 点击选中机房 · 在右侧详情面板编辑`}
              onClick={(e)=>{e.stopPropagation(); onPick(r.code);}}/>
          );
        })}
      </div>
    </div>
  );
}

/* PoD inline 编辑器 · 用户决策 2026-05-28 改造：从 Room 卡浮动 popover 改为 detail.pod-list 行展开 inline 编辑 */
function PodRowEditor({ pod, onSave, onCancel }: {
  pod: PodRow;
  onSave: (patch: Partial<PodRow>) => void;
  onCancel: () => void;
}){
  const [arrived, setArrived] = useState(pod.arrival === "arrived");
  const [date, setDate] = useState(pod.etaDate ?? "");
  const [status, setStatus] = useState<PodRow["status"]>(pod.status);
  const save = () => {
    const arrival: PodRow["arrival"] = arrived ? "arrived" : (date ? "eta" : "unknown");
    const lbl = arrived ? "可上架" : (date ? "在途 " + date.slice(5) : "待定");
    onSave({ arrival, etaLabel: lbl, etaDate: date || undefined, status });
  };
  return (
    <div className="pod-row-edit" onClick={(e)=>e.stopPropagation()}>
      <div className="pre-row">
        <span className="pre-lab">到货状态</span>
        <div className="pre-seg">
          <button className={!arrived?"on":""} onClick={()=>setArrived(false)}>未到货</button>
          <button className={arrived?"on":""} onClick={()=>setArrived(true)}>已到货</button>
        </div>
      </div>
      <div className="pre-row">
        <span className="pre-lab">到货时间</span>
        <input className="pre-in" type="date" value={date} onChange={(e) => setDate(e.target.value)}/>
      </div>
      <div className="pre-row">
        <span className="pre-lab">安装状态</span>
        <div className="pre-seg">
          {([
            { v: "pending",     lab: "未开始" },
            { v: "in_progress", lab: "进行中" },
            { v: "done",        lab: "完成" },
          ] as const).map(o => (
            <button key={o.v} className={status===o.v?"on":""} onClick={()=>setStatus(o.v)}>{o.lab}</button>
          ))}
        </div>
      </div>
      <div className="pre-foot">
        <button className="pre-btn" onClick={onCancel}>取消</button>
        <button className="pre-btn pri" onClick={save}>保存</button>
      </div>
    </div>
  );
}

/* 机房 ready 3 段时间编辑器 · detail.dh 内 inline · 用户决策 2026-05-28 */
function RoomReadyEditor({ room, onUpdateRoom }: {
  room: RoomRow;
  onUpdateRoom: (code: string, patch: Partial<RoomRow>) => void;
}){
  const [c, setC] = useState(room.cableReadyAt ?? "");
  const [e, setE] = useState(room.equipReadyAt ?? "");
  const [l, setL] = useState(room.liquidReadyAt ?? "");
  // 切换机房时同步
  useEffect(() => {
    setC(room.cableReadyAt ?? "");
    setE(room.equipReadyAt ?? "");
    setL(room.liquidReadyAt ?? "");
  }, [room.code]);
  const save = () => {
    let cc = c, ee = e, ll = l;
    const filled = [cc, ee, ll].filter(d => !!d);
    if (filled.length === 1) {
      const d = filled[0]!;
      cc = cc || d; ee = ee || d; ll = ll || d;
    }
    onUpdateRoom(room.code, {
      cableReadyAt:  cc || undefined,
      equipReadyAt:  ee || undefined,
      liquidReadyAt: ll || undefined,
    });
  };
  return (
    <div className="d-ready">
      <div className="d-ready-title">机房 ready 时间</div>
      <div className="d-rrow"><span className="d-rlab">可布线</span>
        <input className="d-rin" type="date" value={c} onChange={(ev)=>setC(ev.target.value)}/></div>
      <div className="d-rrow"><span className="d-rlab">可装设备</span>
        <input className="d-rin" type="date" value={e} onChange={(ev)=>setE(ev.target.value)}/></div>
      <div className="d-rrow"><span className="d-rlab">可通液</span>
        <input className="d-rin" type="date" value={l} onChange={(ev)=>setL(ev.target.value)}/></div>
      <div className="d-rhint">只填一段 → 其它两段自动同步</div>
      <button className="mini-btn pri" style={{marginTop:8, width:"100%"}} onClick={save}>保存 ready 时间</button>
    </div>
  );
}
function Drill({ room, onClose }: { room: RoomRow; onClose: () => void }){
  const cnt = (k: PodRow["arrival"])=>room.pods.filter(p=>p.arrival===k).length;
  return (
    <div className="drill" onMouseDown={(e)=>e.stopPropagation()}>
      <div className="drill-head">
        <button className="drill-back" onClick={onClose}>← 返回画布</button>
        <div className="dt">{I.site(17)} {room.code}
          <span className={"dchip "+deriveSite(room)}>{siteText(room)}</span>
          <span style={{fontSize:12,color:"var(--ink-3)",fontWeight:400}}>{room.proj}</span></div>
        <div className="dmeta"><span>已到货 <b>{cnt("arrived")}</b></span><span>在途 <b>{cnt("eta")}</b></span><span>未明 <b>{cnt("unknown")}</b></span></div>
      </div>
      <div className="pod-grid">
        {room.pods.map((p,i)=>(
          <div className={"pcard "+p.arrival} key={i} style={{animation:"pi-rise .35s ease both",animationDelay:(i*45)+"ms"}}>
            <div className="pcn">{p.id}</div>
            <div className="pst">{p.etaLabel}</div>
            <div className="parr"><span className={"arr-chip "+p.arrival}>{p.arrival==="arrived"?"已到货":p.arrival==="eta"?p.etaLabel:"到货未明"}</span></div>
          </div>
        ))}
      </div>
    </div>
  );
}
/* 批次管理（detail「批次」tab）· PoD 级 · 用户决策 2026-05-29：新建批次框 + 拖 PoD 入框 + 编辑上电/上线时间 */
function BatchManager({ batches, rooms, onAssign, onCreate, onUpdate, onDelete }: {
  batches: BatchRow[]; rooms: RoomRow[];
  onAssign: (podId: string, batchId: string | null) => void;
  onCreate: () => void;
  onUpdate: (id: string, patch: Partial<BatchRow>) => void;
  onDelete: (id: string) => void;
}){
  const podRoom = useMemo(() => {
    const m: Record<string, string> = {};
    rooms.forEach(r => r.pods.forEach(p => { m[p.id] = "机房" + (r.code.replace(/\D/g, "") || r.code); }));
    return m;
  }, [rooms]);
  const allPods = useMemo(() => rooms.flatMap(r => r.pods.map(p => p.id)), [rooms]);
  // 批次只显示/计数当前机房真实存在的 PoD —— 与现有机房对齐（默认 6 机房×2=12），过滤已删机房残留
  const allPodSet = useMemo(() => new Set(allPods), [allPods]);
  const assigned = useMemo(() => new Set(batches.flatMap(b => b.podIds)), [batches]);
  const unassigned = allPods.filter(id => !assigned.has(id));
  const [over, setOver] = useState<string | null>(null);

  const chip = (id: string, color?: string) => (
    <span key={id} className={"bm-chip" + (color ? " tinted" : "")} draggable
      onDragStart={(e) => { e.dataTransfer.setData("text/plain", id); e.dataTransfer.effectAllowed = "move"; }}
      title={(podRoom[id] || "") + " · " + id}
      style={color ? { borderColor: color, color, background: hexAlpha(color, .10) } : undefined}>
      <b>{id}</b><i className="bm-chip-room">{podRoom[id] || ""}</i>
    </span>
  );
  const drop = (target: string | null, key: string) => ({
    onDragOver: (e: React.DragEvent) => { e.preventDefault(); if (over !== key) setOver(key); },
    onDragLeave: () => setOver(o => o === key ? null : o),
    onDrop: (e: React.DragEvent) => { e.preventDefault(); const id = e.dataTransfer.getData("text/plain"); if (id) onAssign(id, target); setOver(null); },
  });

  return (
    <div className="batch-mgr">
      <div className="bm-tip">把 PoD 拖进批次框 · 批次按 PoD 编号区分</div>
      <div className={"bm-pool" + (over === "pool" ? " over" : "")} {...drop(null, "pool")}>
        <div className="bm-row-h">未分批 <b>{unassigned.length}</b></div>
        <div className="bm-chips">
          {unassigned.length === 0 ? <span className="bm-empty">全部已分批</span> : unassigned.map(id => chip(id))}
        </div>
      </div>
      {batches.map((b, i) => {
        const pods = b.podIds.filter(id => allPodSet.has(id));  // 仅当前机房真实存在的 PoD
        return (
        <div key={b.id} className={"bm-box" + (over === b.id ? " over" : "")} style={{ borderColor: b.color }} {...drop(b.id, b.id)}>
          <div className="bm-box-h" style={{ background: b.color }}>
            <span className="bm-no">{i + 1}</span>
            <input className="bm-name" value={b.name} onChange={(e) => onUpdate(b.id, { name: e.target.value })}/>
            <span className="bm-count">{pods.length} PoD</span>
            <button className="bm-x" title="删除批次" onClick={() => onDelete(b.id)}>✕</button>
          </div>
          <div className="bm-dates">
            <label>上电<input type="date" value={b.powerOnDate} onChange={(e) => onUpdate(b.id, { powerOnDate: e.target.value })}/></label>
            <label>上线<input type="date" value={b.goLiveDate} onChange={(e) => onUpdate(b.id, { goLiveDate: e.target.value })}/></label>
          </div>
          <div className="bm-chips">
            {pods.length === 0 ? <span className="bm-empty">拖 PoD 到此</span> : pods.map(id => chip(id, b.color))}
          </div>
        </div>
        );
      })}
      <button className="bm-create" onClick={onCreate}>＋ 新建批次</button>
    </div>
  );
}

function IsoYard({ clk, picked, onPick, step, pointerStart, pointerEnd, rooms, updatePod, updateRoom, removeRoom, addRoom, batches, assignPodToBatch, createBatch, updateBatch, deleteBatch }: {
  clk: number; picked: string|null; onPick: (c: string|null)=>void; step: number;
  pointerStart: string; pointerEnd: string;
  rooms: RoomRow[];
  updatePod: (roomCode: string, podId: string, patch: Partial<PodRow>) => void;
  updateRoom: (roomCode: string, patch: Partial<RoomRow>) => void;
  removeRoom: (roomCode: string) => void;
  addRoom: (batchId: string) => void;
  batches: BatchRow[];
  assignPodToBatch: (podId: string, batchId: string | null) => void;
  createBatch: () => void;
  updateBatch: (id: string, patch: Partial<BatchRow>) => void;
  deleteBatch: (id: string) => void;
}){
  const [vw,setVw] = useState({s:0.5, tx:0, ty:0});
  const [lay,setLay] = useState<Lay>(()=>{ try{ const s=localStorage.getItem("aida_lay_v1"); return s?{...DEFAULT_LAY,...JSON.parse(s)}:DEFAULT_LAY; }catch(e){ return DEFAULT_LAY; } });
  const [showLay,setShowLay] = useState(false);
  const [drill,setDrill] = useState<string | null>(null);
  // detail.pod-list 行展开编辑 · 用户决策 2026-05-28：PoD 编辑入口从浮动 popover 迁到此处
  const [editPodId, setEditPodId] = useState<string | null>(null);
  // detail 顶部 tab：机房编辑 / 批次管理 · 用户决策 2026-05-29
  const [detailTab, setDetailTab] = useState<"room" | "batch">("batch");  // 默认展示批次 · 用户决策 2026-05-29
  useEffect(() => { if (picked) setDetailTab("room"); }, [picked]);
  const pan = useRef<{x:number;y:number;tx:number;ty:number}|null>(null); const moved = useRef(false); const stageRef = useRef<HTMLDivElement | null>(null); const boardRef = useRef<HTMLDivElement | null>(null);
  const vwRef = useRef(vw); vwRef.current = vw;
  const layRef = useRef(lay); layRef.current = lay;
  const roomsRef = useRef(rooms); roomsRef.current = rooms;
  const posX=(c: number)=> c<3 ? c*lay.cx : c*lay.cx - lay.cx + lay.px;   // 列<3 属左侧项目；>=3 属右侧项目，组间用 px
  const posY=(r: number)=> r<3 ? r*lay.cy : r*lay.cy - lay.cy + lay.py;
  // 盘子尺寸按 plate 边界框算（精准包含所有批次 plate）·  marginLeft/Top 用几何中心确保真正居中
  const PAD=10, TOP_PLATE=26;
  const RH = lay.pod*2+54;
  // plates 动态计算：每批 plate 的 x0/y0/x1/y1 由该批当前机房分布决定
  const plates = useMemo(() => computePlates(rooms), [rooms]);
  const _xs = plates.flatMap(p => [posX(p.x0)-PAD, posX(p.x1)+lay.rw+PAD]);
  const _ys = plates.flatMap(p => [posY(p.y0)-TOP_PLATE, posY(p.y1)+RH+PAD]);
  const _minX = Math.min(..._xs), _maxX = Math.max(..._xs);
  const _minY = Math.min(..._ys), _maxY = Math.max(..._ys);
  const BW = _maxX - _minX, BH = _maxY - _minY;
  // 把 plate 几何中心对准 iso-pan 锚点（之前 -BW/2 默认假设 board 内容从 0 开始，但 plate.left 是负的）
  const boardMarginLeft = -(_minX + BW/2);
  const boardMarginTop  = -(_minY + BH/2);
  useEffect(()=>{ if(window.__aida) window.__aida.layout=(o)=>setLay(v=>({...v,...o})); },[]);
  useEffect(()=>{ try{ localStorage.setItem("aida_lay_v1", JSON.stringify(lay)); }catch(e){} },[lay]);   // 参数自动持久化，刷新沿用

  const fit = useCallback(()=>{ const st=stageRef.current; if(!st) return; const sr=st.getBoundingClientRect();
    const L=layRef.current; const pX=(c: number)=>c<3?c*L.cx:c*L.cx-L.cx+L.px, pY=(r: number)=>r<3?r*L.cy:r*L.cy-L.cy+L.py;
    const PAD=10, TOP_PL=26, RH=L.pod*2+54;
    // fit 用 ref 拿最新 rooms（useCallback([]) 闭包不会更新）
    const dynPlates = computePlates(roomsRef.current);
    const xs = dynPlates.flatMap(p => [pX(p.x0)-PAD, pX(p.x1)+L.rw+PAD]);
    const ys = dynPlates.flatMap(p => [pY(p.y0)-TOP_PL, pY(p.y1)+RH+PAD]);
    const gw = Math.max(...xs) - Math.min(...xs);
    const gh = Math.max(...ys) - Math.min(...ys);
    const rz=L.rz*Math.PI/180, rx=L.rx*Math.PI/180;
    const isoW=gw*Math.cos(rz)+gh*Math.sin(rz);
    const isoH=(gw*Math.sin(rz)+gh*Math.cos(rz))*Math.cos(rx)+gh*0.12;
    // 顶部 chip 行（floorlbl / legend / go-live-strip）占 ~42px
    const TOP_OBSTRUCT = 42;
    const availH = sr.height - TOP_OBSTRUCT;
    const s=clamp(Math.min(sr.width*0.92/isoW, availH*0.94/isoH),0.3,1.7);
    setVw({s:+s.toFixed(3), tx:0, ty: TOP_OBSTRUCT/2});
  },[]);
  useEffect(()=>{ fit(); const onR=()=>fit(); window.addEventListener("resize",onR); return ()=>window.removeEventListener("resize",onR); },[fit]);
  useEffect(()=>{ const el=stageRef.current; if(!el) return;
    const h=(e: WheelEvent)=>{ e.preventDefault(); setVw(v=>({...v, s:clamp(+(v.s*(e.deltaY<0?1.12:0.89)).toFixed(3),0.3,1.8)})); };
    el.addEventListener("wheel",h,{passive:false}); return ()=>el.removeEventListener("wheel",h);
  },[]);

  const onDown=(e: React.MouseEvent)=>{ if(e.button!==0) return; pan.current={x:e.clientX,y:e.clientY,tx:vw.tx,ty:vw.ty}; moved.current=false; stageRef.current&&stageRef.current.classList.add("grabbing"); };
  const onMove=(e: React.MouseEvent)=>{ if(!pan.current) return; const dx=e.clientX-pan.current.x, dy=e.clientY-pan.current.y; if(Math.abs(dx)+Math.abs(dy)>4) moved.current=true; setVw(v=>({...v, tx:pan.current!.tx+dx, ty:pan.current!.ty+dy})); };
  const end=()=>{ pan.current=null; stageRef.current&&stageRef.current.classList.remove("grabbing"); };
  const zoom=(d: number)=> setVw(v=>({...v, s:clamp(+(v.s+d).toFixed(3),0.3,1.8)}));
  const reset=()=> fit();
  const pickRoom=(code: string)=>{ if(moved.current) return; onPick(picked===code?null:code); };
  // viewMode 由角度衍生（rx & rz 都接近 0 = 2D，否则 3D）；切换走 lay 状态变化 + CSS transition
  const viewMode: "3d" | "2d" = (lay.rx < 10 && lay.rz < 10) ? "2d" : "3d";
  const switchView = (m: "3d" | "2d") => {
    if (m === viewMode) return;
    if (m === "2d") {
      setLay(v => ({...v, rx:0, rz:0}));
    } else {
      setLay(v => ({...v, rx:DEFAULT_LAY.rx, rz:DEFAULT_LAY.rz}));
    }
    // 两种模式都重跑 fit，确保 board 居中（tx/ty 重置 + scale 重算）
    setTimeout(() => fit(), 50);
  };

  const hiProj = picked ? (rooms.find(r=>r.code===picked)||{}).proj : null;
  // 批次分框：picked 机房的 goLiveBatch 决定哪个 batch plate 被高亮
  const hiBatch = picked ? (rooms.find(r=>r.code===picked)||{} as Partial<RoomRow>).goLiveBatch : null;
  const room = rooms.find(r=>r.code===picked);
  const drillRoom = rooms.find(r=>r.code===drill);
  const stop=(e: React.SyntheticEvent)=>e.stopPropagation();

  return (
    <div>
      <div className="yard">
        <div className="iso-stage" ref={stageRef} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={end} onMouseLeave={end} onClick={()=>{ if(!moved.current) onPick(null); }}>
          <div className="floorlbl">数字孪生 · 交付盘子底图</div>
          <div className="legend">
            <div className="lg-row lg-shape">
              <span><i className="lg-room"/>机房 · 房间</span>
              <span><i className="lg-pod"/>PoD · 机柜单元</span>
            </div>
            <div className="lg-row">
              {step===2 ? <>
                <span><i style={{background:"var(--ok)"}}/>已到货</span>
                <span><i style={{background:"var(--warn)"}}/>在途</span>
                <span><i style={{background:"var(--surface-3)", border:"1px dashed var(--ink-4)"}}/>未明</span>
              </> : <>
                <span><i style={{background:"var(--ok)"}}/>可进场</span>
                <span><i style={{background:"var(--ink-3)"}}/>待定 / 不可进场</span>
              </>}
            </div>
          </div>
          {/* 上线批 chip 行已移除：画布不再展示批次，只呈现机房 + PoD · 用户决策 2026-05-29（批次改到 detail「批次」tab） */}
          {/* 零状态引导带 · #1 收尾：当 rooms 为空时显示，盖在 stage 中央 */}
          {rooms.length === 0 && (
            <ZeroStateOverlay onAddBatch={addRoom}/>
          )}
          <div className={"iso-viewport"+(viewMode==="2d"?" flat":"")+(rooms.length===0?" empty":"")}>
            <div className="iso-pan" style={{transform:"translate("+vw.tx+"px,"+vw.ty+"px) scale("+vw.s+")"}}>
              <div className="iso-board" ref={boardRef} style={{width:BW, height:BH, marginLeft:boardMarginLeft, marginTop:boardMarginTop, transform:"rotateX("+lay.rx+"deg) rotateZ(-"+lay.rz+"deg)", "--rw":lay.rw+"px", "--rpad":lay.pad+"px", "--pod":lay.pod+"px", "--pgap":lay.pgap+"px"} as React.CSSProperties}>
                {/* 批次 plate 框已移除（画布不再展示批次）· 用户决策 2026-05-29；computePlates 仅保留用于 board 尺寸/居中计算 */}
                {rooms.map((r,i)=>(
                  <Room key={r.code} r={r} idx={i} total={rooms.length} clk={clk} step={step} picked={picked===r.code} cx={lay.cx} cy={lay.cy} px={lay.px} py={lay.py}
                    faint={!!(hiProj && r.proj!==hiProj)} onPick={pickRoom} onDrill={setDrill}
                    pointerStart={pointerStart} pointerEnd={pointerEnd}
                    onRemove={removeRoom} onUpdatePod={updatePod} onUpdateRoom={updateRoom}/>
                ))}
              </div>
            </div>
          </div>
          <div className="iso-toolbar" onClick={(e)=>e.stopPropagation()}>
            <button onMouseDown={stop} onClick={()=>zoom(0.16)} title="放大">+</button>
            <button onMouseDown={stop} onClick={()=>zoom(-0.16)} title="缩小">−</button>
            <button onMouseDown={stop} onClick={reset} title="复位视角" style={{fontSize:14}}>⊙</button>
          </div>
          <div className="iso-tools">
            <LayoutPanel lay={lay} setLay={setLay} open={showLay} onToggle={()=>setShowLay(s=>!s)}/>
            <ViewModeToggle mode={viewMode} onPick={switchView}/>
            <AddRoomBtn rooms={rooms} onAdd={addRoom}/>
          </div>
          <div className="iso-tip">拖拽平移 · 滚轮缩放 · 点机房高亮 · ⚙ 调布局 · 3D/2D 切换视角 · + 加机房</div>
          {drillRoom && <Drill room={drillRoom} onClose={()=>setDrill(null)}/>}
        </div>

        <div className="detail">
          <div className="detail-tabs">
            <button className={detailTab==="batch"?"on":""} onClick={()=>setDetailTab("batch")}>{I.schedule(13)}<span>批次</span><span className="dt-n">{batches.length}</span></button>
            <button className={detailTab==="room"?"on":""} onClick={()=>setDetailTab("room")}>{I.site(13)}<span>机房</span><span className="dt-n">{rooms.length}</span></button>
          </div>
          {detailTab==="batch" ? (
            <BatchManager batches={batches} rooms={rooms} onAssign={assignPodToBatch} onCreate={createBatch} onUpdate={updateBatch} onDelete={deleteBatch}/>
          ) : !room ? (
            <div className="hint">
              <div className="ic">{I.site(22)}</div>
              {step===1
                ? <>共 <b>{rooms.length}</b> 间机房：<span style={{color:"var(--ok)"}}>{rooms.filter(r=>deriveSite(r)==="ready").length} 可进场</span> · <span style={{color:"var(--ink-3)"}}>{rooms.filter(r=>deriveSite(r)!=="ready").length} {rooms.some(r=>r.readyUnknown)?"待定":"不可进场"}</span>。<br/><br/><b>点击任一机房</b> → 右侧可调整其信息（ready 时间 / PoD 到货）。</>
                : <>共 <b>{rooms.length}</b> 间机房 · <b>{rooms.flatMap(r=>r.pods).length}</b> 个 PoD：<span style={{color:"var(--ok)"}}>{rooms.flatMap(r=>r.pods).filter(p=>p.arrival==="arrived").length} 已到货</span> · <span style={{color:"var(--ink-3)"}}>{rooms.flatMap(r=>r.pods).filter(p=>p.arrival!=="arrived").length} 未到货</span>。<br/><br/><b>点击任一机房</b> → 右侧可调整其信息（PoD 到货 / ready 时间）。</>}
            </div>
          ) : (
            <>
              <div className="dh">
                <div className="t">{I.site(15)} {room.code}
                  <span className={"dchip "+deriveSite(room)} style={{marginLeft:"auto"}}>{siteText(room)}</span></div>
                <div className="s">{room.proj} · {room.pods.length} 个 PoD</div>
                <RoomReadyEditor room={room} onUpdateRoom={updateRoom}/>
                <button className="mini-btn pri" style={{marginTop:11,width:"100%"}} onClick={()=>setDrill(room.code)}>⤢ 下钻 · 可视化查看 {room.pods.length} 个 PoD</button>
              </div>
              <div className="pod-list">
                {room.pods.map((p,j)=>(
                  <Fragment key={j}>
                    <div className={"pod-row "+(editPodId===p.id?"editing":"")}
                         onClick={()=>setEditPodId(prev => prev===p.id ? null : p.id)}
                         title="点击展开 / 收起 PoD 编辑">
                      <span className="pn">{p.id}</span>
                      <span className={"arr-chip "+(p.arrival==="arrived"?"arrived":"unknown")}>{p.arrival==="arrived"?"已到货":"未到货"}</span>
                      {p.etaDate && <span className="pdate">{p.etaDate.slice(5)}</span>}
                      <span className={"inst-chip s-"+p.status}>{p.status==="done"?"完成":p.status==="in_progress"?"进行中":"未开始"}</span>
                      <span className="pe-toggle">{editPodId===p.id ? "▾" : "✎"}</span>
                    </div>
                    {editPodId === p.id && (
                      <PodRowEditor pod={p}
                        onSave={(patch)=>{ updatePod(room.code, p.id, patch); setEditPodId(null); }}
                        onCancel={()=>setEditPodId(null)}/>
                    )}
                  </Fragment>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ===================== people ===================== */
/* 队伍编辑 · 左侧详情面板内联编辑（人数/经验/状态，改动实时生效）· 用户决策 2026-05-29，替代浮层 */
function TeamDetailEditor({ team, onChange }: { team: TeamRow; onChange: (patch: Partial<TeamRow>)=>void }){
  return (
    <>
      <div className="dh">
        <div className="t">{I.person(15)} 队 {team.id}
          <span className={"dchip "+(team.st==="on"?"ready":"pending")} style={{marginLeft:"auto"}}>{team.st==="on"?"在场":"待命"}</span></div>
        <div className="s">全能施工单元 · {team.exp==="full"?"经验充分":"经验一般"}</div>
      </div>
      <div className="td-body">
        <div className="td-row"><span className="td-lab">人数</span>
          <div className="num-step">
            <button onClick={()=>onChange({ n: Math.max(1, team.n-1) })}>−</button>
            <span className="num-v">{team.n}</span>
            <button onClick={()=>onChange({ n: Math.min(99, team.n+1) })}>+</button>
          </div>
        </div>
        <div className="td-row"><span className="td-lab">经验</span>
          <div className="td-seg">
            <button className={team.exp==="full"?"on":""} onClick={()=>onChange({ exp:"full" })}>经验充分</button>
            <button className={team.exp==="junior"?"on":""} onClick={()=>onChange({ exp:"junior" })}>经验一般</button>
          </div>
        </div>
        <div className="td-row"><span className="td-lab">状态</span>
          <div className="td-seg">
            <button className={team.st==="on"?"on":""} onClick={()=>onChange({ st:"on" })}>在场</button>
            <button className={team.st==="wait"?"on":""} onClick={()=>onChange({ st:"wait" })}>待命</button>
          </div>
        </div>
        <div className="td-hint">改动实时生效 · 改完点顶部「保存」应用</div>
      </div>
    </>
  );
}

function PeopleView({ clk, teams, updateTeam, addTeam, removeTeam }: { clk: number; teams: TeamRow[]; updateTeam: (id: string, patch: Partial<TeamRow>)=>void; addTeam: (exp: TeamRow["exp"])=>void; removeTeam: (id: string)=>void }){
  // 进人步后延一帧再触发，确保队伍/活动卡有「从无到有」的逐个过渡（否则首次挂载即终态、无动画）
  const [show,setShow] = useState(false);
  useEffect(()=>{ const t=setTimeout(()=>setShow(true), 40); return ()=>clearTimeout(t); },[]);
  const teamIn = show, actIn = show && clk>=13, calcOn = clk>=14;
  // sub-tab：队伍 / SLA / 活动依赖图（#6）
  const [subTab, setSubTab] = useState<"teams" | "sla" | "graph">("teams");
  // 选中编辑的队伍 id（在左侧详情面板编辑，替代原会被裁切的卡片浮层）· 用户决策 2026-05-29
  const [selTeamId, setSelTeamId] = useState<string | null>(null);
  const selTeam = teams.find(t => t.id === selTeamId) || null;
  // 队伍统计动态计算（替代原静态 TEAM_STAT）
  const stat = useMemo(() => {
    const fullList = teams.filter(t => t.exp === "full");
    const jrList = teams.filter(t => t.exp === "junior");
    const fullHc = fullList.reduce((s, t) => s + t.n, 0);
    const jrHc = jrList.reduce((s, t) => s + t.n, 0);
    const onList = teams.filter(t => t.st === "on");
    const waitList = teams.filter(t => t.st === "wait");
    const onHc = onList.reduce((s, t) => s + t.n, 0);
    const waitHc = waitList.reduce((s, t) => s + t.n, 0);
    const totalHc = fullHc + jrHc;
    return {
      fullTeams: fullList.length, fullHc,
      jrTeams: jrList.length, jrHc,
      onTeams: onList.length, onHc,
      waitTeams: waitList.length, waitHc,
      onPct: totalHc ? Math.round(onHc / totalHc * 100) : 0,
      effective: Math.round(fullHc + jrHc * 0.7),
      total: teams.length, totalHc,
    };
  }, [teams]);
  return (
    <div className="people">
      <div className="people-tabs">
        <button className={subTab==="teams"?"on":""} onClick={()=>setSubTab("teams")}>
          {I.people(13)} 队伍
        </button>
        <button className={subTab==="sla"?"on":""} onClick={()=>setSubTab("sla")}>
          {I.flow(13)} SLA · 工期换算
        </button>
        <button className={subTab==="graph"?"on":""} onClick={()=>setSubTab("graph")}>
          {I.cable(13)} 活动依赖图
        </button>
      </div>

      {subTab==="teams" && (
      <div className="team-wrap">
        <div className="panel team-panel">
          {/* 核爆 hero：突出「队伍数 + 人数」两个重点数字（无总产能概念）· 用户决策 2026-05-29 */}
          <div className="team-hero">
            <div className="th-kpis">
              <div className="th-tile">
                <span className="th-ico">{I.people(30)}</span>
                <span className="th-main"><b className="tnum">{stat.total}</b><span className="th-lab">支队伍</span></span>
              </div>
              <div className="th-tile">
                <span className="th-ico">{I.person(26)}</span>
                <span className="th-main"><b className="tnum">{stat.totalHc}</b><span className="th-lab">总人数</span></span>
              </div>
            </div>
            <div className="th-alloc">
              <div className="th-col-h">人力配置</div>
              <div className="th-bar" aria-hidden="true">
                <span className="th-bar-on" style={{width:stat.onPct+"%"}}/>
              </div>
              <div className="th-alloc-legend">
                <span className="ths on"><i/>在场 <b className="tnum">{stat.onTeams}</b> 队 · <b className="tnum">{stat.onHc}</b> 人</span>
                <span className="ths wait"><i/>待分配 <b className="tnum">{stat.waitTeams}</b> 队 · <b className="tnum">{stat.waitHc}</b> 人</span>
              </div>
            </div>
            <div className="th-split">
              <div className="th-col-h">经验结构</div>
              <span className="ths full"><i/>经验充分 <b className="tnum">{stat.fullTeams}</b> 队 · <b className="tnum">{stat.fullHc}</b> 人</span>
              <span className="ths jr"><i/>经验一般 <b className="tnum">{stat.jrTeams}</b> 队 · <b className="tnum">{stat.jrHc}</b> 人</span>
            </div>
          </div>
          {/* 两类分行：经验充分 / 经验一般；卡上可直接删除，行尾「＋加队伍」· 用户决策 2026-05-29 */}
          {([{ exp:"full" as const, lab:"经验充分" }, { exp:"junior" as const, lab:"经验一般" }]).map(g=>(
            <div className="team-group" key={g.exp}>
              <div className="tg-head"><i className={"tg-dot "+g.exp}/>{g.lab} <b className="tnum">{teams.filter(t=>t.exp===g.exp).length}</b> 队</div>
              <div className="team-grid">
                {teams.filter(t=>t.exp===g.exp).map((t,i)=>(
                  <div className={"tcard2 "+t.exp+(teamIn?" in":"")+(selTeamId===t.id?" sel":"")} key={t.id}
                       style={{transitionDelay:(i*60)+"ms"}}
                       onClick={()=>setSelTeamId(prev => prev===t.id ? null : t.id)} title="点击编辑此队伍">
                    <div className="tc2-top">
                      <span className="tc2-id">队 {t.id}</span>
                      <span className="tc2-act">
                        <span className={"tc2-st "+t.st}>{t.st==="on"?"在场":"待命"}</span>
                        <button className="tc2-del" title="删除此队伍"
                          onClick={(e)=>{ e.stopPropagation(); if(confirm("确认删除 队 "+t.id+"？")){ removeTeam(t.id); if(selTeamId===t.id) setSelTeamId(null); } }}>✕</button>
                      </span>
                    </div>
                    <div className="tc2-num"><b className="tnum">{t.n}</b><span className="u">人</span></div>
                    <div className="tc2-dots" aria-hidden="true">{Array.from({length:t.n}).map((_,j)=>(<i key={j}/>))}</div>
                    <div className={"tc2-exp "+t.exp}>{g.lab}</div>
                  </div>
                ))}
                <button className="tcard-add" title={"加一支"+g.lab+"队伍"} onClick={()=>addTeam(g.exp)}>＋<span>加队伍</span></button>
              </div>
            </div>
          ))}
        </div>
        {/* 右侧：队伍编辑详情面板（替代会被裁切的卡片浮层）· 用户决策 2026-05-29 */}
        <div className="detail team-detail">
          {selTeam ? (
            <TeamDetailEditor team={selTeam} onChange={(patch)=>updateTeam(selTeam.id, patch)}/>
          ) : (
            <div className="hint"><div className="ic">{I.person(22)}</div>点击左侧队伍卡片<br/>在此编辑 <b>人数 / 经验 / 状态</b></div>
          )}
        </div>
      </div>
      )}

      {subTab==="sla" && (
      <div className="panel">
        <div className="ph"><div className="t">{I.flow(15)} 硬装活动 · 工期 = 工作量 ÷ 有效人力</div><div className="meta">蓝色 = 受人数约束 · 经验折算产能</div></div>
        <div className="calc-list">
          <div className="calc-group elastic">
          <div className="calc-gh">{I.flow(12)} 弹性工期 · 加人可压缩（压缩着力点）</div>
          {ACTS.filter(a=>a.bound).map((a,i)=>(
            <div className={"calc-row "+(actIn?"in":"")} key={a.name} style={{transitionDelay:(i*170)+"ms"}}>
              <div className="cr-head"><span className="cdim">{a.dim}</span><span className="cnm">{a.name}</span></div>
              <div className="cr-flow">
                <div className="cr-seg"><span className="seg-lab">工作量</span>
                  <span className="seg-val">{I[a.wIcon]&&I[a.wIcon](13)}{a.work}<span style={{color:"var(--ink-3)",fontWeight:400}}>{a.workU}</span></span></div>
                <span className="cr-op">÷</span>
                <div className="cr-seg"><span className="seg-lab">投入 {a.ppl} {a.pplU}</span>
                  <span className="seg-figs">{Array.from({length:Math.min(a.ppl!,12)}).map((_,j)=>(<span className="fig" key={j}>{I.person(12)}</span>))}</span></div>
                <span className="cr-op">=</span>
                <div className="cr-seg cr-dur"><span className="seg-lab">工期 · {a.rate}</span>
                  <div className="dur-track">
                    <div className="dur-base" style={{width:(a.base!/DUR_MAX*100)+"%"}}><span className="dur-cap">{a.base} 天</span></div>
                    <div className="dur-cut" style={{width:(calcOn?a.cut!/DUR_MAX*100:0)+"%"}}/>
                  </div>
                  <div className="cut-note" style={{opacity:calcOn?1:0}}>↓ 加人后可缩至 <b>{a.cut}</b> 天</div>
                </div>
              </div>
            </div>
          ))}
          </div>
          <div className="calc-group rigid">
          <div className="calc-gh">{I.lock(12)} 刚性工期 · 加人无效（外部约束）</div>
          {ACTS.filter(a=>!a.bound).map((a,i)=>(
            <div className={"calc-row "+(actIn?"in":"")} key={a.name} style={{transitionDelay:((3+i)*150)+"ms"}}>
              <div className="cr-head"><span className="cdim">{a.dim}</span><span className="cnm">{a.name}</span></div>
              <div className="cr-flow">
                <div className="cr-seg"><span className="seg-lab">约束</span>
                  <span className="seg-val">{I[a.wIcon]&&I[a.wIcon](13)}{a.reason}</span></div>
                <span className="cr-op" style={{opacity:0}}>÷</span>
                <div className="cr-seg cr-dur"><span className="seg-lab">工期（固定）</span>
                  <div className="dur-track"><div className="dur-fix" style={{width:(a.dur!/DUR_MAX*100)+"%"}}><span className="dur-cap">{a.durLabel}{a.durLabel!=="ETA"?" 天":""}</span></div></div>
                  <div className="fix-note">{I.lock(11)} 外部约束 · 加人无效</div>
                </div>
              </div>
            </div>
          ))}
          </div>
        </div>
      </div>
      )}

      {subTab==="graph" && <ActivitiesGraph/>}
    </div>
  );
}

/* 队伍 inline 编辑 popover · #3 收尾 */
function TeamEditPopover({ team, onSave, onClose }: { team: TeamRow; onSave: (patch: Partial<TeamRow>)=>void; onClose: ()=>void }){
  const [n, setN] = useState(team.n);
  const [exp, setExp] = useState<TeamRow["exp"]>(team.exp);
  const [st, setSt] = useState<TeamRow["st"]>(team.st);
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();
  return (
    <div className="team-pop" onMouseDown={stop} onClick={stop} onWheel={stop}>
      <div className="pop-h">
        <span>编辑队 <b>{team.id}</b></span>
        <button className="pop-close" onClick={onClose}>×</button>
      </div>
      <div className="pop-row">
        <span className="pop-lab">人数</span>
        <div className="num-step">
          <button onClick={() => setN(v => Math.max(1, v-1))}>−</button>
          <span className="num-v">{n}</span>
          <button onClick={() => setN(v => Math.min(99, v+1))}>+</button>
        </div>
      </div>
      <div className="pop-row">
        <span className="pop-lab">经验</span>
        <div className="pop-seg">
          <button className={exp==="full"?"on":""} onClick={()=>setExp("full")}>经验充分</button>
          <button className={exp==="junior"?"on":""} onClick={()=>setExp("junior")}>经验待教</button>
        </div>
      </div>
      <div className="pop-row">
        <span className="pop-lab">状态</span>
        <div className="pop-seg">
          <button className={st==="on"?"on":""} onClick={()=>setSt("on")}>在场</button>
          <button className={st==="wait"?"on":""} onClick={()=>setSt("wait")}>待分配</button>
        </div>
      </div>
      <div className="pop-foot">
        <button className="pop-btn" onClick={onClose}>取消</button>
        <button className="pop-btn pri" onClick={()=>onSave({ n, exp, st })}>保存</button>
      </div>
    </div>
  );
}

/* ===================== schedule ===================== */
function Gantt({ rows, showDeadline }: { rows: GanttRow[]; showDeadline: boolean }){
  const AX=42, DL=32; // 轴 42 天, 移交线在 32 天
  return (
    <div className="gantt">
      <div className="g-scale">
        {showDeadline && <>
          <div className="deadline-line" style={{left:(DL/AX*100)+"%"}}/>
          <div className="dl-lab" style={{left:(DL/AX*100)+"%"}}>移交 09-20</div>
        </>}
      </div>
      {rows.map((g,i)=>(
        <div className="g-row" key={i}>
          <span className="gl">{g[0]}</span>
          <div className="g-track">
            <div className="g-base" style={{left:(g[1]/AX*100)+"%",width:(g[2]/AX*100)+"%"}}/>
            <div className={"g-bar "+(g[5]?"bound":"")} style={{left:(g[3]/AX*100)+"%",width:(g[4]/AX*100)+"%"}}/>
          </div>
        </div>
      ))}
      <div className="g-foot"><span><i style={{background:"var(--surface-3)",border:"1px solid var(--line)"}}/>初排基线</span><span><i style={{background:"var(--brand)"}}/>受约束·已压缩</span><span><i style={{background:"var(--ink-3)"}}/>固定活动</span></div>
    </div>
  );
}
/* ScheduleView 已删除：adjust 改走 基线→调整推演→ABC，不再用旧批次摘要 · 2026-05-30 */

/* ===================== 压缩策略：缺口 + 多策略方案 + 操作 ===================== */
/* 方案卡：渲染在排期内容区顶部（时间轴正下方、clock stage-head 之上）· 仅 adjust 用 */
function CompressionPlans({ clk, selPlan, onSelPlan, onOpenGantt, onDispatch }: { clk: number; selPlan: string|null; onSelPlan: (id: string)=>void; onOpenGantt?: (id: string)=>void; onDispatch?: (id: string)=>void }){
  const showGap = clk>=17;
  const plansIn = clk>=18;
  return (
    <>
      {showGap && (
        <div className="gap-banner fade">
          <div className="gx late"><div className="lab">预计完成</div><div className="val">09-30</div></div>
          <div className="arrow-mid"><div className="gd">超出移交 +10 天 · 需压缩</div></div>
          <div className="gx deadline"><div className="lab">合同移交目标</div><div className="val">09-20</div></div>
        </div>
      )}

      {showGap && (
        <div className="stage-head" style={{margin:"4px 2px 12px"}}>
          <span className="k">构建 <span className="dim">3</span> 套压缩策略供选择</span>
          <span className="d">压缩通过给「受人数约束」的活动加人实现</span>
        </div>
      )}

      <div className="plans">
        {PLANS.map((p,i)=>(
          <div key={p.id} className={"plan "+(plansIn?"in ":"")+(p.rec?"rec ":"")+(selPlan===p.id?"sel":"")}
            style={{transitionDelay:(i*120)+"ms"}} onClick={()=>onSelPlan(p.id)}>
            <div className="pl-h">
              {p.rec && <span className="rec-badge">★ 推荐</span>}
              <div className="nm">{p.name}</div>
              <div className="ds">{p.ds}</div>
            </div>
            <div className="kpis">{p.kpi.map((k,j)=>(
              <div className="kpi" key={j}><div className={"v "+(k[2]||"")}>{k[0]}</div><div className="l">{k[1]}</div></div>))}</div>
            <Gantt rows={p.gantt} showDeadline={true}/>
            <div className="pl-risks">
              <div className="plr-h">引入的风险</div>
              {p.risks.map((r, k) => (
                <div className="plr-row" key={k}>
                  <span className={"plr-lv lv-" + (r.lv === "高" ? "hi" : r.lv === "中" ? "mid" : "lo")}>{r.lv}</span>
                  <span className="plr-tx"><b>{r.t}</b><i>{r.d}</i></span>
                </div>
              ))}
              <div className="plr-advice"><span className="plr-adv-ic">{I.spark(11)}</span><span><b>建议</b> · {p.advice}</span></div>
            </div>
            <div className="pl-foot">
              {selPlan===p.id ? (<>
                {onOpenGantt && <button className="open-gantt" onClick={(e)=>{ e.stopPropagation(); onOpenGantt(p.id); }}>{I.schedule(13)} 查看排期详情</button>}
                <button className="choose" onClick={(e)=>{ e.stopPropagation(); onDispatch && onDispatch(p.id); }}>确认&下发</button>
              </>) : (
                <button className="choose" onClick={(e)=>{ e.stopPropagation(); onSelPlan(p.id); }}>选择此方案</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

/* ===================== empty ===================== */
function Empty(){
  return (<div className="empty">
    <div className="ring">{I.flow(34)}</div>
    <div><h2>等待 Claw 发送交付资料</h2>
      <p>在左侧上传合同 / HLD / BOQ / 到货表 / 排班并发送，AIDA 将按 站 → 货 → 人 逐步解析这批数据，并构建第一版排期。</p></div>
    <div className="arrow">← 在左侧点击「发送 · 开始初排」</div>
  </div>);
}

/* ===================== app ===================== */
/* ④ 使用引导 · 首次进入浮层 + 顶部「?」重看 · 用户决策 2026-05-29（A 浮层 + B 常驻 affordance，不做独立页） */
function GuideOverlay({ onClose }: { onClose: ()=>void }){
  const steps = [
    { ic: I.site(20),     t: "四步切换",     d: "顶部 站 / 货 / 人 / 排期，点图标切换视角" },
    { ic: I.goods(20),    t: "改机房 / PoD", d: "画布点机房 → 右侧面板改 ready 时间、PoD 到货" },
    { ic: I.schedule(18), t: "分批次",       d: "右侧「批次」tab：新建批次框，把 PoD 拖进框" },
    { ic: I.check(18),    t: "应用变更",     d: "改完点顶部「保存 / 执行变更」即生效" },
  ];
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();
  return (
    <div className="guide-mask" onClick={onClose}>
      <div className="guide-modal" onClick={stop}>
        <div className="gm-head">
          <span className="gm-title">{I.spark(15)} 快速上手 · 人货站怎么改</span>
          <button className="gm-close" title="关闭" onClick={onClose}>×</button>
        </div>
        <div className="gm-steps">
          {steps.map((s,i)=>(
            <div className="gm-step" key={i}>
              <span className="gm-no">{i+1}</span>
              <span className="gm-ic">{s.ic}</span>
              <div className="gm-txt"><b>{s.t}</b><span>{s.d}</span></div>
            </div>
          ))}
        </div>
        <button className="gm-ok" onClick={onClose}>知道了,开始</button>
      </div>
    </div>
  );
}

/* ===================== BackwardSchedule · 批次目标图（init 倒排结果 / adjust 基线，两页共用）=====================
   variant=suggest（init）：红旗倒推「建议到货 / 机房 ready」(✦AI)；variant=given（adjust）：到货/机房显示为已知。
   拖「上线/上电」红旗 → 据 batches 实时重算倒推；init 点批次开甘特，adjust 点「调整推演」→ thinking → ABC。 */
const LEAD_LIVE_TO_ARRIVE = 31;   // 上线 −31 天 = 货最晚到（沿用既有 09-20→08-20 倒排口径）
const LEAD_LIVE_TO_ROOM   = 35;   // 机房须先于到货就绪，留改造验收缓冲

const bwdShift = (iso: string, delta: number) => {
  const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + delta);  // UTC 解析+步进，避免本地时区把日期退一天
  return d.toISOString().slice(0, 10);
};
const bwdDays = (a: string, b: string) =>
  Math.round((new Date(a + "T00:00:00Z").getTime() - new Date(b + "T00:00:00Z").getTime()) / 86400000);
const bwdMD = (iso: string) => (iso ? iso.slice(5) : "—");

// 红旗：建议到货 / 建议机房 ready 的「必达目标」标记（视觉突出，用户决策 2026-05-29）
const BWD_FLAG = (
  <svg className="bwd-flag-svg" width="11" height="12" viewBox="0 0 11 12" fill="none" aria-hidden="true">
    <path d="M2 1.4V11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M2.7 1.6H9.4L7.6 3.7L9.4 5.8H2.7Z" fill="currentColor"/>
  </svg>
);
function BwdMk({ x, cls, lab, date, sug, big, below, color, draggable, onGrab, dragging, flag }: {
  x: number; cls: string; lab: string; date: string;
  sug?: boolean; big?: boolean; below?: boolean; color?: string;
  draggable?: boolean; onGrab?: (e: React.MouseEvent) => void; dragging?: boolean; flag?: boolean;
}) {
  return (
    <div className={"bwd-mk " + cls + (sug ? " sug" : "") + (big ? " big" : "") + (below ? " below" : "") + (draggable ? " draggable" : "") + (dragging ? " dragging" : "") + (flag ? " flagged" : "")}
      style={{ left: x + "%" }}
      onMouseDown={draggable ? onGrab : undefined}
      title={draggable ? lab + " · 按住左右拖动调整目标日期" : undefined}>
      <span className="bwd-dot" style={color ? { background: color, borderColor: color } : undefined} />
      <div className="bwd-cap">
        <span className="bwd-mlab">{flag && <i className="bwd-flag">{BWD_FLAG}</i>}{sug && <i className="bwd-ai" aria-hidden="true">{I.spark(10)}</i>}{lab}{draggable && <i className="bwd-grip" aria-hidden="true">⇆</i>}</span>
        <span className="bwd-mdate">{date}</span>
      </div>
    </div>
  );
}

const SCHED_TODAY = PROJECT_START;   // 拖拽下限：不早于今天
type BwdRow = BatchRow & { pods: string[]; arrive: string; room: string };
// 倒排时间轴范围：含 6 天留白；拖拽时冻结，避免轴随被拖日期跳动
function axisOf(rows: BwdRow[]) {
  const ds = rows.flatMap(r => [r.room, r.arrive, r.powerOnDate, r.goLiveDate].filter(Boolean));
  if (!ds.length) return { min: PROJECT_START, max: PROJECT_END, span: Math.max(1, bwdDays(PROJECT_END, PROJECT_START)) };
  let min = ds.reduce((m, d) => (d < m ? d : m), ds[0]!);
  let max = ds.reduce((m, d) => (d > m ? d : m), ds[0]!);
  min = bwdShift(min, -6); max = bwdShift(max, 6);
  return { min, max, span: Math.max(1, bwdDays(max, min)) };
}

// 批次盘子 → BwdRow[]（机房就位/到货 + 上电/上线 + pods）· suggest=倒推 / given=实际已知
// 从 BackwardSchedule 抽出，便于「区间交付看板」移入甘特后复用（同一口径）· 用户决策 2026-06-01
function bwdRowsFromPlan(batches: BatchRow[], rooms: RoomRow[], sug: boolean): BwdRow[] {
  const allPodSet = new Set(rooms.flatMap(r => r.pods.map(p => p.id)));
  const podInfo: Record<string, { pod: PodRow; room: RoomRow }> = {};
  rooms.forEach(rm => rm.pods.forEach(p => { podInfo[p.id] = { pod: p, room: rm }; }));
  const maxDate = (ds: (string | null | undefined)[]): string | null => { const v = ds.filter((d): d is string => !!d); return v.length ? v.reduce((a, b) => (a > b ? a : b)) : null; };
  return batches
    .filter(b => b.goLiveDate && b.podIds.some(id => allPodSet.has(id)))
    .map(b => {
      const pods = b.podIds.filter(id => allPodSet.has(id));
      // 整批已到货（PoD 全 arrived、无具体 eta）：到货按上线倒推（−31），不塌到 PROJECT_START
      const allArrived = pods.length > 0 && pods.every(id => podInfo[id]?.pod.arrival === "arrived");
      let arrive: string, room: string;
      if (sug) {
        arrive = bwdShift(b.goLiveDate, -LEAD_LIVE_TO_ARRIVE);
        room = bwdShift(b.goLiveDate, -LEAD_LIVE_TO_ROOM);
      } else {
        arrive = allArrived
          ? bwdShift(b.goLiveDate, -LEAD_LIVE_TO_ARRIVE)
          : (maxDate(pods.map(id => { const p = podInfo[id]?.pod; return p ? (p.etaDate || parseEtaToDate(p.etaLabel)) : null; })) || bwdShift(b.goLiveDate, -LEAD_LIVE_TO_ARRIVE));
        const roomMap: Record<string, RoomRow> = {}; pods.forEach(id => { const rm = podInfo[id]?.room; if (rm) roomMap[rm.code] = rm; });
        room = maxDate(Object.values(roomMap).flatMap(rm => [rm.cableReadyAt, rm.equipReadyAt, rm.liquidReadyAt])) || bwdShift(b.goLiveDate, -LEAD_LIVE_TO_ROOM);
      }
      return { ...b, pods, arrive, room };
    })
    .sort((a, b) => (a.goLiveDate < b.goLiveDate ? -1 : 1));
}

/* ===================== 区间交付看板 · 选时间窗口看「区间内计划交付的 PoD」· 用户决策 2026-06-01（移入甘特顶部）===================== */
// 与 bwd 同轴(复用 axis)；四类批次里程碑(机房就位/到货/上电/上线)按 PoD 数聚合；仅 adjust(given) 显示。
// 注：早先做过「实际 vs 计划」双口径(依赖"今天")，用户 2026-06-01 反馈暂不标注"今天"→ 收为 planned-only，待定真实进度基准再加回。
const RO_CATS: { field: "room" | "arrive" | "powerOnDate" | "goLiveDate"; lab: string; color: string; tone: string }[] = [
  { field: "room",        lab: "机房就位", color: "var(--brand)",  tone: "brand" },
  { field: "arrive",      lab: "到货",     color: "var(--ok)",     tone: "ok" },
  { field: "powerOnDate", lab: "上电",     color: "var(--warn)",   tone: "warn" },
  { field: "goLiveDate",  lab: "上线",     color: "var(--danger)", tone: "danger" },
];
function WindowReadout({ rows, dim, axis, collapsible = false }: { rows: BwdRow[]; dim: "all" | string; axis: { min: string; max: string; span: number }; collapsible?: boolean }) {
  const PAD = 8;
  const xp = (iso: string) => PAD + (bwdDays(iso, axis.min) / axis.span) * (100 - 2 * PAD);
  const clampDate = (d: string) => (d < axis.min ? axis.min : d > axis.max ? axis.max : d);
  const [open, setOpen] = useState(true);   // 甘特里可收起，给甘特让出高度 · 用户决策 2026-06-01
  const [dragEnd, setDragEnd] = useState<"s" | "e" | null>(null);
  const firstLive = rows.reduce((m, r) => (r.goLiveDate < m ? r.goLiveDate : m), rows[0]!.goLiveDate);
  // 默认「至首批上线」——子区间才看得出各动作交付量差异（全区间则四类都满，无区分）
  const [win, setWin] = useState<{ s: string; e: string }>({ s: axis.min, e: clampDate(firstLive) });
  const s = clampDate(win.s), e = clampDate(win.e);

  const presets = [
    { k: "first", lab: "至首批上线", s: axis.min,             e: clampDate(firstLive) },
    { k: "after", lab: "首批之后",   s: clampDate(firstLive), e: axis.max },
    { k: "all",   lab: "全部",       s: axis.min,             e: axis.max },
  ];

  const beginDragWin = (ev: React.MouseEvent, which: "s" | "e") => {
    ev.preventDefault(); ev.stopPropagation();
    const track = (ev.currentTarget as HTMLElement).closest(".ro-track") as HTMLElement | null;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    setDragEnd(which);
    const onMove = (mv: MouseEvent) => {
      const pct = ((mv.clientX - rect.left) / rect.width) * 100;
      const days = Math.round((pct - PAD) / (100 - 2 * PAD) * axis.span);
      const nd = clampDate(bwdShift(axis.min, days));
      setWin(w => which === "s" ? { s: nd <= w.e ? nd : w.e, e: w.e } : { s: w.s, e: nd >= w.s ? nd : w.s });
    };
    const onUp = () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); document.body.style.cursor = ""; document.body.style.userSelect = ""; setDragEnd(null); };
    document.body.style.cursor = "ew-resize"; document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove); window.addEventListener("mouseup", onUp);
  };

  const scope = dim === "all" ? rows : rows.filter(r => r.id === dim);
  // 区间内该动作交付的 PoD id（落入窗口的批次里程碑 → 该批 PoD id）· 用户决策 2026-06-01：数量→ id
  const cats = RO_CATS.map(c => {
    const ids: string[] = [];
    scope.forEach(r => { const d = r[c.field] as string; if (d && d >= s && d <= e) ids.push(...r.pods); });
    ids.sort();
    return { ...c, ids };
  });

  return (
    <div className={"bwd-readout fade" + (collapsible ? " in-gantt" : "") + (open ? "" : " collapsed")}>
      <div className="ro-head">
        {collapsible && <button className="ro-collapse" onClick={() => setOpen(o => !o)} title={open ? "收起看板" : "展开看板"}>{open ? "▾" : "▸"}</button>}
        <span className="ro-title">{I.schedule(15)} 区间交付看板</span>
        <span className="ro-sub">选定窗口内 · 各动作交付的 PoD 编号</span>
        {open && (
          <span className="ro-presets">
            {presets.map(p => (
              <button key={p.k} className={s === p.s && e === p.e ? "on" : ""} onClick={() => setWin({ s: p.s, e: p.e })}>{p.lab}</button>
            ))}
          </span>
        )}
      </div>
      {open && (<>
        <div className="ro-rail">
          <span className="ro-rail-lab">时间窗口</span>
          <div className="ro-track">
            <div className="ro-baseline" />
            <div className="ro-band" style={{ left: xp(s) + "%", width: (xp(e) - xp(s)) + "%" }}>
              <span className={"ro-handle s" + (dragEnd === "s" ? " on" : "")} onMouseDown={ev => beginDragWin(ev, "s")}><i className="ro-handle-date tnum">{bwdMD(s)}</i></span>
              <span className={"ro-handle e" + (dragEnd === "e" ? " on" : "")} onMouseDown={ev => beginDragWin(ev, "e")}><i className="ro-handle-date tnum">{bwdMD(e)}</i></span>
            </div>
          </div>
        </div>
        <div className="ro-cats">
          {cats.map(c => (
            <div className="ro-cat" key={c.field}>
              <span className="ro-cat-lab"><i className="ro-cat-dot" style={{ background: c.color }} />{c.lab}</span>
              <div className="ro-ids">
                {c.ids.length === 0
                  ? <span className="ro-empty">窗口内无</span>
                  : c.ids.map(id => <span className={"ro-id tone-" + c.tone} key={id}>{id}</span>)}
              </div>
              <span className="ro-cat-num"><b className="tnum">{c.ids.length}</b><i className="ro-unit">PoD</i></span>
            </div>
          ))}
        </div>
      </>)}
    </div>
  );
}

function BackwardSchedule({ batches, rooms, updateBatch, onConfirm, variant = "suggest", onPickBatch, showConfirm = true, confirmTitle = "确认上线 / 上电目标", confirmDesc = "系统据此倒推建议到货 / 机房就位，并生成 A / B / C 多策略排期方案", confirmLabel = "确认目标 · 生成排期方案 →", events = [], onAddEvent, onRemoveEvent }: {
  batches: BatchRow[]; rooms: RoomRow[];
  updateBatch: (id: string, patch: Partial<BatchRow>) => void;
  onConfirm: () => void;
  variant?: "suggest" | "given";          // suggest=倒排建议(✦AI) / given=已知(基线)
  onPickBatch?: (idx: number, batch: BwdRow) => void;  // 传入则批次可点 → 开甘特详情
  showConfirm?: boolean;                   // false=倒排直出(init)，不显示确认区
  confirmTitle?: string;
  confirmDesc?: string;
  confirmLabel?: string;
  events?: SchedEvent[];                    // 已注入的意外事件（adjust）
  onAddEvent?: (ev: SchedEventDraft) => void;   // 草稿（无 id）→ PlanBoard 发号
  onRemoveEvent?: (id: string) => void;
}) {
  const sug = variant === "suggest";
  const [dragKey, setDragKey] = useState<string | null>(null); // 正在拖的标记
  const [dim, setDim] = useState<"all" | string>("all");       // 全部 / 单批次 视图切换
  const frozenAxis = useRef<{ min: string; max: string; span: number } | null>(null);

  // 意外事件配置表单（adjust 基线下方）· 用户决策 2026-06-02：2 种类型，每条可填 原因 / 影响时间；效率打折再选档位，可加多条
  const [evDraft, setEvDraft] = useState<SchedEventDraft | null>(null);
  const openEvForm = (kind: "efficiency" | "holiday") => setEvDraft({ kind, ...EVENT_FORM_DEFAULTS[kind] });
  const submitEvForm = () => {
    if (!evDraft || !onAddEvent) return;
    let { start, end } = evDraft;
    if (start > end) { const t = start; start = end; end = t; }   // 起止颠倒则交换，容错
    onAddEvent({
      kind: evDraft.kind,
      label: evDraft.label.trim() || (evDraft.kind === "efficiency" ? "效率打折" : "假期停工"),
      start, end,
      efficiency: evDraft.kind === "holiday" ? 0 : evDraft.efficiency,
    });
    setEvDraft(null);
  };

  // 批次行计算抽到模块级 bwdRowsFromPlan（区间看板移入甘特后两处共用同一口径）· 用户决策 2026-06-01
  const allRows: BwdRow[] = useMemo(() => bwdRowsFromPlan(batches, rooms, sug), [batches, rooms, sug]);

  // given(adjust)：到货 / 机房 ready 冻结在基线快照——拖「上电 / 上线」目标只动该旗，不联动它们；
  // 再排期(组件重挂载)时按新结果刷新 · 用户决策 2026-05-31。suggest(init)保持实时倒推。
  const baseRef = useRef<Record<string, { arrive: string; room: string }> | null>(null);
  if (!sug && baseRef.current === null && allRows.length) {
    const snap: Record<string, { arrive: string; room: string }> = {};
    allRows.forEach(r => { snap[r.id] = { arrive: r.arrive, room: r.room }; });
    baseRef.current = snap;
  }
  const dispRows: BwdRow[] = sug ? allRows : allRows.map(r => { const f = baseRef.current?.[r.id]; return f ? { ...r, arrive: f.arrive, room: f.room } : r; });

  const liveAxis = useMemo(() => axisOf(dispRows), [dispRows]);
  const axis = frozenAxis.current || liveAxis;
  const PAD = 8;
  const x = (iso: string) => PAD + (bwdDays(iso, axis.min) / axis.span) * (100 - 2 * PAD);

  // 全部 / 单批次 视图过滤（轴仍按全部批次算，保证位置一致）
  useEffect(() => { if (dim !== "all" && !allRows.some(r => r.id === dim)) setDim("all"); }, [allRows, dim]);
  const rows = dim === "all" ? dispRows : dispRows.filter(r => r.id === dim);

  if (allRows.length === 0)
    return (
      <div className="bwd-empty fade">
        <span className="bwd-ei">{I.schedule(30)}</span>
        <p>暂无可排的批次 — 在右侧「批次」tab 设上线目标并分配 PoD，系统即按上线目标算出建议到货 / 机房就位时间。</p>
      </div>
    );

  const firstArrive = dispRows.reduce((m, r) => (r.arrive < m ? r.arrive : m), dispRows[0]!.arrive);
  const firstRoom = dispRows.reduce((m, r) => (r.room < m ? r.room : m), dispRows[0]!.room);
  const lastLive = dispRows.reduce((m, r) => (r.goLiveDate > m ? r.goLiveDate : m), dispRows[0]!.goLiveDate);

  // ② 拖动 上电/上线 红旗 → 改 batch 日期 → 建议（到货/机房ready）实时倒推
  const beginDrag = (e: React.MouseEvent, row: BwdRow, field: "powerOnDate" | "goLiveDate") => {
    e.preventDefault(); e.stopPropagation();
    const trackEl = (e.currentTarget as HTMLElement).closest(".bwd-track") as HTMLElement | null;
    if (!trackEl) return;
    const rect = trackEl.getBoundingClientRect();
    const pxPerDay = (rect.width * (100 - 2 * PAD) / 100) / axis.span;
    const startX = e.clientX;
    const startDate = (row[field] as string) || row.goLiveDate;
    frozenAxis.current = liveAxis;
    setDragKey(row.id + field);
    const onMove = (mv: MouseEvent) => {
      const delta = Math.round((mv.clientX - startX) / pxPerDay);
      let nd = bwdShift(startDate, delta);
      if (field === "goLiveDate") {
        const lo = row.powerOnDate ? bwdShift(row.powerOnDate, 1) : SCHED_TODAY;
        if (nd < lo) nd = lo;
      } else {
        if (nd < SCHED_TODAY) nd = SCHED_TODAY;
        const hi = bwdShift(row.goLiveDate, -1);
        if (nd > hi) nd = hi;
      }
      updateBatch(row.id, { [field]: nd });
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = ""; document.body.style.userSelect = "";
      frozenAxis.current = null; setDragKey(null);
    };
    document.body.style.cursor = "ew-resize"; document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div className="bwd">
      {/* 倒排说明条 · gap-banner 的镜像：右端给定目标 → 向左反推建议 */}
      <div className="bwd-banner fade">
        <div className={"bwd-bx" + (sug ? " sug" : "")}><div className="lab">机房最晚 ready</div><div className="val">{bwdMD(firstRoom)}</div></div>
        <div className={"bwd-bx" + (sug ? " sug" : "")}><div className="lab">货最晚到</div><div className="val">{bwdMD(firstArrive)}</div></div>
        <div className="bwd-mid"><span className="bwd-arrow">←</span><div className="gd">上线前置期 · {LEAD_LIVE_TO_ARRIVE} 天</div></div>
        <div className="bwd-bx goal"><div className="lab">{sug ? "最迟上线目标 · 给定" : "最迟上线目标"}</div><div className="val">{bwdMD(lastLive)}</div></div>
      </div>

      <div className="bwd-chart fade">
        <div className="bwd-chart-head">
          <div className="bch-titles">
            <div className="bch-title">{I.schedule(15)}<span>{sug ? "上线目标 · 倒推就位建议" : "当前基线排期 · 计划调整"}</span></div>
            <div className="bch-sub">{I.spark(11)} {sug
              ? "拖「上电 / 上线」红旗调整目标，建议实时倒推；点批次查看排期详情"
              : "拖「上电 / 上线」红旗调整目标、注入意外事件，确认后由 Agent 重排"}</div>
          </div>
          <div className="bwd-seg">
            <button className={dim === "all" ? "on" : ""} onClick={() => setDim("all")}>全部</button>
            {allRows.map((r, i) => (
              <button key={r.id} className={dim === r.id ? "on" : ""} onClick={() => setDim(r.id)}
                style={dim === r.id ? { background: r.color, borderColor: r.color, color: "var(--on-brand)" } : undefined}>批次 {i + 1}</button>
            ))}
          </div>
        </div>
        {rows.map((r, ri) => {
          const i = dispRows.findIndex(rr => rr.id === r.id);
          return (
          <div className="bwd-row" key={r.id} style={{ transitionDelay: ri * 90 + "ms" }}>
            <span className={"bwd-name" + (onPickBatch ? " clickable" : "")}
              onClick={onPickBatch ? () => onPickBatch(i, r) : undefined}
              title={onPickBatch ? "查看该批次排期详情" : undefined}>
              <i style={{ background: r.color }} /><b>批次 {i + 1}</b><span className="bwd-pods">{r.pods.length} PoD</span>
            </span>
            <div className="bwd-track">
              <div className="bwd-lead" style={{ left: x(r.room) + "%", width: (x(r.goLiveDate) - x(r.room)) + "%", background: r.color }} />
              <BwdMk x={x(r.room)} cls="mk-room" lab={sug ? "建议机房 ready" : "机房 ready"} date={bwdMD(r.room)} sug={sug} below />
              <BwdMk x={x(r.arrive)} cls="mk-arrive" lab={sug ? "建议到货" : "到货"} date={bwdMD(r.arrive)} sug={sug} />
              {r.powerOnDate && <BwdMk x={x(r.powerOnDate)} cls="mk-power" lab="上电目标" date={bwdMD(r.powerOnDate)} below flag
                draggable dragging={dragKey === r.id + "powerOnDate"} onGrab={(e) => beginDrag(e, r, "powerOnDate")} />}
              <BwdMk x={x(r.goLiveDate)} cls="mk-live" lab="上线目标" date={bwdMD(r.goLiveDate)} big color={r.color} flag
                draggable dragging={dragKey === r.id + "goLiveDate"} onGrab={(e) => beginDrag(e, r, "goLiveDate")} />
            </div>
            {onPickBatch && <button className="bwd-open" onClick={() => onPickBatch(i, r)}>排期详情 →</button>}
          </div>
          );
        })}
      </div>

      {/* 区间交付看板已移到「排期详情」甘特顶部（见 GanttDetailOverlay）· 用户决策 2026-06-01 */}

      {/* 意外事件入口（adjust）：可配置 2 种类型(效率打折/假期停工)，每条填 原因/影响时间，效率打折选档 → 影响排期 · 用户决策 2026-06-02 */}
      {!sug && onAddEvent && (
        <div className="bwd-events fade">
          <div className="be-head">
            <div className="be-titles">
              <div className="be-title">{I.warn(15)}<span>意外事件 · 影响排期</span></div>
              <div className="be-sub">配置突发事件（效率打折 / 假期停工 · 可填原因与影响时间），确认重排时纳入影响、甘特高亮受影响活动</div>
            </div>
            <div className="be-add">
              <button className={"be-add-btn eff" + (evDraft?.kind === "efficiency" ? " active" : "")}
                onClick={() => openEvForm("efficiency")} title="效率打折：窗口内产能按比例下降（如台风 / 高温限电）">
                {I.warn(13)} ＋ 效率打折
              </button>
              <button className={"be-add-btn hol" + (evDraft?.kind === "holiday" ? " active" : "")}
                onClick={() => openEvForm("holiday")} title="假期停工：机房不开放、窗口内无法施工（如国庆 / 春节）">
                {I.cal(13)} ＋ 假期停工
              </button>
            </div>
          </div>

          {/* 配置表单（点类型按钮展开）· 用户决策 2026-06-02 */}
          {evDraft && (
            <div className={"be-form " + evDraft.kind}>
              <div className="be-form-h">
                {evDraft.kind === "efficiency" ? I.warn(13) : I.cal(13)}
                <b>新增 · {evDraft.kind === "efficiency" ? "效率打折" : "假期停工"}</b>
                <span>{evDraft.kind === "efficiency" ? "窗口内产能按比例下降，工期相应拉长" : "窗口内机房停工、不可施工（效率 0），工期顺延"}</span>
              </div>
              <div className="be-form-body">
                <label className="be-fld">
                  <span className="be-fld-lab">原因</span>
                  <input className="be-input" type="text" value={evDraft.label} maxLength={16}
                    placeholder={evDraft.kind === "efficiency" ? "如：台风登陆 / 高温限电" : "如：国庆假期 / 春节"}
                    onChange={e => setEvDraft(d => d && { ...d, label: e.target.value })} />
                </label>
                <label className="be-fld">
                  <span className="be-fld-lab">影响时间</span>
                  <span className="be-dates">
                    <input className="be-date" type="date" min={PROJECT_START} max="2026-12-31" value={evDraft.start}
                      onChange={e => setEvDraft(d => d && { ...d, start: e.target.value })} />
                    <i>~</i>
                    <input className="be-date" type="date" min={PROJECT_START} max="2026-12-31" value={evDraft.end}
                      onChange={e => setEvDraft(d => d && { ...d, end: e.target.value })} />
                  </span>
                </label>
                {evDraft.kind === "efficiency" && (
                  <div className="be-fld">
                    <span className="be-fld-lab">效率</span>
                    <span className="be-eff">
                      {EFF_PRESETS.map(v => (
                        <button key={v} className={"be-eff-btn" + (Math.abs(evDraft.efficiency - v) < 1e-9 ? " on" : "")}
                          onClick={() => setEvDraft(d => d && { ...d, efficiency: v })}>{Math.round(v * 100)}%</button>
                      ))}
                      <span className="be-eff-custom">自定义
                        <input type="number" min={1} max={99} value={Math.round(evDraft.efficiency * 100)}
                          onChange={e => { const p = Math.min(99, Math.max(1, Math.round(Number(e.target.value) || 0))); setEvDraft(d => d && { ...d, efficiency: p / 100 }); }} />
                        <i>%</i>
                      </span>
                    </span>
                  </div>
                )}
              </div>
              <div className="be-form-act">
                <button className="be-cancel" onClick={() => setEvDraft(null)}>取消</button>
                <button className={"be-submit " + evDraft.kind} onClick={submitEvForm}>{I.check(13)} 添加意外事件</button>
              </div>
            </div>
          )}

          <div className="be-list">
            {events.length === 0
              ? <div className="be-empty">暂无意外事件 · 排期按计划推进</div>
              : events.map(ev => (
                <div className={"be-chip " + ev.kind} key={ev.id}>
                  <span className="be-chip-ic">{ev.kind === "efficiency" ? I.warn(13) : I.cal(13)}</span>
                  <span className="be-chip-main">
                    <b>{ev.label}</b>
                    <i>{ev.kind === "efficiency" ? "效率降至 " + Math.round(ev.efficiency * 100) + "%" : "机房停工"} · {ev.start.slice(5)}~{ev.end.slice(5)}</i>
                  </span>
                  <button className="be-chip-del" onClick={() => onRemoveEvent && onRemoveEvent(ev.id)} title="移除">×</button>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className="bwd-foot fade">
        <span><i className={sug ? "sug" : "given"} />{sug ? "AI 建议（货到 / 机房就位）" : "已知（货到 / 机房就位）"}</span>
        <span><i className="given" />{sug ? "给定目标（上电 / 上线）" : "目标（上电 / 上线）"}</span>
        <span className="bwd-tip">{sug ? "拖红旗或改右侧「批次」tab → 建议实时重算" : "拖红旗调整目标 → 点「调整推演」重新计算方案"}</span>
      </div>

      {/* 确认目标 → 生成多策略方案（init 倒排直出，showConfirm=false 时不显示） */}
      {showConfirm && (
        <div className="bwd-confirm fade">
          <div className="bwd-confirm-txt">
            <b>{confirmTitle}</b>
            <span>{confirmDesc}</span>
          </div>
          <button className="bwd-confirm-btn" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      )}
    </div>
  );
}

/* ===================== 排期计算 · 思考过程（确认 → 方案 之间的 AI 可解释）===================== */
// 思考步骤：adjust 多策略(ABC) / init 首次排期(标准 SLA → 就位建议，不出现"正排/倒排"字样)
const THINK_STEPS_ABC = [
  { t: "解析约束链", d: "上线 / 上电目标 → 倒推到货 / 机房就位窗口" },
  { t: "识别压缩着力点", d: "标记受人数约束的弹性活动（可加人压缩）" },
  { t: "多策略寻优", d: "均摊 / TopK极限 / 货期提拉 三条路径并行试算" },
  { t: "生成 A / B / C 方案", d: "按工期、增员、风险三维择优排序" },
];
const THINK_STEPS_SUGGEST = [
  { t: "解析人货站约束", d: "读取机房、PoD、队伍与上线 / 上电目标" },
  { t: "按标准 SLA 推算", d: "用标准活动工期，从上线目标推算各批次窗口" },
  { t: "校核资源与依赖", d: "检查队伍产能与活动先后顺序是否冲突" },
  { t: "生成就位建议", d: "给出每批次 建议机房 ready / 建议到货时间" },
];
function ScheduleThinking({ onDone, steps = THINK_STEPS_ABC, title = "AIDA 正在排期计算…" }: { onDone: () => void; steps?: { t: string; d: string }[]; title?: string }) {
  const STEPS = steps;
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (step >= STEPS.length) { const t = setTimeout(onDone, 460); return () => clearTimeout(t); }
    const t = setTimeout(() => setStep(s => s + 1), 540);
    return () => clearTimeout(t);
  }, [step]);
  return (
    <div className="sched-think fade">
      <div className="st-orb"><span className="st-core">{I.spark(20)}</span><span className="st-ring" /><span className="st-ring r2" /></div>
      <div className="st-title">{title}</div>
      <div className="st-steps">
        {STEPS.map((s, i) => (
          <div className={"st-step " + (i < step ? "done" : i === step ? "active" : "")} key={i}>
            <span className="st-ic">{i < step ? I.check(13) : i === step ? <span className="st-spin" /> : <span className="st-wait" />}</span>
            <span className="st-tx"><b>{s.t}</b><span>{s.d}</span></span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ===================== ④ 甘特排期详情 · 全屏覆盖层 =====================
   用户决策 2026-05-30：从选定 ABC 方案「查看排期详情」进入；移植 07 甘特原型的 CPM 级联
   （拖耗时 → 依赖向后顺延 → 末批上线 / 整体交付实时位移）+ 内联改天数 + 依赖线 + 关键路径。
   数据对齐 planinit：单项目 6 机房 / 12 PoD / 3 上线批。保存 = 写回系统（mock）。 */
const GD = {
  parse: (s: string) => new Date(s + "T00:00:00Z"),
  iso: (dt: Date) => dt.toISOString().slice(0, 10),
  add: (dt: Date, n: number) => { const x = new Date(dt); x.setUTCDate(x.getUTCDate() + n); return x; },
  diff: (a: string | Date, b: string | Date) =>
    Math.round(((typeof b === "string" ? GD.parse(b) : b).getTime() - (typeof a === "string" ? GD.parse(a) : a).getTime()) / 86400000),
  between: (a: string, b: string) => GD.diff(a, b) + 1,
  weekend: (dt: Date) => { const d = dt.getUTCDay(); return d === 0 || d === 6; },
};
// 阶段色引用 .planinit 局部 token（定义见 planinit.css，与全局语义对齐）· R3 ②
const GD_PHASES = [
  { key: "plan",    name: "规划采购", color: "var(--gd-plan)" },
  { key: "dc",      name: "机房改造", color: "var(--gd-dc)" },
  { key: "goods",   name: "设备到货", color: "var(--gd-goods)" },
  { key: "install", name: "上架布线", color: "var(--gd-install)" },
  { key: "power",   name: "上电联调", color: "var(--gd-power)" },
  { key: "accept",  name: "验收交付", color: "var(--gd-accept)" },
];
type GdAct = { id: string; phase: string; name: string; batch: string; start: string; end: string; deps: string[]; progress: number; milestone?: boolean };
type GdPhase = typeof GD_PHASES[number];
type GdRow = { type: "phase"; phase: GdPhase; items: GdAct[] } | { type: "task"; a: GdAct };
const GD_ACTS: GdAct[] = [
  { id: "G00", phase: "plan", name: "项目立项 · 采购冻结",       batch: "—", start: "2026-06-01", end: "2026-06-08", deps: [], progress: 1 },
  { id: "G01", phase: "plan", name: "长周期物料下单 (GPU/光模块)", batch: "—", start: "2026-06-08", end: "2026-06-16", deps: ["G00"], progress: 1 },
  // 批1（上线 08-20）
  { id: "B1D", phase: "dc",      name: "机房改造与验收 · 批1", batch: "批1", start: "2026-06-16", end: "2026-07-08", deps: ["G00"], progress: .6 },
  { id: "B1A", phase: "goods",   name: "设备到货齐套 · 批1",   batch: "批1", start: "2026-07-04", end: "2026-07-20", deps: ["G01"], progress: .3 },
  { id: "B1I", phase: "install", name: "机柜上架安装 · 批1",   batch: "批1", start: "2026-07-20", end: "2026-08-02", deps: ["B1D", "B1A"], progress: 0 },
  { id: "B1C", phase: "install", name: "综合布线 · 批1",       batch: "批1", start: "2026-07-30", end: "2026-08-08", deps: ["B1I"], progress: 0 },
  { id: "B1P", phase: "power",   name: "上电点亮 · 批1",       batch: "批1", start: "2026-08-08", end: "2026-08-12", deps: ["B1C"], progress: 0 },
  { id: "B1U", phase: "power",   name: "系统联调测试 · 批1",   batch: "批1", start: "2026-08-12", end: "2026-08-19", deps: ["B1P"], progress: 0 },
  { id: "B1G", phase: "power",   name: "批次1 上线",           batch: "批1", start: "2026-08-20", end: "2026-08-20", deps: ["B1U"], progress: 0, milestone: true },
  // 批2（上线 09-05）
  { id: "B2D", phase: "dc",      name: "机房改造与验收 · 批2", batch: "批2", start: "2026-07-01", end: "2026-07-24", deps: ["G00"], progress: .35 },
  { id: "B2A", phase: "goods",   name: "设备到货齐套 · 批2",   batch: "批2", start: "2026-07-18", end: "2026-08-04", deps: ["G01"], progress: .1 },
  { id: "B2I", phase: "install", name: "机柜上架安装 · 批2",   batch: "批2", start: "2026-08-04", end: "2026-08-17", deps: ["B2D", "B2A"], progress: 0 },
  { id: "B2C", phase: "install", name: "综合布线 · 批2",       batch: "批2", start: "2026-08-14", end: "2026-08-23", deps: ["B2I"], progress: 0 },
  { id: "B2P", phase: "power",   name: "上电点亮 · 批2",       batch: "批2", start: "2026-08-23", end: "2026-08-27", deps: ["B2C"], progress: 0 },
  { id: "B2U", phase: "power",   name: "系统联调测试 · 批2",   batch: "批2", start: "2026-08-27", end: "2026-09-04", deps: ["B2P"], progress: 0 },
  { id: "B2G", phase: "power",   name: "批次2 上线",           batch: "批2", start: "2026-09-05", end: "2026-09-05", deps: ["B2U"], progress: 0, milestone: true },
  // 批3（上线 09-20，关键路径）
  { id: "B3D", phase: "dc",      name: "机房改造与验收 · 批3", batch: "批3", start: "2026-07-14", end: "2026-08-08", deps: ["G00"], progress: .1 },
  { id: "B3A", phase: "goods",   name: "设备到货齐套 · 批3",   batch: "批3", start: "2026-08-02", end: "2026-08-19", deps: ["G01"], progress: 0 },
  { id: "B3I", phase: "install", name: "机柜上架安装 · 批3",   batch: "批3", start: "2026-08-19", end: "2026-09-01", deps: ["B3D", "B3A"], progress: 0 },
  { id: "B3C", phase: "install", name: "综合布线 · 批3",       batch: "批3", start: "2026-08-29", end: "2026-09-07", deps: ["B3I"], progress: 0 },
  { id: "B3P", phase: "power",   name: "上电点亮 · 批3",       batch: "批3", start: "2026-09-07", end: "2026-09-11", deps: ["B3C"], progress: 0 },
  { id: "B3U", phase: "power",   name: "系统联调测试 · 批3",   batch: "批3", start: "2026-09-11", end: "2026-09-19", deps: ["B3P"], progress: 0 },
  { id: "B3G", phase: "power",   name: "批次3 上线",           batch: "批3", start: "2026-09-20", end: "2026-09-20", deps: ["B3U"], progress: 0, milestone: true },
  // 整体验收交付
  { id: "G99", phase: "accept",  name: "客户整体验收交付", batch: "—", start: "2026-09-20", end: "2026-09-26", deps: ["B3U"], progress: 0 },
  { id: "G98", phase: "accept",  name: "整体交付里程碑",   batch: "—", start: "2026-09-26", end: "2026-09-26", deps: ["G99"], progress: 0, milestone: true },
];
const GD_CRIT = new Set(["G00", "G01", "B3A", "B3I", "B3C", "B3P", "B3U", "B3G", "G99", "G98"]);
const gdPhase = (k: string) => GD_PHASES.find(p => p.key === k) || GD_PHASES[0]!;

/* ===================== 意外事件（效率打折 / 假期停工）· 用户决策 2026-06-01；2026-06-02 改可配置 =====================
   从「当前基线」处配置注入 → 影响甘特 CPM（efficiency=窗口内产能系数：停工 0 / 降效 0~1） → 受影响活动/批次高亮。
   事件是**时间窗口**扰动，作用于窗口内**实际在施工**的活动（甘特按 eff 动态判定）：8 月降效推迟工期、10 月停工再咬住被推迟的尾段。
   2026-06-02：由「2 预置一键注入」改为**可配置表单**——2 种类型(效率打折/假期停工)，每条可填 原因 / 影响时间，效率打折再选档位，可加多条。 */
type SchedEvent = { id: string; kind: "efficiency" | "holiday"; label: string; start: string; end: string; efficiency: number };
type SchedEventDraft = { kind: "efficiency" | "holiday"; label: string; start: string; end: string; efficiency: number };
// 表单预填默认（仍复现经典级联：效率打折→台风 8 月减半 / 假期停工→国庆 10 月停工），均可改 · 用户决策 2026-06-02
const EVENT_FORM_DEFAULTS: Record<"efficiency" | "holiday", { label: string; start: string; end: string; efficiency: number }> = {
  efficiency: { label: "台风登陆", start: "2026-08-15", end: "2026-08-25", efficiency: 0.5 },
  holiday:    { label: "国庆假期", start: "2026-10-01", end: "2026-10-07", efficiency: 0 },
};
const EFF_PRESETS = [0.75, 0.5, 0.25];  // 效率打折固定档（75/50/25），另支持自定义 1~99%
// 受影响高亮**只在排期推演完成后**呈现（甘特 affectedActs，按 eff 动态判定）· 用户决策 2026-06-02
// 基线「新增调整需求」阶段不再预判受影响批次（原 affectedBatchSet 已删）。

function GanttDetailOverlay({ title, backLabel = "← 返回", onClose, onSaved, batches, rooms, events }: { title: string; backLabel?: string; onClose: () => void; onSaved: () => void; batches: BatchRow[]; rooms: RoomRow[]; events: SchedEvent[] }) {
  // 区间交付看板（移入甘特顶部）：批次基线行 given + 轴 · 用户决策 2026-06-01
  const roRows = useMemo(() => bwdRowsFromPlan(batches, rooms, false), [batches, rooms]);
  const roAxis = useMemo(() => axisOf(roRows), [roRows]);
  const [durations, setDurations] = useState<Record<string, number>>({});
  const [dragPreview, setDragPreview] = useState<{ id: string; days: number } | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [showDeps, setShowDeps] = useState(true);
  const [showCrit, setShowCrit] = useState(true);
  // 意外事件由「当前基线」处注入 → props.events（甘特只渲染影响）；跳周末仍是甘特本地开关 · 用户决策 2026-06-01
  const [skipWeekends, setSkipWeekends] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const ganttRowRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const dayW = 16, ROW_H = 34, HEADER = 36;

  const range = useMemo(() => {
    const starts = GD_ACTS.map(a => a.start), ends = GD_ACTS.map(a => a.end);
    const min = starts.reduce((m, d) => (d < m ? d : m), starts[0]!);
    const max = ends.reduce((m, d) => (d > m ? d : m), ends[0]!);
    const start = GD.add(GD.parse(min), -4);
    const days = GD.diff(start, GD.add(GD.parse(max), 8)) + 1;
    return { start, days };
  }, []);

  const base = useMemo(() => {
    const start: Record<string, string> = {}, end: Record<string, string> = {}, dur: Record<string, number> = {}, lag: Record<string, number | null> = {};
    GD_ACTS.forEach(a => { start[a.id] = a.start; end[a.id] = a.end; dur[a.id] = a.milestone ? 0 : GD.between(a.start, a.end); });
    GD_ACTS.forEach(a => {
      if (!a.deps.length) { lag[a.id] = null; return; }
      let mx: Date | null = null; a.deps.forEach(d => { const e = GD.parse(end[d]!); if (!mx || e > mx) mx = e; });
      lag[a.id] = GD.diff(GD.add(mx!, 1), GD.parse(a.start));
    });
    return { start, end, dur, lag };
  }, []);

  const eff = useMemo(() => {
    const start: Record<string, string> = {}, end: Record<string, string> = {}, dur: Record<string, number> = {};
    const getDur = (id: string): number => dragPreview && dragPreview.id === id ? dragPreview.days : (durations[id] != null ? durations[id] : base.dur[id]!);
    // 工作日历 → 每日产能系数 factor∈[0,1]：事件按**时间窗口**作用于当天所有在施工活动（停工=0 / 降效=比例）、否则 1；跳周末=0。
    // 活动按 factor 累计工作量 → factor<1 拉长、factor=0 暂停顺延、下游级联（factor 全 1 时与旧整数步进等价）· 用户决策 2026-06-01 晚2
    const dayFactor = (dt: Date) => {
      if (skipWeekends && GD.weekend(dt)) return 0;
      const iso = GD.iso(dt);
      let f = 1;
      events.forEach(ev => { if (iso >= ev.start && iso <= ev.end) f = Math.min(f, ev.efficiency); });
      return f;
    };
    const firstWork = (dt: Date) => { let x = dt, g = 0; while (dayFactor(x) <= 0 && g++ < 600) x = GD.add(x, 1); return x; };
    const workEnd = (s: string, d: number) => { let dt = firstWork(GD.parse(s)), acc = 0, g = 0; while (g++ < 2000) { acc += dayFactor(dt); if (acc >= d - 1e-9) return GD.iso(dt); dt = GD.add(dt, 1); } return GD.iso(dt); };
    const compute = (a: GdAct) => {
      const d = getDur(a.id); let s: string;
      if (!a.deps.length || base.lag[a.id] === null) { s = base.start[a.id]!; }
      else { let mx: Date | null = null; a.deps.forEach(dep => { const e = GD.parse(end[dep] || base.end[dep]!); if (!mx || e > mx) mx = e; }); s = GD.iso(GD.add(mx!, 1 + base.lag[a.id]!)); }
      s = GD.iso(firstWork(GD.parse(s)));
      start[a.id] = s; dur[a.id] = d; end[a.id] = a.milestone ? s : workEnd(s, d);
    };
    for (let p = 0; p < 6; p++) GD_ACTS.forEach(compute);
    return { start, end, dur };
  }, [durations, dragPreview, base, events, skipWeekends]);

  // 受影响活动（动态）：eff 执行期与任一事件窗口重叠 → 高亮 · 用户决策 2026-06-01 晚2
  const affectedActs = useMemo(() => {
    const s = new Set<string>();
    if (!events.length) return s;
    GD_ACTS.forEach(a => { if (a.milestone) return; const as = eff.start[a.id] || a.start, ae = eff.end[a.id] || a.end; if (events.some(ev => as <= ev.end && ae >= ev.start)) s.add(a.id); });
    return s;
  }, [events, eff]);

  const rows = useMemo<GdRow[]>(() => {
    const out: GdRow[] = [];
    GD_PHASES.forEach(ph => {
      const items = GD_ACTS.filter(a => a.phase === ph.key);
      if (!items.length) return;
      out.push({ type: "phase", phase: ph, items });
      items.forEach(a => out.push({ type: "task", a }));
    });
    return out;
  }, []);
  const rowIndex = (id: string) => rows.findIndex(r => r.type === "task" && r.a.id === id);

  const focusGanttAct = useCallback((id: string) => {
    setSel(id);
    requestAnimationFrame(() => {
      ganttRowRefs.current[id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      const canvas = canvasRef.current;
      const act = GD_ACTS.find((x) => x.id === id);
      if (!canvas || !act) return;
      const s = GD.diff(range.start, GD.parse(eff.start[act.id] || act.start));
      const e = GD.diff(range.start, GD.parse(eff.end[act.id] || act.end));
      const left = s * dayW;
      const width = Math.max((e - s + 1) * dayW, dayW);
      canvas.scrollLeft = Math.max(0, left + width / 2 - canvas.clientWidth / 2);
      const idx = rowIndex(id);
      if (idx >= 0 && listRef.current) {
        const top = HEADER + idx * ROW_H;
        const viewH = listRef.current.clientHeight;
        const target = Math.max(0, top - viewH / 2 + ROW_H / 2);
        listRef.current.scrollTop = target;
        canvas.scrollTop = target;
      }
    });
  }, [eff, range, dayW]);

  const barRect = (a: GdAct) => {
    const s = GD.diff(range.start, GD.parse(eff.start[a.id] || a.start));
    const e = GD.diff(range.start, GD.parse(eff.end[a.id] || a.end));
    return { left: s * dayW, width: Math.max((e - s + 1) * dayW, dayW) };
  };

  const months = useMemo(() => {
    const out: { label: string; days: number }[] = []; let cur = new Date(range.start); let mStart = 0;
    const endDate = GD.add(range.start, range.days - 1);
    while (cur <= endDate) {
      const next = new Date(Date.UTC(cur.getUTCFullYear(), cur.getUTCMonth() + 1, 1));
      const endIdx = Math.min(GD.diff(range.start, next), range.days);
      out.push({ label: (cur.getUTCMonth() + 1) + "月", days: endIdx - mStart });
      mStart = endIdx; cur = next;
    }
    return out;
  }, [range]);

  const depPaths = useMemo(() => {
    if (!showDeps) return [];
    const out: { d: string; crit: boolean; key: string }[] = [];
    GD_ACTS.forEach(a => {
      const ri = rowIndex(a.id); if (ri < 0) return;
      a.deps.forEach(dep => {
        const di = rowIndex(dep); if (di < 0) return;
        const fr = barRect(GD_ACTS.find(x => x.id === dep)!), to = barRect(a);
        const x1 = fr.left + fr.width, y1 = HEADER + di * ROW_H + ROW_H / 2;
        const x2 = to.left, y2 = HEADER + ri * ROW_H + ROW_H / 2;
        const midX = Math.max(x1 + 4, x2 - 7);
        out.push({ d: `M${x1} ${y1} L${midX} ${y1} L${midX} ${y2} L${x2 - 2} ${y2}`, crit: GD_CRIT.has(dep) && GD_CRIT.has(a.id), key: dep + "-" + a.id });
      });
    });
    return out;
  }, [showDeps, eff, rows]);

  const beginDrag = (e: React.MouseEvent, a: GdAct) => {
    e.stopPropagation(); e.preventDefault(); if (a.milestone) return;
    const startX = e.clientX, startDays = eff.dur[a.id]!; let cur = startDays;
    const onMove = (mv: MouseEvent) => { cur = Math.max(1, startDays + Math.round((mv.clientX - startX) / dayW)); setDragPreview({ id: a.id, days: cur }); };
    const onUp = () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); document.body.style.cursor = ""; document.body.style.userSelect = ""; if (cur !== startDays) setDurations(d => ({ ...d, [a.id]: cur })); setDragPreview(null); };
    document.body.style.cursor = "ew-resize"; document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove); window.addEventListener("mouseup", onUp);
  };
  const commitDur = (id: string, val: string) => { const n = Math.max(1, Math.round(Number(val) || 0)); if (n > 0) setDurations(d => ({ ...d, [id]: n })); setEditing(null); };

  const baseGo = base.start["B3G"]!, projGo = eff.start["B3G"] || baseGo;
  const goDelta = GD.diff(baseGo, projGo);
  const projAccept = eff.start["G98"] || base.start["G98"]!;
  const modCount = Object.keys(durations).length;
  const gdDirty = modCount > 0 || skipWeekends;  // 做了调整(改工期/跳周末)才显「取消 / 保存并写回」（意外事件在基线处管理）· 用户决策 2026-06-01
  const canvasW = range.days * dayW, canvasH = HEADER + rows.length * ROW_H;
  const todayLeft = GD.diff(range.start, PROJECT_START) * dayW + dayW / 2;

  return (
    <div className="gd-panel gd-inline">
        <div className="gd-head">
          <div className="gd-head-l">
            <button className="gd-back" onClick={onClose}>{backLabel}</button>
            <div className="gd-title">{I.schedule(16)} 排期详情 · <b>{title}</b></div>
            <span className="gd-sub">单项目 · {BATCH.rooms} 机房 / {BATCH.pods} PoD / {INITIAL_BATCHES.length} 批 · 拖活动条右端或点天数改工期,下游自动顺延</span>
          </div>
          <div className="gd-head-r">
            {modCount > 0 && <button className="gd-btn" onClick={() => setDurations({})}>重置 {modCount} 项</button>}
            {gdDirty && <button className="gd-btn" onClick={onClose}>取消</button>}
            {gdDirty && <button className="gd-btn pri" onClick={onSaved}>{I.check(13)} 保存并写回</button>}
          </div>
        </div>

        <div className="gd-kpis">
          <div className={"gd-kpi" + (goDelta > 0 ? " late" : goDelta < 0 ? " early" : "")}>
            <div className="gd-kpi-l">末批上线 · 预计</div>
            <div className="gd-kpi-v">{projGo.slice(5)}</div>
            <div className="gd-kpi-d">{goDelta === 0 ? "= 基线 09-20" : (goDelta > 0 ? `晚 ${goDelta} 天` : `早 ${-goDelta} 天`)} · 目标 09-20</div>
          </div>
          <div className="gd-kpi">
            <div className="gd-kpi-l">整体交付 · 预计</div>
            <div className="gd-kpi-v">{projAccept.slice(5)}</div>
            <div className="gd-kpi-d">客户整体验收完成</div>
          </div>
          <div className={"gd-kpi" + (showCrit ? " gd-kpi-crit-on" : "")}>
            <div className="gd-kpi-l">关键路径</div>
            <div className="gd-kpi-v">{GD_CRIT.size}<span className="u"> 节点</span></div>
            <div className="gd-kpi-d">{showCrit ? "批次3 链路最紧 · 下方时间轴已展开" : "勾选右侧「关键路径」展开时间轴"}</div>
          </div>
          <div className="gd-kpi">
            <div className="gd-kpi-l">已改工期</div>
            <div className="gd-kpi-v">{modCount}<span className="u"> 项</span></div>
            <div className="gd-kpi-d">{modCount > 0 ? "下游已级联重算" : "拖动活动条试试"}</div>
          </div>
          <div className="gd-toolbar">
            <label><input type="checkbox" checked={showDeps} onChange={e => setShowDeps(e.target.checked)} /> 依赖线</label>
            <label><input type="checkbox" checked={showCrit} onChange={e => setShowCrit(e.target.checked)} /> 关键路径</label>
            <label><input type="checkbox" checked={skipWeekends} onChange={e => setSkipWeekends(e.target.checked)} /> 跳周末</label>
          </div>
        </div>

        <CriticalPathTimeline
          acts={GD_ACTS}
          eff={eff}
          base={base}
          diff={GD.diff}
          visible={showCrit}
          selectedId={sel}
          onSelectNode={focusGanttAct}
        />

        {/* 意外事件影响 · 只读摘要（增删在「当前基线」处的意外事件入口）· 用户决策 2026-06-01 */}
        {events.length > 0 && (
          <div className="gd-exc-bar readonly">
            <span className="gd-exc-ic">{I.warn(13)} 意外事件影响 · {events.length}</span>
            {events.map(ev => {
              const n = GD_ACTS.filter(a => !a.milestone && (eff.start[a.id] || a.start) <= ev.end && (eff.end[a.id] || a.end) >= ev.start).length;
              return (
                <span className={"gd-evchip " + ev.kind} key={ev.id} title={ev.label + " · 在「当前基线」处增删"}>
                  <i />{ev.kind === "efficiency" ? "效率降至 " + Math.round(ev.efficiency * 100) + "%" : "机房停工"} · {ev.label} · {ev.start.slice(5)}~{ev.end.slice(5)} · {n} 活动
                </span>
              );
            })}
            <span className="gd-exc-note">在「当前基线」处增删</span>
          </div>
        )}

        {/* 区间交付看板 · 甘特顶部：按时间窗口看各动作交付的 PoD · 用户决策 2026-06-01 */}
        {roRows.length > 0 && <WindowReadout rows={roRows} dim="all" axis={roAxis} collapsible />}

        {/* 甘特体撑成全高（所有行一次铺开）→ 整页 stage-wrap 滚动看全；+12 给画布横向滚动条(9px)留余量，避免触发纵向幻影滚动条 · 用户决策 2026-06-02 */}
        <div className="gd-gantt" style={{ height: canvasH + 12 }}>
          <div className="gd-list" ref={listRef} onScroll={(e) => { if (canvasRef.current) canvasRef.current.scrollTop = e.currentTarget.scrollTop; }}>
            <div className="gd-list-h"><span>活动</span><span>批次</span><span className="r">工期</span></div>
            {rows.map((r) => {
              if (r.type === "phase") return (
                <div className="gd-lrow phase" key={"p" + r.phase.key}>
                  <span className="gd-lname"><i className="gd-sw" style={{ background: r.phase.color }} />{r.phase.name}<em>· {r.items.length}</em></span>
                </div>
              );
              const a = r.a as GdAct; const mod = durations[a.id] != null; const crit = showCrit && GD_CRIT.has(a.id); const aff = affectedActs.has(a.id);
              return (
                <div
                  className={"gd-lrow" + (sel === a.id ? " sel" : "") + (aff ? " affected" : "")}
                  key={a.id}
                  ref={(el) => { ganttRowRefs.current[a.id] = el; }}
                  onClick={() => focusGanttAct(a.id)}
                >
                  <span className="gd-lname task" title={a.name}>{a.milestone && <i className="gd-dia" />}{a.name}{crit && <i className="gd-crit-pill">关键</i>}{aff && <i className="gd-aff-pill">受影响</i>}</span>
                  <span className="gd-lbatch">{a.batch}</span>
                  <span className={"gd-ldur" + (mod ? " mod" : "")}>{a.milestone ? "—" : eff.dur[a.id] + "d"}{mod && <i>◆</i>}</span>
                </div>
              );
            })}
          </div>
          <div className="gd-canvas" ref={canvasRef}
            onWheel={(e) => {  /* 画布是横向滚动容器(overflow-x)，会吞掉竖直滚轮 → 手动把竖直滚动转交整页(stage-wrap)，横向仍归画布 · 用户决策 2026-06-02 */
              if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
                const sw = (e.currentTarget as HTMLElement).closest(".stage-wrap") as HTMLElement | null;
                if (sw) sw.scrollTop += e.deltaY;
              }
            }}
            onScroll={(e) => { if (listRef.current) listRef.current.scrollTop = e.currentTarget.scrollTop; }}>
            <div style={{ width: canvasW, position: "relative" }}>
              <div className="gd-chead">
                <div className="gd-months">{months.map((m, i) => <div key={i} className="gd-month" style={{ width: m.days * dayW }}>{m.label}</div>)}</div>
                <div className="gd-days">{Array.from({ length: range.days }).map((_, i) => { const dt = GD.add(range.start, i); const we = GD.weekend(dt); const today = GD.iso(dt) === PROJECT_START; return <div key={i} className={"gd-day" + (we ? " we" : "") + (today ? " today" : "")} style={{ width: dayW }}>{dt.getUTCDate() % 2 === 0 ? dt.getUTCDate() : ""}</div>; })}</div>
              </div>
              <div className="gd-grid" style={{ height: rows.length * ROW_H }}>
                <div className="gd-today" style={{ left: todayLeft, height: rows.length * ROW_H }} />
                {events.map(ev => (
                  <div className={"gd-exc-band" + (ev.kind === "efficiency" ? " eff" : "")} key={ev.id} title={ev.label}
                    style={{ left: GD.diff(range.start, GD.parse(ev.start)) * dayW, width: (GD.diff(GD.parse(ev.start), GD.parse(ev.end)) + 1) * dayW, height: rows.length * ROW_H }} />
                ))}
                {showDeps && <svg className="gd-deps" width={canvasW} height={canvasH} style={{ top: -HEADER }}>
                  <defs>
                    <marker id="gd-arr" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 1 L6 4 L0 7 Z" fill="#94a3b8" /></marker>
                    <marker id="gd-arrc" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 1 L6 4 L0 7 Z" fill="#CE382F" /></marker>
                  </defs>
                  {depPaths.map(p => <path key={p.key} d={p.d} className={"gd-dep" + (p.crit && showCrit ? " crit" : "")} markerEnd={p.crit && showCrit ? "url(#gd-arrc)" : "url(#gd-arr)"} />)}
                </svg>}
                {rows.map((r, i) => {
                  if (r.type === "phase") return <div className="gd-grow phase" key={"p" + r.phase.key} style={{ top: i * ROW_H }} />;
                  const a = r.a as GdAct; const rect = barRect(a); const crit = showCrit && GD_CRIT.has(a.id);
                  const dragging = !!(dragPreview && dragPreview.id === a.id); const mod = durations[a.id] != null; const aff = affectedActs.has(a.id);
                  return (
                    <div className={"gd-grow" + (aff ? " affected" : "")} key={a.id} style={{ top: i * ROW_H }}>
                      {a.milestone
                        ? <div className={"gd-ms" + (crit ? " crit" : "")} style={{ left: rect.left }} title={a.name + " · " + (eff.start[a.id] || a.start)} />
                        : <div className={"gd-bar" + (crit ? " crit" : "") + (sel === a.id ? " sel" : "") + (dragging ? " dragging" : "") + (mod ? " mod" : "") + (aff ? " affected" : "")}
                            style={{ left: rect.left, width: rect.width, background: gdPhase(a.phase).color }}
                            onClick={() => focusGanttAct(a.id)} title={a.name}>
                            <div className="gd-prog" style={{ width: (a.progress * 100) + "%" }} />
                            <span className="gd-bar-lab">{a.name}</span>
                            <div className="gd-grip" title="拖拽改工期" onMouseDown={(e) => beginDrag(e, a)} />
                          </div>}
                      {!a.milestone && <div className={"gd-dur" + (mod ? " mod" : "") + (dragging ? " dragging" : "")} style={{ left: rect.left + rect.width + 5 }}
                        onClick={(e) => { e.stopPropagation(); setEditing(a.id); }} title="点击改工期">
                        {editing === a.id
                          ? <input type="number" min="1" autoFocus defaultValue={eff.dur[a.id]} onClick={e => e.stopPropagation()} onBlur={e => commitDur(a.id, e.target.value)} onKeyDown={e => { if (e.key === "Enter") commitDur(a.id, (e.target as HTMLInputElement).value); else if (e.key === "Escape") setEditing(null); }} />
                          : <><span>{eff.dur[a.id]}</span><span className="u">d</span>{mod && <span className="o">原 {base.dur[a.id]}d</span>}</>}
                      </div>}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
  );
}

// 「调整面板」(路径③) · 用户决策 2026-05-31：右侧滑出，一处集中改 站/货/人；
// 复用 RoomReadyEditor / PodRowEditor + 内联队伍编辑，改动走同一套 updateRoom/updatePod/updateTeam
// → markDirty → 累计到「计划调整」卡，确认后统一推演（漏斗路径③，与跳转②/上传①殊途同归）。
function AdjustPanel({ rooms, teams, updateRoom, updatePod, updateTeam, onClose }: {
  rooms: RoomRow[]; teams: TeamRow[];
  updateRoom: (code: string, patch: Partial<RoomRow>) => void;
  updatePod: (roomCode: string, podId: string, patch: Partial<PodRow>) => void;
  updateTeam: (id: string, patch: Partial<TeamRow>) => void;
  onClose: () => void;
}){
  const [openKey, setOpenKey] = useState<string | null>(null);
  const toggle = (k: string) => setOpenKey(p => p === k ? null : k);
  const pods = rooms.flatMap(r => r.pods.map(p => ({ ...p, room: r.code })));
  const gapRooms = rooms.filter(r => !hasAnyReady(r)).length;
  const gapPods  = pods.filter(p => p.arrival === "unknown").length;
  const gapTeams = teams.filter(t => t.st === "wait").length;
  const gapLab = (n: number, w: string) => n ? `${n} ${w}` : "已齐";
  return (
    <div className="adj-mask" onMouseDown={(e)=>{ if(e.target===e.currentTarget) onClose(); }}>
      <aside className="adj-panel" role="dialog" aria-modal="true">
        <div className="adj-head">
          <span className="adj-title">计划调整 · 直接改 <span className="adj-dims">站 / 货 / 人</span></span>
          <button className="adj-close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="adj-hint">在这一处补齐或修改，改动累计到「计划调整」卡，确认后由 Agent 统一推演。</div>
        <div className="adj-body">
          {/* 站 · 机房 ready */}
          <section className="adj-sec d-site">
            <div className="adj-sec-h"><span className="adj-dim">站</span>机房 ready<span className="adj-gap">{gapLab(gapRooms,"待确认")}</span></div>
            {rooms.map(r => {
              const k = "room:" + r.code; const ready = hasAnyReady(r);
              return (
                <div className={"adj-item"+(openKey===k?" open":"")+(ready?"":" gap")} key={k}>
                  <button className="adj-item-h" onClick={()=>toggle(k)}>
                    <span className="adj-code">机房{r.code.replace(/\D/g,"") || r.code}</span>
                    <span className={"adj-arr "+(ready?"ready":"unknown")}>{ready?"可进场":"待定"}</span>
                    <span className="adj-caret" aria-hidden="true">▾</span>
                  </button>
                  {openKey===k && <div className="adj-edit"><RoomReadyEditor room={r} onUpdateRoom={updateRoom}/></div>}
                </div>
              );
            })}
          </section>
          {/* 货 · PoD 到货 */}
          <section className="adj-sec d-goods">
            <div className="adj-sec-h"><span className="adj-dim">货</span>PoD 到货<span className="adj-gap">{gapLab(gapPods,"待补")}</span></div>
            {pods.map(p => {
              const k = "pod:" + p.id;
              return (
                <div className={"adj-item"+(openKey===k?" open":"")+(p.arrival==="unknown"?" gap":"")} key={k}>
                  <button className="adj-item-h" onClick={()=>toggle(k)}>
                    <span className="adj-code">{p.id}</span><span className="adj-room">{p.room}</span>
                    <span className={"adj-arr "+p.arrival}>{p.arrival==="arrived"?"已到货":p.arrival==="eta"?p.etaLabel:"待定"}</span>
                    <span className="adj-caret" aria-hidden="true">▾</span>
                  </button>
                  {openKey===k && <div className="adj-edit"><PodRowEditor pod={p} onSave={(patch)=>{ updatePod(p.room, p.id, patch); setOpenKey(null); }} onCancel={()=>setOpenKey(null)}/></div>}
                </div>
              );
            })}
          </section>
          {/* 人 · 队伍 */}
          <section className="adj-sec d-people">
            <div className="adj-sec-h"><span className="adj-dim">人</span>队伍<span className="adj-gap">{gapLab(gapTeams,"待分配")}</span></div>
            {teams.map(t => {
              const k = "team:" + t.id;
              return (
                <div className={"adj-item"+(openKey===k?" open":"")+(t.st==="wait"?" gap":"")} key={k}>
                  <button className="adj-item-h" onClick={()=>toggle(k)}>
                    <span className="adj-code">队 {t.id}</span><span className="adj-room">{t.n} 人 · {t.exp==="full"?"经验充分":"经验一般"}</span>
                    <span className={"adj-arr "+(t.st==="on"?"ready":"unknown")}>{t.st==="on"?"在场":"待分配"}</span>
                    <span className="adj-caret" aria-hidden="true">▾</span>
                  </button>
                  {openKey===k && (
                    <div className="adj-edit adj-team">
                      <div className="adj-te-row"><span className="adj-te-lab">人数</span>
                        <div className="num-step">
                          <button onClick={()=>updateTeam(t.id,{n:Math.max(1,t.n-1)})}>−</button>
                          <span className="num-v">{t.n}</span>
                          <button onClick={()=>updateTeam(t.id,{n:Math.min(99,t.n+1)})}>+</button>
                        </div></div>
                      <div className="adj-te-row"><span className="adj-te-lab">经验</span>
                        <div className="td-seg">
                          <button className={t.exp==="full"?"on":""} onClick={()=>updateTeam(t.id,{exp:"full"})}>经验充分</button>
                          <button className={t.exp==="junior"?"on":""} onClick={()=>updateTeam(t.id,{exp:"junior"})}>经验一般</button>
                        </div></div>
                      <div className="adj-te-row"><span className="adj-te-lab">状态</span>
                        <div className="td-seg">
                          <button className={t.st==="on"?"on":""} onClick={()=>updateTeam(t.id,{st:"on"})}>在场</button>
                          <button className={t.st==="wait"?"on":""} onClick={()=>updateTeam(t.id,{st:"wait"})}>待分配</button>
                        </div></div>
                    </div>
                  )}
                </div>
              );
            })}
          </section>
        </div>
      </aside>
    </div>
  );
}

function PlanBoard({ mode = "init" }: { mode?: "init" | "adjust" }){
  const isAdjust = mode === "adjust";
  const [started,setStarted] = useState(false);
  const [clk,setClk] = useState(0);
  const [paused,setPaused] = useState(false);
  const [sel,setSel] = useState<number | null>(null);  // 用户点击回看的 step（null=跟随直播）
  const [picked,setPicked] = useState<string | null>(null);  // 选中机房
  const [selPlan,setSelPlan] = useState<string | null>(null);
  // 排期步内部状态机（init 倒排页）：倒排建议 → 思考 → 多策略方案 · 用户决策 2026-05-30
  // 排期步状态机 · 用户决策 2026-05-30：
  //   init（信息少）：thinking（思考动画）→ result（倒排结果，点批次开甘特），无 confirm/ABC
  //   adjust（信息全）：backward（基线·可拖）→ thinking → plans（ABC）→ 甘特
  const phase0: "backward" | "result" | "thinking" | "plans" = mode === "adjust" ? "backward" : "thinking";
  const [schedPhase,setSchedPhase] = useState<"backward" | "result" | "thinking" | "plans">(phase0);
  const [gantt,setGantt] = useState<{ title: string; back: string } | null>(null);  // 打开的甘特详情（标题 + 返回文案）
  const [ganttReturn,setGanttReturn] = useState<number | null>(null);  // 从顶栏入口打开甘特时，记录返回的步
  const [panelOpen,setPanelOpen] = useState(false);  // 调整面板（路径③）开关 · 用户决策 2026-05-31
  // 时间轴区间：4 个 step 共享的「时间窗口」· #10（双点版）
  // 区间内（goLiveDate ∈ [start, end]）的 PoD/机房高亮，区间外淡化
  const [pointerStart, setPointerStart] = useState<string>(PROJECT_START);
  const [pointerEnd, setPointerEnd] = useState<string>(PROJECT_END);
  // 站货人数据 state · #3 inline 编辑 + #1 增删的基础
  const [rooms, setRooms] = useState<RoomRow[]>(mode === "adjust" ? INITIAL_ROOMS : INITIAL_ROOMS_BARE);
  const [teams, setTeams] = useState<TeamRow[]>(INITIAL_TEAMS);
  // 批次（PoD 级）state · 用户决策 2026-05-29：detail「批次」tab 拖拽编辑（步骤①，画布暂未联动）
  const [batches, setBatches] = useState<BatchRow[]>(INITIAL_BATCHES);
  const assignPodToBatch = (podId: string, batchId: string | null) => {
    setBatches(bs => bs.map(b => ({ ...b, podIds: b.podIds.filter(id => id !== podId) }))
                       .map(b => b.id === batchId ? { ...b, podIds: [...b.podIds, podId] } : b));
    markDirty("pod:" + podId);
  };
  const createBatch = () => {
    setBatches(bs => {
      const maxN = bs.reduce((m, b) => Math.max(m, parseInt(b.name.replace(/\D/g, ""), 10) || 0), 0);
      const n = maxN + 1;
      return [...bs, { id: "bt-" + n, name: "批次" + n, color: BATCH_COLORS[(n - 1) % BATCH_COLORS.length]!, powerOnDate: "", goLiveDate: "", podIds: [] }];
    });
    markDirty("batch:new");
  };
  const updateBatch = (id: string, patch: Partial<BatchRow>) => {
    setBatches(bs => bs.map(b => b.id === id ? { ...b, ...patch } : b));
    markDirty("batch:" + id);
  };
  const deleteBatch = (id: string) => {
    setBatches(bs => bs.filter(b => b.id !== id));
    markDirty("batch:" + id);
  };
  // 待推演变更：跨 站/货/人/排期 累计（按实体去重）；单一「调整推演」消费并清零 · 用户决策 2026-05-31
  const [changes, setChanges] = useState<Set<string>>(new Set());
  // 意外事件（效率打折 / 假期停工）· 用户决策 2026-06-01：基线处注入、甘特读取并影响 CPM；2026-06-02 改可配置表单（id 由 evSeq 发号）
  const [schedEvents, setSchedEvents] = useState<SchedEvent[]>([]);
  const evSeq = useRef(0);
  const [toast, setToast] = useState<string | null>(null);
  // ④ 首次进入引导浮层 + 顶部「?」重看 · 用户决策 2026-05-29
  const [guideOpen, setGuideOpen] = useState(false);
  const closeGuide = () => { setGuideOpen(false); try { localStorage.setItem("aida_guide_v1","1"); } catch(e){} };
  useEffect(()=>{ if(started){ try { if(!localStorage.getItem("aida_guide_v1")) setGuideOpen(true); } catch(e){} } }, [started]);
  const markDirty = (key: string) => setChanges(s => { const n = new Set(s); n.add(key); return n; });
  // 单一触发：跨页累计的变更交 Agent 重新推演（→ 排期步 → 思考 → ABC），并清零（若在看甘特则先收起）
  const runReschedule = () => { setGantt(null); setGanttReturn(null); setSel(4); setSchedPhase("thinking"); setChanges(new Set()); };
  // 意外事件 · 用户决策 2026-06-02：从基线配置表注入草稿（无 id）→ evSeq 发号 → 计入待重排变更（甘特按 eff 动态级联 + 高亮），可加多条
  const addSchedEvent = (ev: SchedEventDraft) => {
    const id = "ev-" + (++evSeq.current);
    setSchedEvents(es => [...es, { id, ...ev }]);
    markDirty("event:" + id);
  };
  const removeSchedEvent = (id: string) => { setSchedEvents(es => es.filter(e => e.id !== id)); markDirty("event:" + id); };
  // 「确认&下发」：选定方案 → 确认并下发执行（mock toast；真下发=派工单属后端）· 用户决策 2026-05-31
  const runDispatch = (id: string) => { const p = PLANS.find(pl => pl.id === id); setToast(`已确认并下发执行：${p?.name ?? "该方案"} · 通知 ${teams.length} 支队伍进场`); setTimeout(() => setToast(null), 2800); };
  // 路径①：上传资料表 → mock 回灌盘子（按文件名命中：到货→PoD ETA / 排班→队伍 / 机房→ready；兜底回灌现有缺口）→ markDirty + toast · 用户决策 2026-05-31
  const runIngest = (names: string[]) => {
    const txt = names.join(" "); const keys: string[] = []; const parts: string[] = [];
    if (/到货|arrival/i.test(txt)) {
      const ids = rooms.flatMap(r => r.pods.filter(p => p.arrival === "unknown").map(p => p.id)).slice(0, 4);
      if (ids.length) {
        const md = ["07-10","07-16","07-22","07-28"]; const pick = new Map(ids.map((id, k) => [id, md[k] || "07-30"]));
        setRooms(rs => rs.map(r => ({ ...r, pods: r.pods.map(p => pick.has(p.id) ? { ...p, arrival: "eta", etaLabel: "在途 " + pick.get(p.id), etaDate: "2026-" + pick.get(p.id) } : p) })));
        ids.forEach(id => keys.push("pod:" + id)); parts.push(`${ids.length} 个 PoD 到货 ETA`);
      }
    }
    if (/排班|施工|schedule/i.test(txt)) {
      const ids = teams.filter(t => t.st === "wait").slice(0, 3).map(t => t.id);
      if (ids.length) { const ws = new Set(ids); setTeams(ts => ts.map(t => ws.has(t.id) ? { ...t, st: "on" } : t)); ids.forEach(id => keys.push("team:" + id)); parts.push(`${ids.length} 支队伍排班就位`); }
    }
    if (/机房|场地|HLD|site/i.test(txt)) {
      const codes = rooms.filter(r => !hasAnyReady(r)).slice(0, 3).map(r => r.code);
      if (codes.length) { const cs = new Set(codes); setRooms(rs => rs.map(r => cs.has(r.code) ? { ...r, cableReadyAt: "2026-07-05", equipReadyAt: "2026-07-18", liquidReadyAt: "2026-07-25" } : r)); codes.forEach(code => keys.push("room:" + code)); parts.push(`${codes.length} 间机房 ready`); }
    }
    // 兜底：未命中关键词但有缺口 → 回灌现有缺口，保证演示有反馈
    if (parts.length === 0) {
      const pid = rooms.flatMap(r => r.pods.filter(p => p.arrival === "unknown").map(p => p.id)).slice(0, 3);
      if (pid.length) { const ps = new Set(pid); setRooms(rs => rs.map(r => ({ ...r, pods: r.pods.map(p => ps.has(p.id) ? { ...p, arrival: "eta", etaLabel: "在途 07-20", etaDate: "2026-07-20" } : p) }))); pid.forEach(id => keys.push("pod:" + id)); parts.push(`${pid.length} 个 PoD 到货 ETA`); }
      else { const tid = teams.filter(t => t.st === "wait").slice(0, 2).map(t => t.id); if (tid.length) { const ws = new Set(tid); setTeams(ts => ts.map(t => ws.has(t.id) ? { ...t, st: "on" } : t)); tid.forEach(id => keys.push("team:" + id)); parts.push(`${tid.length} 支队伍排班就位`); } }
    }
    if (keys.length) { setChanges(s => { const n = new Set(s); keys.forEach(k => n.add(k)); return n; }); setToast(`已从上传资料回灌：${parts.join(" · ")}`); }
    else setToast("资料已加入清单 · 盘子信息已齐，无需回灌");
    setTimeout(() => setToast(null), 2600);
  };
  const updateTeam = (id: string, patch: Partial<TeamRow>) => {
    setTeams(ts => ts.map(t => t.id === id ? { ...t, ...patch } : t));
    markDirty("team:" + id);
  };
  // 增 / 删队伍 · 用户决策 2026-05-29（卡上直接删、行尾加；新队人数 10~12 随机）
  const addTeam = (exp: TeamRow["exp"]) => {
    setTeams(ts => {
      const maxId = ts.reduce((m, t) => Math.max(m, parseInt(t.id, 10) || 0), 0);
      const id = String(maxId + 1).padStart(2, "0");
      const n = 10 + Math.floor(Math.random() * 3); // 10~12
      return [...ts, { id, n, exp, st: "wait" }];
    });
    markDirty("team:new");
  };
  const removeTeam = (id: string) => {
    setTeams(ts => ts.filter(t => t.id !== id));
    markDirty("team:" + id);
  };
  const updatePod = (roomCode: string, podId: string, patch: Partial<PodRow>) => {
    setRooms(rs => rs.map(r => r.code === roomCode
      ? { ...r, pods: r.pods.map(p => p.id === podId ? { ...p, ...patch } : p) }
      : r));
    markDirty("pod:" + podId);
  };
  const updateRoom = (roomCode: string, patch: Partial<RoomRow>) => {
    setRooms(rs => rs.map(r => r.code === roomCode ? { ...r, ...patch } : r));
    markDirty("room:" + roomCode);
  };
  const removeRoom = (roomCode: string) => {
    setRooms(rs => rs.filter(r => r.code !== roomCode));
    markDirty("room:" + roomCode);
  };
  // #1 添加机房：默认归属指定批，自动分配 gx (该批在 GO_LIVE_BATCHES 中的索引) + gy (该列下一个空位)
  const addRoom = (batchId: string) => {
    setRooms(rs => {
      const batchIdx = GO_LIVE_BATCHES.findIndex(b => b.id === batchId);
      if (batchIdx < 0) return rs;
      const gx = batchIdx;
      const usedY = rs.filter(r => r.gx === gx).map(r => r.gy);
      const gy = usedY.length === 0 ? 0 : Math.max(...usedY) + 1;
      const maxRoomNum = rs.reduce((m, r) => Math.max(m, parseInt(r.code.replace(/[^\d]/g,""), 10) || 0), 0);
      const maxPodNum  = rs.reduce((m, r) => r.pods.reduce((m2, p) => Math.max(m2, parseInt(p.id.replace(/[^\d]/g,""), 10) || 0), m), 0);
      const code = "M" + (maxRoomNum + 1);
      const readyBatch = "B-ready-" + (batchIdx + 1);
      const newRoom: RoomRow = {
        code, proj: "智算一期", gx, gy, site: "pending", readyBatch, goLiveBatch: batchId,
        pods: [
          { id: "P-" + String(maxPodNum + 1).padStart(2,"0"), arrival: "unknown", etaLabel: "待定", status: "pending", goLiveBatch: batchId },
          { id: "P-" + String(maxPodNum + 2).padStart(2,"0"), arrival: "unknown", etaLabel: "待定", status: "pending", goLiveBatch: batchId },
        ],
      };
      return [...rs, newRoom];
    });
    markDirty("room:new");
  };

  // 时钟推进
  useEffect(()=>{
    if(!started || paused || clk>=TOTAL) return;
    const delay = (clk===STEPS[1]!.end) ? 2700 : 680;   // 货步 PoD 解析呈现完成后停 ~2 秒，再切到「人」
    const id = setTimeout(()=>setClk(c=>c+1), delay);
    return ()=>clearTimeout(id);
  },[started,paused,clk]);

  // 推荐方案在揭示时默认选中
  useEffect(()=>{ if(clk>=20 && selPlan===null) setSelPlan("single"); },[clk,selPlan]);
  // 「计划调整」卡的实时状态 → Claw 侧栏 · 用户决策 2026-05-31：缺口(站/货/人) + 待推演变更数 + 模式；
  // ready=clk 到末才出卡；deps 含 rooms/teams/changes，改完即随动（init 实时补齐 / adjust 累计变更）
  useEffect(()=>{
    const allPods = rooms.flatMap(r=>r.pods);
    window.dispatchEvent(new CustomEvent('aida:plan-state', { detail:{
      ready:   clk>=TOTAL,
      site:    rooms.filter(r=>!hasAnyReady(r)).length,        // 机房 ready 待确认（无任何 ready 段）
      goods:   allPods.filter(p=>p.arrival==="unknown").length, // PoD 到货未明
      people:  teams.filter(t=>t.st==="wait").length,           // 待分配队伍
      changes: changes.size,                                    // 待推演变更数（仅 adjust 用）
      mode,                                                     // init 实时 / adjust 攒变更
    }}));
  },[clk, rooms, teams, changes]);
  // 货步默认不预选：全部项目正常高亮，由用户点击聚焦某项目

  const activeStep = useMemo(()=>{
    const a = STEPS.find(s=>stepStatus(s.n,clk)==="active");
    return a? a.n : (clk>=TOTAL? 4 : 1);
  },[clk]);
  const view = sel || activeStep;

  // 调试钩子（预览用：jump/end 会暂停时钟以定格在目标步，便于查 DOM）
  useEffect(()=>{ window.__aida = {
    start:()=>{setStarted(true);setPaused(false);setClk(0);setSel(null);},
    jump:(n)=>{setStarted(true);setSel(null);setPaused(true);setClk(clamp(n,0,TOTAL));},
    end:()=>{setStarted(true);setSel(null);setPaused(true);setClk(TOTAL);},
    play:()=>setPaused(false),
    total:TOTAL };
  },[]);

  const start = ()=>{ setStarted(true); setClk(0); setSel(null); setPicked(null); setSelPlan(null); setSchedPhase(phase0); setGantt(null); };
  const replay = ()=>{ setClk(0); setSel(null); setPicked(null); setSelPlan(null); setSchedPhase(phase0); setGantt(null); setPaused(false); };
  // 由 04 右侧 Claw 助手「发送」触发解析（保留 Claw 发送驱动叙事）
  useEffect(()=>{ const h=()=>start(); window.addEventListener('aida:claw-send', h); return ()=>window.removeEventListener('aida:claw-send', h); },[]);
  // 「计划调整」卡 → 行内「调整」跳到 站/货/人 步就地改（路径②）；「调整面板」开面板（路径③）· 用户决策 2026-05-31
  // 确认重排走主区跨步飘红条（.resched-banner，直接调 runReschedule）
  useEffect(()=>{
    const goTo=(e: Event)=>{ const s=(e as CustomEvent<{ step?: number }>).detail?.step; if(typeof s==="number"&&s>=1&&s<=3){ setGantt(null); setSel(s); } };
    const openPanel=()=>{ setGantt(null); setPanelOpen(true); };
    window.addEventListener('aida:plan-goto', goTo);
    window.addEventListener('aida:plan-open-panel', openPanel);
    return ()=>{ window.removeEventListener('aida:plan-goto', goTo); window.removeEventListener('aida:plan-open-panel', openPanel); };
  },[]);
  // 路径①：上传资料表回灌（deps 含 rooms/teams，取最新盘子算缺口）· 用户决策 2026-05-31
  useEffect(()=>{
    const onIngest=(e: Event)=>runIngest((e as CustomEvent<{ names?: string[] }>).detail?.names || []);
    window.addEventListener('aida:plan-ingest', onIngest);
    return ()=>window.removeEventListener('aida:plan-ingest', onIngest);
  },[rooms, teams]);

  const curStep = STEPS[view-1]!;
  // tb-stats 动态化：机房 / PoD / 队伍 / 人数 / 上线目标 跟随真实 rooms·teams·batches 状态 · 用户决策 2026-05-30
  const statRooms = rooms.length;
  const statPods = rooms.reduce((s, r) => s + r.pods.length, 0);
  const statTeams = teams.length;
  const statHeadcount = teams.reduce((s, t) => s + t.n, 0);
  const statPodSet = new Set(rooms.flatMap(r => r.pods.map(p => p.id)));
  const statGoLiveList = batches.filter(b => b.goLiveDate && b.podIds.some(id => statPodSet.has(id))).map(b => b.goLiveDate);
  const statGoLive = statGoLiveList.length ? statGoLiveList.reduce((m, d) => (d > m ? d : m), statGoLiveList[0]!) : "待定";
  const headMap = {
    site:["机房逐个浮现，标注进场状态","系统正在识别交付盘子里有哪些机房、是否具备进场施工条件。"],
    goods:["PoD 落位并按到货状态着色","每个机房里安装哪些 PoD（带编号）、各自到货是否就绪。"],
    people:["队伍就绪与活动 SLA 的人力换算","识别哪些硬装活动的工期受人数约束——它们是后续压缩的着力点。"],
    plan:["排期对照移交目标，构建多策略方案","信息已足够：必要项齐备、其他项由系统建议，给出第一版排期供选择。"],
  };

  // claw 宽度可拖 + 左右互换（排期页内联 claw 自管，不走 B 的 AppShell claw 机制）
  const [clawWidth, setClawWidth] = useState(312);
  const [clawSide, setClawSide] = useState<'left' | 'right'>('left');

  return (
    <div className={`planinit${clawSide === 'right' ? ' sched-cr-right' : ''}`}>
      <ScheduleClawRail width={clawWidth} side={clawSide} onResize={setClawWidth} onSwap={() => setClawSide(s => (s === 'left' ? 'right' : 'left'))} />
      <div className="main">
        <div className="topbar">
          <div className="tb-left">
            <div className="crumb">交付 Claw <span className="sep">›</span> 计划排期 <span className="sep">·</span> <span className="on">{isAdjust ? "计划调整" : "初始化"}</span></div>
            <h1>{isAdjust ? "改交付条件，Agent 重排多策略方案" : "从交付资料，自动排出第一版排期"}</h1>
            <div className="tb-sub">{isAdjust ? "比选 A / B / C 择优" : "上线目标倒推「货到 / 机房就位」"}</div>
            {started && <div className="tb-stats">
              <span className="tb-stat"><b className="tnum">{statRooms}</b><span className="u">机房</span></span>
              <span className="tb-stat"><b className="tnum">{statPods}</b><span className="u">PoD</span></span>
              <span className="tb-stat"><b className="tnum">{statTeams}</b><span className="u">队伍</span></span>
              <span className="tb-stat"><b className="tnum">{statHeadcount}</b><span className="u">人</span></span>
              <span className="tb-stat">上线目标 <b className="tnum" style={{fontSize:13}}>{statGoLive}</b></span>
            </div>}
          </div>
          {started && <div className="tb-right">
            <span className={"live-tag "+(sel?"review":"")}>
              <span className="live-dot"/>{sel? "回看中 · 第"+sel+"步" : (clk>=TOTAL? "解析完成":"实时解析中")}</span>
            <button className="ctrl-btn" title={paused?"继续":"暂停"} onClick={()=>setPaused(p=>!p)}>{paused?I.play():I.pause()}</button>
            <button className="ctrl-btn" title="重播" onClick={replay}>{I.replay()}</button>
            <button className="ctrl-btn ctrl-gantt" title="查看当前计划 · 整体排期甘特" onClick={()=>{ setGanttReturn(view); setSel(4); setGantt({ title:"整体排期 · 全量甘特", back:"← 返回" }); }}>{I.schedule(13)}当前计划</button>
            <button className="ctrl-btn ctrl-help" title="使用引导（怎么改人货站）" onClick={()=>setGuideOpen(true)}>?</button>
          </div>}
        </div>

        {started && <Stepper clk={clk} view={view} onPick={(n)=>setSel(n===activeStep?null:n)} rooms={rooms} isAdjust={isAdjust}/>}

        {/* 跨步常驻飘红：站/货/人/排期 任一步有数据变动即提示确认重排（adjust）· 用户决策 2026-05-31 */}
        {started && isAdjust && changes.size > 0 && (
          <div className="resched-banner">
            <span className="rb-dot"/>
            <span className="rb-msg">已修改 <b className="tnum">{changes.size}</b> 项信息 · 确认后由 Agent 重新推演排期</span>
            <button className="rb-btn" onClick={runReschedule}>确认调整需求，排期推演</button>
          </div>
        )}

        <div className="stage-wrap">
          {!started ? <Empty/> : (<>
            {!(view===4 && gantt) && <div className="stage-head fade" key={curStep.key + (curStep.key==="plan"?schedPhase:"")}>
              {/* k 文案按 view 切换 · 用户决策 2026-05-28：站/货 用更具叙事感的描述，人/排期 保留 lbl；d 副标题整体去除 */}
              <span className="k">{
                curStep.key === "site"  ? "站 · 识别机房个数,是否具备进场施工条件" :
                curStep.key === "goods" ? "货 · 识别每个机房里安装哪些 PoD,对应到货是否就绪" :
                curStep.key !== "plan"  ? curStep.lbl :
                !isAdjust
                  ? (schedPhase==="thinking" ? "排期 · 正在推算就位建议…" : "排期 · 上线目标 → 建议到货 / 机房就位")
                  : (schedPhase==="backward" ? "排期 · 当前基线 · 拖动目标后点「调整推演」"
                     : schedPhase==="thinking" ? "排期 · 正在重新计算多策略方案…"
                     : "排期 · 多策略方案 · 择优进入排期详情")
              }</span>
              <span className="tick mono">clock {clk}/{TOTAL}</span>
            </div>}
            {(view===1||view===2) && <IsoYard clk={clk} picked={picked} onPick={setPicked} step={view}
              pointerStart={pointerStart} pointerEnd={pointerEnd}
              rooms={rooms} updatePod={updatePod} updateRoom={updateRoom} removeRoom={removeRoom} addRoom={addRoom}
              batches={batches} assignPodToBatch={assignPodToBatch} createBatch={createBatch} updateBatch={updateBatch} deleteBatch={deleteBatch}/>}
            {view===3 && <PeopleView clk={clk} teams={teams} updateTeam={updateTeam} addTeam={addTeam} removeTeam={removeTeam}/>}
            {/* —— 排期详情甘特：内联展示（替换排期内容区，可返回）· 用户决策 2026-05-31 —— */}
            {view===4 && gantt &&
              <GanttDetailOverlay title={gantt.title} backLabel={gantt.back} batches={batches} rooms={rooms} events={schedEvents}
                onClose={()=>{ setGantt(null); if(ganttReturn!=null){ setSel(ganttReturn===activeStep?null:ganttReturn); setGanttReturn(null); } }}
                onSaved={()=>{ setGantt(null); if(ganttReturn!=null){ setSel(ganttReturn===activeStep?null:ganttReturn); setGanttReturn(null); } setToast("排期已写回系统"); setTimeout(()=>setToast(null),1800); }}/>}
            {/* —— init（信息少 / 倒排）：思考 → 倒排结果（点批次开甘特），无 confirm / ABC —— */}
            {view===4 && !isAdjust && !gantt && schedPhase==="thinking" &&
              <ScheduleThinking steps={THINK_STEPS_SUGGEST} title="AIDA 正在推算就位建议…" onDone={()=>setSchedPhase("result")}/>}
            {view===4 && !isAdjust && !gantt && schedPhase==="result" &&
              <BackwardSchedule batches={batches} rooms={rooms} updateBatch={updateBatch}
                variant="suggest" showConfirm={false} onConfirm={()=>{}}
                onPickBatch={(idx)=> setGantt({ title: `批次 ${idx+1}`, back: "← 返回排期" })}/>}
            {/* —— adjust（信息全 / 调整）：基线(已知) → 调整推演 → 思考 → ABC → 甘特 —— */}
            {view===4 && isAdjust && !gantt && schedPhase==="backward" &&
              <BackwardSchedule batches={batches} rooms={rooms} updateBatch={updateBatch}
                variant="given" showConfirm={false} onConfirm={()=>{}}
                events={schedEvents} onAddEvent={addSchedEvent} onRemoveEvent={removeSchedEvent}/>}
            {view===4 && isAdjust && !gantt && schedPhase==="thinking" &&
              <ScheduleThinking onDone={()=>setSchedPhase("plans")}/>}
            {view===4 && isAdjust && !gantt && schedPhase==="plans" && (<>
              <div className="sched-back fade">
                <button className="sched-back-btn" onClick={()=>setSchedPhase("backward")}>← 返回调整目标</button>
                <span className="sched-back-tip">选定方案后点「排期详情」进入可编辑甘特</span>
              </div>
              <CompressionPlans clk={TOTAL} selPlan={selPlan} onSelPlan={setSelPlan} onDispatch={runDispatch} onOpenGantt={(id)=> setGantt({ title: PLANS.find(p=>p.id===id)?.name ?? id, back: "← 返回方案" })}/>
            </>)}
          </>)}
        </div>

        {/* TimeAxis（底部时间窗口双滑块）已移除 · 用户决策 2026-05-30：排期步不再展示 */}
      </div>
      {/* 甘特排期详情已内联到排期内容区（见上 stage-wrap）· 用户决策 2026-05-31 */}
      {/* #4 toast · 简单 fixed 底部居中 · 1.8s 自动消失 */}
      {panelOpen && <AdjustPanel rooms={rooms} teams={teams} updateRoom={updateRoom} updatePod={updatePod} updateTeam={updateTeam} onClose={()=>setPanelOpen(false)}/>}
      {guideOpen && <GuideOverlay onClose={closeGuide}/>}
      {toast && <div className="aida-toast">{toast}</div>}
    </div>
  );
}

function PlanInit(){ return <PlanBoard mode="init"/>; }
function PlanAdjust(){ return <PlanBoard mode="adjust"/>; }

export { PlanBoard, ScheduleClawRail, PlanInit, PlanAdjust };
