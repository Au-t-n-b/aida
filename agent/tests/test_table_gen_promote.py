"""Tests for table_gen promote layer (IPO SSOT)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.skills.early_io.output_tables import PROPOSAL_OUTPUT_TABLES, SPEC_XLSX_NAMES
from agent.skills.early_io.paths import EarlyIoPaths, project_physical_root
from agent.skills.early_io.promote import load_parse_rows, promote_all_tables, promote_table
from agent.skills.early_io.output_tables import OUTPUT_TABLE_BY_XLSX


def _io(tmp_path: Path, project_id: str = "test-proj") -> EarlyIoPaths:
    root = tmp_path / "projects" / project_id
    root.mkdir(parents=True)
    parse = root / "早期介入/交付预案/解析结果"
    out = root / "早期介入/交付预案/输出结果"
    parse.mkdir(parents=True)
    out.mkdir(parents=True)
    return EarlyIoPaths(
        project_id=project_id,
        project_root=root,
        contract_boq_upload=root / "早期介入/合同/输入文件/BOQ",
        contract_boq_parse=root / "早期介入/合同/解析结果/BOQ设备解析原始结果",
        contract_service_boq_parse=root / "早期介入/合同/解析结果/服务BOQ解析结果",
        contract_simulation_out=root / "早期介入/合同/输出结果/建模仿真",
        contract_simulation_md=root / "早期介入/合同/输出结果/建模仿真/建模仿真设备信息表.md",
        proposal_parse_root=parse,
        proposal_output_root=out,
        proposal_device_table_out=out / "设备信息表.xlsx",
        proposal_tech_proposal_in=root / "早期介入/交付预案/输入文件/技术建议书",
        proposal_testcases_in=root / "早期介入/交付预案/输入文件/测试用例",
        proposal_tech_proposal_parse=parse / "服务建议书解析结果",
        proposal_testcase_parse=parse / "测试用例解析结果",
        proposal_acceptance_parse=parse / "验收策略解析结果",
        proposal_hld_parse=parse / "HLD解析结果",
        proposal_maint_proposal_parse=parse / "维保建议书解析结果",
    )


def test_output_tables_cover_spec() -> None:
    assert len(PROPOSAL_OUTPUT_TABLES) == 17
    assert "设备信息表.xlsx" in SPEC_XLSX_NAMES
    assert "测试用例.xlsx" in SPEC_XLSX_NAMES
    assert "验收策略.xlsx" in SPEC_XLSX_NAMES


def test_load_parse_rows_cases_envelope() -> None:
    rows, err = load_parse_rows(
        Path("/nonexistent"),
        "cases",
    )
    assert rows == []
    assert err


def test_load_parse_rows_auto(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    p.write_text(
        json.dumps({"cases": [{"id": "1.1.1", "l1": "a"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    rows, err = load_parse_rows(p, "auto")
    assert not err
    assert len(rows) == 1
    assert rows[0]["id"] == "1.1.1"


def test_promote_testcases_from_parse_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.skills.early_io.paths.BUSINESS_ROOT",
        tmp_path,
    )
    io = _io(tmp_path)
    parse_dir = io.proposal_testcase_parse
    parse_dir.mkdir(parents=True)
    (parse_dir / "cases.json").write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "1.1.1",
                        "l1": "计算",
                        "l2": "功能",
                        "l3": "检测",
                        "purpose": "p",
                        "topology": "NA",
                        "pre": "pre",
                        "steps": ["s1"],
                        "expects": ["e1"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    spec = OUTPUT_TABLE_BY_XLSX["测试用例.xlsx"]
    result = promote_table(io, spec)
    assert result.status == "written"
    assert result.row_count == 1
    assert (io.proposal_output_root / "测试用例.xlsx").is_file()


def test_promote_skips_existing_upstream_device_table(tmp_path: Path) -> None:
    io = _io(tmp_path)
    out = io.proposal_output_root / "设备信息表.xlsx"
    out.write_bytes(b"existing")
    spec = OUTPUT_TABLE_BY_XLSX["设备信息表.xlsx"]
    result = promote_table(io, spec)
    assert result.status == "skipped"


def test_promote_all_tables_writes_empty_headers(tmp_path: Path) -> None:
    io = _io(tmp_path)
    results = promote_all_tables(io)
    assert len(results) == 16  # excludes version table
    written_or_empty = [r for r in results if r.status in ("written", "empty")]
    assert len(written_or_empty) >= 1
    for r in written_or_empty:
        if r.path:
            assert (io.project_root / r.path).is_file()


def test_table_gen_release_step_promote_hitl(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent.skills.early_io.paths.BUSINESS_ROOT",
        tmp_path,
    )
    from agent.skills.proposal_gen.steps.table_gen_release import TableGenReleaseStep
    from agent.skills.base import SkillContext

    io = _io(tmp_path)
    parse_dir = io.proposal_testcase_parse
    parse_dir.mkdir(parents=True, exist_ok=True)
    (parse_dir / "cases.json").write_text(
        json.dumps({"rows": [{"id": "1", "l1": "a", "l2": "b", "l3": "c"}]}),
        encoding="utf-8",
    )

    step = TableGenReleaseStep()
    ctx = SkillContext(
        skill_id="proposal_gen",
        work_root=tmp_path,
        run_id="run-1",
        project={"project_id": "test-proj"},
        llm_factory=None,
        emit_push=None,
    )
    result = step.run(ctx, {"files": {}}, lambda m: None)
    assert result.get("hitl")
    assert result["metrics"]["table_gen_stub"] is False
    assert (io.proposal_output_root / "测试用例.xlsx").is_file()


def test_release_meta_append(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.proposal.version_info_store.physical_project_root",
        lambda pid: tmp_path / "projects" / pid,
    )
    from agent.skills.proposal_gen.release_meta import append_release_version

    pid = "rel-proj"
    (tmp_path / "projects" / pid / "早期介入/交付预案/输出结果").mkdir(parents=True)
    row = append_release_version(pid, operator="测试")
    assert row["proposalVersion"].startswith("V")
    records = tmp_path / "projects" / pid / "早期介入/交付预案/输出结果/预案版本信息表.records.json"
    assert records.is_file()
