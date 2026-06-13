from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

SCHEDULE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SCHEDULE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agent.schedule.engine import ScheduleResult, build_adjustment_options, generate_plan  # noqa: E402
from agent.schedule.contracts.api import ChangeSet  # noqa: E402
from agent.schedule.contracts.common import DateRange, TargetRef  # noqa: E402
from agent.schedule.contracts.inputs import (  # noqa: E402
    Activity,
    ArrivalItem,
    Batch,
    DemandRequest,
    Dependency,
    IncidentEvent,
    InputBundle,
    Pod,
    Project,
    RiskRule,
    ReworkEvent,
    Room,
    RuleConfig,
    Team,
    WorkloadRule,
)


def test_uniform_strategy_spreads_gap_across_critical_path():
    inputs = _project_bundle(
        activities=[
            _activity("critical_a", "关键施工 A", 4),
            _activity("critical_b", "关键施工 B", 4),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="critical_a", to_activity_id="critical_b", dep_type="FS"),
            Dependency(from_activity_id="critical_b", to_activity_id="done", dep_type="FS"),
        ],
    )
    seed = _seed(inputs)
    deadline = _activity_by_id(seed.plan)["project/done"].end_date - timedelta(days=4)

    adjustment = _adjust(inputs, _deadline_change("project/done", deadline), seed)

    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["project/critical_a"].actual_sla_days == 2
    assert activities["project/critical_b"].actual_sla_days == 2
    assert activities["project/done"].end_date == deadline


def test_concentrated_strategy_uses_configured_top_k():
    inputs = _project_bundle(
        activities=[
            _activity("critical_a", "关键施工 A", 4),
            _activity("critical_b", "关键施工 B", 4),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="critical_a", to_activity_id="critical_b", dep_type="FS"),
            Dependency(from_activity_id="critical_b", to_activity_id="done", dep_type="FS"),
        ],
        rule_config=RuleConfig(concentrate_top_k=1),
    )
    seed = _seed(inputs)
    deadline = _activity_by_id(seed.plan)["project/done"].end_date - timedelta(days=3)

    adjustment = _adjust(inputs, _deadline_change("project/done", deadline), seed)

    option = _option(adjustment.options, "B")
    activities = _activity_by_id(option.plan)
    assert activities["project/critical_a"].actual_sla_days == 1
    assert activities["project/critical_b"].actual_sla_days == 4
    assert activities["project/done"].end_date == deadline


def test_pull_inputs_returns_unlocked_room_and_arrival_but_skips_locked_predecessors():
    future_start = date.today() + timedelta(days=30)
    unlocked = _room_arrival_bundle(
        start=future_start,
        room_ready=future_start,
        arrival_date=future_start + timedelta(days=1),
        arrival_status="在途",
    )
    unlocked_seed = _seed(unlocked)
    unlocked_deadline = _target_end(unlocked_seed.plan, "B1/online") - timedelta(days=2)

    unlocked_adjustment = _adjust(
        unlocked,
        _deadline_change_for_target(TargetRef(kind="批次上线", ref_id="B1"), unlocked_deadline),
        unlocked_seed,
    )

    pulled_targets = {item.target_desc for item in _option(unlocked_adjustment.options, "C").pulled_inputs}
    assert pulled_targets == {"机房就位(R1)", "到货(P1)"}

    past_start = date.today() - timedelta(days=60)
    locked = _room_arrival_bundle(
        start=past_start,
        room_ready=past_start,
        arrival_date=past_start + timedelta(days=1),
        arrival_status="已到货",
    )
    locked_seed = _seed(locked)
    locked_deadline = _target_end(locked_seed.plan, "B1/online") - timedelta(days=2)

    locked_adjustment = _adjust(
        locked,
        _deadline_change_for_target(TargetRef(kind="批次上线", ref_id="B1"), locked_deadline),
        locked_seed,
    )

    assert _option(locked_adjustment.options, "C").pulled_inputs == []
    assert locked_adjustment.unmet
    assert "已锁定" in locked_adjustment.unmet[-1].reason


