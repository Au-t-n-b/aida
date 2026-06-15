/* ─────────────────────────────────────────────────────────────
 * 交付里程碑看板 · 类型 + Mock 数据 + 派生（PoD 维度）
 *
 * 数据契约（后续数据中心接口返回同结构即可直接替换）：
 *   - 9 个 PoD × 6 个标准里程碑节点（顺序固定）
 *   - 每节点：名称 / 计划时间(必有) / 实际时间(未完成为 null) / 进度% / 状态枚举
 *
 * 设计原则（见 milestone-board.tsx 顶部）：渲染层只「读结论」不「读原始日期」——
 * 所有 计划/实际 对比都在这里预派生成 偏差/逾期/verdict，板面不出现日期墙。
 * ───────────────────────────────────────────────────────────── */

export const MILESTONE_STEPS = [
  { key: 'roomReady', name: '机房Ready' },
  { key: 'arrival', name: '到货' },
  { key: 'cabling', name: '综合布线' },
  { key: 'powerOn', name: '设备上电' },
  { key: 'online', name: '上线' },
  { key: 'handover', name: '移交' },
] as const satisfies readonly { key: string; name: string }[];

export type MilestoneKey = (typeof MILESTONE_STEPS)[number]['key'];

/** 未开工 / 进行中 / 已完成 / 延期（延期 = 未完成且已超计划时间，需 PD 关注） */
export type MilestoneStatus = 'notStarted' | 'inProgress' | 'done' | 'delayed';

export const STATUS_META = {
  done: { label: '已完成' },
  inProgress: { label: '进行中' },
  delayed: { label: '延期' },
  notStarted: { label: '未开工' },
} as const satisfies Record<MilestoneStatus, { label: string }>;

export interface Milestone {
  key: MilestoneKey;
  name: string;
  /** 计划完成时间 YYYY-MM-DD，必有 */
  plannedDate: string;
  /** 实际完成时间，未完成为 null */
  actualDate: string | null;
  /** 进度 0–100 */
  progress: number;
  status: MilestoneStatus;
}

export interface PodMilestones {
  podId: string;
  /** 机房归属（展示用副标） */
  room: string;
  /** 6 个标准节点，顺序与 MILESTONE_STEPS 一致 */
  milestones: readonly Milestone[];
}

interface DeliverySnapshotStage {
  expectedEnd?: string;
  actualEnd?: string;
  progress?: number;
}

interface DeliverySnapshotPod {
  pod?: string;
  batch?: string;
  stages?: Partial<Record<MilestoneKey, DeliverySnapshotStage>>;
}

export interface DeliveryMilestoneSnapshot {
  pods?: readonly DeliverySnapshotPod[];
}

/** 数据快照日（mock 固定值，保证「逾期 N 天」与状态枚举自洽，不随浏览器时间漂移） */
export const AS_OF = '2026-06-12';

/* ── mock 构造器：done/doing/late/todo 四态，让 54 个节点的故事一行可读 ── */
type MilestoneSpec = Omit<Milestone, 'key' | 'name'>;
type SpecRow = readonly [MilestoneSpec, MilestoneSpec, MilestoneSpec, MilestoneSpec, MilestoneSpec, MilestoneSpec];

const done = (plannedDate: string, actualDate: string): MilestoneSpec =>
  ({ plannedDate, actualDate, progress: 100, status: 'done' });
const doing = (plannedDate: string, progress: number): MilestoneSpec =>
  ({ plannedDate, actualDate: null, progress, status: 'inProgress' });
const late = (plannedDate: string, progress: number): MilestoneSpec =>
  ({ plannedDate, actualDate: null, progress, status: 'delayed' });
const todo = (plannedDate: string): MilestoneSpec =>
  ({ plannedDate, actualDate: null, progress: 0, status: 'notStarted' });

const pod = (podId: string, room: string, specs: SpecRow): PodMilestones => ({
  podId,
  room,
  milestones: MILESTONE_STEPS.map((step, i) => ({ ...step, ...specs[i]! })),
});

