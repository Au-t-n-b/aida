"""Read the real 06 Excel files into the contracts InputBundle."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook

from agent.schedule.contracts.inputs import (
    Activity,
    ArrivalItem,
    Batch,
    Dependency,
    InputBundle,
    Pod,
    Project,
    RiskRule,
    Room,
    Team,
    WorkloadRule,
)


PLAN_SHEET = "集群集成 + A3液冷场景活动&依赖&工时(1014）"
DEFAULT_SCALE_BUCKET = "千卡至万卡"


class DataImportError(ValueError):
    """Raised when a source workbook cannot be mapped into the frozen contract."""


@dataclass(frozen=True)
class ActivitySeed:
    activity_id: str
    activity_name: str
    sla: str | None


@dataclass(frozen=True)
class PlanActivity:
    row_number: int
    activity_id: str
    activity_name: str
    level1: str | None
    stage: str | None
    scope: str | None
    standard_work: str | None
    limit_work: str | None
    duration_mode: str | None
    work_note: str | None
    responsibility: str | None
    risk_values: dict[str, str | None]
    dependency_cells: dict[str, str | None]


@dataclass(frozen=True)
class WorkloadEntry:
    workload_source: str
    unit: str | None
    daily_rate: float


def load_input_bundle(project_root: str | Path | None = None, total_card_count: int | None = None) -> InputBundle:
    """Load all T-001 source workbooks under project-data into an InputBundle."""

    root = _find_project_root(project_root)
    data_root = root / "project-data"

    arrivals = _load_arrivals(data_root)
    project = _load_project(data_root, total_card_count)
    activity_seeds = _load_activity_definitions(data_root)
    plan_activities, extra_aliases = _load_plan_activities(data_root)
    name_to_id = _build_activity_reference_map(activity_seeds, plan_activities, extra_aliases)
    activities = _build_activities(activity_seeds, plan_activities, project.project_scale, project.total_card_count)
    dependencies = _load_dependencies(data_root, plan_activities, name_to_id, {a.activity_id for a in activities})
    rooms, pods = _load_rooms_and_pods(data_root, arrivals)
    batches = _load_batches(data_root, pods)
    teams = _load_teams(data_root)

    return InputBundle(
        project=project,
        rooms=rooms,
        pods=pods,
        arrivals=arrivals,
        teams=teams,
        activities=activities,
        dependencies=dependencies,
        batches=batches,
    )


def write_input_bundle_json(
    output_path: str | Path,
    project_root: str | Path | None = None,
    total_card_count: int | None = None,
) -> None:
    """Write a deterministic golden JSON fixture for the real data bundle."""

    bundle = load_input_bundle(project_root, total_card_count)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _find_project_root(project_root: str | Path | None) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()

    schedule_root = Path(__file__).resolve().parents[1]
    candidates = [schedule_root, Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        if (candidate / "project-data").exists() and (candidate / "contracts").exists():
            return candidate
    raise DataImportError("无法定位排期项目根目录：未找到 project-data 与 contracts")


def _load_project(data_root: Path, total_card_count: int | None) -> Project:
    rows = _read_table_with_row_numbers(data_root / "02_活动依赖" / "A3-液冷-活动依赖.xlsx", "sheet0")
    if not rows:
        raise DataImportError("活动依赖表没有数据行，无法推导项目元信息")
    excel_row, first = rows[0]
    project_id = _required(first, "PROJECT_ID", "活动依赖表")
    table_card_count = _parse_optional_positive_int(
        first.get("TOTAL_CARD_COUNT"),
        f"活动依赖表第{excel_row}行《TOTAL_CARD_COUNT》",
    )
    if total_card_count is not None and total_card_count <= 0:
        raise DataImportError(f"IMPORT_ERROR: total_card_count 必须为正整数：{total_card_count!r}")

    return Project(
        project_id=project_id,
        project_name=_blank_to_none(first.get("PROJECT_NAME")) or project_id,
        scene=_blank_to_none(first.get("PROJECT_SCENE")),
        product_form=_blank_to_none(first.get("PRODUCT_FORM")),
        cooling_method=_blank_to_none(first.get("COOLING_METHOD")),
        project_scale=_blank_to_none(first.get("PROJECT_SCALE")),
        total_card_count=total_card_count if total_card_count is not None else table_card_count,
    )


def _load_activity_definitions(data_root: Path) -> list[ActivitySeed]:
    rows = _read_table(data_root / "01_活动定义" / "A3-液冷-活动定义.xlsx", "sheet0")
    seeds: list[ActivitySeed] = []
    for row in rows:
        activity_id = _clean_id(row.get("ACTIVITY_ID"))
        activity_name = _clean_text(row.get("ACTIVITY_NAME"))
        if not activity_id or not activity_name or activity_id.endswith(".0"):
            continue
        seeds.append(ActivitySeed(activity_id, activity_name, _blank_to_none(row.get("SLA"))))
    return seeds


def _load_plan_activities(data_root: Path) -> tuple[dict[str, PlanActivity], dict[str, str]]:
    path = data_root / "04_计划基线" / "计划基线0609.xlsx"
    plan_activities: dict[str, PlanActivity] = {}
    extra_aliases: dict[str, str] = {}

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook[PLAN_SHEET]
        for row_number, row in enumerate(sheet.iter_rows(min_row=4, max_row=sheet.max_row, values_only=True), start=4):
            values = list(row[:21])
            seq = _clean_id(values[0])
            activity_name = _clean_text(values[2])

            if not seq:
                if activity_name.startswith("机房改造实施("):
                    extra_aliases[activity_name] = "2.3"
                continue
            if seq.startswith("阶段") or not re.fullmatch(r"\d+(?:\.\d+)+", seq):
                continue

            plan_activities[seq] = PlanActivity(
                row_number=row_number,
                activity_id=seq,
                activity_name=activity_name,
                level1=_blank_to_none(values[1]),
                stage=_blank_to_none(values[7]),
                scope=_blank_to_none(values[9]),
                standard_work=_blank_to_none(values[10]),
                limit_work=_blank_to_none(values[11]),
                duration_mode=_clean_text(values[12]) or None,
                work_note=_blank_to_none(values[13]),
                responsibility=_blank_to_none(values[14]),
                risk_values={
                    "trigger_logic": _blank_to_none(values[15]),
                    "risk_name": _blank_to_none(values[16]),
                    "description": _blank_to_none(values[17]),
                    "impact": _blank_to_none(values[18]),
                    "mitigation": _blank_to_none(values[19]),
                    "mitigation_owner": _blank_to_none(values[20]),
                },
                dependency_cells={
                    "SS": _blank_to_none(values[3]),
                    "SF": _blank_to_none(values[4]),
                    "FS": _blank_to_none(values[5]),
                    "FF": _blank_to_none(values[6]),
                },
            )
    finally:
        workbook.close()
    return plan_activities, extra_aliases


def _build_activities(
    activity_seeds: list[ActivitySeed],
    plan_activities: dict[str, PlanActivity],
    project_scale: str | None,
    total_card_count: int | None,
) -> list[Activity]:
    activities: list[Activity] = []
    seen: set[str] = set()

    for seed in activity_seeds:
        detail = plan_activities.get(seed.activity_id)
        activities.append(_build_activity(seed, detail, project_scale, total_card_count))
        seen.add(seed.activity_id)

    for activity_id, detail in plan_activities.items():
        if activity_id in seen:
            continue
        seed = ActivitySeed(activity_id, detail.activity_name, None)
        activities.append(_build_activity(seed, detail, project_scale, total_card_count))

    return activities


def _build_activity(
    seed: ActivitySeed,
    detail: PlanActivity | None,
    project_scale: str | None,
    total_card_count: int | None,
) -> Activity:
    activity_name = detail.activity_name if detail else seed.activity_name
    raw_mode = detail.duration_mode if detail else None
    row_number = detail.row_number if detail else None
    activity_type = _infer_activity_type(activity_name)

    if raw_mode == "弹性":
        workload_rules = _parse_workload_rules(
            activity_name=activity_name,
            standard_text=detail.standard_work if detail else None,
            limit_text=detail.limit_work if detail else None,
            note=detail.work_note if detail else None,
            row_number=row_number,
        )
        standard_days = None
        minimum_days = None
        duration_mode = "弹性"
    elif raw_mode == "规模分档":
        standard_days = _pick_scale_days(detail.standard_work, project_scale, total_card_count, row_number, "标准工时")
        minimum_days = _pick_scale_days(detail.limit_work, project_scale, total_card_count, row_number, "极限工时")
        workload_rules = []
        duration_mode = "规模分档"
    elif raw_mode == "—":
        standard_days = None
        minimum_days = None
        workload_rules = []
        duration_mode = "固定"
    else:
        standard_days = _parse_days(detail.standard_work if detail else seed.sla, row_number, "标准工时", required=False)
        minimum_days = _parse_days(detail.limit_work if detail else None, row_number, "极限工时", required=False)
        workload_rules = []
        duration_mode = "固定"

    risk_rule = _build_risk_rule(detail.risk_values) if detail and any(detail.risk_values.values()) else None

    return Activity(
        activity_id=seed.activity_id,
        activity_name=activity_name,
        phase=_infer_phase(detail),
        scope=_as_scope(detail.scope if detail else None, seed.activity_id),
        activity_type=activity_type,
        constraint_source=_infer_constraint_source(activity_name, activity_type, duration_mode),
        duration_mode=duration_mode,
        standard_sla_days=standard_days,
        minimum_sla_days=minimum_days,
        workload_rules=workload_rules,
        is_default_milestone=_is_default_milestone(activity_name),
        responsibility=detail.responsibility if detail else None,
        note=_build_note(detail),
        risk_rule=risk_rule,
    )


def _load_dependencies(
    data_root: Path,
    plan_activities: dict[str, PlanActivity],
    name_to_id: dict[str, str],
    activity_ids: set[str],
) -> list[Dependency]:
    dependencies: list[Dependency] = []
    seen: set[tuple[str, str, str]] = set()

    for row in _read_table(data_root / "02_活动依赖" / "A3-液冷-活动依赖.xlsx", "sheet0"):
        from_id = _clean_id(row.get("FROM_ACTIVITY_ID"))
        to_id = _clean_id(row.get("DEST_ACTIVITY_ID"))
        if from_id and to_id and from_id in activity_ids and to_id in activity_ids:
            _append_dependency(dependencies, seen, from_id, to_id, "FS")

    for detail in plan_activities.values():
        for dep_type, cell_text in detail.dependency_cells.items():
            for token in _split_dependency_cell(cell_text):
                from_id = _resolve_activity_reference(token, name_to_id, activity_ids, detail.row_number, dep_type)
                _append_dependency(dependencies, seen, from_id, detail.activity_id, dep_type)

    return dependencies


def _load_arrivals(data_root: Path) -> list[ArrivalItem]:
    rows = _read_table(data_root / "06_到货表" / "04 JD三期_A3液冷到货表_260309.xlsx", "JD三期")
    arrivals: list[ArrivalItem] = []
    today = date.today()
    for excel_row, row in enumerate(rows, start=2):
        arrival_date = _to_date(row.get("到货日期"), f"到货表第{excel_row}行《到货日期》")
        arrivals.append(
            ArrivalItem(
                arrival_id=_required(row, "ID", f"到货表第{excel_row}行"),
                pod_id=_required(row, "管理单元", f"到货表第{excel_row}行"),
                device_type=_required(row, "设备类型", f"到货表第{excel_row}行"),
                device_model=_blank_to_none(row.get("型号")),
                unit=_blank_to_none(row.get("单位")),
                quantity=_to_float(_required(row, "数量", f"到货表第{excel_row}行"), f"到货表第{excel_row}行《数量》"),
                arrival_date=arrival_date,
                arrival_status=_arrival_status(arrival_date, today),
                note=_blank_to_none(row.get("备注")),
            )
        )
    return arrivals


def _load_rooms_and_pods(data_root: Path, arrivals: list[ArrivalItem]) -> tuple[list[Room], list[Pod]]:
    arrival_counts: dict[str, dict[str, int]] = {}
    for arrival in arrivals:
        counts = arrival_counts.setdefault(arrival.pod_id, {"compute": 0, "other": 0})
        if arrival.unit == "柜":
            quantity = int(arrival.quantity)
            if arrival.device_type == "计算柜":
                counts["compute"] += quantity
            else:
                counts["other"] += quantity

    rows = _read_table(data_root / "05_机房机柜信息" / "机房机柜信息表.xlsx", "Sheet1")
    rooms_by_id: dict[str, Room] = {}
    pod_rows: dict[str, dict[str, Any]] = {}
    cabinet_counts: dict[str, dict[str, int]] = {}

    for excel_row, row in enumerate(rows, start=2):
        pod_id = _required(row, "PoD名称", f"机房机柜表第{excel_row}行")
        room_id = _required(row, "机房名称", f"机房机柜表第{excel_row}行")
        rooms_by_id.setdefault(room_id, Room(room_id=room_id))
        pod_rows.setdefault(pod_id, {"pod_id": pod_id, "room_id": room_id})
        counts = cabinet_counts.setdefault(pod_id, {"compute": 0, "other": 0})
        counts["compute"] += _count_cabinet_tokens(row.get("计算柜"))
        for key in ("总线柜", "参数面Leaf柜", "样本面Leaf柜", "业务面Leaf柜", "管理面柜"):
            counts["other"] += _count_cabinet_tokens(row.get(key))

    pods: list[Pod] = []
    for pod_id, pod_row in pod_rows.items():
        counts = cabinet_counts.get(pod_id, {"compute": 0, "other": 0})
        fallback = arrival_counts.get(pod_id, {"compute": 0, "other": 0})
        compute_count = counts["compute"] or fallback["compute"] or None
        other_count = counts["other"] or fallback["other"] or None
        pods.append(
            Pod(
                pod_id=pod_id,
                room_id=pod_row["room_id"],
                compute_cabinet_count=compute_count,
                other_cabinet_count=other_count,
            )
        )

    return list(rooms_by_id.values()), pods


def _load_batches(data_root: Path, pods: list[Pod]) -> list[Batch]:
    rows = _read_optional_table_with_row_numbers(data_root / "09_批次信息" / "批次信息.xlsx", "Sheet1")
    if not rows:
        return [Batch(batch_id="batch-all", batch_name="批次1", pod_ids=[pod.pod_id for pod in pods])]

    known_pod_ids = {pod.pod_id for pod in pods}
    batches: list[Batch] = []
    seen_batch_ids: set[str] = set()
    for excel_row, row in rows:
        source = f"批次信息第{excel_row}行"
        batch_name = _required(row, "批次名", source)
        if batch_name in seen_batch_ids:
            raise DataImportError(f"IMPORT_ERROR: {source}《批次名》重复：{batch_name!r}")
        seen_batch_ids.add(batch_name)

        pod_ids = _split_list_cell(row.get("该批包含的PoD"))
        if not pod_ids:
            raise DataImportError(f"IMPORT_ERROR: {source}《该批包含的PoD》为空")
        for pod_id in pod_ids:
            if pod_id not in known_pod_ids:
                raise DataImportError(
                    f"IMPORT_ERROR: {source}《该批包含的PoD》PoD id {pod_id!r} "
                    "对不上 05_机房机柜信息《PoD名称》"
                )

        batches.append(
            Batch(
                batch_id=batch_name,
                batch_name=batch_name,
                pod_ids=pod_ids,
                power_on_target_date=_to_date(row.get("上电目标日期"), f"{source}《上电目标日期》"),
                online_target_date=_to_date(row.get("上线目标日期"), f"{source}《上线目标日期》"),
            )
        )
    return batches


def _load_teams(data_root: Path) -> list[Team]:
    rows = _read_optional_table_with_row_numbers(data_root / "08_施工队伍信息" / "施工队伍信息.xlsx", "Sheet1")
    teams: list[Team] = []
    seen_team_ids: set[str] = set()
    for excel_row, row in rows:
        source = f"施工队伍信息第{excel_row}行"
        team_id = _required(row, "队伍编号", source)
        if team_id in seen_team_ids:
            raise DataImportError(f"IMPORT_ERROR: {source}《队伍编号》重复：{team_id!r}")
        seen_team_ids.add(team_id)

        size = 12 if _is_blank(row.get("人数")) else _to_int(row.get("人数"), f"{source}《人数》")
        teams.append(
            Team(
                team_id=team_id,
                size=size,
                experience=_map_experience(row.get("经验等级"), f"{source}《经验等级》"),
                on_site=_parse_on_site(row.get("在场状态"), f"{source}《在场状态》"),
            )
        )
    return teams


def _read_table(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    return [record for _, record in _read_table_with_row_numbers(path, sheet_name)]


def _read_table_with_row_numbers(path: Path, sheet_name: str) -> list[tuple[int, dict[str, Any]]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet_name not in workbook.sheetnames:
            raise DataImportError(f"{path} 缺少工作表 {sheet_name!r}")
        sheet = workbook[sheet_name]
        rows = sheet.iter_rows(values_only=True)
        try:
            headers = [_clean_text(value) for value in next(rows)]
        except StopIteration:
            return []
        records: list[tuple[int, dict[str, Any]]] = []
        for excel_row, row in enumerate(rows, start=2):
            if not any(_clean_text(value) for value in row):
                continue
            records.append((excel_row, {headers[index]: value for index, value in enumerate(row) if index < len(headers)}))
        return records
    finally:
        workbook.close()


def _read_optional_table_with_row_numbers(path: Path, sheet_name: str) -> list[tuple[int, dict[str, Any]]]:
    if not path.exists():
        return []
    return _read_table_with_row_numbers(path, sheet_name)


def _build_activity_reference_map(
    activity_seeds: list[ActivitySeed],
    plan_activities: dict[str, PlanActivity],
    extra_aliases: dict[str, str],
) -> dict[str, str]:
    name_to_id: dict[str, str] = {}
    for seed in activity_seeds:
        _add_name_alias(name_to_id, seed.activity_name, seed.activity_id)
    for detail in plan_activities.values():
        _add_name_alias(name_to_id, detail.activity_name, detail.activity_id)
    for name, activity_id in extra_aliases.items():
        _add_name_alias(name_to_id, name, activity_id)
    return name_to_id


def _add_name_alias(name_to_id: dict[str, str], name: str, activity_id: str) -> None:
    normalized = _normalize_activity_ref(name)
    if normalized:
        name_to_id[normalized] = activity_id
        name_to_id.setdefault(normalized.replace("与", ""), activity_id)


def _resolve_activity_reference(
    token: str,
    name_to_id: dict[str, str],
    activity_ids: set[str],
    row_number: int,
    dep_type: str,
) -> str:
    clean = _clean_id(token)
    if clean in activity_ids:
        return clean

    normalized = _normalize_activity_ref(clean)
    if normalized in name_to_id:
        return name_to_id[normalized]
    without_and = normalized.replace("与", "")
    if without_and in name_to_id:
        return name_to_id[without_and]

    candidates = {
        activity_id
        for name, activity_id in name_to_id.items()
        if normalized and (normalized in name or name in normalized)
    }
    if len(candidates) == 1:
        return next(iter(candidates))

    raise DataImportError(f"计划基线第{row_number}行《{dep_type}》依赖 {token!r} 解析不到活动 id")


def _append_dependency(
    dependencies: list[Dependency],
    seen: set[tuple[str, str, str]],
    from_id: str,
    to_id: str,
    dep_type: str,
) -> None:
    key = (from_id, to_id, dep_type)
    if from_id == to_id or key in seen:
        return
    dependencies.append(Dependency(from_activity_id=from_id, to_activity_id=to_id, dep_type=dep_type))
    seen.add(key)


def _split_dependency_cell(value: Any) -> list[str]:
    text = _clean_text(value)
    if _is_blank(text):
        return []
    parts = re.split(r"[、,，/\n\r]+", text)
    return [part.strip() for part in parts if not _is_blank(part)]


def _split_list_cell(value: Any) -> list[str]:
    return [_clean_text(part) for part in re.split(r"[、,，/\n\r]+", _clean_text(value)) if not _is_blank(part)]


def _parse_workload_rules(
    activity_name: str,
    standard_text: str | None,
    limit_text: str | None,
    note: str | None,
    row_number: int | None,
) -> list[WorkloadRule]:
    standard_entries = _parse_workload_entries(standard_text, activity_name, row_number, "标准工时")
    limit_entries = _parse_workload_entries(limit_text, activity_name, row_number, "极限工时") if limit_text else []
    if not standard_entries:
        row = f"第{row_number}行" if row_number else ""
        raise DataImportError(f"计划基线{row}{activity_name} 缺少可解析的弹性工时")

    limit_by_source = {_normalize_activity_ref(entry.workload_source): entry for entry in limit_entries}
    rules: list[WorkloadRule] = []
    for index, entry in enumerate(standard_entries):
        limit_entry = limit_by_source.get(_normalize_activity_ref(entry.workload_source))
        if limit_entry is None and len(limit_entries) == len(standard_entries):
            limit_entry = limit_entries[index]
        rules.append(
            WorkloadRule(
                workload_source=entry.workload_source,
                unit=entry.unit,
                standard_daily_rate=entry.daily_rate,
                limit_daily_rate=limit_entry.daily_rate if limit_entry else None,
                assumed_crew=_parse_assumed_crew(note, entry.workload_source),
            )
        )
    return rules


def _parse_workload_entries(
    text: str | None,
    activity_name: str,
    row_number: int | None,
    column_name: str,
) -> list[WorkloadEntry]:
    if _is_blank(text):
        return []

    entries: list[WorkloadEntry] = []
    for raw_line in re.split(r"[\n;；]+", _clean_text(text)):
        line = re.sub(r"^\s*\d+[.、]\s*", "", raw_line.strip())
        if _is_blank(line):
            continue

        days_match = re.search(
            r"(?:(?P<label>[^:：,，/]+?)\s*[:：,，]\s*)?约?(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>根|柜|台)\s*/\s*(?P<days>\d+(?:\.\d+)?)\s*天",
            line,
        )
        if days_match:
            quantity = float(days_match.group("qty"))
            days = float(days_match.group("days"))
            label = _clean_text(days_match.group("label")) or _infer_workload_source(activity_name)
            entries.append(WorkloadEntry(label, days_match.group("unit"), quantity / days))
            continue

        rate_match = re.search(
            r"(?:(?P<label>[^:：,，/]+?)\s*[:：,，]\s*)?(?P<rate>\d+(?:\.\d+)?)\s*(?P<unit>根|柜|台)\s*/\s*天",
            line,
        )
        if rate_match:
            label = _clean_text(rate_match.group("label")) or _infer_workload_source(activity_name)
            entries.append(WorkloadEntry(label, rate_match.group("unit"), float(rate_match.group("rate"))))
            continue

        row = f"第{row_number}行" if row_number else ""
        raise DataImportError(f"计划基线{row}《{column_name}》无法解析工时文本：{raw_line!r}")

    return entries


def _pick_scale_days(
    text: str | None,
    project_scale: str | None,
    total_card_count: int | None,
    row_number: int | None,
    column_name: str,
) -> int:
    if _is_blank(text):
        row = f"第{row_number}行" if row_number else ""
        raise DataImportError(f"计划基线{row}《{column_name}》缺少规模分档文本")

    entries: list[tuple[str, int]] = []
    for raw_label, raw_days in re.findall(r"(?:^|\n)\s*(?:\d+[.、]\s*)?([^，,\n]+)[，,]\s*(\d+)\s*天", _clean_text(text)):
        label = _clean_text(raw_label)
        entries.append((label, int(raw_days)))

    if not entries:
        row = f"第{row_number}行" if row_number else ""
        raise DataImportError(f"计划基线{row}《{column_name}》无法解析规模分档：{text!r}")

    wanted = _scale_bucket_for_card_count(total_card_count)
    scale = _clean_text(project_scale)
    aliases = {
        "标准项目": "千卡至万卡",
        "中型项目": "千卡至万卡",
        "小型项目": "千卡以下",
        "大型项目": "万卡以上",
    }
    if wanted is None:
        wanted = aliases.get(scale, scale) if scale else DEFAULT_SCALE_BUCKET

    for label, days in entries:
        if wanted and (_normalize_activity_ref(wanted) in _normalize_activity_ref(label)):
            return days

    if total_card_count is None and scale == "标准项目" and len(entries) >= 2:
        return entries[1][1]

    row = f"第{row_number}行" if row_number else ""
    if total_card_count is not None:
        raise DataImportError(
            f"计划基线{row}《{column_name}》找不到卡数 {total_card_count} 对应分档 {wanted!r}"
        )
    raise DataImportError(f"计划基线{row}《{column_name}》找不到项目规模 {project_scale!r} 对应分档")


def _scale_bucket_for_card_count(total_card_count: int | None) -> str | None:
    if total_card_count is None:
        return None
    if total_card_count < 1000:
        return "千卡以下"
    if total_card_count <= 10000:
        return "千卡至万卡"
    return "万卡以上"


def _parse_days(value: Any, row_number: int | None, column_name: str, required: bool) -> int | None:
    if _is_blank(value):
        if required:
            row = f"第{row_number}行" if row_number else ""
            raise DataImportError(f"计划基线{row}《{column_name}》为空，无法解析 SLA")
        return None
    text = _clean_text(value)
    match = re.search(r"(\d+)\s*天", text)
    if not match:
        row = f"第{row_number}行" if row_number else ""
        raise DataImportError(f"计划基线{row}《{column_name}》无法解析 SLA：{text!r}")
    return int(match.group(1))


def _parse_assumed_crew(note: str | None, source: str) -> int | None:
    if _is_blank(note):
        return None
    text = _clean_text(note)
    source_pattern = re.escape(source)
    source_match = re.search(source_pattern + r"\s*(\d+)(?:\s*-\s*(\d+))?\s*人", text)
    if source_match:
        return int(source_match.group(2) or source_match.group(1))

    matches = re.findall(r"(\d+)(?:\s*-\s*(\d+))?\s*人", text)
    if not matches:
        return None
    return max(int(high or low) for low, high in matches)


def _infer_workload_source(activity_name: str) -> str:
    if "液冷计算柜" in activity_name or "计算柜" in activity_name:
        return "计算柜"
    if "总线设备柜" in activity_name:
        return "总线设备柜"
    if "通算" in activity_name:
        return "通算"
    if "存储" in activity_name:
        return "存储"
    if "网络" in activity_name:
        return "网络"
    if "线缆" in activity_name:
        return activity_name.split("-")[-1]
    return activity_name


def _build_risk_rule(values: dict[str, str | None]) -> RiskRule:
    return RiskRule(
        trigger_logic=values.get("trigger_logic"),
        risk_name=values.get("risk_name"),
        description=values.get("description"),
        impact=values.get("impact"),
        mitigation=values.get("mitigation"),
        mitigation_owner=values.get("mitigation_owner"),
    )


def _build_note(detail: PlanActivity | None) -> str | None:
    if detail is None:
        return None
    notes = []
    if detail.work_note:
        notes.append(detail.work_note)
    return "\n".join(notes) if notes else None


def _infer_phase(detail: PlanActivity | None) -> str | None:
    if detail is None:
        return None
    if detail.level1:
        return detail.level1
    return detail.stage


def _infer_activity_type(activity_name: str) -> str:
    if "到货" in activity_name:
        return "到货"
    if activity_name.startswith("机房改造实施"):
        return "机房准备"
    if _is_default_milestone(activity_name):
        return "里程碑"
    return "普通"


def _infer_constraint_source(activity_name: str, activity_type: str, duration_mode: str) -> str | None:
    if activity_type == "机房准备":
        return "站"
    if activity_type == "到货":
        return "货"
    if duration_mode == "弹性" or any(keyword in activity_name for keyword in ("安装", "布线", "调测", "测试", "验收")):
        return "人"
    return None


def _is_default_milestone(activity_name: str) -> bool:
    return activity_name in {"设备上电", "集群性能调优", "移交"} or activity_name.endswith("设备上电")


def _as_scope(value: str | None, activity_id: str) -> str:
    if value in {"项目级", "机房级", "批次级", "PoD级"}:
        return value
    major = activity_id.split(".", 1)[0]
    if major in {"6", "7", "8"}:
        return "PoD级"
    if major in {"9", "12"}:
        return "批次级"
    return "项目级"


def _arrival_status(arrival_date: date | None, today: date) -> str:
    if arrival_date is None:
        return "未明"
    return "已到货" if arrival_date <= today else "在途"


def _to_date(value: Any, source: str) -> date | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean_text(value)
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise DataImportError(f"{source} 无法解析日期：{text!r}")


def _to_float(value: Any, source: str) -> float:
    try:
        return float(_clean_text(value))
    except ValueError as exc:
        raise DataImportError(f"{source} 无法解析数值：{value!r}") from exc


def _to_int(value: Any, source: str) -> int:
    text = _clean_text(value)
    try:
        number = float(text)
    except ValueError as exc:
        raise DataImportError(f"IMPORT_ERROR: {source} 无法解析整数：{value!r}") from exc
    if not number.is_integer():
        raise DataImportError(f"IMPORT_ERROR: {source} 不是整数：{value!r}")
    return int(number)


def _parse_optional_positive_int(value: Any, source: str) -> int | None:
    if _is_blank(value):
        return None
    number = _to_int(value, source)
    if number <= 0:
        raise DataImportError(f"IMPORT_ERROR: {source} 必须为正整数：{value!r}")
    return number


def _map_experience(value: Any, source: str) -> str:
    if _is_blank(value):
        return "一般"
    aliases = {
        "丰富": "丰富",
        "经验丰富": "丰富",
        "经验充分": "丰富",
        "充分": "丰富",
        "一般": "一般",
        "经验一般": "一般",
        "普通": "一般",
        "缺乏": "缺乏",
        "经验缺乏": "缺乏",
        "不足": "缺乏",
        "经验不足": "缺乏",
    }
    normalized = _normalize_activity_ref(_clean_text(value))
    if normalized in aliases:
        return aliases[normalized]
    raise DataImportError(f"IMPORT_ERROR: {source} 无法映射：{value!r}（应为 丰富/一般/缺乏）")


def _parse_on_site(value: Any, source: str) -> bool:
    if _is_blank(value):
        return True
    normalized = _normalize_activity_ref(_clean_text(value))
    if normalized in {"在场", "在岗", "可用", "是", "true", "1", "yes", "y"}:
        return True
    if normalized in {"待分配", "不在场", "离场", "否", "false", "0", "no", "n"}:
        return False
    raise DataImportError(f"IMPORT_ERROR: {source} 无法映射：{value!r}（应为 在场/待分配）")


def _count_cabinet_tokens(value: Any) -> int:
    text = _clean_text(value)
    if _is_blank(text):
        return 0
    return len([part for part in re.split(r"[、,，/\n\r]+", text) if not _is_blank(part)])


def _required(row: dict[str, Any], key: str, source: str) -> str:
    value = row.get(key)
    if _is_blank(value):
        raise DataImportError(f"{source} 缺少必填字段《{key}》")
    return _clean_text(value)


def _blank_to_none(value: Any) -> str | None:
    return None if _is_blank(value) else _clean_text(value)


def _is_blank(value: Any) -> bool:
    return _clean_text(value) in {"", "/", "-", "—", "－"}


def _clean_id(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _clean_text(value)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_activity_ref(value: str) -> str:
    text = _clean_text(value)
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("，", ",").replace("：", ":")
    text = re.sub(r"\s+", "", text)
    return text.lower()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import schedule project-data Excel files into InputBundle JSON.")
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--card-count", type=int, default=None, help="集群总卡数；优先用于规模分档取档。")
    args = parser.parse_args(list(argv) if argv is not None else None)

    bundle = load_input_bundle(args.project_root, total_card_count=args.card_count)
    payload = json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
