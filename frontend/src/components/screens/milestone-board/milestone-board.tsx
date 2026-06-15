import { useMemo, useState } from 'react';
import {
  MILESTONE_STEPS,
  POD_MILESTONES,
  STATUS_META,
  batchStats,
  podSummary,
  segmentTone,
  slipDays,
  type BatchStageStat,
  type BatchStat,
  type Milestone,
  type MilestoneStatus,
  type PodMilestones,
  type PodSummary,
  type SegmentTone,
} from './data';

/* ─────────────────────────────────────────────────────────────
 * 交付里程碑看板（PD 视角 · v3.1 · 少即是多）
 *
 * 核心：PoD × 里程碑矩阵就是产品本身。一切为「更快读懂 PoD 里程碑」服务。
 *   · 两个视图：PoD 里程碑（风险优先）/ 批次里程碑（每批聚合 1 行，复用同款渲染）。
 *   · 节点 = 里程碑徽标：进度环 + 上下双日期，同时说清 进度/状态/时间。
 *       上 = 计划（浅灰）· 下 = 实际（深墨）。日期颜色统一，不因延期/晚点变色。
 *   · 五态：已完成·准时 / 已完成·晚点（翡翠盘 + 细琥珀外环）/ 进行中 /
 *       延期·未完成（玫红环 + 脉冲，唯一警报）/ 未开工。
 *   · 连线只走圆圈之间空隙、不穿透：靛蓝实线=已推进 / 灰虚=未来 / 玫红=逾期。
 *   · 列头只留工序名；PoD 左块只留编号；分区只留标签。不在界面算 ±Nd/逾Nd。
 *
 * 数据契约：9 PoD × 6 节点，渲染层只读 data.ts 的派生结论。
 * ───────────────────────────────────────────────────────────── */

type ViewMode = 'pod' | 'batch';
type RowVariant = 'fire' | 'calm' | 'done';

const cn = (date: string): string => {
  const p = date.split('-');
  return `${Number(p[1])}月${Number(p[2])}日`;
};

const RING_CIRC = 2 * Math.PI * 11; // r=11

const connClass = (t: SegmentTone): string => (t === 'overdue' ? 't-od' : t === 'future' ? 't-fu' : 't-go');

