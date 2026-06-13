"""Normalize proposal storage layout for one project (hard cleanup mode).

Usage:
  python agent/scripts/migrate_proposal_storage.py --project-id 56A0TXN --apply
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from agent.config import BUSINESS_ROOT
from agent.proposal.chapter_registry import CHAPTER_BY_JSON


LEGACY_CHAPTER_JSON_MAP = {
    "ch-02-device-info.json": "2.设备配置信息.json",
    "ch-08-1-service-delivery-ui.json": "8.1服务交付界面.json",
    "ch-08-2-service-content.json": "8.2服务配置.json",
    "ch-08-3-maintenance-strategy.json": "8.3维保策略.json",
    "ch-08-4-maintenance-sla.json": "8.4维保SLA.json",
}

LEGACY_FLAT_OUTPUT_FILES = {
    "服务配置.xlsx",
    "服务内容.xlsx",
    "维保策略.xlsx",
    "维保SLA.xlsx",
    "设备信息表.xlsx",
}


@dataclass
class MigrationReport:
    project_id: str
    applied: bool
    moved: list[str] = field(default_factory=list)
    copied: list[str] = field(default_factory=list)
    renamed: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def add(self, bucket: str, message: str) -> None:
        getattr(self, bucket).append(message)

    def dump(self) -> dict:
        return {
            "projectId": self.project_id,
            "applied": self.applied,
            "moved": self.moved,
            "copied": self.copied,
            "renamed": self.renamed,
            "deleted": self.deleted,
            "skipped": self.skipped,
        }


def _project_root(project_id: str) -> Path:
    return BUSINESS_ROOT / "projects" / project_id


def _ensure_dir(path: Path, apply: bool) -> None:
    if apply:
        path.mkdir(parents=True, exist_ok=True)


def _move_dir_contents(src: Path, dst: Path, report: MigrationReport) -> None:
    if not src.exists():
        report.add("skipped", f"missing source dir: {src}")
        return
    _ensure_dir(dst, report.applied)
    for item in sorted(src.iterdir()):
        target = dst / item.name
        if target.exists():
            report.add("skipped", f"target exists, keep source: {item} -> {target}")
            continue
        report.add("moved", f"{item} -> {target}")
        if report.applied:
            shutil.move(str(item), str(target))
    if report.applied and src.exists() and not any(src.iterdir()):
        src.rmdir()


def _delete_path(path: Path, report: MigrationReport) -> None:
    if not path.exists():
        return
    report.add("deleted", str(path))
    if not report.applied:
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _rename_file(src: Path, dst: Path, report: MigrationReport) -> None:
    if not src.exists():
        return
    if dst.exists():
        report.add("skipped", f"rename skipped (target exists): {src} -> {dst}")
        return
    report.add("renamed", f"{src} -> {dst}")
    if report.applied:
        _ensure_dir(dst.parent, True)
        src.rename(dst)


def _normalize_chapter_filenames(draft_dir: Path, report: MigrationReport) -> None:
    if not draft_dir.exists():
        report.add("skipped", f"missing draft dir: {draft_dir}")
        return

    for legacy_name, canonical_name in LEGACY_CHAPTER_JSON_MAP.items():
        legacy_json = draft_dir / legacy_name
        canonical_json = draft_dir / canonical_name
        _rename_file(legacy_json, canonical_json, report)
        if legacy_json.exists() and canonical_json.exists():
            _delete_path(legacy_json, report)

        legacy_xlsx = draft_dir / legacy_name.replace(".json", ".xlsx")
        canonical_xlsx = draft_dir / canonical_name.replace(".json", ".xlsx")
        _rename_file(legacy_xlsx, canonical_xlsx, report)
        if legacy_xlsx.exists() and canonical_xlsx.exists():
            _delete_path(legacy_xlsx, report)

    # Keep JSON source-of-truth only; draft XLSX can be regenerated.
    for xlsx in sorted(draft_dir.glob("*.xlsx")):
        expected_json = xlsx.with_suffix(".json").name
        if expected_json in CHAPTER_BY_JSON:
            _delete_path(xlsx, report)


def _cleanup_output_dir(output_dir: Path, report: MigrationReport) -> None:
    if not output_dir.exists():
        return

    # Remove legacy version snapshots and flat duplicate xlsx/json outputs.
    _delete_path(output_dir / "预案版本", report)
    _delete_path(output_dir / "设备信息表", report)
    version_info_dir = output_dir / "预案版本信息表"
    records_in_dir = version_info_dir / "records.json"
    xlsx_in_dir = version_info_dir / "预案版本信息表.xlsx"
    records_flat = output_dir / "预案版本信息表.records.json"
    xlsx_flat = output_dir / "预案版本信息表.xlsx"
    if records_in_dir.exists() and not records_flat.exists():
        report.add("moved", f"{records_in_dir} -> {records_flat}")
        if report.applied:
            shutil.move(str(records_in_dir), str(records_flat))
    if xlsx_in_dir.exists() and not xlsx_flat.exists():
        report.add("moved", f"{xlsx_in_dir} -> {xlsx_flat}")
        if report.applied:
            shutil.move(str(xlsx_in_dir), str(xlsx_flat))
    if records_in_dir.exists() and records_flat.exists():
        _delete_path(records_in_dir, report)
    if xlsx_in_dir.exists() and xlsx_flat.exists():
        _delete_path(xlsx_in_dir, report)
    if version_info_dir.exists() and report.applied and not any(version_info_dir.iterdir()):
        version_info_dir.rmdir()
    for file_name in LEGACY_FLAT_OUTPUT_FILES:
        _delete_path(output_dir / file_name, report)
    for file in sorted(output_dir.glob("*.json")):
        if file.name == "预案版本信息表.records.json":
            continue
        _delete_path(file, report)
    for file in sorted(output_dir.glob("*.xlsx")):
        if file.name == "预案版本信息表.xlsx":
            continue
        _delete_path(file, report)


def migrate_project(project_id: str, apply: bool) -> MigrationReport:
    report = MigrationReport(project_id=project_id, applied=apply)
    project_root = _project_root(project_id)
    proposal_root = project_root / "早期介入" / "交付预案"
    contract_root = project_root / "早期介入" / "合同"

    proposal_parse = proposal_root / "解析结果"
    proposal_out = proposal_root / "输出结果"
    contract_parse = contract_root / "解析结果"

    _ensure_dir(contract_parse, apply)

    # 1) BOQ 解析目录迁移到合同侧。
    _move_dir_contents(
        proposal_parse / "设备BOQ解析结果",
        contract_parse / "BOQ设备解析原始结果",
        report,
    )
    _move_dir_contents(
        proposal_parse / "服务BOQ解析结果",
        contract_parse / "服务BOQ解析结果",
        report,
    )

    # 2) 维保建议书解析结果归并到单一路径。
    maint_target = proposal_parse / "维保建议书解析结果"
    _move_dir_contents(proposal_parse / "维保建议书", maint_target, report)

    # 3) 草稿目录统一命名并移除重复 XLSX。
    _normalize_chapter_filenames(proposal_parse / "预案草稿", report)

    # 4) 清理 archive 快照和遗留重复输出。
    for archive_dir in sorted(proposal_parse.glob("draft.archive.*")):
        _delete_path(archive_dir, report)
    _cleanup_output_dir(proposal_out, report)

    # 5) 输出迁移报告。
    report_path = proposal_root / "迁移报告.proposal-normalization.json"
    report_json = json.dumps(report.dump(), ensure_ascii=False, indent=2)
    report.add("copied", f"report -> {report_path}")
    if apply:
        report_path.write_text(report_json, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize proposal storage layout.")
    parser.add_argument("--project-id", required=True, help="Target project id.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag runs in dry-run mode.",
    )
    args = parser.parse_args()

    report = migrate_project(project_id=args.project_id, apply=args.apply)
    print(json.dumps(report.dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
