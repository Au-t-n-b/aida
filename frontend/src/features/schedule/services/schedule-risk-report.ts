import type {
  Activity,
  ArrivalItem,
  Batch,
  InputBundle,
  PlanResult,
  Pod,
  Room,
  ScheduledActivity,
} from '@/features/schedule/contracts/schedule.gen';
import { readLatestScheduleReportSnapshot, type ScheduleReportSnapshot } from '@/features/schedule/services/schedule';

export type RiskReportSeverity = '高' | '中' | '低';

export type RiskReportTodoItem = {
  id: string;
  matter: string;
  owner: string;
  suggestedDate: string | null;
  relatedActivity: string;
  status: string;
  severity: RiskReportSeverity;
  reason: string;
};

export type RiskReportCategory = {
  id: 'customer' | 'purchase' | 'supply' | 'sla';
  title: string;
  recognition: string;
  description: string;
  emptyText: string;
  items: RiskReportTodoItem[];
};

export type ScheduleRiskReport = {
  projectName: string;
  projectId: string;
  projectScale: string;
  totalCardCount: number | null;
  scene: string;
  productForm: string;
  baselineVersion: string;
  generatedAt: string;
  committedAt: string;
  projectFinishDate: string | null;
  activityCount: number;
  criticalActivityCount: number;
  todoCount: number;
  highCount: number;
  categories: RiskReportCategory[];
};

export type ScheduleRiskReportState =
  | { status: 'empty' }
  | { status: 'ready'; report: ScheduleRiskReport };

type RiskReportContext = {
  snapshot: ScheduleReportSnapshot;
  inputs: InputBundle;
  plan: PlanResult;
  roomsById: Map<string, Room>;
  podsById: Map<string, Pod>;
  arrivalsByPod: Map<string, ArrivalItem[]>;
  batchByPod: Map<string, Batch>;
  activityById: Map<string, Activity>;
  scheduledByMilestone: ScheduledActivity[];
};

const PROCUREMENT_KEYWORDS = /采购|下单|订货|订单|备货|物料准备|PO/i;

export function getScheduleRiskReportState(): ScheduleRiskReportState {
  const snapshot = readLatestScheduleReportSnapshot();
  if (!snapshot) return { status: 'empty' };
  return { status: 'ready', report: buildScheduleRiskReport(snapshot) };
}

function buildScheduleRiskReport(snapshot: ScheduleReportSnapshot): ScheduleRiskReport {
  const context = buildContext(snapshot);
  const categories = [
    buildCustomerCategory(context),
    buildPurchaseCategory(context),
    buildSupplyCategory(context),
    buildSlaCategory(context),
  ];
  const allItems = categories.flatMap((category) => category.items);
  const project = context.inputs.project;

  return {
    projectName: project.project_name || project.project_id,
    projectId: project.project_id,
    projectScale: project.project_scale ?? '未提供',
    totalCardCount: project.total_card_count ?? null,
    scene: project.scene ?? '未提供',
    productForm: [project.product_form, project.cooling_method].filter(Boolean).join(' / ') || '未提供',
    baselineVersion: `v${snapshot.version}`,
    generatedAt: todayIso(),
    committedAt: snapshot.committed_at,
    projectFinishDate: context.plan.project_finish_date ?? maxIso(context.plan.activities.map((activity) => activity.end_date)),
    activityCount: context.plan.activities.length,
    criticalActivityCount: context.plan.activities.filter((activity) => activity.is_critical).length,
    todoCount: allItems.length,
    highCount: allItems.filter((item) => item.severity === '高').length,
    categories,
  };
}

function buildContext(snapshot: ScheduleReportSnapshot): RiskReportContext {
  const inputs = snapshot.inputs;
  const roomsById = new Map(inputs.rooms.map((room) => [room.room_id, room]));
  const podsById = new Map(inputs.pods.map((pod) => [pod.pod_id, pod]));
  const activityById = new Map(inputs.activities.map((activity) => [activity.activity_id, activity]));
  const arrivalsByPod = new Map<string, ArrivalItem[]>();
  const batchByPod = new Map<string, Batch>();

  (inputs.arrivals ?? []).forEach((arrival) => {
    const arrivals = arrivalsByPod.get(arrival.pod_id) ?? [];
    arrivals.push(arrival);
    arrivalsByPod.set(arrival.pod_id, arrivals);
  });
  inputs.batches.forEach((batch) => {
    batch.pod_ids.forEach((podId) => batchByPod.set(podId, batch));
  });

  return {
    snapshot,
    inputs,
    plan: snapshot.plan,
    roomsById,
    podsById,
    arrivalsByPod,
    batchByPod,
    activityById,
    scheduledByMilestone: snapshot.plan.activities.filter((activity) => activity.milestone_kind),
  };
}

