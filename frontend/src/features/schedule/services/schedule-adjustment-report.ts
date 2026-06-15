import type {
  AdjustResponse,
  CommitResponse,
  MovedActivity,
  PlanResult,
  RiskItem,
  ScheduledActivity,
  StrategyPlan,
  UnmetItem,
} from '@/features/schedule/contracts/schedule.gen';

export type AdjustmentReportKpi = {
  label: string;
  value: string;
  tone?: 'normal' | 'positive' | 'warning';
};

export type AdjustmentReportMovedActivity = {
  instanceId: string;
  name: string;
  oldStart?: string | null;
  oldEnd?: string | null;
  newStart: string;
  newEnd: string;
  direction: string;
};

export type AdjustmentReportRisk = {
  severity: RiskItem['severity'];
  riskType: string;
  message: string;
  mitigation?: string | null;
};

export type AdjustmentReportUnmet = {
  target: string;
  reason: string;
  gapDays?: number | null;
};

export type AdjustmentReport = {
  title: string;
  modeLabel: string;
  strategyLabel: string;
  advice: string;
  planId: string;
  version: number;
  committedPlanVersion: string;
  criticalPathChange: string;
  notes: string[];
  kpis: AdjustmentReportKpi[];
  movedActivities: AdjustmentReportMovedActivity[];
  risks: AdjustmentReportRisk[];
  unmet: AdjustmentReportUnmet[];
  aiSummary?: string | null;
};

export type BuildAdjustmentReportInput = {
  adjustResponse: AdjustResponse;
  selectedOption: StrategyPlan;
  commitResponse: CommitResponse;
  previousPlan?: PlanResult | null;
  durationOverrideCount?: number;
};

export function buildAdjustmentReport(input: BuildAdjustmentReportInput): AdjustmentReport {
  const { adjustResponse, selectedOption, commitResponse, previousPlan, durationOverrideCount = 0 } = input;
  const explanation = adjustResponse.explanation;
  const committedPlan = commitResponse.plan;
  const movedActivities = enrichMovedActivities(
    pickMovedActivities(explanation.moved_activities, previousPlan, committedPlan),
    previousPlan,
    committedPlan,
  );

  return {
    title: '调整报告',
    modeLabel: explanation.is_initial ? '初排' : '调整',
    strategyLabel: selectedOption.strategy,
    advice: selectedOption.advice,
    planId: commitResponse.plan_id,
    version: commitResponse.new_version,
    committedPlanVersion: `v${commitResponse.new_version}`,
    criticalPathChange: explanation.critical_path_change ?? describeCriticalPathChange(previousPlan, committedPlan),
    notes: explanation.notes ?? [],
    kpis: buildKpis(selectedOption, committedPlan, durationOverrideCount),
    movedActivities,
    risks: buildRisks(selectedOption),
    unmet: (adjustResponse.unmet ?? []).map(toReportUnmet),
    aiSummary: null,
  };
}

function buildKpis(option: StrategyPlan, plan: PlanResult, durationOverrideCount: number): AdjustmentReportKpi[] {
  const compressedDays = option.kpis.compressed_days ?? 0;
  const addedCrew = option.kpis.added_crew ?? 0;
  const kpis: AdjustmentReportKpi[] = [
    { label: '总工期', value: `${option.kpis.total_duration_days} 天` },
    { label: '压缩天数', value: `${compressedDays} 天`, tone: compressedDays > 0 ? 'positive' : 'normal' },
    { label: '增员', value: `${addedCrew} 人`, tone: addedCrew > 0 ? 'warning' : 'normal' },
    { label: 'PoD', value: `${option.kpis.pod_count}` },
  ];
  if (plan.project_finish_date) {
    kpis.push({ label: '整体交付日', value: plan.project_finish_date });
  }
  if (durationOverrideCount > 0) {
    kpis.push({ label: '选后微调', value: `${durationOverrideCount} 项`, tone: 'warning' });
  }
  return kpis;
}

function pickMovedActivities(
  movedActivities: MovedActivity[] | undefined,
  previousPlan: PlanResult | null | undefined,
  committedPlan: PlanResult,
): MovedActivity[] {
  if (movedActivities?.length) return movedActivities;
  if (!previousPlan) return [];
  return diffMovedActivities(previousPlan, committedPlan);
}

function diffMovedActivities(before: PlanResult, after: PlanResult): MovedActivity[] {
  const beforeById = new Map(before.activities.map(activity => [activity.instance_id, activity]));
  const moved: MovedActivity[] = [];
  for (const activity of after.activities) {
    const previous = beforeById.get(activity.instance_id);
    if (!previous || (previous.start_date === activity.start_date && previous.end_date === activity.end_date)) continue;
    moved.push({
      instance_id: activity.instance_id,
      old_start: previous.start_date,
      old_end: previous.end_date,
      new_start: activity.start_date,
      new_end: activity.end_date,
      direction: activity.start_date < previous.start_date ? '提前' : '顺延',
    });
    if (moved.length >= 12) break;
  }
  return moved;
}

function enrichMovedActivities(
  movedActivities: MovedActivity[],
  previousPlan: PlanResult | null | undefined,
  committedPlan: PlanResult,
): AdjustmentReportMovedActivity[] {
  const names = new Map<string, ScheduledActivity>();
  previousPlan?.activities.forEach(activity => names.set(activity.instance_id, activity));
  committedPlan.activities.forEach(activity => names.set(activity.instance_id, activity));

  return movedActivities.map(activity => ({
    instanceId: activity.instance_id,
    name: names.get(activity.instance_id)?.activity_name ?? activity.instance_id,
    oldStart: activity.old_start,
    oldEnd: activity.old_end,
    newStart: activity.new_start,
    newEnd: activity.new_end,
    direction: activity.direction,
  }));
}

function describeCriticalPathChange(previousPlan: PlanResult | null | undefined, committedPlan: PlanResult): string {
  const before = previousPlan?.critical_path ?? [];
  const after = committedPlan.critical_path ?? [];
  if (!before.length && !after.length) return '后端未返回关键路径变化说明';
  if (before.length === after.length && before.every((id, index) => id === after[index])) return '关键路径未变化';
  return `关键路径已更新：${before.length || '无'} 个节点 → ${after.length || '无'} 个节点`;
}

function buildRisks(option: StrategyPlan): AdjustmentReportRisk[] {
  return [
    {
      severity: option.risk_level,
      riskType: '方案风险等级',
      message: `综合评估：${option.risk_level}`,
    },
    ...(option.risks ?? []).map(toReportRisk),
  ];
}

function toReportRisk(risk: RiskItem): AdjustmentReportRisk {
  return {
    severity: risk.severity,
    riskType: risk.risk_type,
    message: risk.message,
    mitigation: risk.mitigation,
  };
}

function toReportUnmet(unmet: UnmetItem): AdjustmentReportUnmet {
  return {
    target: unmet.target_desc,
    reason: unmet.reason,
    gapDays: unmet.gap_days,
  };
}
