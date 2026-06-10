/* AIDA · activities-graph.tsx
 * 活动依赖图（基于 data/activities.json）· 任务 #7
 * 默认折到 10 个一级阶段，节点编码约束源（站棕 / 货红 / 人蓝 / 纯依赖灰），FS 箭头。
 * 点击阶段节点 → 下方展开该阶段子节点（含 SLA / 角色 / 责任人 / 子依赖）。
 * 顶部过滤：批次（设备批 2~7）· 约束源 · 角色。
 *
 * 第一版聚焦"成图 + 能演示"，inline 编辑改值留给 #3 任务，本组件先做信息浏览。
 */
import React from 'react';
import { ACTIVITIES, type Activity } from './data/activities';

const { useMemo, useState } = React;

// 约束源 → 配色（参照 planinit.css 已有 token 风格）
const SRC_COLOR: Record<string, { fill: string; stroke: string; text: string }> = {
  "站":     { fill: "#FAF0D9", stroke: "#BC7E14", text: "#7A5409" },
  "货":     { fill: "#FBE8E6", stroke: "#CE382F", text: "#8B221C" },
  "人":     { fill: "#EAEEFC", stroke: "#3551D1", text: "#1F2F8C" },
  "纯依赖": { fill: "#F3F5F8", stroke: "#8B96AC", text: "#46556B" },
};

// 节点几何
const NODE_W = 132;
const NODE_H = 56;
const GAP = 28;
const ROW_Y = 36;
const SVG_PAD_X = 16;
const SVG_H = ROW_Y + NODE_H + 36;

