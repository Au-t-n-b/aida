from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

SCHEDULE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SCHEDULE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agent.schedule.engine import EngineError, ScheduleResult, generate_plan, recalculate_plan_with_duration_overrides  # noqa: E402
from agent.schedule.contracts.common import DateRange, TargetRef  # noqa: E402
from agent.schedule.contracts.inputs import (  # noqa: E402
    Activity,
    Anchor,
    ArrivalItem,
    Batch,
    Dependency,
    IncidentEvent,
    InputBundle,
    Pod,
    Project,
    RiskRule,
    Room,
    RuleConfig,
    Team,
    WorkloadRule,
)


def _activity(
    activity_id: str,
    name: str,
    scope: str,
    days: int | None = 1,
    *,
    activity_type: str = "普通",
    duration_mode: str = "固定",
    constraint_source: str | None = None,
    workload_rules: list[WorkloadRule] | None = None,
    is_default_milestone: bool = False,
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
        minimum_sla_days=1 if days else None,
        workload_rules=workload_rules or [],
        is_default_milestone=is_default_milestone,
        risk_rule=risk_rule,
    )


def _bundle(
    *,
    activities: list[Activity],
    dependencies: list[Dependency] | None = None,
    pods: list[Pod] | None = None,
    rooms: list[Room] | None = None,
    batches: list[Batch] | None = None,
    arrivals: list[ArrivalItem] | None = None,
    teams: list[Team] | None = None,
    anchors: list[Anchor] | None = None,
    start: date | None = date(2026, 1, 1),
    rule_config: RuleConfig | None = None,
) -> InputBundle:
    pod_items = pods or [Pod(pod_id="P1", room_id="R1")]
    room_items = rooms or [Room(room_id="R1")]
    return InputBundle(
        project=Project(project_id="demo", project_name="demo", start_date=start),
        rooms=room_items,
        pods=pod_items,
        arrivals=arrivals or [],
        teams=teams or [Team(team_id="T1", experience="丰富")],
        activities=activities,
        dependencies=dependencies or [],
        batches=batches or [Batch(batch_id="B1", batch_name="批次1", pod_ids=[pod.pod_id for pod in pod_items])],
        anchors=anchors or [],
        rule_config=rule_config or RuleConfig(),
    )


def _by_id(plan):
    return {activity.instance_id: activity for activity in plan.activities}


def _risk_rule(
    name: str,
    impact: str,
    *,
    mitigation: str | None = None,
    owner: str | None = None,
) -> RiskRule:
    return RiskRule(
        trigger_logic="不要输出的触发逻辑",
        risk_name=name,
        impact=impact,
        mitigation=mitigation,
        mitigation_owner=owner,
    )


def test_scope_instantiation_and_batch_convergence_gate():
    inputs = _bundle(
        rooms=[Room(room_id="R1")],
        pods=[Pod(pod_id="P1", room_id="R1"), Pod(pod_id="P2", room_id="R1")],
        batches=[Batch(batch_id="B1", batch_name="批次1", pod_ids=["P1", "P2"])],
        activities=[
            _activity("install", "安装 PoD", "PoD级", 2, constraint_source="人"),
            _activity("power", "设备上电", "批次级", 1, activity_type="里程碑", is_default_milestone=True),
            _activity("single", "单机调测", "PoD级", 1, constraint_source="人"),
            _activity("online", "上线", "批次级", 1, activity_type="里程碑", is_default_milestone=True),
        ],
        dependencies=[
            Dependency(from_activity_id="install", to_activity_id="power", dep_type="FS"),
            Dependency(from_activity_id="power", to_activity_id="single", dep_type="FS"),
            Dependency(from_activity_id="single", to_activity_id="online", dep_type="FS"),
        ],
    )

    plan = generate_plan(inputs)
    activities = _by_id(plan)

    assert set(activities) == {"P1/install", "P2/install", "B1/power", "P1/single", "P2/single", "B1/online"}
    assert activities["B1/power"].predecessor_instance_ids == ["P1/install", "P2/install"]
    assert activities["P1/single"].predecessor_instance_ids == ["B1/power"]
    assert activities["P2/single"].predecessor_instance_ids == ["B1/power"]
    assert activities["B1/online"].predecessor_instance_ids == ["P1/single", "P2/single"]
    assert activities["P1/install"].start_date == date(2026, 1, 1)
    assert activities["P1/install"].end_date == date(2026, 1, 2)
    assert activities["B1/power"].start_date == date(2026, 1, 3)
    assert activities["B1/online"].end_date == date(2026, 1, 5)


