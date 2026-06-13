import type {
  ContingencyGeneration,
  ContingencyLaneKey,
  DeliveryPlanActivityRow,
  GanttActivity,
  GanttModel,
  GanttMonth,
  OntologyNodeView,
  OntologyView,
  SeverityClass,
} from '@/types/domain';

/* 把后端 deriveContingencyRisks 的真实派生结果映射成脑图视图模型。
 * 四条生命周期通道 → 脑图四槽位；槽位 key 沿用 digital-ontology 既有内部键
 * (network/device/service/acceptance)，这样粒子云/动画/布局完全复用、无需改键。 */

interface LaneDef {
  key: ContingencyLaneKey;
  title: string;
  en: string;
  tag: string;
  desc: string;
  pos: { x: number; y: number };
  match: (riskPoint: string) => boolean;
}

const LANES: readonly LaneDef[] = [
  {
    key: 'network',
    title: '维保策略',
    en: 'Maintenance · EOS/GA',
    tag: 'LIFECYCLE',
    desc: '维保策略事实按规则库派生 EOS（产品维保期内停服）、GA 晚于维保开始风险。',
    pos: { x: -1, y: -1 },
    // 镜像后端 _lane_for_contingency_risk_point：EOS/GA → 维保章槽位（服务③）。
    match: (rp: string) => rp.includes('EOS') || rp.includes('GA'),
  },
  {
    key: 'device',
    title: '设备配置',
    en: 'Equipment · EOM/TR5',
    tag: 'LIFECYCLE',
    desc: '设备型号事实派生 EOM 停产、TR5 计划晚于交付窗口风险。',
    pos: { x: 1, y: -1 },
    match: (rp: string) => rp.includes('EOM') || rp.includes('TR5'),
  },
  {
    key: 'service',
    title: '部件配置',
    en: 'Component · ESS',
    tag: 'LIFECYCLE',
    desc: '部件配置事实派生 ESS（超出服务/支持窗口）风险。',
    pos: { x: -1, y: 1 },
    match: (rp: string) => rp.includes('ESS'),
  },
  {
    key: 'acceptance',
    title: '验收策略',
    en: 'Acceptance · ACC-CHK',
    tag: 'ACCEPTANCE',
    desc: '验收策略事实派生到货验收里程碑缺失等可交付性风险。',
    pos: { x: 1, y: 1 },
    match: () => true, // 兜底通道：未命中前三类的风险点归入验收
  },
];

/** riskPoint → 脑图槽位（按 LANES 顺序匹配，兜底落 acceptance）。 */
export function laneForRiskPoint(riskPoint: string): ContingencyLaneKey {
  const rp = riskPoint || '';
  for (const lane of LANES) {
    if (lane.match(rp)) return lane.key;
  }
  return 'acceptance';
}

/** riskLevel(高/中/低) → 严重度等级（复用 RiskCard 的 high/mid/low）。 */
export function severityClass(severity: string): SeverityClass {
  const s = severity || '';
  if (s.includes('高')) return 'high';
  if (s.includes('中')) return 'mid';
  return 'low';
}

/* 4 子决策点的脑图呈现（槽位/英文名/序号）；与 LANES 的四角位置一致，保证粒子/动画键不变。 */
const DECISION_PRESENTATION: Record<ContingencyLaneKey, { pos: { x: number; y: number }; en: string; tag: string }> = {
  network: { pos: { x: -1, y: -1 }, en: 'Network Deliverability', tag: '子决策 ①' },
  device: { pos: { x: 1, y: -1 }, en: 'Equipment Deliverability', tag: '子决策 ②' },
  service: { pos: { x: -1, y: 1 }, en: 'Service Deliverability', tag: '子决策 ③' },
  acceptance: { pos: { x: 1, y: 1 }, en: 'Acceptance Deliverability', tag: '子决策 ④' },
};

const HIDDEN_REPORT_CHAPTER_IDS = new Set(['doc-ch-meta', 'doc-risks']);