/* ──────────────── 里程碑徽标（进度环 + 中心 + 状态；晚点叠琥珀外环） ──────────────── */
function NodeGlyph({ m, late = false, mini = false }: { m: Milestone; late?: boolean; mini?: boolean }) {
  const pct = Math.max(0, Math.min(100, m.progress));
  const dash = `${(RING_CIRC * pct) / 100} ${RING_CIRC}`;
  const cls = `mb-node n-${m.status}${mini ? ' is-mini' : ''}`;

  if (m.status === 'done') {
    return (
      <span className={cls}>
        <svg viewBox="0 0 28 28" aria-hidden="true">
          {late && <circle className="late-ring" cx="14" cy="14" r="13" fill="none" strokeWidth="1.6" />}
          <circle className="disc" cx="14" cy="14" r="11.5" />
          <path className="chk" d="M9 14.3 L12.3 17.6 L19 10.4" fill="none" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (m.status === 'inProgress') {
    return (
      <span className={cls}>
        <svg viewBox="0 0 28 28" aria-hidden="true">
          <circle className="trk" cx="14" cy="14" r="11" fill="#fff" strokeWidth="3" />
          <circle className="arc" cx="14" cy="14" r="11" fill="none" strokeWidth="3" strokeLinecap="round" style={{ strokeDasharray: dash }} transform="rotate(-90 14 14)" />
        </svg>
        {!mini && <span className="mb-node-c">{pct}</span>}
      </span>
    );
  }
  if (m.status === 'delayed') {
    return (
      <span className={cls}>
        <svg viewBox="0 0 28 28" aria-hidden="true">
          <circle className="trk" cx="14" cy="14" r="11" fill="#fff" strokeWidth="3" />
          {pct > 0 && <circle className="arc" cx="14" cy="14" r="11" fill="none" strokeWidth="3" strokeLinecap="round" style={{ strokeDasharray: dash }} transform="rotate(-90 14 14)" />}
        </svg>
        {!mini && <span className="mb-node-c">{pct > 0 ? pct : '!'}</span>}
      </span>
    );
  }
  return (
    <span className={cls}>
      <svg viewBox="0 0 28 28" aria-hidden="true">
        <circle className="hollow" cx="14" cy="14" r="10.5" fill="#fff" strokeWidth="2" strokeDasharray="2 4" strokeLinecap="round" />
      </svg>
    </span>
  );
}

/* ──────────────── hover 详情卡（精确双日期；所有节点含已移交均有） ──────────────── */
function CellTip({ rowId, m, flip }: { rowId: string; m: Milestone; flip: boolean }) {
  const tone = m.status === 'done' ? 't-done' : m.status === 'inProgress' ? 't-live' : m.status === 'delayed' ? 't-fire' : 't-todo';
  return (
    <div className={`mb-tip${flip ? ' flip' : ''}`} role="tooltip">
      <div className="mb-tip-h"><b>{rowId} · {m.name}</b><span className={`mb-tag ${tone}`}>{STATUS_META[m.status].label}</span></div>
      <div className="mb-tip-r"><span>计划完成</span><b>{cn(m.plannedDate)}</b></div>
      <div className="mb-tip-r"><span>实际完成</span><b>{m.actualDate ? cn(m.actualDate) : '—'}</b></div>
      <div className="mb-tip-r"><span>当前进度</span><b>{m.progress}%</b></div>
    </div>
  );
}

/* ──────────────── 单个里程碑单元（上计划 + 节点&连线 + 下实际） ──────────────── */
function MilestoneCell({ row, milestones, index, flipTip }: {
  row: string; milestones: readonly Milestone[]; index: number; flipTip: boolean;
}) {
  const m = milestones[index]!;
  const next = index < milestones.length - 1 ? milestones[index + 1]! : null;
  const late = m.status === 'done' && (slipDays(m) ?? 0) > 0;
  return (
    <div className="mb-cell">
      <div className="mb-date top">{cn(m.plannedDate)}</div>
      <div
        className="mb-track"
        tabIndex={0}
        aria-label={`${row} ${m.name} ${STATUS_META[m.status].label}，进度 ${m.progress}%，计划 ${cn(m.plannedDate)}${m.actualDate ? `，实际 ${cn(m.actualDate)}` : ''}`}
      >
        {next && <i className={`mb-conn ${connClass(segmentTone(m, next))}`} />}
        <NodeGlyph m={m} late={late} />
        <CellTip rowId={row} m={m} flip={flipTip} />
      </div>
      <div className="mb-date bot">{m.actualDate ? cn(m.actualDate) : ' '}</div>
    </div>
  );
}

/* ──────────────── 一行（PoD 或聚合后的批次，渲染完全一致） ──────────────── */
function MatrixRow({ id, sub, milestones, variant, flipTip }: {
  id: string; sub?: string; milestones: readonly Milestone[]; variant: RowVariant; flipTip: boolean;
}) {
  return (
    <div className={`mb-row v-${variant}`}>
      <div className="mb-pod">
        <span className="mb-pod-id">{id}</span>
        {sub && <span className="mb-pod-sub">{sub}</span>}
      </div>
      {milestones.map((_, i) => (
        <MilestoneCell key={i} row={id} milestones={milestones} index={i} flipTip={flipTip} />
      ))}
    </div>
  );
}

function ZoneLabel({ tone, label }: { tone: RowVariant; label: string }) {
  return (
    <div className={`mb-zone z-${tone}`}>
      {tone === 'fire' && <span className="mb-zone-pulse" />}
      <span className="mb-zone-label">{label}</span>
    </div>
  );
}

/* ──────────────── 批次聚合：把一批合成 6 个「聚合里程碑」喂给同一渲染路径 ──────────────── */
function synthStatus(s: BatchStageStat): MilestoneStatus {
  if (s.delayedCount > 0) return 'delayed';
  if (s.doneCount === s.total) return 'done';
  if (s.notStartedCount === s.total) return 'notStarted';
  return 'inProgress';
}

function batchMilestones(b: BatchStat): Milestone[] {
  return b.stages.map(s => ({
    key: s.key,
    name: s.name,
    plannedDate: s.plannedDate,
    actualDate: s.doneCount === s.total ? s.actualDate : null,
    progress: s.avgProgress,
    status: synthStatus(s),
  }));
}

function batchVariant(b: BatchStat): RowVariant {
  if (b.stages.some(s => s.delayedCount > 0)) return 'fire';
  if (b.stages.every(s => s.doneCount === s.total)) return 'done';
  return 'calm';
}

/* ──────────────── 页眉图例（真实徽标做示例 + 上下日期规则） ──────────────── */
const LEGEND_SAMPLES: { m: Milestone; late?: boolean; label: string }[] = [
  { m: { key: 'roomReady', name: '', plannedDate: '', actualDate: '', progress: 100, status: 'done' }, label: '已完成' },
  { m: { key: 'roomReady', name: '', plannedDate: '', actualDate: '', progress: 100, status: 'done' }, late: true, label: '晚点完成' },
  { m: { key: 'roomReady', name: '', plannedDate: '', actualDate: null, progress: 60, status: 'inProgress' }, label: '进行中' },
  { m: { key: 'roomReady', name: '', plannedDate: '', actualDate: null, progress: 40, status: 'delayed' }, label: '延期' },
  { m: { key: 'roomReady', name: '', plannedDate: '', actualDate: null, progress: 0, status: 'notStarted' }, label: '未开工' },
];

function Legend() {
  return (
    <div className="mb-legend">
      <div className="mb-legend-row">
        {LEGEND_SAMPLES.map((s, i) => (
          <span className="mb-lg" key={i}><NodeGlyph m={s.m} late={s.late} mini />{s.label}</span>
        ))}
      </div>
      <div className="mb-legend-rule">
        <span><b>上</b> 计划</span>
        <span><b>下</b> 实际</span>
      </div>
    </div>
  );
}

export default function MilestoneBoard({ pods = POD_MILESTONES }: { pods?: readonly PodMilestones[] }) {
  const [view, setView] = useState<ViewMode>('pod');
  const batches = useMemo(() => batchStats(pods), [pods]);

  const variantOf = (s: PodSummary): RowVariant => s.phase === 'delayed' ? 'fire' : s.phase === 'handedOver' ? 'done' : 'calm';

  const groups = useMemo(() => {
    const ws = pods.map(p => ({ pod: p, summary: podSummary(p) }));
    return {
      fire: ws.filter(x => x.summary.phase === 'delayed').sort((a, b) => b.summary.maxOverdue - a.summary.maxOverdue),
      calm: ws.filter(x => x.summary.phase === 'inProgress' || x.summary.phase === 'notStarted').sort((a, b) => b.summary.progress - a.summary.progress),
      done: ws.filter(x => x.summary.phase === 'handedOver').sort((a, b) => a.pod.podId.localeCompare(b.pod.podId)),
    };
  }, [pods]);

  return (
    <div className="mb">
      <style>{STYLES}</style>

      <div className="mb-head">
        <div className="mb-head-l">
          <span className="mb-title">交付里程碑</span>
        </div>
        <Legend />
        <div className="mb-seg" role="tablist" aria-label="视图切换">
          <button type="button" role="tab" aria-selected={view === 'pod'} className={view === 'pod' ? 'on' : ''} onClick={() => setView('pod')}>PoD 里程碑</button>
          <button type="button" role="tab" aria-selected={view === 'batch'} className={view === 'batch' ? 'on' : ''} onClick={() => setView('batch')}>批次里程碑</button>
        </div>
      </div>

      <div className="mb-colhead">
        <div className="mb-colhead-lead">{view === 'pod' ? '风险优先' : '批次'}</div>
        {MILESTONE_STEPS.map(s => <div className="mb-ch" key={s.key}><div className="mb-ch-name">{s.name}</div></div>)}
      </div>

      <div className="mb-body">
        {view === 'pod' ? (
          <>
            {groups.fire.length > 0 && (<>
              <ZoneLabel tone="fire" label="需立即处理" />
              {groups.fire.map((x, i) => <MatrixRow key={x.pod.podId} id={x.pod.podId} milestones={x.pod.milestones} variant="fire" flipTip={i < 1} />)}
            </>)}
            {groups.calm.length > 0 && (<>
              <ZoneLabel tone="calm" label="推进中" />
              {groups.calm.map(x => <MatrixRow key={x.pod.podId} id={x.pod.podId} milestones={x.pod.milestones} variant={variantOf(x.summary)} flipTip={false} />)}
            </>)}
            {groups.done.length > 0 && (<>
              <ZoneLabel tone="done" label="已移交" />
              {groups.done.map(x => <MatrixRow key={x.pod.podId} id={x.pod.podId} milestones={x.pod.milestones} variant="done" flipTip={false} />)}
            </>)}
          </>
        ) : (
          batches.map(b => (
            <MatrixRow key={b.room} id={b.room} sub={`${b.podCount} PoD`} milestones={batchMilestones(b)} variant={batchVariant(b)} flipTip={false} />
          ))
        )}
      </div>
    </div>
  );
}

/* 自带配色（集中为根 CSS 变量，克制而有锋芒）：
 *   翡翠(完成) / 靛蓝(推进·轨迹) / 玫红(延期·唯一警报) / 琥珀(晚点标记) · 数字 tabular-nums。 */
const STYLES = `
.mb{
  --ink:#141C2E;--ink2:#43506A;--ink3:#8A95AC;--ink4:#B4BDD0;--line:#EEF0F5;--line2:#E3E7EF;
  --done:#0FA371;--done-soft:#E4F6EE;
  --live:#5165F0;--live-soft:#EEF1FE;--live-deep:#3447C9;
  --fire:#E23A5E;--fire-deep:#B22647;--fire-halo:#F6C2CE;--fire-soft:#FDECEF;--fire-band:#FCE3E9;
  --late:#C2820F;--ring-track:#CFD6E2;--line-future:#C9D0DC;
  --font:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
  background:#fff;border:1px solid var(--line2);border-radius:14px;color:var(--ink);font-family:var(--font);overflow:hidden}
.mb *{box-sizing:border-box}
.mb b,.mb em{font-weight:500;font-style:normal}
.mb-asof,.mb-date,.mb-pod-id,.mb-pod-sub,.mb-node-c{font-variant-numeric:tabular-nums}

/* HEADER */
.mb-head{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;padding:14px 20px 12px}
.mb-head-l{display:flex;align-items:baseline;gap:10px}
.mb-title{font-size:16px;font-weight:500;letter-spacing:-.01em}
.mb-asof{font-size:11px;color:var(--ink4)}

/* LEGEND */
.mb-legend{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-left:auto}
.mb-legend-row{display:flex;align-items:center;gap:13px}
.mb-lg{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--ink2)}
.mb-legend-rule{display:flex;align-items:center;gap:12px;padding-left:14px;border-left:1px solid var(--line2);font-size:11px;color:var(--ink3)}
.mb-legend-rule b{display:inline-block;width:15px;height:15px;line-height:15px;text-align:center;border-radius:4px;background:#F3F5F9;color:var(--ink2);font-size:10px;margin-right:4px}

/* VIEW TOGGLE */
.mb-seg{display:inline-flex;padding:2px;border:1px solid var(--line2);border-radius:9px;background:#F3F5F9}
.mb-seg button{border:0;border-radius:7px;padding:6px 13px;background:transparent;color:var(--ink3);font-size:12px;font-weight:400;cursor:pointer;font-family:inherit}
.mb-seg button.on{background:#fff;color:var(--ink);font-weight:500;box-shadow:0 1px 3px rgba(20,28,46,.12)}

/* UNIFIED GRID — colhead + every row share the template → strict vertical alignment */
.mb-colhead,.mb-row{display:grid;grid-template-columns:92px repeat(6,minmax(0,1fr))}
.mb-colhead{align-items:center;padding:11px 20px 10px;border-top:1px solid var(--line);border-bottom:1px solid var(--line2);background:#FBFCFE}
.mb-colhead-lead{font-size:11px;font-weight:500;letter-spacing:.04em;color:var(--ink4);text-transform:uppercase}
.mb-ch{padding:0 8px;text-align:center}
.mb-ch-name{font-size:12px;font-weight:500;color:var(--ink);white-space:nowrap}

/* ZONES (slim, label only) */
.mb-zone{display:flex;align-items:center;gap:8px;height:28px;padding:0 20px;border-bottom:1px solid var(--line)}
.mb-zone-label{font-size:11px;font-weight:500;letter-spacing:.03em}
.mb-zone.z-fire{background:var(--fire-band)}.mb-zone.z-fire .mb-zone-label{color:var(--fire-deep)}
.mb-zone.z-calm .mb-zone-label{color:var(--ink2)}
.mb-zone.z-done{background:#FBFCFE}.mb-zone.z-done .mb-zone-label{color:var(--ink3)}
.mb-zone-pulse{width:7px;height:7px;border-radius:50%;background:var(--fire);box-shadow:0 0 0 0 var(--fire-halo);animation:mbPulse 1.9s ease-out infinite}
@keyframes mbPulse{0%{box-shadow:0 0 0 0 rgba(226,58,94,.45)}70%{box-shadow:0 0 0 7px rgba(226,58,94,0)}100%{box-shadow:0 0 0 0 rgba(226,58,94,0)}}

/* ROWS */
.mb-row{align-items:center;border-bottom:1px solid var(--line);position:relative;padding:0 20px;min-height:70px}
.mb-row:last-child{border-bottom:0}
.mb-row.v-fire{background:var(--fire-soft)}
.mb-row.v-fire::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--fire)}
.mb-row.v-calm:hover{background:#FBFCFE}
.mb-row.v-done{opacity:.6}
.mb-row.v-done:hover{opacity:1;background:#FBFCFE}

/* left block — just the id (+ optional count for batch) */
.mb-pod{padding:8px 12px 8px 0;min-width:0}
.mb-pod-id{font-size:13.5px;font-weight:500;letter-spacing:.01em}
.mb-pod-sub{display:block;margin-top:3px;font-size:10.5px;color:var(--ink3)}

/* CELL: top planned + node(track w/ connector) + bottom actual */
.mb-cell{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;padding:5px 0;min-width:0;overflow:visible}
.mb-date{height:14px;line-height:14px;font-size:10.5px;white-space:nowrap}
.mb-date.top{color:var(--ink3)}
.mb-date.bot{color:var(--ink)}

.mb-track{position:relative;width:100%;height:30px;display:grid;place-items:center;outline:none;overflow:visible}
.mb-track:focus-visible{box-shadow:inset 0 0 0 2px var(--live-soft);border-radius:8px}

/* connector: single continuous segment in the GAP between two circles (edge to edge, no penetration) */
.mb-conn{position:absolute;top:50%;margin-top:-1.25px;left:50%;width:100%;z-index:0}
.mb-conn.t-go{height:2.5px;border-radius:2px;background:var(--live)}
.mb-conn.t-od{height:2.5px;border-radius:2px;background:var(--fire)}
.mb-conn.t-fu{height:0;border-top:2.5px dashed var(--line-future)}

/* NODE medallion */
.mb-node{position:relative;z-index:1;display:grid;place-items:center;width:28px;height:28px}
.mb-node svg{width:100%;height:100%;display:block;overflow:visible}
.mb-node.is-mini{width:16px;height:16px}
.mb-node .trk{stroke:var(--ring-track)}
.mb-node .late-ring{stroke:var(--late)}
.mb-node.n-done .disc{fill:var(--done)}
.mb-node .chk{stroke:#fff}
.mb-node.n-inProgress .arc{stroke:var(--live)}
.mb-node.n-delayed .arc{stroke:var(--fire)}
.mb-node.n-notStarted .arc{stroke:var(--ink4)}
.mb-node.n-notStarted .hollow{stroke:var(--ink4)}
.mb-node-c{position:absolute;inset:0;display:grid;place-items:center;font-size:10.5px;font-weight:500;line-height:1}
.mb-node.n-inProgress .mb-node-c{color:var(--live-deep)}
.mb-node.n-delayed .mb-node-c{color:var(--fire-deep)}
.mb-node.n-delayed:not(.is-mini)::after{content:'';position:absolute;inset:-2px;border-radius:50%;box-shadow:0 0 0 0 var(--fire-halo);animation:mbPulse 1.9s ease-out infinite}

/* TOOLTIP */
.mb-tip{position:absolute;left:50%;bottom:calc(100% + 9px);transform:translateX(-50%) translateY(3px);width:178px;background:#fff;border:1px solid var(--line2);border-radius:9px;box-shadow:0 12px 34px rgba(20,28,46,.18);padding:9px 11px;opacity:0;visibility:hidden;transition:opacity .14s,transform .14s,visibility .14s;z-index:50;pointer-events:none;text-align:left}
.mb-tip.flip{bottom:auto;top:calc(100% + 9px)}
.mb-track:hover .mb-tip,.mb-track:focus-visible .mb-tip{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0)}
.mb-tip-h{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}
.mb-tip-h b{font-size:11.5px;font-weight:500}
.mb-tag{padding:1px 6px;border-radius:4px;font-size:9.5px;line-height:1.6;white-space:nowrap}
.mb-tag.t-done{background:var(--done-soft);color:#0B7A53}.mb-tag.t-live{background:var(--live-soft);color:var(--live-deep)}
.mb-tag.t-fire{background:var(--fire-band);color:var(--fire-deep)}.mb-tag.t-todo{background:#F0F2F6;color:var(--ink3)}
.mb-tip-r{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:11px;line-height:1.95;color:var(--ink3)}
.mb-tip-r b{font-weight:400;color:var(--ink2)}

@media (max-width:1180px){
  .mb-legend{order:3;width:100%;margin-left:0}
  .mb-head{align-items:flex-start}
}
`;