def test_elastic_workload_uses_arrival_quantity_and_experience_efficiency():
    activity = _activity(
        "install",
        "液冷计算柜安装",
        "PoD级",
        None,
        duration_mode="弹性",
        constraint_source="人",
        workload_rules=[
            WorkloadRule(
                workload_source="计算柜",
                unit="柜",
                standard_daily_rate=4,
                limit_daily_rate=5,
            )
        ],
    )
    arrivals = [
        ArrivalItem(
            arrival_id="A1",
            pod_id="P1",
            device_type="计算柜",
            quantity=10,
            arrival_status="已到货",
        )
    ]

    rich_plan = generate_plan(_bundle(activities=[activity], arrivals=arrivals, teams=[Team(team_id="T1", experience="丰富")]))
    regular_plan = generate_plan(_bundle(activities=[activity], arrivals=arrivals, teams=[Team(team_id="T1", experience="一般")]))

    rich_activity = _by_id(rich_plan)["P1/install"]
    regular_activity = _by_id(regular_plan)["P1/install"]
    assert rich_activity.standard_sla_days == 3
    assert rich_activity.actual_sla_days == 3
    assert rich_activity.end_date == date(2026, 1, 3)
    assert regular_activity.actual_sla_days == 4
    assert regular_activity.end_date == date(2026, 1, 4)


def test_incident_windows_use_same_day_minimum_and_pause_zero_efficiency():
    inputs = _bundle(
        activities=[_activity("install", "安装 PoD", "PoD级", 2, constraint_source="人")],
        teams=[Team(team_id="T1", experience="一般")],
    )
    incidents = [
        IncidentEvent(
            incident_id="I1",
            incident_type="效率打折",
            window=DateRange(start=date(2026, 1, 1), end=date(2026, 1, 1)),
            efficiency=0.5,
        ),
        IncidentEvent(
            incident_id="I2",
            incident_type="效率打折",
            window=DateRange(start=date(2026, 1, 1), end=date(2026, 1, 1)),
            efficiency=0.25,
        ),
        IncidentEvent(
            incident_id="I3",
            incident_type="假期停工",
            window=DateRange(start=date(2026, 1, 2), end=date(2026, 1, 2)),
            efficiency=0,
        ),
    ]

    plan = generate_plan(inputs, incidents=incidents)
    scheduled = _by_id(plan)["P1/install"]

    assert scheduled.actual_sla_days == 5
    assert scheduled.end_date == date(2026, 1, 5)


def test_activity_risks_follow_overrun_ratio_tiers_and_business_message():
    inputs = _bundle(
        activities=[
            _activity("plain", "无规则长活动", "项目级", 30),
            _activity("low", "低档活动", "项目级", 10, risk_rule=_risk_rule("低档风险", "低档影响")),
            _activity("medium", "中档活动", "项目级", 10, risk_rule=_risk_rule("中档风险", "中档影响")),
            _activity(
                "high",
                "高档活动",
                "项目级",
                10,
                risk_rule=_risk_rule(
                    "高档风险",
                    "高档影响",
                    mitigation="安排专项复核",
                    owner="交付负责人",
                ),
            ),
        ]
    )

    result = generate_plan(
        inputs,
        include_risks=True,
        duration_overrides={
            "project/plain": 35,
            "project/low": 11,
            "project/medium": 12,
            "project/high": 15,
        },
    )

    assert isinstance(result, ScheduleResult)
    risks = {risk.instance_id: risk for risk in result.risks if risk.risk_type == "活动风险"}
    assert set(risks) == {"project/low", "project/medium", "project/high"}
    assert risks["project/low"].severity == "低"
    assert risks["project/medium"].severity == "中"
    assert risks["project/high"].severity == "高"
    assert "高档风险" in risks["project/high"].message
    assert "高档影响" in risks["project/high"].message
    assert "较标准 SLA 10 天超出 5 天" in risks["project/high"].message
    assert "预案：安排专项复核" in risks["project/high"].message
    assert "责任人：交付负责人" in risks["project/high"].message
    assert "不要输出的触发逻辑" not in risks["project/high"].message
    assert risks["project/high"].mitigation == "安排专项复核"


