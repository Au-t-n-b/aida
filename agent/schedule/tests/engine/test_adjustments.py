from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

SCHEDULE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SCHEDULE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

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
from agent.schedule.contracts.outputs import PlanKpis, PlanResult, StrategyPlan  # noqa: E402
from agent.schedule.engine import ScheduleResult, build_adjustment_options, generate_plan, select_shadow_recommendation  # noqa: E402
from agent.schedule.engine.adjustments import _DemandTarget, _gap_summary, _target_end as _engine_target_end  # noqa: E402


def test_shadow_recommendation_prefers_achievable_option_before_other_scores():
    selected = select_shadow_recommendation(
        [
            _shadow_option("A", gap_days=1, risk_level="低"),
            _shadow_option("B", gap_days=0, risk_level="高"),
            _shadow_option("C", gap_days=2, risk_level="低"),
        ]
    )

    assert selected.option_id == "B"


def test_shadow_recommendation_ladder_orders_risk_added_crew_and_compression():
    risk_selected = select_shadow_recommendation(
        [
            _shadow_option("A", gap_days=0, risk_level="中", added_crew=0),
            _shadow_option("B", gap_days=0, risk_level="低", added_crew=8),
        ]
    )
    crew_selected = select_shadow_recommendation(
        [
            _shadow_option("A", gap_days=0, risk_level="低", added_crew=2, compressed_days=1),
            _shadow_option("B", gap_days=0, risk_level="低", added_crew=1, compressed_days=10),
        ]
    )
    compression_selected = select_shadow_recommendation(
        [
            _shadow_option("A", gap_days=0, risk_level="低", added_crew=0, compressed_days=3),
            _shadow_option("B", gap_days=0, risk_level="低", added_crew=0, compressed_days=1),
        ]
    )

    assert risk_selected.option_id == "B"
    assert crew_selected.option_id == "B"
    assert compression_selected.option_id == "B"


def test_shadow_recommendation_uses_smallest_gap_when_no_option_is_achievable():
    selected = select_shadow_recommendation(
        [
            _shadow_option("A", gap_days=3, risk_level="低"),
            _shadow_option("B", gap_days=1, risk_level="高"),
            _shadow_option("C", gap_days=2, risk_level="低"),
        ]
    )

    assert selected.option_id == "B"


def test_uniform_strategy_spreads_gap_across_critical_path():
    inputs = _project_bundle(
        activities=[
            _elastic_activity("critical_a", "关键施工 A", 4, minimum_days=2),
            _elastic_activity("critical_b", "关键施工 B", 4, minimum_days=2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="critical_a", to_activity_id="critical_b", dep_type="FS"),
            Dependency(from_activity_id="critical_b", to_activity_id="done", dep_type="FS"),
        ],
        arrivals=[_arrival("critical_a", 48), _arrival("critical_b", 48)],
    )
    seed = _seed(inputs)
    deadline = _activity_by_id(seed.plan)["project/done"].end_date - timedelta(days=2)

    adjustment = _adjust(inputs, _deadline_change("project/done", deadline), seed)

    assert adjustment.gap is not None
    assert adjustment.gap.baseline_finish_date == seed.plan.project_finish_date
    assert adjustment.gap.target_date == deadline
    assert adjustment.gap.gap_days == 2
    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["project/critical_a"].actual_sla_days == 3
    assert activities["project/critical_b"].actual_sla_days == 3
    assert activities["project/done"].end_date == deadline
    assert option.kpis.added_crew == 4
    assert option.kpis.gap_days == 0
    assert _option(adjustment.options, "C").kpis.gap_days == 2


def test_zero_gap_demand_returns_single_option_with_gap_summary():
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
    deadline = _target_end(seed.plan, "project/done")

    adjustment = _adjust(inputs, _deadline_change("project/done", deadline), seed)

    assert adjustment.gap is not None
    assert adjustment.gap.baseline_finish_date == seed.plan.project_finish_date
    assert adjustment.gap.target_date == deadline
    assert adjustment.gap.gap_days == 0
    assert [option.option_id for option in adjustment.options] == ["A"]
    assert adjustment.options[0].kpis.gap_days == 0


