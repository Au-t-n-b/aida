from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil
from typing import Sequence

from agent.schedule.engine.scheduler import (
    ScheduleResult,
    _estimate_duration,
    _inputs_with_fs_dependencies_only,
    _instantiate,
    generate_plan,
)
from agent.schedule.contracts.api import ChangeSet
from agent.schedule.contracts.common import TEAM_SIZE_DEFAULT, TEAM_SIZE_MAX, TargetRef
from agent.schedule.contracts.inputs import InputBundle, ReworkEvent
from agent.schedule.contracts.outputs import (
    PlanKpis,
    PlanResult,
    PulledInput,
    RiskItem,
    ScheduledActivity,
    StrategyPlan,
    UnmetItem,
)


@dataclass(frozen=True)
class AdjustmentOptions:
    options: list[StrategyPlan]
    unmet: list[UnmetItem]


@dataclass(frozen=True)
class _DemandTarget:
    target: TargetRef
    target_desc: str
    desired_end: date
    gap_days: int


@dataclass(frozen=True)
class _DurationBound:
    instance_id: str
    activity_name: str
    duration_mode: str
    constraint_source: str | None
    standard_work_days: float
    minimum_work_days: float


def build_adjustment_options(
    inputs: InputBundle,
    changes: ChangeSet,
    seed_plan: PlanResult,
    seed_risks: Sequence[RiskItem],
) -> AdjustmentOptions:
    """Build strategy cards for /adjust without changing the public contracts."""

    base_plan = _apply_reworks(seed_plan, changes.reworks)
    demand = _select_primary_demand(base_plan, changes)
    if demand is None:
        option = _make_option(
            option_id="A",
            strategy="均匀压缩",
            plan=base_plan,
            inputs=inputs,
            risks=list(seed_risks),
            advice="建议采用均匀方案，作为当前可下发的稳定基线。",
        )
        return AdjustmentOptions(options=[option], unmet=[])

    if demand.gap_days > 0:
        a_plan, a_risks, a_overrides, a_unmet = _compress_plan(
            inputs,
            changes,
            seed_plan,
            demand,
            "uniform",
            list(seed_risks),
        )
        b_plan, b_risks, b_overrides, b_unmet = _compress_plan(
            inputs,
            changes,
            seed_plan,
            demand,
            "concentrated",
            list(seed_risks),
        )
        c_option, c_unmet = _pull_inputs_option(inputs, base_plan, list(seed_risks), demand)
        bounds = _duration_bounds(inputs)
        options = [
            _make_option(
                option_id="A",
                strategy="均匀压缩",
                plan=a_plan,
                inputs=inputs,
                risks=a_risks,
                advice="建议采用均匀压缩，关键路径活动共同承担压缩压力。",
                added_crew=_added_crew(a_overrides, bounds),
                has_unmet=bool(a_unmet),
            ),
            _make_option(
                option_id="B",
                strategy="集中压缩",
                plan=b_plan,
                inputs=inputs,
                risks=b_risks,
                advice="建议用于必须快速抢回节点的场景，优先压缩空间最大的关键活动。",
                added_crew=_added_crew(b_overrides, bounds),
                has_unmet=bool(b_unmet),
            ),
            c_option,
        ]
        return AdjustmentOptions(options=options, unmet=_merge_unmet([*a_unmet, *b_unmet, *c_unmet]))

    if demand.gap_days < 0:
        option, unmet = _buffer_option(inputs, changes, seed_plan, list(seed_risks), demand)
        return AdjustmentOptions(options=[option], unmet=unmet)

    option = _make_option(
        option_id="A",
        strategy="均匀压缩",
        plan=base_plan,
        inputs=inputs,
        risks=list(seed_risks),
        advice="调整后已经满足目标节点，暂不需要额外压缩。",
    )
    return AdjustmentOptions(options=[option], unmet=[])