def test_activity_risk_on_critical_path_is_high_even_when_overrun_is_small():
    inputs = _bundle(
        activities=[
            _activity("risky", "关键活动", "项目级", 10, risk_rule=_risk_rule("关键风险", "影响后续节点")),
            _activity("done", "移交", "项目级", 1, activity_type="里程碑", is_default_milestone=True),
        ],
        dependencies=[Dependency(from_activity_id="risky", to_activity_id="done", dep_type="FS")],
    )

    result = generate_plan(inputs, include_risks=True, duration_overrides={"project/risky": 11})

    assert isinstance(result, ScheduleResult)
    risk = next(risk for risk in result.risks if risk.risk_type == "活动风险")
    assert risk.instance_id == "project/risky"
    assert risk.severity == "高"


def test_activity_without_risk_rule_does_not_emit_activity_risk_when_overrun():
    inputs = _bundle(activities=[_activity("plain", "无规则活动", "项目级", 10)])

    result = generate_plan(inputs, include_risks=True, duration_overrides={"project/plain": 20})

    assert isinstance(result, ScheduleResult)
    assert [risk for risk in result.risks if risk.risk_type == "活动风险"] == []


def test_critical_path_is_recomputed_when_durations_change():
    def make_plan(branch_b_days: int):
        return generate_plan(
            _bundle(
                activities=[
                    _activity("A", "链路 A", "项目级", 3),
                    _activity("B", "链路 B", "项目级", branch_b_days),
                    _activity("finish", "移交", "项目级", 1, activity_type="里程碑", is_default_milestone=True),
                ],
                dependencies=[
                    Dependency(from_activity_id="A", to_activity_id="finish", dep_type="FS"),
                    Dependency(from_activity_id="B", to_activity_id="finish", dep_type="FS"),
                ],
            )
        )

    original = make_plan(branch_b_days=2)
    changed = make_plan(branch_b_days=5)

    assert original.critical_path == ["project/A", "project/finish"]
    assert changed.critical_path == ["project/B", "project/finish"]


def test_commit_duration_override_recalculates_downstream_from_backend_plan():
    inputs = _bundle(
        activities=[
            _activity("ready", "机房就位", "机房级", 1, activity_type="机房准备"),
            _activity("install", "安装 PoD", "PoD级", 5, constraint_source="人"),
            _activity("cabling", "综合布线", "PoD级", 2, constraint_source="人"),
        ],
        dependencies=[
            Dependency(from_activity_id="ready", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="install", to_activity_id="cabling", dep_type="FS"),
        ],
    )
    base = generate_plan(inputs)

    recalculated = recalculate_plan_with_duration_overrides(inputs, base, {"P1/install": 7})
    activities = _by_id(recalculated)

    assert activities["P1/install"].start_date == date(2026, 1, 2)
    assert activities["P1/install"].end_date == date(2026, 1, 8)
    assert activities["P1/install"].actual_sla_days == 7
    assert activities["P1/cabling"].start_date == date(2026, 1, 9)
    assert activities["P1/cabling"].end_date == date(2026, 1, 10)
    assert recalculated.project_finish_date == date(2026, 1, 10)


def test_duration_override_below_minimum_sla_is_infeasible():
    inputs = _bundle(
        activities=[
            Activity(
                activity_id="install",
                activity_name="安装 PoD",
                scope="PoD级",
                constraint_source="人",
                standard_sla_days=5,
                minimum_sla_days=2,
            )
        ]
    )

    with pytest.raises(EngineError) as exc_info:
        generate_plan(inputs, duration_overrides={"P1/install": 1})

    assert exc_info.value.code == "INFEASIBLE"
    assert exc_info.value.to_response().conflicts[0].constraint == "活动工期低于极限 SLA"


def test_infeasible_when_forward_window_misses_hard_anchor():
    inputs = _bundle(
        activities=[
            _activity("A", "前置活动", "项目级", 3),
            _activity("M", "移交", "项目级", 1, activity_type="里程碑", is_default_milestone=True),
        ],
        dependencies=[Dependency(from_activity_id="A", to_activity_id="M", dep_type="FS")],
        anchors=[
            Anchor(
                anchor_id="anchor-M",
                target=TargetRef(kind="活动实例", ref_id="project/M"),
                anchor_date=date(2026, 1, 2),
                anchor_source="指定活动",
            )
        ],
    )

    with pytest.raises(EngineError) as exc_info:
        generate_plan(inputs)

    assert exc_info.value.code == "INFEASIBLE"
    assert exc_info.value.to_response().conflicts[0].constraint == "活动锚点早于依赖可行时间"