def test_gap_summary_without_demand_keeps_baseline_only():
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

    adjustment = _adjust(inputs, ChangeSet(), seed)

    assert adjustment.gap is not None
    assert adjustment.gap.baseline_finish_date == seed.plan.project_finish_date
    assert adjustment.gap.target_date is None
    assert adjustment.gap.gap_days == 0
    assert [option.option_id for option in adjustment.options] == ["A"]
    assert adjustment.options[0].kpis.gap_days == 0


def test_gap_summary_recomputes_gap_days_from_baseline_minus_target():
    # 回归 T-045 验收实测 bug：拖动目标后 demand.gap_days 与 desired_end desync，
    # _gap_summary 必须按 (基线预计完成 − 目标).days 重算自洽（与各卡 kpis.gap_days 同口径），
    # 而非透传可能陈旧的 demand.gap_days（live 真链路曾发 13，按 base−target 应为 102）。
    base_plan = PlanResult(
        plan_id="p1",
        version=1,
        activities=[],
        project_finish_date=date(2026, 4, 21),
    )
    demand = _DemandTarget(
        target=TargetRef(kind="项目移交", ref_id=None),
        target_desc="整体移交",
        desired_end=date(2026, 1, 9),
        gap_days=13,  # 故意陈旧/不一致
    )

    gap = _gap_summary(base_plan, demand)

    assert gap.baseline_finish_date == date(2026, 4, 21)
    assert gap.target_date == date(2026, 1, 9)
    assert gap.gap_days == 102  # = (2026-04-21 − 2026-01-09).days，自洽；不再是陈旧的 13


def test_concentrated_strategy_uses_configured_top_k():
    inputs = _project_bundle(
        activities=[
            _elastic_activity("critical_a", "关键施工 A", 6, minimum_days=2),
            _elastic_activity("critical_b", "关键施工 B", 4, minimum_days=2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="critical_a", to_activity_id="critical_b", dep_type="FS"),
            Dependency(from_activity_id="critical_b", to_activity_id="done", dep_type="FS"),
        ],
        arrivals=[_arrival("critical_a", 72), _arrival("critical_b", 48)],
        rule_config=RuleConfig(concentrate_top_k=1),
    )
    seed = _seed(inputs)
    deadline = _activity_by_id(seed.plan)["project/done"].end_date - timedelta(days=2)

    adjustment = _adjust(inputs, _deadline_change("project/done", deadline), seed)

    option = _option(adjustment.options, "B")
    activities = _activity_by_id(option.plan)
    assert activities["project/critical_a"].actual_sla_days == 4
    assert activities["project/critical_b"].actual_sla_days == 4
    assert activities["project/done"].end_date == deadline


