"""智慧工勘 Idle 机房目录：孪生机房机柜表 + 各机房勘测快照。"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from agent.services.proposal_chapter_files import parse_room_rack_output_xlsx
from agent.skills.zhgk.demo_assets import (
    DEFAULT_DEMO_PROJECT_ID,
    REPO_ROOT,
    resolve_room_rack_xlsx,
    survey_output_project_dir,
)
from agent.skills.zhgk.path_config import get_output_dir
from agent.skills.zhgk.services.room_survey_snapshot import resolve_room_snapshot

_CABINET_FIELDS = ("compute", "bus", "param_leaf", "biz_leaf", "mgmt", "sample_leaf")

LOGICAL_PATH = "孪生世界/算力底座孪生/输出结果/机房机柜信息表"


def _count_racks_in_row(row: dict[str, Any]) -> int:
    total = 0
    for key in _CABINET_FIELDS:
        raw = str(row.get(key) or "").strip()
        if not raw:
            continue
        total += len([p for p in raw.split(",") if p.strip()])
    return total


def _aggregate_rooms(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_room: dict[str, dict[str, Any]] = {}
    pods: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        room = str(row.get("room_name") or "").strip()
        pod = str(row.get("pod_name") or "").strip()
        if not room:
            continue
        entry = by_room.setdefault(room, {
            "room_id": room,
            "room_name": room,
            "pod_names": [],
            "rack_count": 0,
        })
        if pod:
            pods[room].add(pod)
        entry["rack_count"] += _count_racks_in_row(row)

    out: list[dict[str, Any]] = []
    for room, entry in sorted(by_room.items(), key=lambda x: x[0]):
        entry["pod_names"] = sorted(pods[room])
        entry["pod_count"] = len(pods[room])
        out.append(entry)
    return out


def load_room_rack_rows(
    *,
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
) -> tuple[list[dict[str, Any]], str, Path | None]:
    """加载孪生机房机柜表行；返回 (rows, source, path)。"""
    path = resolve_room_rack_xlsx(repo_root=repo_root, project_id=project_id)
    if path is None or not path.is_file():
        return [], "missing", None
    rows = parse_room_rack_output_xlsx(path.read_bytes())
    return rows, "project-data", path


def build_room_catalog(
    *,
    repo_root: Path | None = None,
    project_id: str = DEFAULT_DEMO_PROJECT_ID,
    workspace_output_dir: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or REPO_ROOT
    rack_rows, source, rack_path = load_room_rack_rows(repo_root=root, project_id=project_id)
    rooms_base = _aggregate_rooms(rack_rows)

    ws_out = workspace_output_dir or get_output_dir()
    proj_out = survey_output_project_dir(root, project_id)

    rooms: list[dict[str, Any]] = []
    for base in rooms_base:
        snap = resolve_room_snapshot(
            base["room_name"],
            ws_out,
            project_output_dir=proj_out,
        )
        rooms.append({**base, **snap.to_dict()})

    return {
        "rooms": rooms,
        "source": source,
        "logical_path": LOGICAL_PATH,
        "rack_table_path": str(rack_path) if rack_path else None,
        "workspace_output_dir": str(ws_out),
    }
