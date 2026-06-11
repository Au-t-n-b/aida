'use client';

import { useMemo, useState } from 'react';
import Link from '@/compat/link';

/* ─────────────────────────────────────────────
 * 5.28 H-3 · PoD × 里程碑 下钻页
 * 牛博风格界面：
 *   - 行：PoD 10 ~ 15
 *   - 列：10 项里程碑（工程准备 / 设计评审 / 预制 /
 *         设备部署 / 现场施工 / 上电 / ZTP 升级 /
 *         安装 / 测试 / 验收）
 *   - 单元格：双杠 Gantt（上=计划 起止；下=实际 起止）
 *   - 默认隐藏日期；hover 弹卡显示详情
 * ─────────────────────────────────────────────
 */

/* 5.28 拍板：原"挂树"已统一改为"验收" */
const STAGES = [
  { key: 'prep',     name: '工程准备', short: '准备' },
  { key: 'review',   name: '设计评审', short: '评审' },
  { key: 'prefab',   name: '预制',     short: '预制' },
  { key: 'deploy',   name: '设备部署', short: '部署' },
  { key: 'onsite',   name: '现场施工', short: '施工' },
  { key: 'powerup',  name: '上电',     short: '上电' },
  { key: 'ztp',      name: 'ZTP 升级', short: 'ZTP' },
  { key: 'install',  name: '安装',     short: '安装' },
  { key: 'test',     name: '测试',     short: '测试' },
  { key: 'accept',   name: '验收',     short: '验收' },
];

/* mock 10 个 PoD x 10 个里程碑 数据
 * baselineStart / baselineEnd : 计划基线
 * actualStart  / actualEnd    : 实际进展（actualEnd = '' 表示未完成）
 * 时间格式 yyyy-MM-dd
 */
function genCells() {
  const pods: string[] = ['PoD-10','PoD-11','PoD-12','PoD-13','PoD-14','PoD-15'];
  const start = new Date('2026-04-01');
  const rows: Array<{ pod: string; cells: any[] }> = [];
  for (let pi = 0; pi < pods.length; pi++) {
    const cells = STAGES.map((s, si) => {
      // 计划：每个 PoD 偏移 7 天，每个里程碑占 7 天
      const planS = new Date(start.getTime() + (pi * 7 + si * 7) * 86400000);
      const planE = new Date(planS.getTime() + 7 * 86400000);
      // 实际：根据 pi、si 模拟不同状态
      const drift = ((pi * 3 + si * 7) % 11) - 5; // -5 ~ +5 天偏移
      const actS  = new Date(planS.getTime() + drift * 86400000);
      const isDone = (pi * 10 + si) < 28;          // 前 28 个完成
      const isOngoing = !isDone && (pi * 10 + si) < 36;
      const actE  = isDone ? new Date(actS.getTime() + 7 * 86400000) : null;
      let state: 'pending' | 'done' | 'late' | 'doing' | 'risk' = 'pending';
      if (isDone) state = drift > 1 ? 'late' : 'done';
      else if (isOngoing) state = drift > 1 ? 'risk' : 'doing';

      const fmt = (d: Date) => d.toISOString().slice(0, 10);
      return {
        stage: s.key,
        state,
        planStart:   fmt(planS),
        planEnd:     fmt(planE),
        actualStart: isDone || isOngoing ? fmt(actS) : '',
        actualEnd:   actE ? fmt(actE) : '',
        drift,
      };
    });
    rows.push({ pod: pods[pi] as string, cells });
  }
  return rows;
}

const ROWS = genCells();

/* 把全局所有日期取得 min/max，方便算 Gantt 位置 */
const GLOBAL_RANGE = (() => {
  let min = Infinity, max = -Infinity;
  ROWS.forEach(r => r.cells.forEach(c => {
    const ps = +new Date(c.planStart);
    const pe = +new Date(c.planEnd);
    if (ps < min) min = ps; if (pe > max) max = pe;
    if (c.actualStart) {
      const as = +new Date(c.actualStart); if (as < min) min = as;
    }
    if (c.actualEnd) {
      const ae = +new Date(c.actualEnd);   if (ae > max) max = ae;
    }
  }));
  return { min, max };
})();