def _run_variant(
    inputs: InputBundle,
    changes: ChangeSet,
    seed_plan: PlanResult,
    overrides: dict[str, float],
) -> tuple[PlanResult, list[RiskItem]]:
    result = generate_plan(
        inputs,
        incidents=changes.incidents,
        plan_id=seed_plan.plan_id,
        version=seed_plan.version,
        base_version=seed_plan.base_version,
        include_risks=True,
        duration_overrides=overrides,
    )
    assert isinstance(result, ScheduleResult)
    return _apply_reworks(result.plan, changes.reworks), list(result.risks)


def _compress_plan(
    inputs: InputBundle,
    changes: ChangeSet,
    seed_plan: PlanResult,
    demand: _DemandTarget,
    mode: str,
    base_risks: list[RiskItem],
) -> tuple[PlanResult, list[RiskItem], dict[str, float], list[UnmetItem]]:
    bounds = _duration_bounds(inputs)
    overrides: dict[str, float] = {}
    plan = _apply_reworks(seed_plan, changes.reworks)
    risks = list(base_risks)
    guard = 0
    concentrated_ids: set[str] | None = None
    if mode == "concentrated":
        initial_candidates = _compression_candidates(plan, bounds, overrides, demand.target)
        top_k = inputs.rule_config.concentrate_top_k
        concentrated_ids = {
            bound.instance_id
            for bound, _available in sorted(initial_candidates, key=lambda item: item[1], reverse=True)[:top_k]
        }

    while _target_end(plan, demand.target) > demand.desired_end and guard < 500:
        guard += 1
        candidates = _compression_candidates(plan, bounds, overrides, demand.target)
        if not candidates:
            break
        remaining_days = float((_target_end(plan, demand.target) - demand.desired_end).days)
        selected = candidates
        if mode == "concentrated":
            selected = [item for item in candidates if item[0].instance_id in (concentrated_ids or set())]
            selected = sorted(selected, key=lambda item: item[1], reverse=True)
            if not selected:
                break

        changed = False
        for bound, _available in selected:
            if remaining_days <= 0:
                break
            current = overrides.get(bound.instance_id, bound.standard_work_days)
            decrement = min(1.0, current - bound.minimum_work_days, float(remaining_days))
            next_work_days = current - decrement
            if next_work_days < current - 1e-9:
                overrides[bound.instance_id] = next_work_days
                remaining_days -= decrement
                changed = True
        if not changed:
            break
        plan, risks = _run_variant(inputs, changes, seed_plan, overrides)

    unmet = _unmet_for_gap(plan, demand)
    all_risks = _merge_risks([*risks, *_compression_risks(plan)])
    return plan, all_risks, overrides, unmet


def _buffer_option(
    inputs: InputBundle,
    changes: ChangeSet,
    seed_plan: PlanResult,
    base_risks: list[RiskItem],
    demand: _DemandTarget,
) -> tuple[StrategyPlan, list[UnmetItem]]:
    bounds = _duration_bounds(inputs)
    overrides: dict[str, float] = {}
    plan = _apply_reworks(seed_plan, changes.reworks)
    risks = list(base_risks)
    guard = 0

    while _target_end(plan, demand.target) < demand.desired_end and guard < 500:
        guard += 1
        candidates = _buffer_candidates(plan, bounds, demand.target)
        if not candidates:
            break
        bound = candidates[0]
        current = overrides.get(bound.instance_id, bound.standard_work_days)
        trial = dict(overrides)
        trial[bound.instance_id] = current + 1.0
        trial_plan, trial_risks = _run_variant(inputs, changes, seed_plan, trial)
        if _target_end(trial_plan, demand.target) > demand.desired_end:
            break
        overrides = trial
        plan = trial_plan
        risks = trial_risks

    remaining_days = max(0, (demand.desired_end - _target_end(plan, demand.target)).days)
    unmet = []
    if remaining_days:
        unmet.append(
            UnmetItem(
                target_desc=demand.target_desc,
                reason="关键路径缺少可延长的施工活动，无法完全吸收时间富余。",
                gap_days=remaining_days,
            )
        )
    option = _make_option(
        option_id="BUFFER",
        strategy="buffer延长",
        plan=plan,
        inputs=inputs,
        risks=risks,
        advice="建议把富余时间回灌为关键路径 buffer，降低现场扰动风险。",
        has_unmet=bool(unmet),
    )
    return option, unmet