function buildCustomerCategory(context: RiskReportContext): RiskReportCategory {
  const items: RiskReportTodoItem[] = [];

  context.inputs.batches.forEach((batch) => {
    const rooms = unique(
      batch.pod_ids
        .map((podId) => context.podsById.get(podId)?.room_id)
        .filter((roomId): roomId is string => Boolean(roomId)),
    )
      .map((roomId) => context.roomsById.get(roomId))
      .filter((room): room is Room => Boolean(room));

    const pendingRooms = rooms.filter((room) => !hasRoomReady(room));
    if (pendingRooms.length) {
      const suggestedDate = minIso(
        pendingRooms
          .map((room) => milestoneDate(context, '机房就位', room.room_id))
          .filter((date): date is string => Boolean(date)),
      );
      items.push({
        id: `customer-ready-${batch.batch_id}`,
        matter: `${displayBatch(batch)} 机房 ready 待确认`,
        owner: '客户配合',
        suggestedDate,
        relatedActivity: pendingRooms.map((room) => room.room_id).join('、'),
        status: '待确认',
        severity: pendingRooms.length > 1 ? '高' : '中',
        reason: '批次内机房缺少可布线 / 可装设备 / 可通液任一 ready 日期。',
      });
    }

    if (!batch.online_target_date) {
      items.push({
        id: `customer-online-${batch.batch_id}`,
        matter: `${displayBatch(batch)} 上线目标待确认`,
        owner: '客户配合',
        suggestedDate: milestoneDate(context, '上线', batch.batch_id) ?? context.plan.project_finish_date ?? null,
        relatedActivity: `${displayBatch(batch)} 上线里程碑`,
        status: '待确认',
        severity: '中',
        reason: '批次缺少上线目标日期，后续压缩、下发与客户对齐缺少锚点。',
      });
    }
  });

  return {
    id: 'customer',
    title: '客户配合',
    recognition: 'milestone_kind / 机房 ready 状态',
    description: '机房 ready 未确认、上线目标待确认的批次。',
    emptyText: '当前下发版本未识别到客户侧 ready 或目标确认待办。',
    items,
  };
}

function buildPurchaseCategory(context: RiskReportContext): RiskReportCategory {
  const procurementTemplateIds = new Set(
    context.inputs.activities
      .filter(isProcurementActivity)
      .map((activity) => activity.activity_id),
  );

  const items = context.plan.activities
    .filter((activity) => procurementTemplateIds.has(activity.activity_id))
    .sort(byStartThenId)
    .map((activity): RiskReportTodoItem => {
      const template = context.activityById.get(activity.activity_id);
      return {
        id: `purchase-${activity.instance_id}`,
        matter: `${activity.activity_name} 时间要求锁定`,
        owner: template?.responsibility || '采购配合',
        suggestedDate: activity.start_date,
        relatedActivity: activityLabel(activity),
        status: '待跟进',
        severity: activity.is_critical ? '高' : '中',
        reason: '活动名称或类别命中采购 / 下单 / 备货通用规则，需要按基线开始日前完成采购协同。',
      };
    });

  return {
    id: 'purchase',
    title: '采购配合',
    recognition: '活动类别 / 活动名称通用规则',
    description: '采购、下单、订货、备货类活动的基线时间要求。',
    emptyText: '当前活动模板未识别到采购 / 下单 / 备货类待办。',
    items,
  };
}