/* ── 9 个 PoD：批1(01–04)基本移交、批2(05–08)推进中含两处延期、批3(09)起步 ── */
const RAW_PODS: readonly PodMilestones[] = [
  pod('PoD-01', 'B2DH401', [
    done('2026-02-10', '2026-02-08'), done('2026-02-20', '2026-02-19'), done('2026-03-01', '2026-03-01'),
    done('2026-03-10', '2026-03-09'), done('2026-03-20', '2026-03-18'), done('2026-03-31', '2026-03-28'),
  ]),
  pod('PoD-02', 'B2DH401', [
    done('2026-02-10', '2026-02-12'), done('2026-02-25', '2026-03-02'), done('2026-03-08', '2026-03-12'),
    done('2026-03-18', '2026-03-20'), done('2026-03-28', '2026-04-02'), done('2026-04-08', '2026-04-11'),
  ]),
  pod('PoD-03', 'B2DH401', [
    done('2026-02-15', '2026-02-15'), done('2026-03-02', '2026-03-01'), done('2026-03-14', '2026-03-14'),
    done('2026-03-24', '2026-03-25'), done('2026-04-02', '2026-04-02'), done('2026-04-10', '2026-04-09'),
  ]),
  pod('PoD-04', 'B2DH401', [
    done('2026-03-01', '2026-03-01'), done('2026-03-12', '2026-03-11'), done('2026-03-22', '2026-03-24'),
    done('2026-04-05', '2026-04-05'), done('2026-05-20', '2026-05-18'), doing('2026-06-20', 80),
  ]),
  pod('PoD-05', 'B2DH402', [
    done('2026-03-15', '2026-03-16'), done('2026-04-02', '2026-04-02'), done('2026-04-18', '2026-04-17'),
    done('2026-05-10', '2026-05-12'), doing('2026-06-18', 60), todo('2026-06-30'),
  ]),
  pod('PoD-06', 'B2DH402', [
    done('2026-03-15', '2026-03-20'), done('2026-04-10', '2026-04-19'), late('2026-05-28', 45),
    late('2026-06-08', 0), todo('2026-06-25'), todo('2026-07-06'),
  ]),
  pod('PoD-07', 'B2DH402', [
    done('2026-03-20', '2026-03-19'), done('2026-04-15', '2026-04-14'), done('2026-05-08', '2026-05-10'),
    doing('2026-06-16', 70), todo('2026-06-28'), todo('2026-07-10'),
  ]),
  pod('PoD-08', 'B2DH402', [
    done('2026-03-20', '2026-03-22'), done('2026-04-18', '2026-04-25'), done('2026-05-15', '2026-05-21'),
    late('2026-06-05', 30), todo('2026-06-22'), todo('2026-07-08'),
  ]),
  pod('PoD-09', 'B2DH403', [
    done('2026-04-20', '2026-04-20'), done('2026-05-18', '2026-05-16'), doing('2026-06-20', 20),
    todo('2026-07-02'), todo('2026-07-15'), todo('2026-07-30'),
  ]),
];

/* ── 派生计算（纯函数，渲染层共用）── */

const DAY_MS = 86_400_000;
const toTime = (date: string): number => new Date(`${date}T00:00:00`).getTime();

/**
 * 安全重判（守门）：任何未完成且已过计划时间的节点一律视为「延期」，
 * 无论上游枚举给的是什么 —— 杜绝「被误标的火」沉进平静区被 PD 漏看。
 */
function deriveStatus(m: Milestone): MilestoneStatus {
  if (m.status !== 'done' && toTime(AS_OF) > toTime(m.plannedDate)) return 'delayed';
  return m.status;
}

/** 经安全重判后的看板真相源 —— 所有派生与渲染都消费它 */
export const POD_MILESTONES: readonly PodMilestones[] = RAW_PODS.map(p => ({
  ...p,
  milestones: p.milestones.map(m => ({ ...m, status: deriveStatus(m) })),
}));

/** 将现有 delivery-plan.xlsx / 数据中心接口快照适配为新看板契约。 */
export function podMilestonesFromSnapshot(snapshot: DeliveryMilestoneSnapshot): readonly PodMilestones[] {
  return (snapshot.pods ?? []).flatMap(p => {
    const sourceId = p.pod?.trim();
    if (!sourceId) return [];

    const milestones = MILESTONE_STEPS.map(step => {
      const stage = p.stages?.[step.key];
      if (!stage?.expectedEnd) return null;
      const progress = Math.max(0, Math.min(100, Number(stage.progress) || 0));
      const milestone: Milestone = {
        ...step,
        plannedDate: stage.expectedEnd,
        actualDate: stage.actualEnd || null,
        progress,
        status: stage.actualEnd ? 'done' : progress > 0 ? 'inProgress' : 'notStarted',
      };
      return { ...milestone, status: deriveStatus(milestone) };
    });
    if (milestones.some(m => !m)) return [];

    const podNumber = sourceId.match(/POD(\d+)$/i)?.[1];
    return [{
      podId: podNumber ? `PoD-${podNumber.padStart(2, '0')}` : sourceId,
      room: p.batch || sourceId.replace(/-?POD\d+$/i, ''),
      milestones: milestones as Milestone[],
    }];
  });
}