def _pull_inputs_option(
    inputs: InputBundle,
    plan: PlanResult,
    risks: list[RiskItem],
    demand: _DemandTarget,
) -> tuple[StrategyPlan, list[UnmetItem]]:
    pulled_inputs: list[PulledInput] = []
    activity_by_id = {activity.instance_id: activity for activity in plan.activities}
    critical_prefix = _critical_prefix(plan, demand.target)
    candidate_ids: list[str] = []
    for instance_id in critical_prefix:
        candidate_ids.append(instance_id)
        activity = activity_by_id.get(instance_id)
        if activity is not None:
            candidate_ids.extend(activity.predecessor_instance_ids)

    for instance_id in candidate_ids:
        activity = activity_by_id.get(instance_id)
        if activity is None or activity.milestone_kind not in {"到货", "机房就位"}:
            continue
        ref_id = activity.scope_ref.ref_id
        if ref_id is None:
            continue
        suggested_date = activity.end_date - timedelta(days=demand.gap_days)
        if activity.milestone_kind == "到货":
            if _arrival_locked(inputs, ref_id, activity.end_date):
                continue
            pulled_inputs.append(
                PulledInput(
                    target_desc=f"到货({ref_id})",
                    current_date=activity.end_date,
                    suggested_date=suggested_date,
                )
            )
        elif activity.milestone_kind == "机房就位":
            if _room_locked(activity.end_date):
                continue
            pulled_inputs.append(
                PulledInput(
                    target_desc=f"机房就位({ref_id})",
                    current_date=activity.end_date,
                    suggested_date=suggested_date,
                )
            )

    pulled_inputs = _dedupe_pulled_inputs(pulled_inputs)
    unmet = []
    if not pulled_inputs:
        unmet.append(
            UnmetItem(
                target_desc=demand.target_desc,
                reason="关键路径上的站/货前置已锁定或不存在可提拉项，方案 C 不提拉施工。",
                gap_days=demand.gap_days,
            )
        )
    option = _make_option(
        option_id="C",
        strategy="站货提拉",
        plan=plan,
        inputs=inputs,
        risks=risks,
        advice="建议优先协调机房就位或到货时间，不压缩现场施工。",
        pulled_inputs=pulled_inputs,
        has_unmet=bool(unmet),
    )
    return option, unmet


def _select_primary_demand(plan: PlanResult, changes: ChangeSet) -> _DemandTarget | None:
    targets: list[_DemandTarget] = []
    for demand in changes.demands:
        current_end = _target_end(plan, demand.target)
        desired_end: date | None = None
        if demand.direction == "提前" and demand.amount_days is not None:
            desired_end = current_end - timedelta(days=demand.amount_days)
        elif demand.direction == "延后" and demand.amount_days is not None:
            desired_end = current_end + timedelta(days=demand.amount_days)
        elif demand.direction == "某日期前完成" and demand.deadline is not None:
            desired_end = demand.deadline
        if desired_end is None:
            continue
        targets.append(
            _DemandTarget(
                target=demand.target,
                target_desc=_target_desc(demand.target),
                desired_end=desired_end,
                gap_days=(current_end - desired_end).days,
            )
        )
    if not targets:
        return None
    early_targets = [target for target in targets if target.gap_days > 0]
    if early_targets:
        return max(early_targets, key=lambda target: target.gap_days)
    late_targets = [target for target in targets if target.gap_days < 0]
    if late_targets:
        return min(late_targets, key=lambda target: target.gap_days)
    return targets[0]


def _duration_bounds(inputs: InputBundle) -> dict[str, _DurationBound]:
    calculation_inputs = _inputs_with_fs_dependencies_only(inputs)
    bounds: dict[str, _DurationBound] = {}
    for instance in _instantiate(calculation_inputs):
        estimate = _estimate_duration(instance, calculation_inputs)
        minimum_work_days = estimate.minimum_work_days
        if minimum_work_days is None:
            minimum_work_days = estimate.standard_work_days
        bounds[instance.instance_id] = _DurationBound(
            instance_id=instance.instance_id,
            activity_name=instance.activity.activity_name,
            duration_mode=instance.activity.duration_mode,
            constraint_source=instance.activity.constraint_source,
            standard_work_days=estimate.standard_work_days,
            minimum_work_days=max(1.0, minimum_work_days),
        )
    return bounds


