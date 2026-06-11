/* 关键路径时间轴 · 与甘特 eff/base 联动（拖工期 → 节点天数/偏差实时更新） */
import { useMemo } from "react";

type GdAct = { id: string; name: string; progress: number; milestone?: boolean };
type SchedSlice = { start: Record<string, string>; end: Record<string, string>; dur: Record<string, number> };

/** 与 GD_CRIT 一致：批次3 主链路 + 整体验收/交付里程碑，共 10 节点 */
const CP_CHAIN = ["G00", "G01", "B3A", "B3I", "B3C", "B3P", "B3U", "B3G", "G99", "G98"] as const;
const CP_FINAL = "G98";

const cpShortName = (name: string) =>
  name.replace(/\s*\([^)]*\)/g, "").replace(/\s*·\s*批\d+/g, "").trim();

const cpMD = (iso: string) => (iso ? iso.slice(5) : "—");
const cpRange = (s: string, e: string) => (s === e ? cpMD(s) : `${cpMD(s)}~${cpMD(e)}`);

/** 关键路径标题 · 五角星（与 plan-board `I.spark` 等同系 fill 图标） */
function CpStarIcon({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" aria-hidden>
      <path
        d="M9 2.1 L10.85 7.05 L16.15 7.05 L11.85 10.25 L13.7 15.2 L9 12.05 L4.3 15.2 L6.15 10.25 L1.85 7.05 L7.15 7.05 Z"
        fill="currentColor"
      />
    </svg>
  );
}

type CpNode = {
  id: string;
  label: string;
  range: string;
  days: number | null;
  delta: number | null;
  status: "done" | "early" | "late" | "neutral";
  milestone: boolean;
};

function buildNodes(
  acts: Map<string, GdAct>,
  eff: SchedSlice,
  base: SchedSlice,
  diff: (a: string, b: string) => number,
): CpNode[] {
  return CP_CHAIN.map((id) => {
    const a = acts.get(id)!;
    const es = eff.start[id]!, ee = eff.end[id]!;
    const bs = base.start[id]!, be = base.end[id]!;
    const dur = a.milestone ? null : eff.dur[id]!;
    const durDelta = a.milestone ? null : eff.dur[id]! - base.dur[id]!;
    // 与甘特 KPI 一致：diff(基线, 当前) —— 正=延后，负=提前（勿用 diff(当前, 基线)）
    const endSlip = diff(be, ee);
    const startSlip = diff(bs, es);
    // 优先展示工期改动；否则展示级联导致的结束日偏移
    let delta: number | null = null;
    if (a.milestone) delta = startSlip !== 0 ? startSlip : null;
    else if (durDelta !== 0) delta = durDelta;
    else if (endSlip !== 0) delta = endSlip;
    const slip = delta ?? (a.milestone ? startSlip : endSlip);
    let status: CpNode["status"] = "neutral";
    if (a.progress >= 1 && slip <= 0) status = "done";
    else if (slip > 0) status = "late";
    else if (slip < 0) status = "early";
    return {
      id,
      label: cpShortName(a.name),
      range: a.milestone ? cpMD(es) : cpRange(es, ee),
      days: dur,
      delta: delta === 0 ? null : delta,
      status,
      milestone: !!a.milestone,
    };
  });
}

export function CriticalPathTimeline({
  acts,
  eff,
  base,
  diff,
  visible = true,
  selectedId = null,
  onSelectNode,
}: {
  acts: GdAct[];
  eff: SchedSlice;
  base: SchedSlice;
  diff: (a: string, b: string) => number;
  /** 与甘特工具栏「关键路径」勾选联动 · 关=隐藏时间轴 */
  visible?: boolean;
  /** 与甘特行选中联动 · 点节点反选活动 */
  selectedId?: string | null;
  onSelectNode?: (id: string) => void;
}) {
  const actMap = useMemo(() => new Map(acts.map((a) => [a.id, a])), [acts]);

  const nodes = useMemo(() => buildNodes(actMap, eff, base, diff), [actMap, eff, base, diff]);

  const { totalDays, totalDelta, startIso, endIso } = useMemo(() => {
    const startIso = eff.start[CP_CHAIN[0]!]!;
    const endIso = eff.start[CP_FINAL] || base.start[CP_FINAL]!;
    const bStart = base.start[CP_CHAIN[0]!]!;
    const bEnd = base.start[CP_FINAL]!;
    const totalDays = diff(startIso, endIso) + 1;
    const baseTotal = diff(bStart, bEnd) + 1;
    return { totalDays, totalDelta: totalDays - baseTotal, startIso, endIso };
  }, [eff, base, diff]);

  if (!visible) return null;

  return (
    <div className="cp-path in-gantt fade">
      <div className="cp-head">
        <div className="cp-head-l">
          <span className="ro-title">
            <CpStarIcon />
            关键路径
          </span>
          <span className="ro-sub">
            批次3 主链路 / <b className="tnum">{CP_CHAIN.length}</b> 节点
          </span>
          <span className="ro-sub">
            总工期：<b className="tnum">{totalDays}d</b>
            {totalDelta !== 0 && (
              <span className={"cp-total-badge " + (totalDelta > 0 ? "late" : "early")}>
                {totalDelta > 0 ? "+" : ""}{totalDelta}d
              </span>
            )}
          </span>
        </div>
        <div className="cp-head-r tnum">
          <span className="cp-range-s">{cpMD(startIso)}</span>
          <span className="cp-range-arr">→</span>
          <span className="cp-range-e"><b>{cpMD(endIso)}</b> <em>（最终交付）</em></span>
        </div>
      </div>
      <div className="cp-track">
        {nodes.map((n) => (
          <div
            className={"cp-node " + n.status + (n.milestone ? " ms" : "") + (selectedId === n.id ? " sel" : "") + (onSelectNode ? " clickable" : "")}
            key={n.id}
            role={onSelectNode ? "button" : undefined}
            tabIndex={onSelectNode ? 0 : undefined}
            onClick={onSelectNode ? () => onSelectNode(n.id) : undefined}
            onKeyDown={onSelectNode ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectNode(n.id); } } : undefined}
            title={onSelectNode ? "定位到甘特活动" : n.label}
          >
            <span className="cp-node-lab">{n.label}</span>
            <div className="cp-node-mid">
              <span className={"cp-node-dot" + (n.milestone ? " dia" : "")} aria-hidden />
            </div>
            <span className="cp-node-dates tnum">{n.range}</span>
            <span className="cp-node-foot tnum">
              {n.days != null && <span className="cp-node-dur">{n.days}d</span>}
              {n.delta != null && (
                <span className={"cp-node-var " + (n.delta > 0 ? "late" : "early")}>
                  {n.delta > 0 ? "+" : ""}{n.delta}d
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