def test_compression_only_touches_critical_path_and_stops_at_minimum_with_risk():
    inputs = _project_bundle(
        activities=[
            _activity("critical", "关键施工", 5, minimum_days=2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
            _activity("side", "非关键施工", 3),
        ],
        dependencies=[
            Dependency(from_activity_id="critical", to_activity_id="done", dep_type="FS"),
        ],
    )
    seed = _seed(inputs)

    adjustment = _adjust(inputs, _deadline_change("project/done", date(2026, 1, 1)), seed)

    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["project/critical"].actual_sla_days == 2
    assert activities["project/side"].actual_sla_days == 3
    assert any(
        risk.risk_type == "压缩强度" and risk.instance_id == "project/critical"
        for risk in option.risks
    )
    assert adjustment.unmet[0].gap_days == 2


def test_elastic_added_crew_is_capped_and_unmet_reports_remaining_gap():
    workload_rule = WorkloadRule(
        workload_source="计算柜",
        unit="柜",
        standard_daily_rate=6,
        limit_daily_rate=10,
    )
    inputs = _project_bundle(
        activities=[
            _activity(
                "elastic",
                "弹性安装",
                None,
                duration_mode="弹性",
                workload_rules=[workload_rule],
            ),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="elastic", to_activity_id="done", dep_type="FS"),
        ],
        arrivals=[
            ArrivalItem(
                arrival_id="A1",
                pod_id="P1",
                device_type="计算柜",
                quantity=60,
                arrival_status="在途",
            )
        ],
    )
    seed = _seed(inputs)

    adjustment = _adjust(inputs, _deadline_change("project/done", date(2026, 1, 1)), seed)

    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["project/elastic"].actual_sla_days == 6
    assert option.kpis.added_crew == 6
    assert option.kpis.added_crew <= 6
    assert adjustment.unmet[0].gap_days == 6


def test_buffer_extension_stops_at_target_upper_bound():
    inputs = _project_bundle(
        activities=[
            _activity("install", "安装", 2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="install", to_activity_id="done", dep_type="FS"),
        ],
    )
    seed = _seed(inputs)
    target = TargetRef(kind="活动实例", ref_id="project/done")
    desired_end = _target_end(seed.plan, "project/done") + timedelta(days=3)
    changes = ChangeSet(
        demands=[
            DemandRequest(
                demand_id="D-buffer",
                target=target,
                direction="延后",
                amount_days=3,
            )
        ]
    )

    adjustment = _adjust(inputs, changes, seed)

    option = _option(adjustment.options, "BUFFER")
    assert _target_end(option.plan, "project/done") == desired_end
    assert _target_end(option.plan, "project/done") <= desired_end
    assert adjustment.unmet == []


def test_buffer_extension_reports_activity_risk_when_duration_exceeds_standard():
    inputs = _project_bundle(
        activities=[
            _activity("install", "安装", 2, risk_rule=_risk_rule("buffer施工风险", "富余时间回灌后需保障现场节奏")),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="install", to_activity_id="done", dep_type="FS"),
        ],
    )
    seed = _seed(inputs)
    changes = ChangeSet(
        demands=[
            DemandRequest(
                demand_id="D-buffer",
                target=TargetRef(kind="活动实例", ref_id="project/done"),
                direction="延后",
                amount_days=3,
            )
        ]
    )

    adjustment = _adjust(inputs, changes, seed)

    option = _option(adjustment.options, "BUFFER")
    risk = next(risk for risk in option.risks if risk.risk_type == "活动风险")
    assert risk.instance_id == "project/install"
    assert risk.severity == "高"
    assert "buffer施工风险" in risk.message
    assert "较标准 SLA 2 天超出 3 天" in risk.message


def test_adjustment_options_preserve_incident_window_effect():
    inputs = _project_bundle(
        activities=[
            _activity("install", "安装", 2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="install", to_activity_id="done", dep_type="FS"),
        ],
    )
    incidents = [
        IncidentEvent(
            incident_id="I-stop",
            incident_type="假期停工",
            window=DateRange(start=date(2026, 1, 2), end=date(2026, 1, 2)),
            efficiency=0,
        )
    ]
    seed_result = generate_plan(inputs, incidents=incidents, include_risks=True)
    assert isinstance(seed_result, ScheduleResult)

    adjustment = _adjust(inputs, ChangeSet(incidents=incidents), seed_result)

    activities = _activity_by_id(_option(adjustment.options, "A").plan)
    assert activities["project/install"].actual_sla_days == 3
    assert activities["project/done"].end_date == date(2026, 1, 4)


def test_rework_is_inserted_as_independent_activity_and_shifts_downstream():
    inputs = _project_bundle(
        activities=[
            _activity("install", "安装", 2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="install", to_activity_id="done", dep_type="FS"),
        ],
    )
    seed = _seed(inputs)
    changes = ChangeSet(
        reworks=[
            ReworkEvent(
                rework_id="RW1",
                rework_name="返工复测",
                insert_after_instance_id="project/install",
                duration_days=2,
            )
        ]
    )

    adjustment = _adjust(inputs, changes, seed)

    activities = _activity_by_id(_option(adjustment.options, "A").plan)
    assert activities["rework/RW1"].predecessor_instance_ids == ["project/install"]
    assert activities["project/done"].predecessor_instance_ids == ["rework/RW1"]
    assert activities["project/done"].start_date == _activity_by_id(seed.plan)["project/done"].start_date + timedelta(days=2)


