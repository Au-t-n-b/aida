from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil, isfinite
from typing import Iterable, Mapping, Sequence

from agent.schedule.contracts.api import ConflictDetail, ErrorResponse
from agent.schedule.contracts.common import EXPERIENCE_EFFICIENCY, ScopeRef
from agent.schedule.contracts.inputs import (
    Activity,
    ArrivalItem,
    Batch,
    IncidentEvent,
    InputBundle,
    Pod,
    RiskRule,
)
from agent.schedule.contracts.outputs import PlanResult, ReadinessSuggestion, RiskItem, ScheduledActivity

MAX_SCHEDULE_DAYS = 10_000
PROJECT_REF_ID = "project"
ACTIVITY_RISK_HIGH_OVERRUN_RATIO = 0.5
ACTIVITY_RISK_MEDIUM_OVERRUN_RATIO = 0.2


class EngineError(Exception):
    """Business-level scheduling failure that API code can convert to ErrorResponse."""

    def __init__(
        self,
        code: str,
        message: str,
        conflicts: Iterable[ConflictDetail] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.conflicts = list(conflicts or [])
        super().__init__(f"{code}: {message}")

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(code=self.code, message=self.message, conflicts=self.conflicts)


@dataclass(frozen=True)
class _Instance:
    instance_id: str
    activity: Activity
    scope_ref: ScopeRef


@dataclass(frozen=True)
class _DurationEstimate:
    standard_work_days: float
    standard_sla_days: int
    minimum_work_days: float | None


@dataclass(frozen=True)
class _TeamAssignment:
    team_id: str | None
    efficiency: float
    available_from: date | None


@dataclass(frozen=True)
class _ScheduleWindow:
    earliest_start: date | None = None
    exact_start: date | None = None
    exact_or_latest_end: date | None = None
    label: str | None = None


@dataclass(frozen=True)
class ScheduleResult:
    plan: PlanResult
    risks: list[RiskItem]
    readiness_suggestions: list[ReadinessSuggestion]


@dataclass(frozen=True)
class _ReadinessComputation:
    suggestions: list[ReadinessSuggestion]
    starts: dict[str, date]
    ends: dict[str, date]
    actual_days: dict[str, int]
    ai_instance_ids: set[str]


def generate_plan(
    inputs: InputBundle,
    *,
    incidents: Sequence[IncidentEvent] | None = None,
    plan_id: str | None = None,
    version: int = 1,
    base_version: int | None = None,
    include_risks: bool = False,
    duration_overrides: Mapping[str, float] | None = None,
) -> PlanResult | ScheduleResult:
    """Create a deterministic forward schedule from contract input objects.

    The engine is intentionally a pure function: callers provide already parsed
    contract models, optional incident windows, and receive a PlanResult (or a
    ScheduleResult when include_risks=True) or a business error.
    """

    incident_events = list(incidents or [])
    ignored_dependency_risks = _ignored_dependency_risks(inputs)
    calculation_inputs = _inputs_with_fs_dependencies_only(inputs)

    instances = _instantiate(calculation_inputs)
    instance_by_id = {instance.instance_id: instance for instance in instances}
    predecessors, successors = _expand_dependencies(calculation_inputs, instances)
    order = _topological_order(instances, predecessors, successors)
    windows = _collect_windows(calculation_inputs, instances)
    given_availability_dates = _collect_given_availability(calculation_inputs, instances)
    project_start = _project_start(calculation_inputs)

    starts: dict[str, date] = {}
    ends: dict[str, date] = {}
    actual_days: dict[str, int] = {}
    duration_estimates = {
        instance.instance_id: _estimate_duration(instance, calculation_inputs)
        for instance in instances
    }
    if duration_overrides:
        duration_estimates = {
            instance_id: _with_overridden_work_days(instance_id, estimate, duration_overrides.get(instance_id))
            for instance_id, estimate in duration_estimates.items()
        }
    team_assignments = {
        instance.instance_id: _assign_team(instance, calculation_inputs)
        for instance in instances
    }
    readiness = _compute_readiness_suggestions(
        calculation_inputs,
        instances,
        predecessors,
        order,
        windows,
        duration_estimates,
        team_assignments,
        incident_events,
        given_availability_dates,
    )

    for instance_id in order:
        if instance_id in readiness.ends:
            starts[instance_id] = readiness.starts[instance_id]
            ends[instance_id] = readiness.ends[instance_id]
            actual_days[instance_id] = readiness.actual_days[instance_id]
            continue
        if instance_id in given_availability_dates:
            available_date = given_availability_dates[instance_id]
            starts[instance_id] = available_date
            ends[instance_id] = available_date
            actual_days[instance_id] = 1
            continue

        instance = instance_by_id[instance_id]
        predecessor_end = max(
            (
                _predecessor_available_date(pred_id, ends[pred_id], given_availability_dates)
                for pred_id in predecessors[instance_id]
            ),
            default=project_start,
        )
        window = windows.get(instance_id, _ScheduleWindow())
        team = team_assignments[instance_id]
        estimate = duration_estimates[instance_id]

        earliest = max(
            date_value
            for date_value in [predecessor_end, window.earliest_start, team.available_from]
            if date_value is not None
        )

        if window.exact_start is not None:
            if earliest > window.exact_start:
                _raise_infeasible(
                    "活动锚点早于依赖可行时间",
                    f"{instance_id} 最早只能从 {earliest.isoformat()} 开始，锚点要求 {window.exact_start.isoformat()}。",
                )
            start = window.exact_start
            end, elapsed_days = _schedule_work(
                start,
                estimate.standard_work_days,
                instance,
                team,
                incident_events,
                calculation_inputs,
            )
        elif window.exact_or_latest_end is not None:
            start, end, elapsed_days = _schedule_to_deadline(
                earliest,
                window.exact_or_latest_end,
                estimate,
                instance,
                team,
                incident_events,
                calculation_inputs,
            )
        else:
            start = earliest
            end, elapsed_days = _schedule_work(
                start,
                estimate.standard_work_days,
                instance,
                team,
                incident_events,
                calculation_inputs,
            )

        starts[instance_id] = start
        ends[instance_id] = end
        actual_days[instance_id] = elapsed_days

    critical_path = _critical_path(order, predecessors, starts, ends, given_availability_dates)
    critical_ids = set(critical_path)
    activities = [
        _to_scheduled_activity(
            instance_by_id[instance_id],
            starts[instance_id],
            ends[instance_id],
            actual_days[instance_id],
            duration_estimates[instance_id],
            predecessors[instance_id],
            team_assignments[instance_id].team_id,
            instance_id in critical_ids,
            instance_id in readiness.ai_instance_ids,
        )
        for instance_id in order
    ]

    project_finish = max((activity.end_date for activity in activities), default=None)
    plan = PlanResult(
        plan_id=plan_id or f"{calculation_inputs.project.project_id}-plan",
        version=version,
        base_version=base_version,
        activities=activities,
        critical_path=critical_path,
        project_finish_date=project_finish,
    )
    if include_risks:
        activity_risks = _activity_risks(activities, instance_by_id)
        return ScheduleResult(
            plan=plan,
            risks=[*ignored_dependency_risks, *activity_risks],
            readiness_suggestions=readiness.suggestions,
        )
    return plan


def recalculate_plan_with_duration_overrides(
    inputs: InputBundle,
    base_plan: PlanResult,
    duration_overrides: Mapping[str, int],
) -> PlanResult:
    """Recompute a stored backend plan snapshot from duration-only edits.

    Commit-time edits come from the Gantt UI as desired activity durations. The
    frontend is not trusted for dates: this function keeps the backend-selected
    option as the baseline graph, validates the edited durations against the
    input bundle's minimum SLA, then propagates FS successors deterministically.
    """

    if not duration_overrides:
        return base_plan

    activity_by_id = {activity.instance_id: activity for activity in base_plan.activities}
    unknown_ids = sorted(set(duration_overrides) - set(activity_by_id))
    if unknown_ids:
        _raise_infeasible(
            "活动工期微调引用不存在",
            f"找不到活动实例：{', '.join(unknown_ids)}。",
        )

    minimum_days = _minimum_duration_days_by_instance(inputs)
    normalized_overrides = {
        instance_id: _validated_duration_override(instance_id, value, minimum_days.get(instance_id))
        for instance_id, value in duration_overrides.items()
    }

    predecessors = {
        activity.instance_id: [
            predecessor_id
            for predecessor_id in activity.predecessor_instance_ids
            if predecessor_id in activity_by_id
        ]
        for activity in base_plan.activities
    }
    successors = {activity.instance_id: [] for activity in base_plan.activities}
    for instance_id, predecessor_ids in predecessors.items():
        for predecessor_id in predecessor_ids:
            successors[predecessor_id].append(instance_id)
    order = _topological_activity_order(list(activity_by_id), predecessors, successors)

    starts: dict[str, date] = {}
    ends: dict[str, date] = {}
    actual_days: dict[str, int] = {}
    original_end = {activity.instance_id: activity.end_date for activity in base_plan.activities}
    original_start = {activity.instance_id: activity.start_date for activity in base_plan.activities}

    for instance_id in order:
        activity = activity_by_id[instance_id]
        duration_days = normalized_overrides.get(instance_id, activity.actual_sla_days)
        predecessor_ids = predecessors[instance_id]
        if predecessor_ids:
            start = max(
                ends[predecessor_id]
                + timedelta(days=1 + _original_lag_days(instance_id, predecessor_id, original_start, original_end))
                for predecessor_id in predecessor_ids
            )
        else:
            start = activity.start_date
        end = start + timedelta(days=duration_days - 1)
        starts[instance_id] = start
        ends[instance_id] = end
        actual_days[instance_id] = duration_days

    critical_path = _critical_path(order, predecessors, starts, ends)
    critical_ids = set(critical_path)
    activities = [
        activity_by_id[instance_id].model_copy(
            update={
                "start_date": starts[instance_id],
                "end_date": ends[instance_id],
                "actual_sla_days": actual_days[instance_id],
                "is_critical": instance_id in critical_ids,
            }
        )
        for instance_id in order
    ]
    return base_plan.model_copy(
        update={
            "activities": activities,
            "critical_path": critical_path,
            "project_finish_date": max((activity.end_date for activity in activities), default=None),
        }
    )


def _compute_readiness_suggestions(
    inputs: InputBundle,
    instances: Sequence[_Instance],
    predecessors: dict[str, list[str]],
    order: Sequence[str],
    windows: dict[str, _ScheduleWindow],
    duration_estimates: dict[str, _DurationEstimate],
    team_assignments: dict[str, _TeamAssignment],
    incidents: Sequence[IncidentEvent],
    given_availability_dates: Mapping[str, date],
) -> _ReadinessComputation:
    suggestions: list[ReadinessSuggestion] = []
    starts: dict[str, date] = {}
    ends: dict[str, date] = {}
    actual_days: dict[str, int] = {}
    ai_instance_ids: set[str] = set()

    instance_by_id = {instance.instance_id: instance for instance in instances}
    for batch in inputs.batches:
        missing_room_ids = _missing_room_ids(inputs, batch)
        missing_pod_ids = _missing_arrival_pod_ids(inputs, batch)
        has_given_availability = _batch_has_given_availability(
            inputs,
            instances,
            batch,
            given_availability_dates,
        )
        if not missing_room_ids and not missing_pod_ids and not has_given_availability:
            continue

        target_deadlines = _batch_target_deadlines(batch.batch_id, instances, windows)
        if not target_deadlines:
            continue

        backward = _backward_schedule_from_targets(
            inputs,
            instance_by_id,
            predecessors,
            order,
            duration_estimates,
            team_assignments,
            incidents,
            target_deadlines,
        )

        suggested_room_ready = _suggested_room_ready(instances, backward.ends, missing_room_ids)
        suggested_arrival = _suggested_arrival(instances, backward.ends, missing_pod_ids)
        project_target_ancestor_ids = _project_level_target_ancestor_ids(instances, backward.ends)
        should_preplan_given_batch = (
            has_given_availability
            and not missing_room_ids
            and not missing_pod_ids
            and bool(project_target_ancestor_ids)
        )
        if not suggested_room_ready and not suggested_arrival and not has_given_availability:
            continue

        if suggested_room_ready or suggested_arrival:
            suggestions.append(
                ReadinessSuggestion(
                    batch_id=batch.batch_id,
                    suggested_room_ready=suggested_room_ready,
                    suggested_arrival=suggested_arrival,
                )
            )

        batch_instance_ids = _batch_related_instance_ids(inputs, instances, batch)
        if missing_room_ids or missing_pod_ids:
            preplanned_instance_ids = batch_instance_ids.intersection(backward.ends)
        elif should_preplan_given_batch:
            _raise_if_given_availability_after_batch_target(
                batch.batch_id,
                batch_instance_ids,
                given_availability_dates,
                target_deadlines,
            )
            preplanned_instance_ids = (
                batch_instance_ids.union(project_target_ancestor_ids)
                .intersection(backward.ends)
                .difference(given_availability_dates)
            )
        else:
            preplanned_instance_ids = set()
        for instance_id in preplanned_instance_ids:
            _apply_earliest_finish(
                instance_id,
                backward.starts[instance_id],
                backward.ends[instance_id],
                backward.actual_days[instance_id],
                starts,
                ends,
                actual_days,
            )
            if instance_id not in target_deadlines:
                ai_instance_ids.add(instance_id)

    return _ReadinessComputation(
        suggestions=suggestions,
        starts=starts,
        ends=ends,
        actual_days=actual_days,
        ai_instance_ids=ai_instance_ids,
    )


@dataclass(frozen=True)
class _BackwardComputation:
    starts: dict[str, date]
    ends: dict[str, date]
    actual_days: dict[str, int]


def _backward_schedule_from_targets(
    inputs: InputBundle,
    instance_by_id: dict[str, _Instance],
    predecessors: dict[str, list[str]],
    order: Sequence[str],
    duration_estimates: dict[str, _DurationEstimate],
    team_assignments: dict[str, _TeamAssignment],
    incidents: Sequence[IncidentEvent],
    target_deadlines: dict[str, date],
) -> _BackwardComputation:
    latest_ends = dict(target_deadlines)
    starts: dict[str, date] = {}
    ends: dict[str, date] = {}
    actual_days: dict[str, int] = {}

    for instance_id in reversed(order):
        latest_end = latest_ends.get(instance_id)
        if latest_end is None:
            continue

        instance = instance_by_id[instance_id]
        start, end, elapsed_days = _schedule_work_backward(
            latest_end,
            duration_estimates[instance_id].standard_work_days,
            instance,
            team_assignments[instance_id],
            incidents,
            inputs,
        )
        starts[instance_id] = start
        ends[instance_id] = end
        actual_days[instance_id] = elapsed_days

        predecessor_latest_end = start - timedelta(days=1)
        for predecessor_id in predecessors[instance_id]:
            current = latest_ends.get(predecessor_id)
            latest_ends[predecessor_id] = (
                predecessor_latest_end
                if current is None
                else min(current, predecessor_latest_end)
            )

    return _BackwardComputation(starts=starts, ends=ends, actual_days=actual_days)


def _batch_target_deadlines(
    batch_id: str,
    instances: Sequence[_Instance],
    windows: dict[str, _ScheduleWindow],
) -> dict[str, date]:
    deadlines: dict[str, date] = {}
    for instance in instances:
        if instance.scope_ref.scope != "批次级" or instance.scope_ref.ref_id != batch_id:
            continue
        if _milestone_kind(instance.activity) not in {"上电", "上线"}:
            continue
        deadline = windows.get(instance.instance_id)
        if deadline is None or deadline.exact_or_latest_end is None:
            continue
        deadlines[instance.instance_id] = deadline.exact_or_latest_end
    return deadlines


def _missing_room_ids(inputs: InputBundle, batch: Batch) -> set[str]:
    room_ids = {_pod(inputs, pod_id).room_id for pod_id in batch.pod_ids}
    return {room_id for room_id in room_ids if _room_ready_date(inputs, room_id) is None}


def _missing_arrival_pod_ids(inputs: InputBundle, batch: Batch) -> set[str]:
    missing: set[str] = set()
    for pod_id in batch.pod_ids:
        arrivals = [arrival for arrival in inputs.arrivals if arrival.pod_id == pod_id]
        if not arrivals or any(arrival.arrival_date is None for arrival in arrivals):
            missing.add(pod_id)
    return missing


def _suggested_room_ready(
    instances: Sequence[_Instance],
    latest_ends: dict[str, date],
    missing_room_ids: set[str],
) -> dict[str, date]:
    suggestions: dict[str, date] = {}
    for room_id in sorted(missing_room_ids):
        room_instance_ids = [
            instance.instance_id
            for instance in instances
            if instance.scope_ref.scope == "机房级"
            and instance.scope_ref.ref_id == room_id
            and _milestone_kind(instance.activity) == "机房就位"
            and instance.instance_id in latest_ends
        ]
        if room_instance_ids:
            suggestions[room_id] = max(latest_ends[instance_id] for instance_id in room_instance_ids)
    return suggestions


def _suggested_arrival(
    instances: Sequence[_Instance],
    latest_ends: dict[str, date],
    missing_pod_ids: set[str],
) -> dict[str, date]:
    suggestions: dict[str, date] = {}
    for pod_id in sorted(missing_pod_ids):
        arrival_instance_ids = [
            instance.instance_id
            for instance in instances
            if instance.scope_ref.scope == "PoD级"
            and instance.scope_ref.ref_id == pod_id
            and _milestone_kind(instance.activity) == "到货"
            and instance.instance_id in latest_ends
        ]
        if arrival_instance_ids:
            suggestions[pod_id] = max(latest_ends[instance_id] for instance_id in arrival_instance_ids)
    return suggestions


def _batch_related_instance_ids(inputs: InputBundle, instances: Sequence[_Instance], batch: Batch) -> set[str]:
    pod_ids = set(batch.pod_ids)
    room_ids = {_pod(inputs, pod_id).room_id for pod_id in batch.pod_ids}
    related: set[str] = set()
    for instance in instances:
        scope = instance.scope_ref.scope
        ref_id = instance.scope_ref.ref_id
        if scope == "批次级" and ref_id == batch.batch_id:
            related.add(instance.instance_id)
        elif scope == "PoD级" and ref_id in pod_ids:
            related.add(instance.instance_id)
        elif scope == "机房级" and ref_id in room_ids:
            related.add(instance.instance_id)
    return related


def _batch_has_given_availability(
    inputs: InputBundle,
    instances: Sequence[_Instance],
    batch: Batch,
    given_availability_dates: Mapping[str, date],
) -> bool:
    return bool(_batch_related_instance_ids(inputs, instances, batch).intersection(given_availability_dates))


def _project_level_target_ancestor_ids(
    instances: Sequence[_Instance],
    target_ancestor_ends: Mapping[str, date],
) -> set[str]:
    return {
        instance.instance_id
        for instance in instances
        if instance.scope_ref.scope == "项目级" and instance.instance_id in target_ancestor_ends
    }


def _raise_if_given_availability_after_batch_target(
    batch_id: str,
    batch_instance_ids: set[str],
    given_availability_dates: Mapping[str, date],
    target_deadlines: Mapping[str, date],
) -> None:
    if not target_deadlines:
        return
    earliest_target = min(target_deadlines.values())
    late_dates = [
        (instance_id, availability_date)
        for instance_id, availability_date in given_availability_dates.items()
        if instance_id in batch_instance_ids and availability_date > earliest_target
    ]
    if not late_dates:
        return
    instance_id, availability_date = min(late_dates, key=lambda item: item[1])
    _raise_infeasible(
        "给定就位/到货晚于批次目标",
        f"{batch_id} 的 {instance_id} 给定可用日 {availability_date.isoformat()} 晚于批次目标 {earliest_target.isoformat()}。",
    )


def _apply_earliest_finish(
    instance_id: str,
    new_start: date,
    new_end: date,
    new_actual_days: int,
    starts: dict[str, date],
    ends: dict[str, date],
    actual_days: dict[str, int],
) -> None:
    current_end = ends.get(instance_id)
    if current_end is not None and current_end <= new_end:
        return
    starts[instance_id] = new_start
    ends[instance_id] = new_end
    actual_days[instance_id] = new_actual_days


def _inputs_with_fs_dependencies_only(inputs: InputBundle) -> InputBundle:
    fs_dependencies = [dependency for dependency in inputs.dependencies if dependency.dep_type == "FS"]
    if len(fs_dependencies) == len(inputs.dependencies):
        return inputs
    return inputs.model_copy(update={"dependencies": fs_dependencies})


def _ignored_dependency_risks(inputs: InputBundle) -> list[RiskItem]:
    activity_by_id = {activity.activity_id: activity for activity in inputs.activities}
    return [
        RiskItem(
            risk_type="依赖未纳入",
            severity="中",
            instance_id=None,
            message=(
                f"{_activity_label(dependency.from_activity_id, activity_by_id)} -> "
                f"{_activity_label(dependency.to_activity_id, activity_by_id)} 的"
                f"{_dependency_relation_label(dependency.dep_type)}未纳入计算，相关日期可能偏乐观。"
            ),
        )
        for dependency in inputs.dependencies
        if dependency.dep_type != "FS"
    ]


def _activity_risks(
    activities: Sequence[ScheduledActivity],
    instance_by_id: Mapping[str, _Instance],
) -> list[RiskItem]:
    risks: list[RiskItem] = []
    for scheduled in activities:
        rule = instance_by_id[scheduled.instance_id].activity.risk_rule
        standard_days = scheduled.standard_sla_days
        if rule is None or standard_days is None or scheduled.actual_sla_days <= standard_days:
            continue

        overrun_days = scheduled.actual_sla_days - standard_days
        overrun_ratio = overrun_days / standard_days
        risks.append(
            RiskItem(
                risk_type="活动风险",
                severity=_activity_risk_severity(overrun_ratio, scheduled.is_critical),
                instance_id=scheduled.instance_id,
                message=_activity_risk_message(scheduled, rule, overrun_days),
                mitigation=rule.mitigation,
            )
        )
    return risks


def _activity_risk_severity(overrun_ratio: float, is_critical: bool) -> str:
    if is_critical or overrun_ratio >= ACTIVITY_RISK_HIGH_OVERRUN_RATIO:
        return "高"
    if overrun_ratio >= ACTIVITY_RISK_MEDIUM_OVERRUN_RATIO:
        return "中"
    return "低"


def _activity_risk_message(
    activity: ScheduledActivity,
    rule: RiskRule,
    overrun_days: int,
) -> str:
    risk_name = rule.risk_name or f"{activity.activity_name}活动风险"
    parts = [
        (
            f"{activity.activity_name} 命中活动风险「{risk_name}」：实际耗时 "
            f"{activity.actual_sla_days} 天，较标准 SLA {activity.standard_sla_days} 天超出 {overrun_days} 天"
        )
    ]
    if rule.impact:
        parts.append(f"影响：{rule.impact}")
    if rule.mitigation:
        parts.append(f"预案：{rule.mitigation}")
    if rule.mitigation_owner:
        parts.append(f"责任人：{rule.mitigation_owner}")
    return "；".join(parts) + "。"


def _activity_label(activity_id: str, activity_by_id: dict[str, Activity]) -> str:
    activity = activity_by_id.get(activity_id)
    if activity is None or not activity.activity_name:
        return activity_id
    return f"{activity_id}（{activity.activity_name}）"


def _dependency_relation_label(dep_type: str) -> str:
    return {
        "SS": "开始对齐(SS)",
        "SF": "开始-完成关系(SF)",
        "FF": "完成对齐(FF)",
    }.get(dep_type, f"{dep_type} 依赖")


def _instantiate(inputs: InputBundle) -> list[_Instance]:
    instances: list[_Instance] = []
    for activity in inputs.activities:
        if activity.scope == "项目级":
            instances.append(
                _Instance(
                    instance_id=f"{PROJECT_REF_ID}/{activity.activity_id}",
                    activity=activity,
                    scope_ref=ScopeRef(scope=activity.scope, ref_id=None),
                )
            )
        elif activity.scope == "机房级":
            for room in inputs.rooms:
                instances.append(
                    _Instance(
                        instance_id=f"{room.room_id}/{activity.activity_id}",
                        activity=activity,
                        scope_ref=ScopeRef(scope=activity.scope, ref_id=room.room_id),
                    )
                )
        elif activity.scope == "批次级":
            for batch in inputs.batches:
                instances.append(
                    _Instance(
                        instance_id=f"{batch.batch_id}/{activity.activity_id}",
                        activity=activity,
                        scope_ref=ScopeRef(scope=activity.scope, ref_id=batch.batch_id),
                    )
                )
        elif activity.scope == "PoD级":
            for pod in inputs.pods:
                instances.append(
                    _Instance(
                        instance_id=f"{pod.pod_id}/{activity.activity_id}",
                        activity=activity,
                        scope_ref=ScopeRef(scope=activity.scope, ref_id=pod.pod_id),
                    )
                )
        else:
            raise AssertionError(f"Unknown scope: {activity.scope}")
    return instances


def _expand_dependencies(
    inputs: InputBundle,
    instances: Sequence[_Instance],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    by_activity: dict[str, list[_Instance]] = {}
    for instance in instances:
        by_activity.setdefault(instance.activity.activity_id, []).append(instance)

    predecessors = {instance.instance_id: [] for instance in instances}
    successors = {instance.instance_id: [] for instance in instances}
    for dependency in inputs.dependencies:
        from_instances = by_activity.get(dependency.from_activity_id)
        to_instances = by_activity.get(dependency.to_activity_id)
        if not from_instances or not to_instances:
            _raise_infeasible(
                "依赖引用不存在",
                f"{dependency.from_activity_id} -> {dependency.to_activity_id} 找不到对应活动。",
            )
        for from_instance in from_instances:
            for to_instance in to_instances:
                if _instances_are_related(from_instance, to_instance, inputs):
                    predecessors[to_instance.instance_id].append(from_instance.instance_id)
                    successors[from_instance.instance_id].append(to_instance.instance_id)

    return (
        {key: sorted(set(value)) for key, value in predecessors.items()},
        {key: sorted(set(value)) for key, value in successors.items()},
    )


def _instances_are_related(source: _Instance, target: _Instance, inputs: InputBundle) -> bool:
    source_scope = source.scope_ref.scope
    target_scope = target.scope_ref.scope
    source_ref = source.scope_ref.ref_id
    target_ref = target.scope_ref.ref_id

    if source_scope == "项目级" or target_scope == "项目级":
        return True
    if source_scope == target_scope:
        return source_ref == target_ref
    if source_scope == "机房级" and target_scope == "PoD级":
        return _pod(inputs, target_ref).room_id == source_ref
    if source_scope == "PoD级" and target_scope == "机房级":
        return _pod(inputs, source_ref).room_id == target_ref
    if source_scope == "PoD级" and target_scope == "批次级":
        return source_ref in _batch(inputs, target_ref).pod_ids
    if source_scope == "批次级" and target_scope == "PoD级":
        return target_ref in _batch(inputs, source_ref).pod_ids
    if source_scope == "机房级" and target_scope == "批次级":
        return any(_pod(inputs, pod_id).room_id == source_ref for pod_id in _batch(inputs, target_ref).pod_ids)
    if source_scope == "批次级" and target_scope == "机房级":
        return any(_pod(inputs, pod_id).room_id == target_ref for pod_id in _batch(inputs, source_ref).pod_ids)
    return False


def _topological_order(
    instances: Sequence[_Instance],
    predecessors: dict[str, list[str]],
    successors: dict[str, list[str]],
) -> list[str]:
    remaining_predecessors = {key: set(value) for key, value in predecessors.items()}
    ready = sorted(instance.instance_id for instance in instances if not remaining_predecessors[instance.instance_id])
    order: list[str] = []

    while ready:
        instance_id = ready.pop(0)
        order.append(instance_id)
        for successor_id in successors[instance_id]:
            remaining_predecessors[successor_id].discard(instance_id)
            if not remaining_predecessors[successor_id]:
                ready.append(successor_id)
        ready.sort()

    if len(order) != len(instances):
        _raise_infeasible("依赖网络存在环", "FS 依赖无法形成可求解的有向无环网络。")
    return order


def _topological_activity_order(
    instance_ids: Sequence[str],
    predecessors: dict[str, list[str]],
    successors: dict[str, list[str]],
) -> list[str]:
    remaining_predecessors = {key: set(predecessors.get(key, [])) for key in instance_ids}
    ready = sorted(instance_id for instance_id in instance_ids if not remaining_predecessors[instance_id])
    order: list[str] = []

    while ready:
        instance_id = ready.pop(0)
        order.append(instance_id)
        for successor_id in successors.get(instance_id, []):
            remaining_predecessors[successor_id].discard(instance_id)
            if not remaining_predecessors[successor_id]:
                ready.append(successor_id)
        ready.sort()

    if len(order) != len(instance_ids):
        _raise_infeasible("依赖网络存在环", "所选方案的活动依赖无法形成可重算的有向无环网络。")
    return order


def _collect_windows(inputs: InputBundle, instances: Sequence[_Instance]) -> dict[str, _ScheduleWindow]:
    windows: dict[str, _ScheduleWindow] = {}

    for instance in instances:
        batch_id = instance.scope_ref.ref_id if instance.scope_ref.scope == "批次级" else None
        if batch_id is not None:
            batch = _batch(inputs, batch_id)
            kind = _milestone_kind(instance.activity)
            if kind == "上电" and batch.power_on_target_date is not None:
                windows[instance.instance_id] = _merge_window(
                    windows.get(instance.instance_id),
                    _ScheduleWindow(exact_or_latest_end=batch.power_on_target_date, label="批次上电"),
                    instance.instance_id,
                )
            elif kind == "上线" and batch.online_target_date is not None:
                windows[instance.instance_id] = _merge_window(
                    windows.get(instance.instance_id),
                    _ScheduleWindow(exact_or_latest_end=batch.online_target_date, label="批次上线"),
                    instance.instance_id,
                )

    for anchor in inputs.anchors:
        targets = _resolve_anchor_targets(anchor.target.kind, anchor.target.ref_id, instances)
        for instance_id in targets:
            anchor_window = (
                _ScheduleWindow(exact_start=anchor.anchor_date, label=anchor.anchor_source)
                if anchor.target.kind == "活动实例"
                else _ScheduleWindow(exact_or_latest_end=anchor.anchor_date, label=anchor.anchor_source)
            )
            windows[instance_id] = _merge_window(windows.get(instance_id), anchor_window, instance_id)

    return windows


def _collect_given_availability(inputs: InputBundle, instances: Sequence[_Instance]) -> dict[str, date]:
    availability_dates: dict[str, date] = {}
    for instance in instances:
        if instance.activity.activity_type == "机房准备":
            ready_date = _room_ready_date(inputs, instance.scope_ref.ref_id)
            if ready_date is not None:
                availability_dates[instance.instance_id] = ready_date
        elif instance.activity.activity_type == "到货":
            arrival_date = _arrival_ready_date(inputs, instance.scope_ref.ref_id, instance.activity)
            if arrival_date is not None:
                availability_dates[instance.instance_id] = arrival_date
    return availability_dates


def _merge_window(
    current: _ScheduleWindow | None,
    new: _ScheduleWindow,
    instance_id: str,
) -> _ScheduleWindow:
    if current is None:
        return new
    exact_start = current.exact_start
    if new.exact_start is not None:
        if exact_start is not None and exact_start != new.exact_start:
            _raise_infeasible("活动存在多个互斥开始锚点", f"{instance_id} 的开始锚点冲突。")
        exact_start = new.exact_start

    exact_or_latest_end = current.exact_or_latest_end
    if new.exact_or_latest_end is not None:
        exact_or_latest_end = (
            new.exact_or_latest_end
            if exact_or_latest_end is None
            else min(exact_or_latest_end, new.exact_or_latest_end)
        )

    earliest_start = current.earliest_start
    if new.earliest_start is not None:
        earliest_start = (
            new.earliest_start
            if earliest_start is None
            else max(earliest_start, new.earliest_start)
        )
    return _ScheduleWindow(
        earliest_start=earliest_start,
        exact_start=exact_start,
        exact_or_latest_end=exact_or_latest_end,
        label=new.label or current.label,
    )


def _resolve_anchor_targets(kind: str, ref_id: str | None, instances: Sequence[_Instance]) -> list[str]:
    if kind == "活动实例":
        return [ref_id] if ref_id is not None else []
    if kind == "批次上电":
        return [
            instance.instance_id
            for instance in instances
            if instance.scope_ref.scope == "批次级"
            and instance.scope_ref.ref_id == ref_id
            and _milestone_kind(instance.activity) == "上电"
        ]
    if kind == "批次上线":
        return [
            instance.instance_id
            for instance in instances
            if instance.scope_ref.scope == "批次级"
            and instance.scope_ref.ref_id == ref_id
            and _milestone_kind(instance.activity) == "上线"
        ]
    if kind == "项目移交":
        return [
            instance.instance_id
            for instance in instances
            if _milestone_kind(instance.activity) == "移交"
        ]
    if kind == "到货":
        return [
            instance.instance_id
            for instance in instances
            if instance.scope_ref.scope == "PoD级"
            and instance.scope_ref.ref_id == ref_id
            and instance.activity.activity_type == "到货"
        ]
    if kind == "机房就位":
        return [
            instance.instance_id
            for instance in instances
            if instance.scope_ref.scope == "机房级"
            and instance.scope_ref.ref_id == ref_id
            and instance.activity.activity_type == "机房准备"
        ]
    return []


def _estimate_duration(instance: _Instance, inputs: InputBundle) -> _DurationEstimate:
    activity = instance.activity
    if activity.duration_mode == "弹性" and activity.workload_rules:
        standard_work = 0.0
        minimum_work = 0.0
        has_minimum = True
        for rule in activity.workload_rules:
            quantity = _matching_quantity(inputs, instance, rule.workload_source)
            standard_work += quantity / rule.standard_daily_rate
            if rule.limit_daily_rate:
                minimum_work += quantity / rule.limit_daily_rate
            else:
                has_minimum = False
        standard_work = max(standard_work, 1.0)
        minimum: float | None = max(minimum_work, 1.0) if has_minimum else None
        return _DurationEstimate(
            standard_work_days=standard_work,
            standard_sla_days=max(1, ceil(standard_work)),
            minimum_work_days=minimum,
        )

    standard_days = activity.standard_sla_days if activity.standard_sla_days is not None else 1
    minimum_days = activity.minimum_sla_days
    return _DurationEstimate(
        standard_work_days=float(max(1, standard_days)),
        standard_sla_days=max(1, standard_days),
        minimum_work_days=float(minimum_days) if minimum_days is not None else None,
    )


def _with_overridden_work_days(
    instance_id: str,
    estimate: _DurationEstimate,
    work_days: float | None,
) -> _DurationEstimate:
    if work_days is None:
        return estimate
    if not isfinite(float(work_days)) or float(work_days) <= 0:
        _raise_infeasible("活动工期格式不合法", f"{instance_id} 的工期必须是正数。")
    minimum = estimate.minimum_work_days
    if minimum is not None and float(work_days) + 1e-9 < minimum:
        _raise_infeasible(
            "活动工期低于极限 SLA",
            f"{instance_id} 微调为 {work_days:g} 天，低于极限工期 {minimum:g} 天。",
        )
    return _DurationEstimate(
        standard_work_days=max(1.0, float(work_days)),
        standard_sla_days=estimate.standard_sla_days,
        minimum_work_days=estimate.minimum_work_days,
    )


def _minimum_duration_days_by_instance(inputs: InputBundle) -> dict[str, int]:
    calculation_inputs = _inputs_with_fs_dependencies_only(inputs)
    minimums: dict[str, int] = {}
    for instance in _instantiate(calculation_inputs):
        estimate = _estimate_duration(instance, calculation_inputs)
        team = _assign_team(instance, calculation_inputs)
        minimums[instance.instance_id] = _minimum_elapsed_days(estimate, team)
    return minimums


def _minimum_elapsed_days(estimate: _DurationEstimate, team: _TeamAssignment) -> int:
    if estimate.minimum_work_days is None:
        return 1
    minimum_work_days = estimate.minimum_work_days
    return max(1, ceil(minimum_work_days / team.efficiency))


def _validated_duration_override(instance_id: str, value: int, minimum_days: int | None) -> int:
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0 or numeric != int(numeric):
        _raise_infeasible("活动工期格式不合法", f"{instance_id} 的工期必须是正整数天。")
    days = int(numeric)
    if minimum_days is not None and days < minimum_days:
        _raise_infeasible(
            "活动工期低于极限 SLA",
            f"{instance_id} 微调为 {days} 天，低于极限工期 {minimum_days} 天。",
        )
    return days


def _original_lag_days(
    instance_id: str,
    predecessor_id: str,
    original_start: Mapping[str, date],
    original_end: Mapping[str, date],
) -> int:
    lag = (original_start[instance_id] - (original_end[predecessor_id] + timedelta(days=1))).days
    return max(-1, lag)


def _matching_quantity(inputs: InputBundle, instance: _Instance, workload_source: str) -> float:
    pod_ids = set(_pod_ids_for_instance(inputs, instance))
    total = 0.0
    for arrival in inputs.arrivals:
        if arrival.pod_id not in pod_ids:
            continue
        if _arrival_matches(arrival, workload_source):
            total += arrival.quantity
    return total


def _arrival_matches(arrival: ArrivalItem, workload_source: str) -> bool:
    source = workload_source.lower()
    haystack = " ".join(
        value
        for value in [
            arrival.device_type,
            arrival.device_model or "",
            arrival.unit or "",
            arrival.note or "",
        ]
        if value
    ).lower()
    return source in haystack or haystack in source


def _pod_ids_for_instance(inputs: InputBundle, instance: _Instance) -> list[str]:
    scope = instance.scope_ref.scope
    ref_id = instance.scope_ref.ref_id
    if scope == "PoD级":
        return [ref_id] if ref_id is not None else []
    if scope == "机房级":
        return [pod.pod_id for pod in inputs.pods if pod.room_id == ref_id]
    if scope == "批次级":
        return list(_batch(inputs, ref_id).pod_ids)
    return [pod.pod_id for pod in inputs.pods]


def _assign_team(instance: _Instance, inputs: InputBundle) -> _TeamAssignment:
    if instance.activity.constraint_source != "人":
        return _TeamAssignment(team_id=None, efficiency=1.0, available_from=None)

    teams = sorted((team for team in inputs.teams if team.on_site), key=lambda team: team.team_id)
    if not teams:
        return _TeamAssignment(team_id="default-team", efficiency=EXPERIENCE_EFFICIENCY["一般"], available_from=None)

    scope_key = instance.scope_ref.ref_id or PROJECT_REF_ID
    index = sum(ord(char) for char in scope_key) % len(teams)
    team = teams[index]
    return _TeamAssignment(
        team_id=team.team_id,
        efficiency=EXPERIENCE_EFFICIENCY[team.experience],
        available_from=team.available_from,
    )


def _schedule_to_deadline(
    earliest_start: date,
    deadline: date,
    estimate: _DurationEstimate,
    instance: _Instance,
    team: _TeamAssignment,
    incidents: Sequence[IncidentEvent],
    inputs: InputBundle,
) -> tuple[date, date, int]:
    start = earliest_start
    last_valid: tuple[date, date, int] | None = None
    first_late_end: date | None = None
    while start <= deadline:
        end, elapsed_days = _schedule_work(
            start,
            estimate.standard_work_days,
            instance,
            team,
            incidents,
            inputs,
        )
        if end <= deadline:
            last_valid = (start, end, elapsed_days)
            start += timedelta(days=1)
            continue
        first_late_end = end
        break
    if last_valid is None:
        if first_late_end is None:
            first_late_end, _ = _schedule_work(
                earliest_start,
                estimate.standard_work_days,
                instance,
                team,
                incidents,
                inputs,
            )
        late_detail = ""
        if first_late_end is not None:
            late_days = max(1, (first_late_end - deadline).days)
            late_detail = f"，最早完成日 {first_late_end.isoformat()}，晚于目标 {late_days} 天"
        _raise_infeasible(
            "前后向窗口交集为空",
            f"{instance.instance_id} 最早 {earliest_start.isoformat()} 开始也无法在 {deadline.isoformat()} 前完成{late_detail}。",
        )
    return last_valid


def _schedule_work(
    start: date,
    work_days: float,
    instance: _Instance,
    team: _TeamAssignment,
    incidents: Sequence[IncidentEvent],
    inputs: InputBundle,
) -> tuple[date, int]:
    progress = 0.0
    current = start
    elapsed_days = 0

    while progress + 1e-9 < work_days:
        if elapsed_days > MAX_SCHEDULE_DAYS:
            _raise_infeasible("可施工日不足", f"{instance.instance_id} 在 {MAX_SCHEDULE_DAYS} 天内无法完成。")
        progress += _day_efficiency(current, instance, team, incidents, inputs)
        elapsed_days += 1
        end = current
        current += timedelta(days=1)
    return end, elapsed_days


def _schedule_work_backward(
    latest_end: date,
    work_days: float,
    instance: _Instance,
    team: _TeamAssignment,
    incidents: Sequence[IncidentEvent],
    inputs: InputBundle,
) -> tuple[date, date, int]:
    end = latest_end
    guard_days = 0
    while _day_efficiency(end, instance, team, incidents, inputs) <= 0:
        if guard_days > MAX_SCHEDULE_DAYS:
            _raise_infeasible("可施工日不足", f"{instance.instance_id} 在 {MAX_SCHEDULE_DAYS} 天内无法倒推完成。")
        end -= timedelta(days=1)
        guard_days += 1

    progress = 0.0
    current = end
    start = end
    elapsed_days = 0

    while progress + 1e-9 < work_days:
        if elapsed_days > MAX_SCHEDULE_DAYS:
            _raise_infeasible("可施工日不足", f"{instance.instance_id} 在 {MAX_SCHEDULE_DAYS} 天内无法倒推完成。")
        progress += _day_efficiency(current, instance, team, incidents, inputs)
        start = current
        elapsed_days = _closed_days(start, end)
        current -= timedelta(days=1)
    return start, end, elapsed_days


def _day_efficiency(
    day: date,
    instance: _Instance,
    team: _TeamAssignment,
    incidents: Sequence[IncidentEvent],
    inputs: InputBundle,
) -> float:
    if inputs.rule_config.skip_weekends and day.weekday() >= 5:
        return 0.0

    if instance.activity.constraint_source != "人":
        return 1.0

    event_efficiencies = [
        incident.efficiency
        for incident in incidents
        if incident.window.start <= day <= incident.window.end
    ]
    event_efficiency = min(event_efficiencies) if event_efficiencies else 1.0
    return event_efficiency * team.efficiency


def _critical_path(
    order: Sequence[str],
    predecessors: dict[str, list[str]],
    starts: dict[str, date],
    ends: dict[str, date],
    given_availability_dates: Mapping[str, date] | None = None,
) -> list[str]:
    if not order:
        return []

    availability_dates = given_availability_dates or {}
    chain_days: dict[str, int] = {}
    back_pointer: dict[str, str | None] = {}
    for instance_id in order:
        controlling_predecessors = [
            pred_id
            for pred_id in predecessors[instance_id]
            if _predecessor_available_date(pred_id, ends[pred_id], availability_dates) == starts[instance_id]
        ]
        if controlling_predecessors:
            predecessor_id = max(
                controlling_predecessors,
                key=lambda pred_id: (chain_days[pred_id], ends[pred_id], pred_id),
            )
            back_pointer[instance_id] = predecessor_id
            chain_days[instance_id] = chain_days[predecessor_id] + _closed_days(starts[instance_id], ends[instance_id])
        else:
            back_pointer[instance_id] = None
            chain_days[instance_id] = _closed_days(starts[instance_id], ends[instance_id])

    terminal = max(order, key=lambda instance_id: (ends[instance_id], chain_days[instance_id], instance_id))
    path: list[str] = []
    current: str | None = terminal
    while current is not None:
        path.append(current)
        current = back_pointer[current]
    return list(reversed(path))


def _to_scheduled_activity(
    instance: _Instance,
    start: date,
    end: date,
    actual_days: int,
    estimate: _DurationEstimate,
    predecessor_ids: Sequence[str],
    team_id: str | None,
    is_critical: bool,
    is_ai_generated: bool,
) -> ScheduledActivity:
    milestone_kind = _milestone_kind(instance.activity)
    return ScheduledActivity(
        instance_id=instance.instance_id,
        activity_id=instance.activity.activity_id,
        activity_name=instance.activity.activity_name,
        scope_ref=instance.scope_ref,
        start_date=start,
        end_date=end,
        actual_sla_days=actual_days,
        standard_sla_days=estimate.standard_sla_days,
        is_critical=is_critical,
        is_milestone=milestone_kind is not None or instance.activity.activity_type == "里程碑",
        milestone_kind=milestone_kind,
        predecessor_instance_ids=list(predecessor_ids),
        team_id=team_id,
        is_ai_generated=is_ai_generated,
    )


def _milestone_kind(activity: Activity) -> str | None:
    name = activity.activity_name
    if activity.activity_type == "到货" or "到货" in name:
        return "到货"
    if activity.activity_type == "机房准备" or ("机房" in name and ("就位" in name or "改造" in name)):
        return "机房就位"
    if "上电" in name:
        return "上电"
    if "上线" in name or "调优" in name:
        return "上线"
    if "移交" in name:
        return "移交"
    return None


def _room_ready_date(inputs: InputBundle, room_id: str | None) -> date | None:
    if room_id is None:
        return None
    room = next((item for item in inputs.rooms if item.room_id == room_id), None)
    if room is None:
        return None
    dates = [
        value
        for value in [room.cabling_ready_date, room.install_ready_date, room.liquid_ready_date]
        if value is not None
    ]
    return max(dates) if dates else None


def _arrival_ready_date(inputs: InputBundle, pod_id: str | None, activity: Activity) -> date | None:
    if pod_id is None:
        return None
    arrivals = [
        arrival
        for arrival in inputs.arrivals
        if arrival.pod_id == pod_id
        and arrival.arrival_date is not None
        and (activity.activity_name == "" or _arrival_matches(arrival, activity.activity_name) or "到货" in activity.activity_name)
    ]
    if not arrivals:
        return None
    return max(arrival.arrival_date for arrival in arrivals if arrival.arrival_date is not None)


def _predecessor_available_date(
    predecessor_id: str,
    predecessor_end: date,
    given_availability_dates: Mapping[str, date],
) -> date:
    if predecessor_id in given_availability_dates:
        return predecessor_end
    return predecessor_end + timedelta(days=1)


def _project_start(inputs: InputBundle) -> date:
    if inputs.project.start_date is not None:
        return inputs.project.start_date
    known_dates = _known_schedule_dates(inputs)
    if known_dates:
        return min(known_dates)
    _raise_infeasible(
        "项目开始日缺失",
        "输入未提供 project.start_date，且没有机房 ready、到货、批次目标或活动锚点日期可作为排期起点。",
    )


def _known_schedule_dates(inputs: InputBundle) -> list[date]:
    known_dates: list[date] = []
    for room in inputs.rooms:
        known_dates.extend(
            value
            for value in [room.cabling_ready_date, room.install_ready_date, room.liquid_ready_date]
            if value is not None
        )
    known_dates.extend(arrival.arrival_date for arrival in inputs.arrivals if arrival.arrival_date is not None)
    for batch in inputs.batches:
        known_dates.extend(
            value
            for value in [batch.power_on_target_date, batch.online_target_date]
            if value is not None
        )
    known_dates.extend(anchor.anchor_date for anchor in inputs.anchors)
    return known_dates


def _pod(inputs: InputBundle, pod_id: str | None) -> Pod:
    for pod in inputs.pods:
        if pod.pod_id == pod_id:
            return pod
    _raise_infeasible("PoD 引用不存在", f"找不到 PoD：{pod_id}")


def _batch(inputs: InputBundle, batch_id: str | None) -> Batch:
    for batch in inputs.batches:
        if batch.batch_id == batch_id:
            return batch
    _raise_infeasible("批次引用不存在", f"找不到批次：{batch_id}")


def _closed_days(start: date, end: date) -> int:
    return (end - start).days + 1


def _raise_infeasible(constraint: str, detail: str) -> None:
    raise EngineError(
        "INFEASIBLE",
        "当前约束下无法形成可执行排期。",
        [ConflictDetail(constraint=constraint, detail=detail)],
    )