def _compression_candidates(
    plan: PlanResult,
    bounds: dict[str, _DurationBound],
    overrides: dict[str, float],
    target: TargetRef,
) -> list[tuple[_DurationBound, float]]:
    candidates: list[tuple[_DurationBound, float]] = []
    for instance_id in _critical_prefix(plan, target):
        bound = bounds.get(instance_id)
        if bound is None or bound.constraint_source != "人":
            continue
        current = overrides.get(instance_id, bound.standard_work_days)
        available = current - bound.minimum_work_days
        if available > 1e-9:
            candidates.append((bound, available))
    return candidates


def _buffer_candidates(
    plan: PlanResult,
    bounds: dict[str, _DurationBound],
    target: TargetRef,
) -> list[_DurationBound]:
    candidates: list[_DurationBound] = []
    for instance_id in _critical_prefix(plan, target):
        bound = bounds.get(instance_id)
        if bound is not None and bound.constraint_source == "人":
            candidates.append(bound)
    return candidates


def _make_option(
    *,
    option_id: str,
    strategy: str,
    plan: PlanResult,
    inputs: InputBundle,
    risks: Sequence[RiskItem],
    advice: str,
    added_crew: int = 0,
    pulled_inputs: Sequence[PulledInput] | None = None,
    has_unmet: bool = False,
) -> StrategyPlan:
    merged_risks = _merge_risks(risks)
    return StrategyPlan(
        option_id=option_id,
        strategy=strategy,
        kpis=_plan_kpis(plan, inputs, added_crew=added_crew),
        plan=plan,
        risk_level=_risk_level(merged_risks, has_unmet=has_unmet),
        advice=advice,
        risks=merged_risks,
        pulled_inputs=list(pulled_inputs or []),
    )


def _plan_kpis(plan: PlanResult, inputs: InputBundle, *, added_crew: int = 0) -> PlanKpis:
    dates = [(activity.start_date, activity.end_date) for activity in plan.activities]
    if dates:
        start = min(start_date for start_date, _ in dates)
        end = max(end_date for _, end_date in dates)
        total_duration_days = (end - start).days + 1
    else:
        total_duration_days = 0
    compressed_days = sum(
        max(0, (activity.standard_sla_days or activity.actual_sla_days) - activity.actual_sla_days)
        for activity in plan.activities
    )
    return PlanKpis(
        pod_count=len(inputs.pods),
        total_duration_days=total_duration_days,
        compressed_days=compressed_days,
        added_crew=added_crew,
    )


def _compression_risks(plan: PlanResult) -> list[RiskItem]:
    risks: list[RiskItem] = []
    for activity in plan.activities:
        standard_days = activity.standard_sla_days
        if standard_days is None or activity.actual_sla_days >= standard_days:
            continue
        severity = "高" if activity.actual_sla_days * 2 <= standard_days else "中"
        risks.append(
            RiskItem(
                risk_type="压缩强度",
                severity=severity,
                instance_id=activity.instance_id,
                message=(
                    f"{activity.activity_name} 已从标准 {standard_days} 天压缩到 "
                    f"{activity.actual_sla_days} 天，需重点保障交付风险。"
                ),
            )
        )
    return risks


def _added_crew(overrides: dict[str, float], bounds: dict[str, _DurationBound]) -> int:
    added = 0
    for instance_id, work_days in overrides.items():
        bound = bounds.get(instance_id)
        if bound is None or bound.duration_mode != "弹性" or work_days >= bound.standard_work_days:
            continue
        required_size = ceil(TEAM_SIZE_DEFAULT * bound.standard_work_days / work_days)
        added += max(0, min(TEAM_SIZE_MAX, required_size) - TEAM_SIZE_DEFAULT)
    return added