export function mapGenerationToView(result: ContingencyGeneration): OntologyView {
  const byLane: Record<ContingencyLaneKey, number> = {
    network: 0,
    device: 0,
    service: 0,
    acceptance: 0,
  };
  let high = 0;
  let mid = 0;
  let low = 0;
  for (const risk of result.risks) {
    byLane[laneForRiskPoint(risk.riskPoint)] += 1;
    const sc = severityClass(risk.severity);
    if (sc === 'high') high += 1;
    else if (sc === 'mid') mid += 1;
    else low += 1;
  }

  // 脑图四节点 = 4 个子决策点（组网/设备/服务/验收 可交付性），由后端 decisionPoints 驱动；
  // 旧服务无 decisionPoints 时回退按 LANES（生命周期风险通道）渲染。
  const subDecisions = (result.decisionPoints ?? []).filter((d) => d.decisionLevel === 'sub');
  const nodes: OntologyNodeView[] = subDecisions.length
    ? subDecisions.map((dp) => {
        const pres = DECISION_PRESENTATION[dp.domain as ContingencyLaneKey] ?? DECISION_PRESENTATION.acceptance;
        const count = dp.riskCount ?? 0;
        const warning = count > 0;
        return {
          key: dp.domain as ContingencyLaneKey,
          title: dp.decisionName,
          en: pres.en,
          tag: pres.tag,
          desc: dp.decisionQuestion,
          pos: pres.pos,
          result: warning ? 'warning' : 'success',
          resultTag: warning ? `${count} 项风险` : '可交付',
          count,
          anchor: dp.anchorChapterId || `doc-${dp.domain}`,
        };
      })
    : LANES.map((lane) => {
        const count = byLane[lane.key];
        const warning = count > 0;
        return {
          key: lane.key,
          title: lane.title,
          en: lane.en,
          tag: lane.tag,
          desc: lane.desc,
          pos: { x: lane.pos.x, y: lane.pos.y },
          result: warning ? 'warning' : 'success',
          resultTag: warning ? `${count} 项风险` : '无风险',
          count,
        };
      });

  return {
    nodes,
    decision: result.riskCount > 0 ? 'risk' : 'success',
    risks: result.risks,
    // 元数据章（doc-ch-meta）与风险&假设汇总章（doc-risks）已从后端章节目录删除（不再产出），
    // 此过滤仅作兜底：旧后端 / 历史缓存 payload 仍可能带这两章——
    // TOC 目录与报告正文同源于此 chapters，过滤后两处及全部「X 章」计数一并同步。
    // 章节序号按位置重排：裁剪掉部分章后存活章会跳号（2、5、8…），重编为连续 1..N。
    // no 仅作展示（导航锚点用 id），重排安全；全选时本就是 1..13、无变化。
    chapters: (result.chapters ?? [])
      .filter((c) => !HIDDEN_REPORT_CHAPTER_IDS.has(c.id) && !c.consolidatesRisks)
      .map((c, i) => ({ ...c, no: String(i + 1) })),
    decisionPoints: result.decisionPoints ?? [],
    coreDecision: (result.decisionPoints ?? []).find((d) => d.decisionLevel === 'core') ?? null,
    summary: { riskCount: result.riskCount, high, mid, low, byLane },
  };
}

/* =========================================================
   交付计划甘特：delivery_plan_row（计划章）→ 一级活动甘特模型
   一级活动 = activityId 不含小数点（'7' 一级 / '7.1' 二级）；同一活动跨多 PoD 多行，
   按 activityId 聚合（min start / max end / 覆盖 PoD 数 / 是否命中工期风险）。纯函数、可单测。
   ========================================================= */

const EMPTY_GANTT: GanttModel = { activities: [], minDate: '', maxDate: '', months: [], totalDays: 0 };

/** 'YYYY-MM-DD' → 自 epoch 起的整数天号（UTC，规避时区）；无法解析返回 null。 */
function parseDayNumber(value: unknown): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value ?? '').trim());
  if (!m) return null;
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(t) ? null : Math.floor(t / 86_400_000);
}