def test_non_fs_dependencies_are_skipped_and_reported_as_risks():
    inputs = _bundle(
        activities=[
            _activity("A", "前置完成", "项目级", 1),
            _activity("B", "并行完成", "项目级", 5),
            _activity("C", "后续施工", "项目级", 1),
        ],
        dependencies=[
            Dependency(from_activity_id="A", to_activity_id="C", dep_type="FS"),
            Dependency(from_activity_id="B", to_activity_id="C", dep_type="FF"),
        ],
    )

    result = generate_plan(inputs, include_risks=True)

    assert isinstance(result, ScheduleResult)
    activities = _by_id(result.plan)
    assert activities["project/C"].start_date == date(2026, 1, 2)
    assert activities["project/C"].predecessor_instance_ids == ["project/A"]
    assert len(result.risks) == 1
    risk = result.risks[0]
    assert risk.risk_type == "依赖未纳入"
    assert risk.severity == "中"
    assert risk.instance_id is None
    assert "B（并行完成） -> C（后续施工）" in risk.message
    assert "完成对齐(FF)未纳入计算" in risk.message


def test_missing_batch_readiness_is_backsolved_from_target_milestone():
    inputs = _bundle(
        rooms=[Room(room_id="R1")],
        pods=[Pod(pod_id="P1", room_id="R1")],
        teams=[Team(team_id="T1", experience="一般")],
        batches=[Batch(batch_id="B1", batch_name="批次1", pod_ids=["P1"], online_target_date=date(2026, 1, 20))],
        activities=[
            _activity("room_ready", "机房就位", "机房级", 7, activity_type="机房准备", is_default_milestone=True),
            _activity("arrival", "设备到货", "PoD级", 1, activity_type="到货", is_default_milestone=True),
            _activity("install", "机柜上架安装", "PoD级", 5, constraint_source="人"),
            _activity("cabling", "综合布线", "PoD级", 4, constraint_source="人"),
            _activity("power_on", "上电点亮", "批次级", 1, activity_type="里程碑", is_default_milestone=True),
            _activity("online", "批次上线", "批次级", 1, activity_type="里程碑", is_default_milestone=True),
        ],
        dependencies=[
            Dependency(from_activity_id="room_ready", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="arrival", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="install", to_activity_id="cabling", dep_type="FS"),
            Dependency(from_activity_id="cabling", to_activity_id="power_on", dep_type="FS"),
            Dependency(from_activity_id="power_on", to_activity_id="online", dep_type="FS"),
        ],
    )

    result = generate_plan(inputs, include_risks=True)

    assert isinstance(result, ScheduleResult)
    assert len(result.readiness_suggestions) == 1
    suggestion = result.readiness_suggestions[0]
    assert suggestion.batch_id == "B1"
    assert suggestion.suggested_room_ready == {"R1": date(2026, 1, 6)}
    assert suggestion.suggested_arrival == {"P1": date(2026, 1, 6)}

    activities = _by_id(result.plan)
    assert activities["R1/room_ready"].end_date == date(2026, 1, 6)
    assert activities["P1/arrival"].end_date == date(2026, 1, 6)
    assert activities["P1/install"].start_date == date(2026, 1, 7)
    assert activities["B1/online"].end_date == date(2026, 1, 20)
    assert activities["R1/room_ready"].is_ai_generated
    assert activities["P1/arrival"].is_ai_generated
    assert activities["P1/install"].is_ai_generated
    assert not activities["B1/online"].is_ai_generated


def test_given_room_ready_and_arrival_dates_are_forward_availability_points():
    inputs = _bundle(
        start=None,
        rooms=[Room(room_id="R1", install_ready_date=date(2026, 1, 11))],
        pods=[Pod(pod_id="P1", room_id="R1")],
        arrivals=[
            ArrivalItem(
                arrival_id="A1",
                pod_id="P1",
                device_type="设备",
                quantity=1,
                arrival_status="在途",
                arrival_date=date(2026, 1, 12),
            )
        ],
        batches=[Batch(batch_id="B1", batch_name="批次1", pod_ids=["P1"], online_target_date=date(2026, 1, 25))],
        activities=[
            _activity("room_ready", "机房就位", "机房级", 30, activity_type="机房准备"),
            _activity("arrival", "设备到货", "PoD级", 10, activity_type="到货"),
            _activity("install", "机柜上架安装", "PoD级", 5),
            _activity("online", "批次上线", "批次级", 1, activity_type="里程碑"),
        ],
        dependencies=[
            Dependency(from_activity_id="room_ready", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="arrival", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="install", to_activity_id="online", dep_type="FS"),
        ],
    )

    result = generate_plan(inputs, include_risks=True)

    assert isinstance(result, ScheduleResult)
    assert result.readiness_suggestions == []
    activities = _by_id(result.plan)
    assert activities["R1/room_ready"].start_date == date(2026, 1, 11)
    assert activities["R1/room_ready"].end_date == date(2026, 1, 11)
    assert activities["R1/room_ready"].actual_sla_days == 1
    assert activities["P1/arrival"].start_date == date(2026, 1, 12)
    assert activities["P1/arrival"].end_date == date(2026, 1, 12)
    assert activities["P1/arrival"].actual_sla_days == 1
    assert activities["P1/install"].start_date == date(2026, 1, 12)
    assert activities["P1/install"].end_date == date(2026, 1, 16)
    assert activities["B1/online"].end_date == date(2026, 1, 25)