def _unmet_for_gap(plan: PlanResult, demand: _DemandTarget) -> list[UnmetItem]:
    gap_days = max(0, (_target_end(plan, demand.target) - demand.desired_end).days)
    if not gap_days:
        return []
    return [
        UnmetItem(
            target_desc=demand.target_desc,
            reason="关键路径可压活动已到极限，仍无法满足目标。",
            gap_days=gap_days,
        )
    ]


def _target_end(plan: PlanResult, target: TargetRef) -> date:
    instance_ids = _resolve_target_instance_ids(plan, target)
    activities = [
        activity
        for activity in plan.activities
        if not instance_ids or activity.instance_id in instance_ids
    ]
    if not activities:
        return plan.project_finish_date or date.min
    return max(activity.end_date for activity in activities)


def _critical_prefix(plan: PlanResult, target: TargetRef) -> list[str]:
    target_ids = set(_resolve_target_instance_ids(plan, target))
    if not target_ids:
        return list(plan.critical_path)
    prefix: list[str] = []
    for instance_id in plan.critical_path:
        prefix.append(instance_id)
        if instance_id in target_ids:
            return prefix
    return _target_chain(plan, target_ids)


def _target_chain(plan: PlanResult, target_ids: set[str]) -> list[str]:
    activity_by_id = {activity.instance_id: activity for activity in plan.activities}
    target_activities = [
        activity
        for activity in plan.activities
        if activity.instance_id in target_ids
    ]
    if not target_activities:
        return []

    current = max(target_activities, key=lambda activity: (activity.end_date, activity.instance_id))
    chain = [current.instance_id]
    while current.predecessor_instance_ids:
        predecessors = [
            activity_by_id[predecessor_id]
            for predecessor_id in current.predecessor_instance_ids
            if predecessor_id in activity_by_id
        ]
        if not predecessors:
            break
        current = max(
            predecessors,
            key=lambda activity: (activity.end_date, activity.actual_sla_days, activity.instance_id),
        )
        chain.append(current.instance_id)
    return list(reversed(chain))


def _resolve_target_instance_ids(plan: PlanResult, target: TargetRef) -> list[str]:
    if target.kind == "活动实例":
        return [target.ref_id] if target.ref_id is not None else []
    if target.kind == "批次上电":
        return [
            activity.instance_id
            for activity in plan.activities
            if activity.scope_ref.scope == "批次级"
            and activity.scope_ref.ref_id == target.ref_id
            and activity.milestone_kind == "上电"
        ]
    if target.kind == "批次上线":
        return [
            activity.instance_id
            for activity in plan.activities
            if activity.scope_ref.scope == "批次级"
            and activity.scope_ref.ref_id == target.ref_id
            and activity.milestone_kind == "上线"
        ]
    if target.kind == "项目移交":
        matches = [activity.instance_id for activity in plan.activities if activity.milestone_kind == "移交"]
        if matches:
            return matches
        if plan.project_finish_date is None:
            return []
        return [
            activity.instance_id
            for activity in plan.activities
            if activity.end_date == plan.project_finish_date
        ]
    if target.kind == "到货":
        return [
            activity.instance_id
            for activity in plan.activities
            if activity.scope_ref.scope == "PoD级"
            and activity.scope_ref.ref_id == target.ref_id
            and activity.milestone_kind == "到货"
        ]
    if target.kind == "机房就位":
        return [
            activity.instance_id
            for activity in plan.activities
            if activity.scope_ref.scope == "机房级"
            and activity.scope_ref.ref_id == target.ref_id
            and activity.milestone_kind == "机房就位"
        ]
    return []


def _target_desc(target: TargetRef) -> str:
    return f"{target.kind}({target.ref_id})" if target.ref_id else target.kind


def _arrival_locked(inputs: InputBundle, pod_id: str, current_date: date) -> bool:
    if any(arrival.pod_id == pod_id and arrival.arrival_status == "已到货" for arrival in inputs.arrivals):
        return True
    return current_date <= date.today()


def _room_locked(current_date: date) -> bool:
    return current_date <= date.today()


def _dedupe_pulled_inputs(items: Sequence[PulledInput]) -> list[PulledInput]:
    by_target: dict[str, PulledInput] = {}
    for item in items:
        current = by_target.get(item.target_desc)
        if current is None or item.suggested_date < current.suggested_date:
            by_target[item.target_desc] = item
    return list(by_target.values())