function dayPct(date: string) {
  if (!date) return null;
  const t = +new Date(date);
  return ((t - GLOBAL_RANGE.min) / (GLOBAL_RANGE.max - GLOBAL_RANGE.min)) * 100;
}

const STATE_TONE: Record<string, { fill: string; bd: string; label: string }> = {
  done:    { fill: '#22c55e', bd: '#15803d', label: '已完成 · 按期' },
  late:    { fill: '#f59e0b', bd: '#b45309', label: '已完成 · 延期' },
  doing:   { fill: '#1b84ff', bd: '#1e40af', label: '进行中' },
  risk:    { fill: '#ef4444', bd: '#b91c1c', label: '进行中 · 风险' },
  pending: { fill: '#e2e8f0', bd: '#94a3b8', label: '未开始' },
};

export default function MilestonesScreen() {
  const [hover, setHover] = useState<{ pod: string; idx: number } | null>(null);
  const [highlightStage, setHighlightStage] = useState<string | null>(null);

  const summary = useMemo(() => {
    let done = 0, doing = 0, risk = 0, pending = 0;
    ROWS.forEach(r => r.cells.forEach(c => {
      if (c.state === 'done' || c.state === 'late') done++;
      else if (c.state === 'doing') doing++;
      else if (c.state === 'risk') risk++;
      else pending++;
    }));
    return { done, doing, risk, pending, total: ROWS.length * STAGES.length };
  }, []);

  return (
    <div style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        <div className="page-head">
          <div>
            <div className="bc">
              <Link href="/cockpit" style={{ color: 'var(--c-text-muted)', textDecoration: 'none' }}>项目孪生</Link>
              <span style={{ margin: '0 6px', color: 'var(--c-text-faint)' }}>/</span>
              <span>PoD 级里程碑下钻</span>
            </div>
            <h1>PoD × 里程碑 · 双杠 Gantt</h1>
            <div className="sub">6 个 PoD × 10 项里程碑 · 上=计划 下=实际 · hover 看详情</div>
          </div>
          <div className="right">
            <Link href="/cockpit" className="btn-ghost">← 回项目孪生</Link>
          </div>
        </div>

        {/* 顶部小结 */}
        <div className="milestones-summary">
          <div className="milestones-sum-card tone-green">
            <div className="k">已完成</div>
            <div className="v">{summary.done}</div>
            <div className="t">/ {summary.total}</div>
          </div>
          <div className="milestones-sum-card tone-blue">
            <div className="k">进行中</div>
            <div className="v">{summary.doing}</div>
            <div className="t">/ {summary.total}</div>
          </div>
          <div className="milestones-sum-card tone-red">
            <div className="k">风险</div>
            <div className="v">{summary.risk}</div>
            <div className="t">/ {summary.total}</div>
          </div>
          <div className="milestones-sum-card tone-gray">
            <div className="k">未开始</div>
            <div className="v">{summary.pending}</div>
            <div className="t">/ {summary.total}</div>
          </div>
          <div className="milestones-sum-legend">
            <span><i className="state-dot state-done" /> 按期</span>
            <span><i className="state-dot state-doing" /> 进行</span>
            <span><i className="state-dot state-risk" /> 风险</span>
            <span><i className="state-dot state-pending" /> 未开始</span>
          </div>
        </div>

        {/* 主表 */}
        <div className="milestones-table-wrap">
          <table className="milestones-table">
            <thead>
              <tr>
                <th className="col-pod">PoD</th>
                {STAGES.map(s => (
                  <th
                    key={s.key}
                    className={`col-stage${highlightStage === s.key ? ' on' : ''}`}
                    onMouseEnter={() => setHighlightStage(s.key)}
                    onMouseLeave={() => setHighlightStage(null)}
                  >
                    <div className="col-stage-name">{s.name}</div>
                    <div className="col-stage-key">{s.short}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map(r => (
                <tr key={r.pod}>
                  <td className="col-pod">{r.pod}</td>
                  {r.cells.map((c, ci) => (
                    <td
                      key={ci}
                      className={`milestones-cell${highlightStage === c.stage ? ' on-col' : ''}`}
                      onMouseEnter={() => setHover({ pod: r.pod, idx: ci })}
                      onMouseLeave={() => setHover(null)}
                    >
                      <DoubleBar cell={c} />
                      {hover && hover.pod === r.pod && hover.idx === ci && STAGES[ci] && (
                        <CellTooltip pod={r.pod} stage={STAGES[ci] as { key: string; name: string; short: string }} cell={c} />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 说明 */}
        <div className="milestones-help">
          <div className="milestones-help-title">说明</div>
          <ul>
            <li><b>上杠（实心）</b>：计划基线 · 起 / 止</li>
            <li><b>下杠（轮廓）</b>：实际进展 · 已发生段实色，未发生段虚线</li>
            <li><b>颜色</b>：绿=按期 · 蓝=进行 · 黄=完成但延期 · 红=进行+风险 · 灰=未开始</li>
            <li>日期默认隐藏，<b>hover 单元格</b>弹详情</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

/* 双杠组件：在 100% 范围内按 GLOBAL_RANGE 排两条 */
function DoubleBar({ cell }: { cell: any }) {
  const tone = (STATE_TONE[cell.state] ?? STATE_TONE.pending) as { fill: string; bd: string; label: string };
  const planL = dayPct(cell.planStart) ?? 0;
  const planR = dayPct(cell.planEnd)   ?? 0;
  const actL  = dayPct(cell.actualStart);
  const actR  = dayPct(cell.actualEnd);

  return (
    <div className="dbar">
      {/* 计划杠：上 */}
      <div
        className="dbar-row plan"
        style={{
          left:  `${planL}%`,
          width: `${Math.max(planR - planL, 1.5)}%`,
          background: tone.fill,
          borderColor: tone.bd,
        }}
      />
      {/* 实际杠：下 */}
      {actL != null && (
        <div
          className={`dbar-row actual${actR == null ? ' open' : ''}`}
          style={{
            left:  `${actL}%`,
            width: actR != null
              ? `${Math.max(actR - actL, 1.5)}%`
              : `${Math.max((planR - actL) / 2, 1.5)}%`,
            borderColor: tone.bd,
            background: actR != null ? 'transparent' : 'transparent',
          }}
        />
      )}
    </div>
  );
}

type CellTooltipProps = { pod: string; stage: { key: string; name: string; short: string }; cell: any };
function CellTooltip({ pod, stage, cell }: CellTooltipProps) {
  const tone = (STATE_TONE[cell.state] ?? STATE_TONE.pending) as { fill: string; bd: string; label: string };
  return (
    <div className="milestones-tip">
      <div className="milestones-tip-h">
        <span style={{ background: tone.fill, borderColor: tone.bd }} className="milestones-tip-dot" />
        <b>{pod}</b> · {stage.name}
        <span className="milestones-tip-state">{tone.label}</span>
      </div>
      <div className="milestones-tip-rows">
        <div className="row"><span className="k">计划起</span><span className="v">{cell.planStart}</span></div>
        <div className="row"><span className="k">计划止</span><span className="v">{cell.planEnd}</span></div>
        <div className="row"><span className="k">实际起</span><span className="v">{cell.actualStart || '—'}</span></div>
        <div className="row"><span className="k">实际止</span><span className="v">{cell.actualEnd || '—'}</span></div>
        <div className="row">
          <span className="k">偏差</span>
          <span className="v" style={{ color: cell.drift > 1 ? 'var(--c-danger)' : cell.drift < 0 ? 'var(--c-success)' : 'var(--c-text)' }}>
            {cell.drift > 0 ? `+${cell.drift}` : cell.drift} 天
          </span>
        </div>
      </div>
    </div>
  );
}
