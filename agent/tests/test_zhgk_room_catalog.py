"""zhgk room-catalog · 机房目录与勘测快照。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import openpyxl

from agent.skills.zhgk.services.room_catalog import _aggregate_rooms, build_room_catalog, load_room_rack_rows
from agent.skills.zhgk.services.room_survey_snapshot import resolve_room_snapshot
from agent.services.proposal_chapter_files import parse_room_rack_output_xlsx


def _write_minimal_rack_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["PoD名称", "机房名称", "计算柜", "总线柜", "参数面Leaf柜", "业务面Leaf柜", "管理面柜", "样本面Leaf柜"])
    ws.append(["POD1", "401", "A01,A02", "A03", "", "", "", ""])
    ws.append(["POD2", "401", "B01,B02", "B03", "", "", "", ""])
    ws.append(["POD3", "402", "C01", "", "", "", "", ""])
    wb.save(path)
    wb.close()


def _write_survey_table(path: Path, *, with_ai: bool = False) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["序号", "细分场景", "勘测要素", "项目", "检查内容", "勘测方法",
               "最新检查结果", "AI评估结果", "图片1", "图片2", "第一轮勘测结果", "备注"])
    ws.append([1, "场景", "要素", "项", "内容", "现场", "ok", "满足" if with_ai else "", "", "", "", ""])
    ws.append([2, "场景", "要素", "项", "内容", "现场", "", "未勘测" if with_ai else "", "", "", "", ""])
    wb.save(path)
    wb.close()


def test_aggregate_rooms_groups_by_room_name(tmp_path: Path):
    tmp = tmp_path / "rack.xlsx"
    _write_minimal_rack_xlsx(tmp)
    rows = parse_room_rack_output_xlsx(tmp.read_bytes())
    rooms = _aggregate_rooms(rows)
    assert len(rooms) == 2
    by_id = {r["room_id"]: r for r in rooms}
    assert by_id["401"]["pod_count"] == 2
    assert by_id["402"]["pod_count"] == 1


def test_resolve_room_snapshot_pending_and_assessed(tmp_path: Path):
    out = tmp_path / "Output"
    out.mkdir()
    snap0 = resolve_room_snapshot("401", out)
    assert snap0.status == "pending"
    assert snap0.five_values["满足"] == 0

    table = out / "ACT001_项目_401_全量勘测结果表.xlsx"
    _write_survey_table(table, with_ai=True)
    snap1 = resolve_room_snapshot("401", out)
    assert snap1.status == "assessed"
    assert snap1.five_values["满足"] == 1
    assert snap1.total == 2


def test_build_room_catalog_with_project_data(tmp_path: Path, monkeypatch):
    from agent.skills.zhgk.services import room_catalog as rc

    rack = tmp_path / "rack.xlsx"
    _write_minimal_rack_xlsx(rack)

    def fake_resolve(project_id=..., business_root=None):
        return rack

    monkeypatch.setattr(rc, "resolve_room_rack_xlsx", fake_resolve)
    monkeypatch.setattr(rc, "get_output_dir", lambda: tmp_path / "ws_out")

    cat = build_room_catalog(project_id="test")
    assert cat["source"] == "project-data"
    assert len(cat["rooms"]) == 2
    ids = {r["room_id"] for r in cat["rooms"]}
    assert ids == {"401", "402"}
