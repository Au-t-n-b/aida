"""按机房扫描 Output 产物，推导 Idle 机房卡的状态与五值统计。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.skills.zhgk.services.assessment_engine import get_assessment_statistics

FIVE_VALUE_KEYS = ("满足", "不满足", "不涉及", "未勘测", "无法识别")

STATUS_LABELS = {
    "pending": "待启动",
    "active": "勘测中",
    "assessed": "已评估",
    "done": "已完成",
}


@dataclass
class RoomSurveySnapshot:
    status: str = "pending"
    status_label: str = "待启动"
    five_values: dict[str, int] = field(default_factory=lambda: {k: 0 for k in FIVE_VALUE_KEYS})
    total: int = 0
    survey_round: int | None = None
    issue_count: int = 0
    has_report: bool = False
    survey_table_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "status_label": self.status_label,
            "five_values": dict(self.five_values),
            "total": self.total,
            "survey_round": self.survey_round,
            "issue_count": self.issue_count,
            "has_report": self.has_report,
            "survey_table_path": self.survey_table_path,
        }


def _room_token(room_name: str) -> str:
    return str(room_name or "").strip()


def _glob_survey_tables(output_dir: Path, room_name: str) -> list[Path]:
    token = _room_token(room_name)
    if not token or not output_dir.is_dir():
        return []
    patterns = [
        f"*_{token}_全量勘测结果表*.xlsx",
        f"*{token}*全量勘测结果表*.xlsx",
    ]
    found: dict[str, Path] = {}
    for pat in patterns:
        for p in output_dir.glob(pat):
            if p.is_file():
                found[p.name] = p
    return sorted(found.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def _glob_issue_tables(output_dir: Path, room_name: str) -> list[Path]:
    token = _room_token(room_name)
    if not token or not output_dir.is_dir():
        return []
    found: dict[str, Path] = {}
    for pat in (f"*_{token}_问题清单表*.xlsx", f"*{token}*问题清单表*.xlsx"):
        for p in output_dir.glob(pat):
            if p.is_file():
                found[p.name] = p
    return list(found.values())


def _glob_reports(output_dir: Path, room_name: str) -> list[Path]:
    token = _room_token(room_name)
    if not token or not output_dir.is_dir():
        return []
    found: dict[str, Path] = {}
    for pat in (f"*_{token}_工勘报告*.docx", f"*{token}*工勘报告*.docx", f"*{token}*工勘报告*.pdf"):
        for p in output_dir.glob(pat):
            if p.is_file():
                found[p.name] = p
    return list(found.values())


def _parse_round_from_name(name: str) -> int | None:
    m = re.search(r"_R(\d+)", name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _count_issue_rows(path: Path) -> int:
    try:
        import openpyxl
    except ImportError:
        return 0
    if not path.is_file():
        return 0
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        n = max(0, (ws.max_row or 1) - 1)
        wb.close()
        return n
    except Exception:
        return 0


def resolve_room_snapshot(
    room_name: str,
    output_dir: Path,
    *,
    project_output_dir: Path | None = None,
) -> RoomSurveySnapshot:
    """从工作区 Output（及可选项目 IPO 输出）推导机房勘测快照。"""
    snap = RoomSurveySnapshot()
    dirs = [output_dir]
    if project_output_dir and project_output_dir.is_dir():
        dirs.append(project_output_dir)

    survey_tables: list[Path] = []
    reports: list[Path] = []
    issues: list[Path] = []
    for d in dirs:
        survey_tables.extend(_glob_survey_tables(d, room_name))
        reports.extend(_glob_reports(d, room_name))
        issues.extend(_glob_issue_tables(d, room_name))

    if reports:
        snap.has_report = True

    if issues:
        snap.issue_count = _count_issue_rows(sorted(issues, key=lambda p: p.stat().st_mtime, reverse=True)[0])

    if not survey_tables:
        if snap.has_report:
            snap.status = "done"
            snap.status_label = STATUS_LABELS["done"]
        return snap

    table = survey_tables[0]
    snap.survey_table_path = str(table)
    snap.survey_round = _parse_round_from_name(table.name)

    stats = get_assessment_statistics(str(table))
    snap.five_values = {k: int(stats.get(k, 0) or 0) for k in FIVE_VALUE_KEYS}
    snap.total = sum(snap.five_values.values())

    evaluated = snap.five_values["满足"] + snap.five_values["不满足"] + snap.five_values["无法识别"]
    if snap.has_report:
        snap.status = "done"
    elif evaluated > 0 or snap.five_values["不涉及"] > 0:
        snap.status = "assessed"
    else:
        snap.status = "active"

    snap.status_label = STATUS_LABELS.get(snap.status, snap.status)
    return snap
