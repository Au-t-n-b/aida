"""zhgk_files 齐备检查单元测试（v4 路径）。"""
from __future__ import annotations

from pathlib import Path

from agent.skills.zhgk.files import (
    PERSONNEL_FILENAME,
    check_need_files,
    check_project_files,
    infer_upload_kind,
)


def test_check_project_files_all_present(tmp_path: Path) -> None:
    """v4：Template/ 两张底表 + Input/ BOQ = 3 必选项全齐 → ok=True。"""
    root = tmp_path
    for rel in (
        "ProjectData/Template/入场评估标准表.xlsx",
        "ProjectData/Template/工勘常见高风险库.xlsx",
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    boq = root / "ProjectData/Input/BOQ-test.xlsx"
    boq.parent.mkdir(parents=True, exist_ok=True)
    boq.write_bytes(b"x")
    out = check_project_files(root)
    assert out["ok"] is True
    assert out["total"] == 3           # base_table + risk_lib + BOQ


def test_check_project_files_missing_template(tmp_path: Path) -> None:
    """缺 base_table 时 ok=False。"""
    root = tmp_path
    # 只放风险库和 BOQ，缺 base_table
    risk = root / "ProjectData/Template/工勘常见高风险库.xlsx"
    risk.parent.mkdir(parents=True, exist_ok=True)
    risk.write_bytes(b"x")
    boq = root / "ProjectData/Input/BOQ.xlsx"
    boq.parent.mkdir(parents=True, exist_ok=True)
    boq.write_bytes(b"x")
    out = check_project_files(root)
    assert out["ok"] is False
    assert out["found_count"] == 2


def test_check_project_files_optional_not_counted(tmp_path: Path) -> None:
    """可选项（报告模板）不影响 ok 结果。"""
    root = tmp_path
    for rel in (
        "ProjectData/Template/入场评估标准表.xlsx",
        "ProjectData/Template/工勘常见高风险库.xlsx",
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    boq = root / "ProjectData/Input/BOQ.xlsx"
    boq.parent.mkdir(parents=True, exist_ok=True)
    boq.write_bytes(b"x")
    # 不放报告模板
    out = check_project_files(root)
    assert out["ok"] is True          # 报告模板可选，不影响 ok
    # 可选项出现在 items 里，但 total 不包含
    optional_items = [i for i in out["items"] if i.get("optional")]
    assert len(optional_items) == 1
    assert optional_items[0]["found"] is False


def test_check_need_files_glob_boq(tmp_path: Path) -> None:
    boq = tmp_path / "ProjectData/Input/BOQ.xlsx"
    boq.parent.mkdir(parents=True, exist_ok=True)
    boq.write_bytes(b"x")
    out = check_need_files(tmp_path, ["ProjectData/Input/*BOQ*.xlsx"])
    assert out["ok"] is True
    assert out["items"][0]["found"] is True


def test_check_need_files_template(tmp_path: Path) -> None:
    """Template/ 路径检查。"""
    tbl = tmp_path / "ProjectData/Template/入场评估标准表.xlsx"
    tbl.parent.mkdir(parents=True, exist_ok=True)
    tbl.write_bytes(b"x")
    out = check_need_files(tmp_path, ["ProjectData/Template/入场评估标准表.xlsx"])
    assert out["ok"] is True


def test_check_need_files_exact_personnel(tmp_path: Path) -> None:
    rel = f"ProjectData/Input/{PERSONNEL_FILENAME}"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"{}")
    out = check_need_files(tmp_path, [rel])
    assert out["ok"] is True


def test_infer_upload_kind_v4() -> None:
    assert infer_upload_kind("BOQ.xlsx") == "boq"
    assert infer_upload_kind("远近人员表.xlsx") == "personnel"
    assert infer_upload_kind("入场评估标准表.xlsx") == "template"
    assert infer_upload_kind("工勘常见高风险库.xlsx") == "template"
    assert infer_upload_kind("新版项目工勘报告模板.docx") == "template"
    assert infer_upload_kind("勘测结果.xlsx") == "input"
    assert infer_upload_kind("photo.jpg") == "image"