/**
 * 偏差天数（>0 = 晚于计划）：
 *   已完成 → 实际 vs 计划；延期 → 快照日 vs 计划（即已逾期天数）；其余无意义返回 null
 */
export function slipDays(m: Milestone): number | null {
  if (m.status === 'done' && m.actualDate) {
    return Math.round((toTime(m.actualDate) - toTime(m.plannedDate)) / DAY_MS);
  }
  if (m.status === 'delayed') {
    return Math.max(1, Math.round((toTime(AS_OF) - toTime(m.plannedDate)) / DAY_MS));
  }
  return null;
}

export type PodPhase = 'handedOver' | 'delayed' | 'inProgress' | 'notStarted';

export interface PodSummary {
  /** 六节点进度均值 0–100 */
  progress: number;
  /** 延期节点数 */
  delayedCount: number;
  /** 最大逾期天数（无延期为 0） */
  maxOverdue: number;
  phase: PodPhase;
  /** 当前推进（或受阻）节点；已移交 → null */
  frontier: Milestone | null;
  /** 全部延期节点，按逾期天数降序（rich row 用） */
  delayedNodes: readonly Milestone[];
}

/** 第一个未完成节点（PoD 当前所处的「推进面」）；全完成 → null */
export function frontierNode(p: PodMilestones): Milestone | null {
  return p.milestones.find(m => m.status !== 'done') ?? null;
}

export function podSummary(p: PodMilestones): PodSummary {
  const ms = p.milestones;
  const progress = Math.round(ms.reduce((sum, m) => sum + m.progress, 0) / ms.length);
  const delayedNodes = ms
    .filter(m => m.status === 'delayed')
    .slice()
    .sort((a, b) => (slipDays(b) ?? 0) - (slipDays(a) ?? 0));
  const allDone = ms.every(m => m.status === 'done');
  const allTodo = ms.every(m => m.status === 'notStarted');
  const phase: PodPhase = allDone
    ? 'handedOver'
    : delayedNodes.length ? 'delayed' : allTodo ? 'notStarted' : 'inProgress';
  const maxOverdue = delayedNodes.reduce((max, m) => Math.max(max, slipDays(m) ?? 0), 0);
  return { progress, delayedCount: delayedNodes.length, maxOverdue, phase, frontier: frontierNode(p), delayedNodes };
}

/** 已移交 PoD 的一句话结论（计划 vs 实际的「累计」对比，替代 6 组日期） */
export function podVerdict(p: PodMilestones): { tone: 'good' | 'slip'; text: string } {
  const lateSlips = p.milestones.map(m => slipDays(m) ?? 0).filter(s => s > 0);
  if (!lateSlips.length) return { tone: 'good', text: '全程按期' };
  const min = Math.min(...lateSlips);
  const max = Math.max(...lateSlips);
  return { tone: 'slip', text: min === max ? `累计晚 ${max}d` : `累计晚 ${min}–${max}d` };
}

export type SegmentTone = 'reach' | 'late' | 'live' | 'overdue' | 'future';

/** 两节点间连线的语义色：达成(绿) / 曾晚点(珊瑚) / 在途(蓝) / 逾期(红虚) / 未来(灰虚) */
export function segmentTone(prev: Milestone, cur: Milestone): SegmentTone {
  if (prev.status === 'delayed' || cur.status === 'delayed') return 'overdue';
  if (cur.status === 'inProgress') return 'live';
  if (cur.status === 'notStarted') return 'future';
  // 两端皆 done
  const slipped = (slipDays(prev) ?? 0) > 0 || (slipDays(cur) ?? 0) > 0;
  return slipped ? 'late' : 'reach';
}

export interface BoardStats {
  counts: Record<MilestoneStatus, number>;
  /** 全部节点进度均值 0–100 */
  overall: number;
  /** 存在延期节点的 PoD 数 */
  podsDelayed: number;
  /** 推进中（无延期）的 PoD 数 */
  podsInProgress: number;
  /** 已移交的 PoD 数 */
  podsDone: number;
  /** 全局最长逾期天数 */
  maxOverdue: number;
}

export function boardStats(pods: readonly PodMilestones[]): BoardStats {
  const counts: Record<MilestoneStatus, number> = { done: 0, inProgress: 0, delayed: 0, notStarted: 0 };
  let sum = 0;
  let total = 0;
  let maxOverdue = 0;
  pods.forEach(p => p.milestones.forEach(m => {
    counts[m.status] += 1;
    sum += m.progress;
    total += 1;
    if (m.status === 'delayed') maxOverdue = Math.max(maxOverdue, slipDays(m) ?? 0);
  }));
  const summaries = pods.map(podSummary);
  return {
    counts,
    overall: total ? Math.round(sum / total) : 0,
    podsDelayed: summaries.filter(s => s.phase === 'delayed').length,
    podsInProgress: summaries.filter(s => s.phase === 'inProgress' || s.phase === 'notStarted').length,
    podsDone: summaries.filter(s => s.phase === 'handedOver').length,
    maxOverdue,
  };
}