def test_pull_inputs_returns_unlocked_room_and_arrival_but_skips_locked_predecessors(monkeypatch):
    monkeypatch.setenv("SCHEDULE_AS_OF_DATE", "2025-10-01")
    future_start = date(2026, 1, 1)
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

    monkeypatch.setenv("SCHEDULE_AS_OF_DATE", "2026-06-16")
    past_start = date(2026, 1, 1)
    locked = _room_arrival_bundle(
        start=past_start,
        room_ready=past_start,
        arrival_date=past_start + timedelta(days=1),
        arrival_status="在途",
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


def test_pull_inputs_replans_real_bundle_to_meet_tightened_batch_target(monkeypatch):
    monkeypatch.setenv("SCHEDULE_AS_OF_DATE", "2025-10-01")
    inputs = _load_golden_bundle()
    seed = generate_plan(inputs, include_risks=True)
    assert isinstance(seed, ScheduleResult)
    batch = inputs.batches[0]
    target = TargetRef(kind="批次上线", ref_id=batch.batch_id)
    baseline_end = _engine_target_end(seed.plan, target)
    deadline = baseline_end - timedelta(days=14)

    adjustment = build_adjustment_options(
        inputs,
        _deadline_change_for_target(target, deadline),
        seed.plan,
        list(seed.risks),
    )

    option = _option(adjustment.options, "C")
    assert {item.target_desc.split("(", maxsplit=1)[0] for item in option.pulled_inputs} == {"到货", "机房就位"}
    assert _engine_target_end(option.plan, target) <= deadline
    assert option.kpis.gap_days <= 0
    assert inputs.batches[0].online_target_date == baseline_end


def test_pull_inputs_clamps_real_bundle_suggestions_to_day_after_as_of(monkeypatch):
    as_of = date(2025, 10, 1)
    monkeypatch.setenv("SCHEDULE_AS_OF_DATE", as_of.isoformat())
    inputs = _load_golden_bundle()
    seed = generate_plan(inputs, include_risks=True)
    assert isinstance(seed, ScheduleResult)
    batch = inputs.batches[0]
    target = TargetRef(kind="批次上线", ref_id=batch.batch_id)
    baseline_end = _engine_target_end(seed.plan, target)
    deadline = baseline_end - timedelta(days=120)

    adjustment = build_adjustment_options(
        inputs,
        _deadline_change_for_target(target, deadline),
        seed.plan,
        list(seed.risks),
    )

    option = _option(adjustment.options, "C")
    assert option.pulled_inputs
    assert {item.suggested_date for item in option.pulled_inputs} == {as_of + timedelta(days=1)}
    assert option.kpis.gap_days <= 0


def test_pull_inputs_keeps_c_with_unmet_when_real_bundle_station_goods_locked(monkeypatch):
    monkeypatch.setenv("SCHEDULE_AS_OF_DATE", "2026-06-16")
    inputs = _load_golden_bundle()
    seed = generate_plan(inputs, include_risks=True)
    assert isinstance(seed, ScheduleResult)
    batch = inputs.batches[0]
    target = TargetRef(kind="批次上线", ref_id=batch.batch_id)
    baseline_end = _engine_target_end(seed.plan, target)
    deadline = baseline_end - timedelta(days=14)

    adjustment = build_adjustment_options(
        inputs,
        _deadline_change_for_target(target, deadline),
        seed.plan,
        list(seed.risks),
    )

    option = _option(adjustment.options, "C")
    assert option.pulled_inputs == []
    assert option.kpis.gap_days == 14
    assert any(
        item.target_desc == f"批次上线({batch.batch_id})" and "已锁定" in item.reason and item.gap_days == 14
        for item in adjustment.unmet
    )


def test_compression_only_touches_critical_path_and_stops_at_minimum_with_risk():
    inputs = _project_bundle(
        activities=[
            _elastic_activity("critical", "关键施工", 5, minimum_days=2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
            _activity("side", "非关键施工", 3),
        ],
        dependencies=[
            Dependency(from_activity_id="critical", to_activity_id="done", dep_type="FS"),
        ],
        arrivals=[_arrival("critical", 60)],
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


def test_rigid_activity_is_not_added_crew_candidate():
    inputs = _project_bundle(
        activities=[
            _activity("critical", "刚性施工", 5, minimum_days=2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="critical", to_activity_id="done", dep_type="FS"),
        ],
    )
    seed = _seed(inputs)

    adjustment = _adjust(inputs, _deadline_change("project/done", date(2026, 1, 1)), seed)

    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["project/critical"].actual_sla_days == 5
    assert option.kpis.added_crew == 0
    assert adjustment.unmet[0].gap_days == 5


def test_compression_minimum_sla_uses_experience_efficiency():
    inputs = _project_bundle(
        activities=[
            _elastic_activity("critical", "关键施工", 5, minimum_days=2),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="critical", to_activity_id="done", dep_type="FS"),
        ],
        arrivals=[_arrival("critical", 60)],
        teams=[Team(team_id="T1", experience="一般")],
    )
    seed = _seed(inputs)

    adjustment = _adjust(inputs, _deadline_change("project/done", date(2026, 1, 1)), seed)

    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["project/critical"].actual_sla_days == 3
    assert activities["project/critical"].end_date == date(2026, 1, 3)
    assert adjustment.unmet[0].gap_days == 3


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
    assert activities["project/elastic"].actual_sla_days == 7
    assert option.kpis.added_crew == 6
    assert option.kpis.added_crew <= 6
    assert adjustment.unmet[0].gap_days == 7


def test_arrival_bound_compression_rolls_back_ineffective_added_crew_and_points_to_c():
    arrival_date = date.today() + timedelta(days=60)
    target_date = arrival_date + timedelta(days=5)
    arrival = _arrival("install", 60).model_copy(update={"arrival_date": arrival_date})
    inputs = _project_bundle(
        activities=[
            _activity("arrival", "设备到货", 1, scope="PoD级", activity_type="到货", constraint_source=None),
            _elastic_activity("install", "弹性安装", 5, minimum_days=1),
            _activity("online", "批次上线", 1, scope="批次级", activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="arrival", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="install", to_activity_id="online", dep_type="FS"),
        ],
        arrivals=[arrival],
    ).model_copy(
        update={
            "batches": [
                Batch(
                    batch_id="B1",
                    batch_name="批次1",
                    pod_ids=["P1"],
                    online_target_date=target_date,
                )
            ]
        }
    )
    seed = _seed(inputs)

    adjustment = _adjust(
        inputs,
        _deadline_change_for_target(TargetRef(kind="批次上线", ref_id="B1"), target_date - timedelta(days=10)),
        seed,
    )

    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["project/install"].actual_sla_days == 5
    assert activities["B1/online"].end_date == target_date
    assert option.kpis.added_crew == 0
    assert any(
        risk.risk_type == "链路聚合" and "到货约束" in risk.message and "C 站货提拉" in risk.message
        for risk in option.risks
    )
    assert "到货约束" in option.advice
    assert any("加人无效" in item.reason for item in adjustment.unmet)


def test_room_ready_bound_compression_rolls_back_and_points_to_ready_adjustment():
    ready_date = date.today() + timedelta(days=60)
    target_date = ready_date + timedelta(days=5)
    install = _elastic_activity("install", "弹性安装", 5, minimum_days=1).model_copy(
        update={"scope": "机房级"}
    )
    inputs = _project_bundle(
        activities=[
            _activity("ready", "机房就位", 1, scope="机房级", activity_type="机房准备", constraint_source=None),
            install,
            _activity("online", "批次上线", 1, scope="批次级", activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="ready", to_activity_id="install", dep_type="FS"),
            Dependency(from_activity_id="install", to_activity_id="online", dep_type="FS"),
        ],
        arrivals=[_arrival("install", 60)],
    ).model_copy(
        update={
            "rooms": [Room(room_id="R1", install_ready_date=ready_date)],
            "batches": [
                Batch(
                    batch_id="B1",
                    batch_name="批次1",
                    pod_ids=["P1"],
                    online_target_date=target_date,
                )
            ],
        }
    )
    seed = _seed(inputs)

    adjustment = _adjust(
        inputs,
        _deadline_change_for_target(TargetRef(kind="批次上线", ref_id="B1"), target_date - timedelta(days=10)),
        seed,
    )

    option = _option(adjustment.options, "A")
    activities = _activity_by_id(option.plan)
    assert activities["R1/install"].actual_sla_days == 5
    assert activities["B1/online"].end_date == target_date
    assert option.kpis.added_crew == 0
    assert any(
        risk.risk_type == "链路聚合" and "机房就位约束" in risk.message and "调整机房就位日期" in risk.message
        for risk in option.risks
    )
    assert "机房就位约束" in option.advice
    assert any("加人无效" in item.reason for item in adjustment.unmet)


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

    assert adjustment.gap is not None
    assert adjustment.gap.baseline_finish_date == seed.plan.project_finish_date
    assert adjustment.gap.target_date == desired_end
    assert adjustment.gap.gap_days == -3
    option = _option(adjustment.options, "BUFFER")
    assert _target_end(option.plan, "project/done") == desired_end
    assert _target_end(option.plan, "project/done") <= desired_end
    assert option.kpis.gap_days == 0
    assert adjustment.unmet == []


def test_buffer_extension_can_weave_slack_into_elastic_activity():
    inputs = _project_bundle(
        activities=[
            _elastic_activity("install", "弹性安装", 2, minimum_days=1),
            _activity("done", "移交", 1, activity_type="里程碑", constraint_source=None),
        ],
        dependencies=[
            Dependency(from_activity_id="install", to_activity_id="done", dep_type="FS"),
        ],
        arrivals=[_arrival("install", 24)],
    )
    seed = _seed(inputs)
    desired_end = _target_end(seed.plan, "project/done") + timedelta(days=3)
    changes = ChangeSet(
        demands=[
            DemandRequest(
                demand_id="D-buffer-elastic",
                target=TargetRef(kind="活动实例", ref_id="project/done"),
                direction="延后",
                amount_days=3,
            )
        ]
    )

    adjustment = _adjust(inputs, changes, seed)

    option = _option(adjustment.options, "BUFFER")
    activities = _activity_by_id(option.plan)
    assert _target_end(option.plan, "project/done") == desired_end
    assert activities["project/install"].actual_sla_days == 5
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


def _load_golden_bundle() -> InputBundle:
    """真盘子（golden 70 活动·真实活动目录）——回归 T-064，避开 2 活动玩具盘子的覆盖盲区。"""
    golden = SCHEDULE_ROOT / "tests" / "fixtures" / "input_bundle.golden.json"
    return InputBundle.model_validate_json(golden.read_text(encoding="utf-8"))


def test_postpone_batch_target_is_met_not_runaway_buffer_on_real_bundle():
    # 回归 T-064（demo-breaker「超 511 天」）：真盘子（golden 70 活动）下把某批次上线目标往后挪。
    # 旧逻辑：gap<0 一律进 buffer 延长 → 延长「不在该批前置链上」的活动推不动目标 → 撞 guard=500、
    #         把某活动拉长约 500 天（实测「集群验收方案设计」25→525）、项目完成日崩到次年。
    # 新逻辑：把目标往后拖 = 放宽要求 = 达标，给单张稳定方案、不动活动、不失控。
    inputs = _load_golden_bundle()
    seed = generate_plan(inputs, include_risks=True)
    assert isinstance(seed, ScheduleResult)
    batch = inputs.batches[1]
    online_end = _engine_target_end(seed.plan, TargetRef(kind="批次上线", ref_id=batch.batch_id))
    later_deadline = online_end + timedelta(days=15)
    changes = ChangeSet(
        demands=[
            DemandRequest(
                demand_id="D-postpone",
                target=TargetRef(kind="批次上线", ref_id=batch.batch_id),
                direction="某日期前完成",
                deadline=later_deadline,
            )
        ]
    )

    adjustment = build_adjustment_options(inputs, changes, seed.plan, list(seed.risks))

    # 达标：单张方案、绝不是 buffer 延长
    assert [option.option_id for option in adjustment.options] == ["A"]
    assert adjustment.options[0].strategy != "buffer延长"
    # 不失控：项目完成日原样不动；没有任何活动被拉长（旧 bug 会把某活动 +500 天）
    assert adjustment.options[0].plan.project_finish_date == seed.plan.project_finish_date
    base_sla = {activity.instance_id: activity.actual_sla_days for activity in seed.plan.activities}
    assert all(
        activity.actual_sla_days <= base_sla.get(activity.instance_id, activity.actual_sla_days)
        for activity in adjustment.options[0].plan.activities
    )
    # 缺口口径自洽：该批次上线已满足 → 卡 gap_days ≤ 0、banner 同号 ≤ 0
    # （不再「banner 说超期·需压缩」却配「buffer/达标」方案自相矛盾）
    assert adjustment.options[0].kpis.gap_days <= 0
    assert adjustment.gap is not None and adjustment.gap.gap_days <= 0
    assert adjustment.unmet == []


def test_explicit_postpone_still_buffers_but_stays_bounded_on_real_bundle():
    # 显式「延后 N 天」仍走 buffer 延长（用户明确要留缓冲）；非进展护栏保证真盘子下也不失控。
    inputs = _load_golden_bundle()
    seed = generate_plan(inputs, include_risks=True)
    assert isinstance(seed, ScheduleResult)
    changes = ChangeSet(
        demands=[
            DemandRequest(
                demand_id="D-buffer",
                target=TargetRef(kind="项目移交", ref_id=None),
                direction="延后",
                amount_days=10,
            )
        ]
    )

    adjustment = build_adjustment_options(inputs, changes, seed.plan, list(seed.risks))

    option = adjustment.options[0]
    assert option.option_id == "BUFFER"
    # 不失控：完成日最多往后约 amount_days，绝不暴涨数百天（旧 bug 会 +500）
    grew = (option.plan.project_finish_date - seed.plan.project_finish_date).days
    assert 0 <= grew <= 15


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


def _shadow_option(
    option_id: str,
    *,
    gap_days: int,
    risk_level: str,
    added_crew: int = 0,
    compressed_days: int = 0,
) -> StrategyPlan:
    return StrategyPlan(
        option_id=option_id,
        strategy="均匀压缩",
        kpis=PlanKpis(
            pod_count=1,
            total_duration_days=1,
            compressed_days=compressed_days,
            added_crew=added_crew,
            gap_days=gap_days,
        ),
        plan=PlanResult(plan_id=f"shadow-{option_id}", version=1, activities=[]),
        risk_level=risk_level,
        advice=f"方案 {option_id}",
    )


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


def _elastic_activity(
    activity_id: str,
    name: str,
    standard_days: int,
    *,
    minimum_days: int,
    assumed_crew: int = 6,
) -> Activity:
    standard_daily_rate = 12
    quantity = standard_days * standard_daily_rate
    return _activity(
        activity_id,
        name,
        None,
        minimum_days=None,
        duration_mode="弹性",
        workload_rules=[
            WorkloadRule(
                workload_source=activity_id,
                unit="柜",
                standard_daily_rate=standard_daily_rate,
                limit_daily_rate=quantity / minimum_days,
                assumed_crew=assumed_crew,
            )
        ],
    )


def _arrival(workload_source: str, quantity: float) -> ArrivalItem:
    return ArrivalItem(
        arrival_id=f"A-{workload_source}",
        pod_id="P1",
        device_type=workload_source,
        quantity=quantity,
        arrival_status="在途",
    )


def _project_bundle(
    *,
    activities: list[Activity],
    dependencies: list[Dependency],
    arrivals: list[ArrivalItem] | None = None,
    rule_config: RuleConfig | None = None,
    teams: list[Team] | None = None,
) -> InputBundle:
    return InputBundle(
        project=Project(project_id="adjust-demo", project_name="adjust demo", start_date=date(2026, 1, 1)),
        rooms=[Room(room_id="R1")],
        pods=[Pod(pod_id="P1", room_id="R1")],
        arrivals=arrivals or [],
        teams=teams or [Team(team_id="T1", size=12, experience="丰富")],
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