function buildSupplyCategory(context: RiskReportContext): RiskReportCategory {
  const podIds = unique(context.inputs.pods.map((pod) => pod.pod_id));
  const items = podIds.flatMap((podId): RiskReportTodoItem[] => {
    const arrivals = context.arrivalsByPod.get(podId) ?? [];
    const missingEta = arrivals.length === 0 || arrivals.some((arrival) => !arrival.arrival_date || arrival.arrival_status === '未明');
    const inTransit = arrivals.some((arrival) => arrival.arrival_status === '在途');
    if (!missingEta && !inTransit) return [];

    const batch = context.batchByPod.get(podId);
    const latestEta = maxIso(arrivals.map((arrival) => arrival.arrival_date));
    const suggestedDate = latestEta ?? milestoneDate(context, '到货', podId);
    const status = missingEta ? 'ETA 待补' : '在途未到';

    return [{
      id: `supply-${podId}`,
      matter: `${podId} ${status}`,
      owner: '供应配合',
      suggestedDate,
      relatedActivity: batch ? `${displayBatch(batch)} / 到货里程碑` : '到货里程碑',
      status,
      severity: missingEta ? '高' : '中',
      reason: missingEta
        ? 'PoD 缺少可执行 ETA 或到货状态仍为未明。'
        : 'PoD 已有 ETA 但仍未到货，需要按基线建议日跟进供应承诺。',
    }];
  });

  return {
    id: 'supply',
    title: '供应配合',
    recognition: 'ArrivalItem.arrival_status / ETA',
    description: '到货 ETA 待补、在途未到的 PoD 与建议到货日。',
    emptyText: '当前下发版本未识别到 ETA 待补或在途未到 PoD。',
    items,
  };
}

function buildSlaCategory(context: RiskReportContext): RiskReportCategory {
  const items = context.plan.activities
    .filter((activity) => Number.isFinite(activity.standard_sla_days) && activity.standard_sla_days !== null)
    .filter((activity) => activity.actual_sla_days > (activity.standard_sla_days ?? 0))
    .sort((a, b) => ((b.actual_sla_days - (b.standard_sla_days ?? 0)) - (a.actual_sla_days - (a.standard_sla_days ?? 0))) || a.instance_id.localeCompare(b.instance_id))
    .map((activity): RiskReportTodoItem => {
      const standard = activity.standard_sla_days ?? 0;
      const exceeded = activity.actual_sla_days - standard;
      const template = context.activityById.get(activity.activity_id);
      return {
        id: `sla-${activity.instance_id}`,
        matter: `${activity.activity_name} 超 SLA ${exceeded} 天`,
        owner: template?.responsibility || activity.team_id || '交付团队',
        suggestedDate: activity.end_date,
        relatedActivity: activityLabel(activity),
        status: '需盯防',
        severity: exceeded >= 5 ? '高' : '中',
        reason: `排期工期 ${activity.actual_sla_days} 天，高于标准 SLA ${standard} 天。`,
      };
    });

  return {
    id: 'sla',
    title: '超 SLA 基线',
    recognition: 'actual_sla_days > standard_sla_days',
    description: '排期实际工期超过标准 SLA 的活动清单。',
    emptyText: '当前下发版本未识别到超过标准 SLA 的活动。',
    items,
  };
}

function isProcurementActivity(activity: Activity): boolean {
  const text = [
    activity.activity_name,
    activity.phase,
    activity.activity_type,
    activity.constraint_source,
    activity.responsibility,
    activity.note,
  ]
    .filter(Boolean)
    .join(' ');
  return PROCUREMENT_KEYWORDS.test(text);
}

function hasRoomReady(room: Room): boolean {
  return Boolean(room.cabling_ready_date || room.install_ready_date || room.liquid_ready_date);
}

function milestoneDate(
  context: RiskReportContext,
  kind: NonNullable<ScheduledActivity['milestone_kind']>,
  refId: string,
): string | null {
  const matches = context.scheduledByMilestone.filter(
    (activity) => activity.milestone_kind === kind && activity.scope_ref.ref_id === refId,
  );
  return minIso(matches.map((activity) => activity.end_date));
}

function displayBatch(batch: Batch): string {
  return batch.batch_name || batch.batch_id;
}

function activityLabel(activity: ScheduledActivity): string {
  const ref = activity.scope_ref.ref_id ? ` · ${activity.scope_ref.ref_id}` : '';
  return `${activity.activity_name}${ref}`;
}

function byStartThenId(a: ScheduledActivity, b: ScheduledActivity): number {
  if (a.start_date !== b.start_date) return a.start_date.localeCompare(b.start_date);
  return a.instance_id.localeCompare(b.instance_id);
}

function unique<T>(items: T[]): T[] {
  return Array.from(new Set(items));
}

function minIso(dates: Array<string | null | undefined>): string | null {
  const values = dates.filter((date): date is string => Boolean(date));
  return values.length ? values.reduce((earliest, date) => (date < earliest ? date : earliest), values[0]!) : null;
}

function maxIso(dates: Array<string | null | undefined>): string | null {
  const values = dates.filter((date): date is string => Boolean(date));
  return values.length ? values.reduce((latest, date) => (date > latest ? date : latest), values[0]!) : null;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