export interface ColumnStat {
  key: MilestoneKey;
  name: string;
  doneCount: number;
  delayedCount: number;
}

export function columnStats(pods: readonly PodMilestones[]): readonly ColumnStat[] {
  return MILESTONE_STEPS.map((step, i) => {
    let doneCount = 0;
    let delayedCount = 0;
    pods.forEach(p => {
      const m = p.milestones[i];
      if (!m) return;
      if (m.status === 'done') doneCount += 1;
      else if (m.status === 'delayed') delayedCount += 1;
    });
    return { key: step.key, name: step.name, doneCount, delayedCount };
  });
}

/* ── 批次视图：把同机房的 PoD 聚成一批，给「批次 × 工序」的滚动结论 ── */

/** 状态严重度：值越小越「需关注」（延期 > 进行中 > 未开工 > 已完成），用于取该批该工序的最差态着色 */
const STATUS_SEVERITY: Record<MilestoneStatus, number> = {
  delayed: 0,
  inProgress: 1,
  notStarted: 2,
  done: 3,
};

export interface BatchStageStat {
  key: MilestoneKey;
  name: string;
  doneCount: number;
  delayedCount: number;
  inProgressCount: number;
  notStartedCount: number;
  total: number;
  /** 该批该工序进度均值 0–100（驱动批次徽标的进度环） */
  avgProgress: number;
  /** 该批该工序最差状态（驱动着色 / 报警） */
  worstStatus: MilestoneStatus;
  /** 该批该工序最晚计划日（整批清完此工序的计划时间） */
  plannedDate: string;
  /** 整批此工序全部完成时的最晚实际日；未全完成为 null */
  actualDate: string | null;
  /** 该批此工序中「晚于计划完成」的节点数（聚合徽标的晚点标记用） */
  lateCount: number;
}

export interface BatchStat {
  /** 展示用批次名 批1 / 批2 / 批3（按机房首次出现顺序） */
  batch: string;
  room: string;
  podCount: number;
  /** 全批延期节点数 */
  delayedCount: number;
  stages: readonly BatchStageStat[];
}

/** 按机房聚合为批次，逐工序滚动 PoD 的完成/延期/进度（渲染层直接读结论） */
export function batchStats(pods: readonly PodMilestones[]): readonly BatchStat[] {
  const rooms: string[] = [];
  pods.forEach(p => { if (!rooms.includes(p.room)) rooms.push(p.room); });

  return rooms.map((room, ri) => {
    const group = pods.filter(p => p.room === room);
    let delayedTotal = 0;

    const stages: BatchStageStat[] = MILESTONE_STEPS.map((step, i) => {
      let doneCount = 0;
      let delayedCount = 0;
      let inProgressCount = 0;
      let notStartedCount = 0;
      let progressSum = 0;
      let worstStatus: MilestoneStatus = 'done';
      let plannedDate = '';
      let maxActual = '';
      let lateCount = 0;

      group.forEach(p => {
        const m = p.milestones[i];
        if (!m) return;
        progressSum += m.progress;
        if (m.status === 'done') {
          doneCount += 1;
          if (m.actualDate) {
            if (m.actualDate > maxActual) maxActual = m.actualDate;
            if (m.actualDate > m.plannedDate) lateCount += 1;
          }
        }
        else if (m.status === 'delayed') { delayedCount += 1; delayedTotal += 1; }
        else if (m.status === 'inProgress') inProgressCount += 1;
        else notStartedCount += 1;
        if (STATUS_SEVERITY[m.status] < STATUS_SEVERITY[worstStatus]) worstStatus = m.status;
        if (m.plannedDate > plannedDate) plannedDate = m.plannedDate;
      });

      const total = group.length;
      return {
        key: step.key,
        name: step.name,
        doneCount,
        delayedCount,
        inProgressCount,
        notStartedCount,
        total,
        avgProgress: total ? Math.round(progressSum / total) : 0,
        worstStatus,
        plannedDate,
        actualDate: doneCount === total && maxActual ? maxActual : null,
        lateCount,
      };
    });

    return { batch: `批${ri + 1}`, room, podCount: group.length, delayedCount: delayedTotal, stages };
  });
}