/** 天号 → 'YYYY-MM-DD'。 */
function dayNumberToISO(day: number): string {
  const d = new Date(day * 86_400_000);
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, '0');
  const da = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${mo}-${da}`;
}

/** 一级活动判定：activityId 非空且不含小数点。 */
export function isFirstLevelActivityId(activityId: unknown): boolean {
  const id = String(activityId ?? '').trim();
  return id.length > 0 && !id.includes('.');
}

interface FirstLevelAgg {
  activityId: string;
  nameCounts: Map<string, number>;
  owner: string;
  pods: Set<string>;
  startDay: number | null;
  endDay: number | null;
  hasRisk: boolean;
}

/** 把 delivery_plan_row 投影行聚合成一级活动甘特模型（按月时间轴 + 每条 bar 的定位百分比）。 */
export function buildFirstLevelGantt(rows: readonly DeliveryPlanActivityRow[] | null | undefined): GanttModel {
  if (!Array.isArray(rows) || rows.length === 0) return EMPTY_GANTT;

  const groups = new Map<string, FirstLevelAgg>();
  for (const row of rows) {
    if (!row || !isFirstLevelActivityId(row.activityId)) continue;
    const id = String(row.activityId).trim();
    let g = groups.get(id);
    if (!g) {
      g = { activityId: id, nameCounts: new Map(), owner: '', pods: new Set(), startDay: null, endDay: null, hasRisk: false };
      groups.set(id, g);
    }
    const name = String(row.activityName ?? '').trim();
    if (name) g.nameCounts.set(name, (g.nameCounts.get(name) ?? 0) + 1);
    const owner = String(row.owner ?? '').trim();
    if (owner && !g.owner) g.owner = owner;
    const pod = String(row.managementUnit ?? '').trim();
    if (pod) g.pods.add(pod);
    if (String(row.riskBelowStandard ?? '').trim()) g.hasRisk = true;
    const s = parseDayNumber(row.startDate);
    if (s !== null) g.startDay = g.startDay === null ? s : Math.min(g.startDay, s);
    const e = parseDayNumber(row.endDate);
    if (e !== null) g.endDay = g.endDay === null ? e : Math.max(g.endDay, e);
  }

  // 只保留能在时间轴上定位的活动（同时有有效起止）。
  const placeable = [...groups.values()].filter(
    (g): g is FirstLevelAgg & { startDay: number; endDay: number } => g.startDay !== null && g.endDay !== null,
  );
  if (placeable.length === 0) return EMPTY_GANTT;

  const minDay = Math.min(...placeable.map((g) => g.startDay));
  const maxDay = Math.max(...placeable.map((g) => g.endDay));
  const totalDays = maxDay - minDay + 1;

  const mostCommonName = (g: FirstLevelAgg): string => {
    let best = '';
    let bestN = -1;
    for (const [name, n] of g.nameCounts) {
      if (n > bestN) {
        best = name;
        bestN = n;
      }
    }
    return best || g.activityId;
  };

  const activities: GanttActivity[] = placeable
    .map((g) => {
      const durationDays = g.endDay - g.startDay + 1;
      return {
        activityId: g.activityId,
        name: mostCommonName(g),
        start: dayNumberToISO(g.startDay),
        end: dayNumberToISO(g.endDay),
        owner: g.owner,
        podCount: g.pods.size,
        durationDays,
        hasRisk: g.hasRisk,
        leftPct: ((g.startDay - minDay) / totalDays) * 100,
        widthPct: (durationDays / totalDays) * 100,
      } satisfies GanttActivity;
    })
    .sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : Number(a.activityId) - Number(b.activityId)));

  // 月份轴列：从 minDay 所在月遍历到 maxDay 所在月，列宽 = 该月落区间天数 / 总跨度。
  const months: GanttMonth[] = [];
  const first = new Date(minDay * 86_400_000);
  let y = first.getUTCFullYear();
  let mo = first.getUTCMonth(); // 0-based
  for (;;) {
    const monthFirstDay = Math.floor(Date.UTC(y, mo, 1) / 86_400_000);
    const monthLastDay = Math.floor(Date.UTC(y, mo + 1, 0) / 86_400_000); // 下月第0天 = 本月最后一天
    if (monthFirstDay > maxDay) break;
    const overlapStart = Math.max(minDay, monthFirstDay);
    const overlapEnd = Math.min(maxDay, monthLastDay);
    const overlapDays = Math.max(0, overlapEnd - overlapStart + 1);
    months.push({
      key: `${y}-${String(mo + 1).padStart(2, '0')}`,
      label: `${y}-${String(mo + 1).padStart(2, '0')}`,
      widthPct: (overlapDays / totalDays) * 100,
    });
    mo += 1;
    if (mo > 11) {
      mo = 0;
      y += 1;
    }
  }

  return { activities, minDate: dayNumberToISO(minDay), maxDate: dayNumberToISO(maxDay), months, totalDays };
}
