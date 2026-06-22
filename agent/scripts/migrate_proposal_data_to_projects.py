#!/usr/bin/env python3
"""Migrate legacy delivery/mock proposal data into BUSINESS_ROOT/projects/{project_id}.

Sources:
  - data/delivery/mock/mock_project/**
  - data/delivery/** (flat legacy files)
  - data/projects/{project_id}/** (partial existing tree)
  - data/proposal_store.json (global chapter 5/7 store)

Usage:
  python agent/scripts/migrate_proposal_data_to_projects.py \\
    --project-id 70e5ca737ae5433e9f0f3134d216acf7
  python agent/scripts/migrate_proposal_data_to_projects.py --project-id ... --dry-run
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent.config import BUSINESS_ROOT
from agent.constants.org_assets_paths import LEGACY_ORG_ASSETS_DIR, org_assets_root
from agent.services.proposal_project_paths import (
    chapter57_store_path,
    legacy_global_store_path,
    legacy_repo_data_store_path,
    physical_project_root,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Known business-code keys in legacy proposal_store.json → map into UUID project dir
LEGACY_STORE_PROJECT_ALIASES = ("56A0TXN", "mock_project", "K1903")


def _legacy_delivery_root() -> Path:
    for name in ("delivery", "delivery.bak"):
        root = REPO_ROOT / "data" / name
        if root.is_dir():
            return root
    return REPO_ROOT / "data" / "delivery"


def _legacy_mock_root() -> Path:
    delivery = _legacy_delivery_root()
    return delivery / "mock" / "mock_project"


def _legacy_mock_assets_root() -> Path | None:
    delivery = _legacy_delivery_root()
    candidates = [
        delivery / "mock" / LEGACY_ORG_ASSETS_DIR,
        delivery / "mock" / "org-assets",
        REPO_ROOT / "data" / LEGACY_ORG_ASSETS_DIR,
        REPO_ROOT / "data" / "org-assets",
    ]
    for root in candidates:
        if root.is_dir():
            return root
    return None


LEGACY_PROJECTS_ROOT = REPO_ROOT / "data" / "projects"

# nested legacy output dir → flat IPO output xlsx under 早期介入/交付预案/输出结果/
NESTED_TO_FLAT: dict[str, str] = {
    "早期介入/交付预案/输出结果/网络平面配置信息表/网络平面配置信息表.xlsx":
        "早期介入/交付预案/输出结果/网络平面配置信息表.xlsx",
    "早期介入/交付预案/输出结果/网管服务器配置表/网管服务器配置表.xlsx":
        "早期介入/交付预案/输出结果/网管服务器配置表.xlsx",
    "早期介入/交付预案/输出结果/集群设备清单表/集群设备清单表.xlsx":
        "早期介入/交付预案/输出结果/集群设备清单表.xlsx",
    "早期介入/交付预案/输出结果/共平面类型表/共平面类型表.xlsx":
        "早期介入/交付预案/输出结果/共平面类型表.xlsx",
    "孪生世界/算力底座孪生/输出结果/机房机柜信息表/机房机柜信息表.xlsx":
        "孪生世界/算力底座孪生/输出结果/机房机柜信息表.xlsx",
}

# legacy parse paths under 交付预案 → contract parse (整改规范)
PARSE_RELOCATIONS: dict[str, str] = {
    "早期介入/交付预案/解析结果/服务BOQ解析结果":
        "早期介入/合同/解析结果/服务BOQ解析结果",
    "早期介入/交付预案/解析结果/BOQ设备解析原始结果":
        "早期介入/合同/解析结果/BOQ设备解析原始结果",
    "早期介入/交付预案/解析结果/设备BOQ解析结果":
        "早期介入/合同/解析结果/BOQ设备解析原始结果",
}


@dataclass
class MigrationReport:
    project_id: str
    business_root: str
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    relocated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _normalize_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _target_rel(rel: str) -> str:
    if rel in NESTED_TO_FLAT:
        return NESTED_TO_FLAT[rel]
    for src_prefix, dst_prefix in PARSE_RELOCATIONS.items():
        if rel == src_prefix or rel.startswith(src_prefix + "/"):
            return rel.replace(src_prefix, dst_prefix, 1)
    return rel


def _copy_file(
    src: Path,
    dst: Path,
    *,
    dry_run: bool,
    overwrite: bool,
    report: MigrationReport,
    label: str,
) -> None:
    if dst.exists() and not overwrite:
        report.skipped.append(f"{label}: {dst}")
        return
    if dry_run:
        report.copied.append(f"[dry-run] {src} -> {dst}")
        return
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        report.copied.append(f"{src} -> {dst}")
    except Exception as exc:
        report.errors.append(f"{label}: {exc}")


def _migrate_tree(
    src_root: Path,
    project_id: str,
    *,
    dry_run: bool,
    overwrite: bool,
    report: MigrationReport,
    label: str,
) -> None:
    if not src_root.is_dir():
        return
    dest_base = physical_project_root(project_id)
    for path in sorted(src_root.rglob("*")):
        if not path.is_file():
            continue
        rel = _normalize_rel(path, src_root)
        target_rel = _target_rel(rel)
        dst = dest_base / Path(target_rel)
        if target_rel != rel:
            report.relocated.append(f"{rel} -> {target_rel}")
        _copy_file(path, dst, dry_run=dry_run, overwrite=overwrite, report=report, label=label)


def _migrate_legacy_delivery_files(
    project_id: str,
    *,
    dry_run: bool,
    overwrite: bool,
    report: MigrationReport,
) -> None:
    legacy_delivery = _legacy_delivery_root()
    mappings = {
        legacy_delivery / "delivery-plan.xlsx":
            "项目管理/计划/输入文件/交付计划表.xlsx",
        legacy_delivery / "device-info.xlsx":
            "早期介入/交付预案/输出结果/设备信息表.xlsx",
    }
    dest_base = physical_project_root(project_id)
    for src, rel in mappings.items():
        if not src.is_file():
            continue
        _copy_file(
            src,
            dest_base / rel,
            dry_run=dry_run,
            overwrite=overwrite,
            report=report,
            label="legacy-delivery",
        )

    net_mgmt = legacy_delivery / "net-mgmt"
    if net_mgmt.is_dir():
        for f in net_mgmt.rglob("*"):
            if f.is_file():
                dst_dir = dest_base / "早期介入/交付预案/输入文件/服务建议书"
                _copy_file(
                    f,
                    dst_dir / f.name,
                    dry_run=dry_run,
                    overwrite=overwrite,
                    report=report,
                    label="net-mgmt",
                )


def _pick_store_bucket(raw: dict[str, Any], project_id: str, key: str) -> list[Any]:
    bucket = raw.get(key) or {}
    if project_id in bucket and bucket[project_id]:
        return list(bucket[project_id])
    for alias in LEGACY_STORE_PROJECT_ALIASES:
        if alias in bucket and bucket[alias]:
            return list(bucket[alias])
    if len(bucket) == 1:
        only = next(iter(bucket.values()))
        if only:
            return list(only)
    return []


def _migrate_proposal_store(project_id: str, *, dry_run: bool, overwrite: bool, report: MigrationReport) -> None:
    dst = chapter57_store_path(project_id)
    if dst.is_file() and not overwrite:
        report.skipped.append(f"chapter57_store exists: {dst}")
        return

    for legacy in (legacy_global_store_path(), legacy_repo_data_store_path()):
        if not legacy.is_file():
            continue
        try:
            raw = json.loads(legacy.read_text(encoding="utf-8"))
        except Exception as exc:
            report.errors.append(f"proposal_store parse: {exc}")
            return

        per_project = {
            "net_plane_rows": _pick_store_bucket(raw, project_id, "net_plane_rows"),
            "room_rack_rows": _pick_store_bucket(raw, project_id, "room_rack_rows"),
            "net_mgmt_rows": _pick_store_bucket(raw, project_id, "net_mgmt_rows"),
            "cluster_device_rows": _pick_store_bucket(raw, project_id, "cluster_device_rows"),
        }

        if not any(per_project.values()):
            report.skipped.append(f"proposal_store: no rows for {project_id}")
            return

        if dry_run:
            report.copied.append(f"[dry-run] chapter57_store -> {dst}")
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(per_project, ensure_ascii=False, indent=2), encoding="utf-8")
        report.copied.append(f"chapter57_store -> {dst}")
        return


def _migrate_org_assets(*, dry_run: bool, overwrite: bool, report: MigrationReport) -> None:
    """Copy legacy mock org assets → BUSINESS_ROOT/org-assets (cross-project SSOT)."""
    src_root = _legacy_mock_assets_root()
    if src_root is None:
        report.skipped.append("org_assets: no legacy org-assets source")
        return
    dest_root = org_assets_root()
    if dest_root.resolve() == src_root.resolve():
        report.skipped.append("org_assets: source already at org-assets root")
        return
    for path in sorted(src_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src_root).as_posix()
        dst = dest_root / rel
        _copy_file(path, dst, dry_run=dry_run, overwrite=overwrite, report=report, label="org_assets")


def migrate(
    project_id: str,
    *,
    business_root: Path | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> MigrationReport:
    if business_root:
        import agent.config as cfg

        cfg.BUSINESS_ROOT = business_root.resolve()

    report = MigrationReport(project_id=project_id, business_root=str(BUSINESS_ROOT.resolve()))

    _migrate_tree(
        _legacy_mock_root(),
        project_id,
        dry_run=dry_run,
        overwrite=overwrite,
        report=report,
        label="mock_project",
    )
    # Skip re-copying the destination project tree onto itself.
    _migrate_legacy_delivery_files(project_id, dry_run=dry_run, overwrite=overwrite, report=report)
    _migrate_org_assets(dry_run=dry_run, overwrite=overwrite, report=report)
    _migrate_proposal_store(project_id, dry_run=dry_run, overwrite=overwrite, report=report)

    dest = physical_project_root(project_id)
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate proposal data to projects/{project_id}")
    parser.add_argument("--project-id", required=True, help="Target project UUID")
    parser.add_argument("--business-root", default="", help="Override AIDA_BUSINESS_ROOT")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--report", default="", help="Write JSON report to path")
    args = parser.parse_args()

    root = Path(args.business_root).resolve() if args.business_root else None
    report = migrate(
        args.project_id,
        business_root=root,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )

    summary = {
        "projectId": report.project_id,
        "businessRoot": report.business_root,
        "copied": len(report.copied),
        "skipped": len(report.skipped),
        "relocated": report.relocated,
        "errors": report.errors,
        "details": report.copied[:50],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.report:
        Path(args.report).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