def _adjust(inputs: InputBundle, changes: ChangeSet, seed: ScheduleResult | None = None):
    result = seed or _seed(inputs)
    return build_adjustment_options(inputs, changes, result.plan, result.risks)


def _seed(inputs: InputBundle) -> ScheduleResult:
    result = generate_plan(inputs, include_risks=True)
    assert isinstance(result, ScheduleResult)
    return result


def _option(options, option_id: str):
    return next(option for option in options if option.option_id == option_id)


def _activity_by_id(plan):
    return {activity.instance_id: activity for activity in plan.activities}


def _risk_rule(name: str, impact: str) -> RiskRule:
    return RiskRule(
        trigger_logic="不要输出的触发逻辑",
        risk_name=name,
        impact=impact,
    )


def _target_end(plan, instance_id: str) -> date:
    return _activity_by_id(plan)[instance_id].end_date


def _deadline_change(instance_id: str, deadline: date) -> ChangeSet:
    return _deadline_change_for_target(TargetRef(kind="活动实例", ref_id=instance_id), deadline)


def _deadline_change_for_target(target: TargetRef, deadline: date) -> ChangeSet:
    return ChangeSet(
        demands=[
            DemandRequest(
                demand_id=f"D-{target.kind}-{target.ref_id or 'project'}",
                target=target,
                direction="某日期前完成",
                deadline=deadline,
            )
        ]
    )


def _activity(
    activity_id: str,
    name: str,
    days: int | None,
    *,
    scope: str = "项目级",
    activity_type: str = "普通",
    constraint_source: str | None = "人",
    minimum_days: int | None = 1,
    duration_mode: str = "固定",
    workload_rules: list[WorkloadRule] | None = None,
    risk_rule: RiskRule | None = None,
) -> Activity:
    return Activity(
        activity_id=activity_id,
        activity_name=name,
        scope=scope,
        activity_type=activity_type,
        constraint_source=constraint_source,
        duration_mode=duration_mode,
        standard_sla_days=days,
        minimum_sla_days=minimum_days,
        workload_rules=workload_rules or [],
        risk_rule=risk_rule,
    )


def _project_bundle(
    *,
    activities: list[Activity],
    dependencies: list[Dependency],
    arrivals: list[ArrivalItem] | None = None,
    rule_config: RuleConfig | None = None,
) -> InputBundle:
    return InputBundle(
        project=Project(project_id="adjust-demo", project_name="adjust demo", start_date=date(2026, 1, 1)),
        rooms=[Room(room_id="R1")],
        pods=[Pod(pod_id="P1", room_id="R1")],
        arrivals=arrivals or [],
        teams=[Team(team_id="T1", size=12, experience="丰富")],
        activities=activities,
        dependencies=dependencies,
        batches=[Batch(batch_id="B1", batch_name="批次1", pod_ids=["P1"])],
        rule_config=rule_config or RuleConfig(),
    )


def _room_arrival_bundle(
    *,
    start: date,
    room_ready: date,
    arrival_date: date,
    arrival_status: str,
) -> InputBundle:
    return InputBundle(
        project=Project(project_id="pull-demo", project_name="pull demo", start_date=start),
        rooms=[Room(room_id="R1", install_ready_date=room_ready)],
        pods=[Pod(pod_id="P1", room_id="R1")],
        arrivals=[
            ArrivalItem(
                arrival_id="A1",
                pod_id="P1",
                device_type="设备",
                quantity=1,
                arrival_status=arrival_status,
                arrival_date=arrival_date,
            )
        ],
        teams=[Team(team_id="T1", size=12, experience="丰富")],
        activities=[
            _activity("ready", "机房就位", 1, scope="机房级", activity_type="机房准备", constraint_source=None),
            _activity("arrival", "设备到货", 1, scope="PoD级", activity_type="到货", constraint_source=None),
            _activity("install", "安装", 5, scope="PoD级"),
            _activity("online", "批次上线", 1, scope="批次级", activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="ready", to_activity_id="arrival", dep_type="FS"),
            Dependency(from_activity_id="arrival", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="install", to_activity_id="online", dep_type="FS"),
        ],
        batches=[Batch(batch_id="B1", batch_name="批次1", pod_ids=["P1"])],
    )