def _apply_reworks(plan: PlanResult, reworks: Sequence[ReworkEvent]) -> PlanResult:
    result = plan
    for rework in reworks:
        result = _apply_rework(result, rework)
    return result


def _apply_rework(plan: PlanResult, rework: ReworkEvent) -> PlanResult:
    activities = list(plan.activities)
    target_index = next(
        (index for index, activity in enumerate(activities) if activity.instance_id == rework.insert_after_instance_id),
        None,
    )
    if target_index is None:
        return plan

    target = activities[target_index]
    shift_days = rework.duration_days if rework.blocks_downstream else 0
    rework_instance_id = f"rework/{rework.rework_id}"
    descendants = _descendant_ids(activities, target.instance_id) if rework.blocks_downstream else set()
    shifted: list[ScheduledActivity] = []
    for activity in activities:
        predecessor_ids = list(activity.predecessor_instance_ids)
        if rework.blocks_downstream and target.instance_id in predecessor_ids:
            predecessor_ids = [
                rework_instance_id if predecessor_id == target.instance_id else predecessor_id
                for predecessor_id in predecessor_ids
            ]
        updates = {"predecessor_instance_ids": predecessor_ids}
        if activity.instance_id in descendants:
            updates["start_date"] = activity.start_date + timedelta(days=shift_days)
            updates["end_date"] = activity.end_date + timedelta(days=shift_days)
        shifted.append(activity.model_copy(update=updates))

    rework_start = target.end_date + timedelta(days=1)
    rework_activity = ScheduledActivity(
        instance_id=rework_instance_id,
        activity_id=rework.rework_id,
        activity_name=rework.rework_name,
        scope_ref=target.scope_ref,
        start_date=rework_start,
        end_date=rework_start + timedelta(days=rework.duration_days - 1),
        actual_sla_days=rework.duration_days,
        standard_sla_days=rework.duration_days,
        is_critical=target.is_critical,
        is_milestone=False,
        milestone_kind=None,
        predecessor_instance_ids=[target.instance_id],
        team_id=target.team_id,
    )

    insert_at = target_index + 1
    new_activities = [*shifted[:insert_at], rework_activity, *shifted[insert_at:]]
    critical_path = list(plan.critical_path)
    if target.instance_id in critical_path and rework_instance_id not in critical_path:
        critical_path.insert(critical_path.index(target.instance_id) + 1, rework_instance_id)
    return plan.model_copy(
        update={
            "activities": new_activities,
            "critical_path": critical_path,
            "project_finish_date": max((activity.end_date for activity in new_activities), default=None),
        }
    )


def _descendant_ids(activities: Sequence[ScheduledActivity], root_id: str) -> set[str]:
    successors: dict[str, list[str]] = {}
    for activity in activities:
        for predecessor_id in activity.predecessor_instance_ids:
            successors.setdefault(predecessor_id, []).append(activity.instance_id)
    descendants: set[str] = set()
    stack = list(successors.get(root_id, []))
    while stack:
        instance_id = stack.pop()
        if instance_id in descendants:
            continue
        descendants.add(instance_id)
        stack.extend(successors.get(instance_id, []))
    return descendants


def _risk_level(risks: Sequence[RiskItem], *, has_unmet: bool) -> str:
    if has_unmet or any(risk.severity == "高" for risk in risks):
        return "高"
    if risks:
        return "中"
    return "低"


def _merge_risks(risks: Sequence[RiskItem]) -> list[RiskItem]:
    seen: set[tuple[str, str | None, str]] = set()
    merged: list[RiskItem] = []
    for risk in risks:
        key = (risk.risk_type, risk.instance_id, risk.message)
        if key in seen:
            continue
        seen.add(key)
        merged.append(risk)
    return merged


def _merge_unmet(items: Sequence[UnmetItem]) -> list[UnmetItem]:
    seen: set[tuple[str, str, int | None]] = set()
    merged: list[UnmetItem] = []
    for item in items:
        key = (item.target_desc, item.reason, item.gap_days)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged
