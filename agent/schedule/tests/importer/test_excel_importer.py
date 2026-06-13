from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

SCHEDULE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SCHEDULE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agent.schedule.contracts.inputs import Pod  # noqa: E402

from agent.schedule.importer.excel import (  # noqa: E402
    DataImportError,
    _load_batches,
    _load_project,
    _load_teams,
    _pick_scale_days,
    _resolve_activity_reference,
    load_input_bundle,
    main,
)


SCALE_STANDARD_TEXT = "千卡以下，5天\n千卡至万卡，11天\n万卡以上，18天"
SCALE_LIMIT_TEXT = "千卡以下，5天\n千卡至万卡，9天\n万卡以上，15天"


def _write_workbook(
    path: Path,
    headers: list[str],
    rows: list[list[object | None]],
    sheet_name: str = "Sheet1",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def _write_activity_dependency_metadata(
    data_root: Path,
    *,
    project_id: str = "P-001",
    project_name: object | None = "Project Alpha",
    project_scale: object | None = "标准项目",
    total_card_count: object | None = 3456,
    include_project_name: bool = True,
) -> None:
    headers = ["PROJECT_ID", "PROJECT_SCENE", "PRODUCT_FORM", "COOLING_METHOD", "PROJECT_SCALE"]
    row: list[object | None] = [project_id, "集群集成", "A3", "liquid_cooling", project_scale]
    if include_project_name:
        headers.append("PROJECT_NAME")
        row.append(project_name)
    headers.append("TOTAL_CARD_COUNT")
    row.append(total_card_count)
    _write_workbook(
        data_root / "02_活动依赖" / "A3-液冷-活动依赖.xlsx",
        headers,
        [row],
        sheet_name="sheet0",
    )


@pytest.fixture(scope="module")
def bundle():
    return load_input_bundle(SCHEDULE_ROOT)


def test_real_excel_files_build_valid_input_bundle(bundle):
    assert bundle.project.project_id == "6336ff05cffc4144aa6d96a87e66a36e"
    assert bundle.project.project_name == "A3液冷集群集成"
    assert bundle.project.scene == "集群集成"
    assert bundle.project.product_form == "A3"
    assert bundle.project.cooling_method == "liquid_cooling"
    assert bundle.project.project_scale == "标准项目"
    assert bundle.project.total_card_count == 3456

    assert len(bundle.rooms) == 3
    assert len(bundle.pods) == 9
    assert len(bundle.arrivals) == 36
    assert len(bundle.teams) == 2
    assert len(bundle.activities) == 70
    assert bundle.dependencies
    assert len(bundle.batches) == 3

    imported_pod_ids = {pod_id for batch in bundle.batches for pod_id in batch.pod_ids}
    assert imported_pod_ids == {pod.pod_id for pod in bundle.pods}


def test_project_metadata_reads_name_and_card_count_from_table(tmp_path):
    _write_activity_dependency_metadata(tmp_path, project_name="项目甲", total_card_count=2345)

    project = _load_project(tmp_path, total_card_count=None)

    assert project.project_id == "P-001"
    assert project.project_name == "项目甲"
    assert project.total_card_count == 2345


def test_project_metadata_explicit_card_count_overrides_table(tmp_path):
    _write_activity_dependency_metadata(tmp_path, total_card_count=2345)

    project = _load_project(tmp_path, total_card_count=10001)

    assert project.total_card_count == 10001


def test_project_metadata_blank_card_count_falls_back_to_project_scale(tmp_path):
    _write_activity_dependency_metadata(tmp_path, project_scale="标准项目", total_card_count=None)

    project = _load_project(tmp_path, total_card_count=None)

    assert project.total_card_count is None
    assert _pick_scale_days(SCALE_STANDARD_TEXT, project.project_scale, project.total_card_count, 123, "标准工时") == 11


def test_project_metadata_blank_card_count_and_scale_defaults_middle_bucket(tmp_path):
    _write_activity_dependency_metadata(tmp_path, project_scale=None, total_card_count=None)

    project = _load_project(tmp_path, total_card_count=None)

    assert project.project_scale is None
    assert project.total_card_count is None
    assert _pick_scale_days(SCALE_STANDARD_TEXT, project.project_scale, project.total_card_count, 123, "标准工时") == 11


@pytest.mark.parametrize("invalid_card_count", [0, "not-a-number"])
def test_project_metadata_invalid_card_count_is_loud_import_error(tmp_path, invalid_card_count):
    _write_activity_dependency_metadata(tmp_path, total_card_count=invalid_card_count)

    with pytest.raises(DataImportError, match="IMPORT_ERROR.*活动依赖表第2行.*TOTAL_CARD_COUNT"):
        _load_project(tmp_path, total_card_count=None)


def test_project_metadata_missing_project_name_falls_back_to_project_id(tmp_path):
    _write_activity_dependency_metadata(tmp_path, project_id="P-FALLBACK", include_project_name=False)

    project = _load_project(tmp_path, total_card_count=None)

    assert project.project_name == "P-FALLBACK"


def test_project_metadata_blank_project_name_falls_back_to_project_id(tmp_path):
    _write_activity_dependency_metadata(tmp_path, project_id="P-BLANK", project_name=None)

    project = _load_project(tmp_path, total_card_count=None)

    assert project.project_name == "P-BLANK"


def test_real_batches_are_loaded_with_targets(bundle):
    batches = {batch.batch_name: batch for batch in bundle.batches}

    assert batches["批次1"].batch_id == "批次1"
    assert batches["批次1"].power_on_target_date == date(2026, 1, 21)
    assert batches["批次1"].online_target_date == date(2026, 2, 4)
    assert batches["批次1"].pod_ids == [
        "B2DH401-POD01",
        "B2DH401-POD02",
        "B2DH401-POD03",
        "B2DH401-POD04",
    ]

    # 2026-06-13 指挥人修正 09 表：批次2 上电01-25/上线02-04；批次3 上电03-17/上线04-04
    # （前一版同步 761692c 曾把三批统一 02-04，与业务 §4「批次3 04-04 移交」矛盾，此次回正）
    assert batches["批次2"].power_on_target_date == date(2026, 1, 25)
    assert batches["批次2"].online_target_date == date(2026, 2, 4)
    assert batches["批次2"].pod_ids == ["B2DH403-POD09"]

    assert batches["批次3"].power_on_target_date == date(2026, 3, 17)
    assert batches["批次3"].online_target_date == date(2026, 4, 4)
    assert batches["批次3"].pod_ids == [
        "B2DH402-POD05",
        "B2DH402-POD06",
        "B2DH402-POD07",
        "B2DH402-POD08",
    ]


def test_real_teams_are_loaded_with_defaults_and_aliases(bundle):
    # 2026-06-12 指挥人更正：JD3 期 2 支队伍、每队 18 人
    assert [team.team_id for team in bundle.teams] == ["1", "2"]
    for team in bundle.teams:
        assert team.size == 18
        assert team.experience == "丰富"
        assert team.on_site is True


def test_blank_team_size_falls_back_to_contract_default(tmp_path):
    path = tmp_path / "08_施工队伍信息" / "施工队伍信息.xlsx"
    _write_workbook(path, ["队伍编号", "人数", "经验等级", "在场状态"], [["9", None, "经验充分", None]])

    teams = _load_teams(tmp_path)

    assert len(teams) == 1
    assert teams[0].size == 12
    assert teams[0].experience == "丰富"
    assert teams[0].on_site is True


def test_missing_batch_file_falls_back_to_default(tmp_path):
    pods = [Pod(pod_id="P-01", room_id="R1"), Pod(pod_id="P-02", room_id="R1")]

    batches = _load_batches(tmp_path, pods)

    assert len(batches) == 1
    assert batches[0].batch_id == "batch-all"
    assert batches[0].pod_ids == ["P-01", "P-02"]


def test_empty_batch_file_falls_back_to_default(tmp_path):
    path = tmp_path / "09_批次信息" / "批次信息.xlsx"
    _write_workbook(path, ["批次名", "上电目标日期", "上线目标日期", "该批包含的PoD"], [])
    pods = [Pod(pod_id="P-01", room_id="R1")]

    batches = _load_batches(tmp_path, pods)

    assert len(batches) == 1
    assert batches[0].pod_ids == ["P-01"]


def test_unknown_batch_pod_is_loud_import_error(tmp_path):
    path = tmp_path / "09_批次信息" / "批次信息.xlsx"
    _write_workbook(
        path,
        ["批次名", "上电目标日期", "上线目标日期", "该批包含的PoD"],
        [["批次A", "2026-01-01", "2026-01-02", "P-MISSING"]],
    )
    pods = [Pod(pod_id="P-01", room_id="R1")]

    with pytest.raises(DataImportError, match="IMPORT_ERROR.*第2行.*P-MISSING.*05_机房机柜信息"):
        _load_batches(tmp_path, pods)


def test_missing_team_file_falls_back_to_no_explicit_teams(tmp_path):
    assert _load_teams(tmp_path) == []


def test_workload_four_forms_are_parsed(bundle):
    activities = {activity.activity_id: activity for activity in bundle.activities}

    lingqu = activities["7.3"].workload_rules[0]
    assert lingqu.workload_source == "灵衢线缆"
    assert lingqu.unit == "根"
    assert lingqu.standard_daily_rate == 224
    assert lingqu.limit_daily_rate == 384

    compute = activities["7.19"].workload_rules[0]
    assert compute.workload_source == "计算柜"
    assert compute.unit == "柜"
    assert compute.standard_daily_rate == 48
    assert compute.limit_daily_rate == 48

    network_rules = {rule.workload_source: rule for rule in activities["7.13"].workload_rules}
    assert set(network_rules) == {"盒式", "框式"}
    assert network_rules["盒式"].standard_daily_rate == 40
    assert network_rules["盒式"].limit_daily_rate == 80
    assert network_rules["框式"].standard_daily_rate == 16
    assert network_rules["框式"].limit_daily_rate == 24

    scale_activity = activities["4.2"]
    assert scale_activity.duration_mode == "规模分档"
    assert scale_activity.standard_sla_days == 11
    assert scale_activity.minimum_sla_days == 9


@pytest.mark.parametrize(
    ("card_count", "standard_days", "minimum_days"),
    [
        (999, 5, 5),
        (1000, 11, 9),
        (10000, 11, 9),
        (10001, 18, 15),
    ],
)
def test_total_card_count_drives_scale_bucket(card_count, standard_days, minimum_days):
    bundle = load_input_bundle(SCHEDULE_ROOT, total_card_count=card_count)
    activities = {activity.activity_id: activity for activity in bundle.activities}
    scale_activity = activities["4.2"]

    assert bundle.project.total_card_count == card_count
    assert scale_activity.duration_mode == "规模分档"
    assert scale_activity.standard_sla_days == standard_days
    assert scale_activity.minimum_sla_days == minimum_days


def test_scale_bucket_falls_back_to_project_scale_without_card_count():
    assert _pick_scale_days(SCALE_STANDARD_TEXT, "标准项目", None, 123, "标准工时") == 11
    assert _pick_scale_days(SCALE_LIMIT_TEXT, "标准项目", None, 123, "极限工时") == 9


def test_scale_bucket_defaults_to_middle_without_card_count_or_project_scale():
    assert _pick_scale_days(SCALE_STANDARD_TEXT, None, None, 123, "标准工时") == 11
    assert _pick_scale_days(SCALE_LIMIT_TEXT, None, None, 123, "极限工时") == 9


def test_cli_card_count_populates_project_and_scale_bucket(tmp_path, capsys):
    output_path = tmp_path / "input_bundle.json"

    assert main(["--project-root", str(SCHEDULE_ROOT), "--card-count", "10001", "--output", str(output_path)]) == 0
    assert capsys.readouterr().out == ""

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    activities = {activity["activity_id"]: activity for activity in payload["activities"]}

    assert payload["project"]["total_card_count"] == 10001
    assert activities["4.2"]["standard_sla_days"] == 18
    assert activities["4.2"]["minimum_sla_days"] == 15


def test_stage_rows_and_room_ready_subrows_are_not_activities(bundle):
    activities = {activity.activity_id: activity for activity in bundle.activities}
    activity_names = {activity.activity_name for activity in bundle.activities}

    assert not any(activity_id.startswith("阶段") for activity_id in activities)
    assert "机房改造实施(可布线)" not in activity_names
    assert "机房改造实施(可装服务器)" not in activity_names
    assert "机房改造实施(可通液)" not in activity_names

    room_ready = activities["2.3"]
    assert room_ready.activity_type == "机房准备"
    assert room_ready.standard_sla_days is None
    assert room_ready.minimum_sla_days is None

    dependency_keys = {
        (dependency.from_activity_id, dependency.to_activity_id, dependency.dep_type)
        for dependency in bundle.dependencies
    }
    assert ("2.3", "7.1", "FS") in dependency_keys
    assert ("2.3", "7.19", "FS") in dependency_keys


def test_plan_dependency_parse_error_includes_row_number():
    with pytest.raises(DataImportError, match="第123行.*不存在活动"):
        _resolve_activity_reference("不存在活动", {}, {"1.1"}, row_number=123, dep_type="FS")


def test_golden_fixture_matches_real_import(bundle):
    fixture_path = SCHEDULE_ROOT / "tests" / "fixtures" / "input_bundle.golden.json"
    golden = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert golden == bundle.model_dump(mode="json")