function ActivitiesGraph(){
  const [batchFilter, setBatchFilter] = useState<number | "all">("all");
  const [srcFilter, setSrcFilter] = useState<string>("all");
  const [roleFilter, setRoleFilter] = useState<string>("all"); // all / R / S
  const [openPhase, setOpenPhase] = useState<string | null>(null);

  // ===== 过滤后的活动集 =====
  const filtered = useMemo(() => ACTIVITIES.filter(a => {
    if (batchFilter !== "all" && a.batch !== batchFilter) return false;
    if (srcFilter !== "all" && a.constraintSource !== srcFilter) return false;
    if (roleFilter !== "all") {
      const has = (roleFilter === "R") ? (a.remoteTeam === "R") : (a.siteTeam === "S");
      if (!has) return false;
    }
    return true;
  }), [batchFilter, srcFilter, roleFilter]);

  // ===== 阶段节点（一级）=====
  // 总是显示全部 10 个一级阶段（保留骨架感），但子节点数和颜色反映过滤后结果
  const allPhases = useMemo(() => ACTIVITIES
    .filter(a => a.level === 1)
    .sort((a,b) => parseFloat(a.id) - parseFloat(b.id)), []);

  // 过滤态下，每个阶段在过滤集中的子节点数
  const childCount = useMemo(() => {
    const map = new Map<string, number>();
    for (const a of filtered) {
      if (a.parentId) map.set(a.parentId, (map.get(a.parentId) || 0) + 1);
    }
    return map;
  }, [filtered]);

  // ===== 阶段间 FS 依赖聚合 =====
  // 规则：对每条三级活动 A 的依赖 D，找到 D 所在阶段 P_D 与 A 所在阶段 P_A，若 P_D ≠ P_A 则加边 P_D → P_A
  const phaseEdges = useMemo(() => {
    const byName = new Map<string, Activity>();
    ACTIVITIES.forEach(a => byName.set(a.name, a));
    const seen = new Set<string>();
    const edges: { from: string; to: string }[] = [];
    for (const a of filtered) {
      if (!a.parentId) continue;
      for (const dn of a.depNames) {
        const dep = byName.get(dn);
        if (!dep || !dep.parentId) continue;
        if (dep.parentId === a.parentId) continue;
        const k = dep.parentId + "→" + a.parentId;
        if (seen.has(k)) continue;
        seen.add(k);
        edges.push({ from: dep.parentId, to: a.parentId });
      }
    }
    return edges;
  }, [filtered]);

  const xOf = (id: string) => {
    const idx = allPhases.findIndex(p => p.id === id);
    return SVG_PAD_X + idx * (NODE_W + GAP);
  };
  const svgW = SVG_PAD_X * 2 + (allPhases.length - 1) * (NODE_W + GAP) + NODE_W;

  // 阶段间边：相邻直线，跨阶段弯一下避免穿过中间节点
  const renderEdge = (e: { from: string; to: string }, i: number) => {
    const fi = allPhases.findIndex(p => p.id === e.from);
    const ti = allPhases.findIndex(p => p.id === e.to);
    if (fi < 0 || ti < 0) return null;
    const x1 = xOf(e.from) + NODE_W;
    const x2 = xOf(e.to);
    const y = ROW_Y + NODE_H / 2;
    const dist = Math.abs(ti - fi);
    let path: string;
    if (dist === 1) {
      path = `M ${x1} ${y} L ${x2} ${y}`;
    } else {
      // 跨阶段：向上拱起，避开中间节点
      const lift = 22 + (dist - 1) * 6;
      const mx = (x1 + x2) / 2;
      path = `M ${x1} ${y} C ${x1 + 18} ${y - lift}, ${x2 - 18} ${y - lift}, ${x2} ${y}`;
    }
    return <path key={i} d={path} fill="none" stroke="#A8B3C6" strokeWidth={1.3} markerEnd="url(#arrowhead)" />;
  };

  // 展开阶段的子节点（来自过滤后集合）
  const openChildren = useMemo(() => {
    if (!openPhase) return [];
    return filtered.filter(a => a.parentId === openPhase)
      .sort((a,b) => (parseFloat(a.id || "0") - parseFloat(b.id || "0")));
  }, [openPhase, filtered]);

  const openPhaseObj = openPhase ? allPhases.find(p => p.id === openPhase) : null;

  return (
    <div className="act-graph">
      {/* ===== 顶部过滤 ===== */}
      <div className="ag-filters">
        <span className="ag-fl-l">过滤</span>
        <label className="ag-fl">批次
          <select value={batchFilter === "all" ? "all" : String(batchFilter)}
            onChange={e => setBatchFilter(e.target.value === "all" ? "all" : +e.target.value)}>
            <option value="all">全部</option>
            <option value="2">批 2 · 通用线缆</option>
            <option value="3">批 3 · 通算</option>
            <option value="4">批 4 · 网络</option>
            <option value="5">批 5 · 计算柜</option>
            <option value="6">批 6 · 灵衢线缆</option>
            <option value="7">批 7 · 存储</option>
          </select>
        </label>
        <label className="ag-fl">约束源
          <select value={srcFilter} onChange={e => setSrcFilter(e.target.value)}>
            <option value="all">全部</option>
            <option value="站">站</option>
            <option value="货">货</option>
            <option value="人">人</option>
            <option value="纯依赖">纯依赖</option>
          </select>
        </label>
        <label className="ag-fl">角色
          <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}>
            <option value="all">全部</option>
            <option value="R">远程 R</option>
            <option value="S">现场 S</option>
          </select>
        </label>
        <span className="ag-stat">{filtered.length} / {ACTIVITIES.length} 活动 · {phaseEdges.length} 跨阶段依赖</span>
      </div>

      {/* ===== 图例 ===== */}
      <div className="ag-legend">
        {Object.entries(SRC_COLOR).map(([k,c]) => (
          <span key={k} className="ag-leg-item">
            <i style={{background:c.fill, border:`1px solid ${c.stroke}`}}/> {k}
          </span>
        ))}
        <span className="ag-leg-sep"/>
        <span className="ag-leg-item">→ FS 跨阶段依赖</span>
        <span className="ag-leg-item">默认折到 10 个一级阶段，点节点展开</span>
      </div>

      {/* ===== 主图（SVG）===== */}
      <div className="ag-svg-wrap">
        <svg width={svgW} height={SVG_H} viewBox={`0 0 ${svgW} ${SVG_H}`} className="ag-svg">
          <defs>
            <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#A8B3C6" />
            </marker>
          </defs>
          {/* 边 */}
          <g className="ag-edges">{phaseEdges.map((e,i) => renderEdge(e, i))}</g>
          {/* 节点 */}
          <g className="ag-nodes">
            {allPhases.map(p => {
              const c = SRC_COLOR[p.constraintSource] || SRC_COLOR["纯依赖"]!;
              const x = xOf(p.id);
              const cc = childCount.get(p.id) || 0;
              const dim = cc === 0;
              const open = openPhase === p.id;
              return (
                <g key={p.id} className="ag-node" transform={`translate(${x},${ROW_Y})`}
                   onClick={() => setOpenPhase(prev => prev === p.id ? null : p.id)} style={{cursor:"pointer"}}>
                  <rect width={NODE_W} height={NODE_H} rx={9} ry={9}
                    fill={dim ? "#F8F9FB" : c.fill}
                    stroke={open ? "var(--brand,#3551D1)" : (dim ? "#D8DEE7" : c.stroke)}
                    strokeWidth={open ? 2.2 : 1.4} opacity={dim ? .55 : 1}/>
                  <text x={NODE_W/2} y={22} textAnchor="middle"
                    fontSize="12.5" fontWeight="600" fill={dim ? "#8B96AC" : c.text}>
                    {p.name.length > 8 ? p.name.slice(0,8)+"…" : p.name}
                  </text>
                  <text x={NODE_W/2} y={40} textAnchor="middle"
                    fontSize="10" fontFamily="var(--mono)" fill={dim ? "#A8B3C6" : c.text} opacity={.78}>
                    {p.id} · {cc} 活动 · {p.constraintSource}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* ===== 展开详情 ===== */}
      {openPhase && openPhaseObj && (
        <div className="ag-detail">
          <div className="ag-dh">
            <span className="ag-dh-name">
              <i className="ag-dh-dot" style={{background:(SRC_COLOR[openPhaseObj.constraintSource]||SRC_COLOR["纯依赖"]!).stroke}}/>
              {openPhaseObj.name}
            </span>
            <span className="ag-dh-meta">{openPhaseObj.id} · {openPhaseObj.constraintSource}约束 · {openChildren.length} 个子活动</span>
            <button className="ag-dh-close" onClick={() => setOpenPhase(null)}>收起 ×</button>
          </div>
          {openChildren.length === 0 ? (
            <div className="ag-empty">当前过滤下，本阶段没有可见活动。试试调整顶部过滤条。</div>
          ) : (
            <div className="ag-rows">
              {openChildren.map(a => {
                const c = SRC_COLOR[a.constraintSource] || SRC_COLOR["纯依赖"]!;
                return (
                  <div className="ag-row" key={a.id}
                       style={{borderLeftColor: c.stroke}}>
                    <span className="ag-r-id">{a.id}</span>
                    <span className="ag-r-name">{a.name}</span>
                    <span className={"ag-r-src "+(a.constraintSource==="站"?"s":a.constraintSource==="货"?"g":a.constraintSource==="人"?"r":"d")}>
                      {a.constraintSource}
                    </span>
                    <span className="ag-r-sla">{a.slaDays != null ? `${a.slaDays}d` : (a.level === 1 ? "阶段" : "—")}</span>
                    <span className="ag-r-batch">{a.batch ? `批${a.batch}` : ""}</span>
                    <span className="ag-r-role">
                      {a.siteTeam === "S" && <span className="ag-pip s">S 现场</span>}
                      {a.remoteTeam === "R" && <span className="ag-pip r">R 远程</span>}
                    </span>
                    <span className="ag-r-owner">{a.owner || ""}</span>
                    {a.depNames.length > 0 && (
                      <span className="ag-r-deps">← {a.depNames.join("、")}</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export { ActivitiesGraph };