def test_late_given_ready_reports_infeasible_against_batch_target():
    inputs = _bundle(
        start=None,
        rooms=[Room(room_id="R1", install_ready_date=date(2026, 1, 20))],
        pods=[Pod(pod_id="P1", room_id="R1")],
        arrivals=[
            ArrivalItem(
                arrival_id="A1",
                pod_id="P1",
                device_type="设备",
                quantity=1,
                arrival_status="在途",
                arrival_date=date(2026, 1, 20),
            )
        ],
        batches=[Batch(batch_id="B1", batch_name="批次1", pod_ids=["P1"], online_target_date=date(2026, 1, 23))],
        activities=[
            _activity("room_ready", "机房就位", "机房级", 30, activity_type="机房准备"),
            _activity("arrival", "设备到货", "PoD级", 10, activity_type="到货"),
            _activity("install", "机柜上架安装", "PoD级", 5),
            _activity("online", "批次上线", "批次级", 1, activity_type="里程碑"),
        ],
        dependencies=[
            Dependency(from_activity_id="room_ready", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="arrival", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="install", to_activity_id="online", dep_type="FS"),
        ],
    )

    with pytest.raises(EngineError) as exc_info:
        generate_plan(inputs)

    assert exc_info.value.code == "INFEASIBLE"
    conflict = exc_info.value.to_response().conflicts[0]
    assert conflict.constraint == "前后向窗口交集为空"
    assert "B1/online" in conflict.detail
    assert "晚于目标" in conflict.detail


def test_golden_fixture_non_fs_dependencies_are_skipped_with_risks():
    fixture_path = SCHEDULE_ROOT / "tests" / "fixtures" / "input_bundle.golden.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    bundle = InputBundle.model_validate(payload)

    plan = generate_plan(bundle)
    result = generate_plan(bundle, include_risks=True)

    assert isinstance(result, ScheduleResult)
    assert len(plan.activities) > len(bundle.activities)
    assert len({activity.instance_id for activity in plan.activities}) == len(plan.activities)
    assert plan.project_finish_date is not None
    assert result.plan == plan
    dependency_risks = [risk for risk in result.risks if risk.risk_type == "依赖未纳入"]
    assert len(dependency_risks) == 21
    assert all(risk.severity == "中" for risk in dependency_risks)
    assert any("完成对齐(FF)未纳入计算" in risk.message for risk in dependency_risks)
    assert any("开始对齐(SS)未纳入计算" in risk.message for risk in dependency_risks)


def test_golden_fixture_fs_subset_can_be_scheduled_without_importer():
    fixture_path = SCHEDULE_ROOT / "tests" / "fixtures" / "input_bundle.golden.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["project"]["start_date"] = "2026-01-01"
    payload["dependencies"] = [dependency for dependency in payload["dependencies"] if dependency["dep_type"] == "FS"]
    bundle = InputBundle.model_validate(payload)

    plan = generate_plan(bundle)
    full_bundle = InputBundle.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))
    full_result = generate_plan(full_bundle, include_risks=True)

    assert isinstance(full_result, ScheduleResult)
    assert full_result.plan.project_finish_date == plan.project_finish_date == date(2026, 4, 21)
    assert len(full_result.plan.activities) == len(plan.activities)
    assert {activity.instance_id for activity in full_result.plan.activities} == {
        activity.instance_id for activity in plan.activities
    }
    assert len(full_result.readiness_suggestions) == 3
    assert len(plan.activities) > len(bundle.activities)
    assert len({activity.instance_id for activity in plan.activities}) == len(plan.activities)
    assert plan.project_finish_date is not None
