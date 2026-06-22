#!/usr/bin/env python3
"""Sync local project tree → remote datacenter (diff + bulk upload).

Usage:
  python agent/scripts/sync_project_files_to_datacenter.py \\
    --project-id 70e5ca737ae5433e9f0f3134d216acf7 --dry-run
  python agent/scripts/sync_project_files_to_datacenter.py \\
    --project-id 70e5ca737ae5433e9f0f3134d216acf7
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import httpx

from agent.config import BUSINESS_ROOT
from agent.constants.org_assets_paths import org_assets_root
from agent.services.dc_path_mapper import map_local_file, map_project_relative, org_assets_relative
from shared.datacenter import DataCenterClient, DataCenterError, SemanticFileRef
from shared.datacenter.config import datacenter_base, http_proxy, ssl_verify


async def _login(username: str, password: str) -> str:
    base = datacenter_base()
    async with httpx.AsyncClient(
        base_url=base,
        timeout=httpx.Timeout(30.0, connect=10.0),
        proxy=http_proxy(),
        verify=ssl_verify(),
        trust_env=False,
    ) as client:
        resp = await client.post(
            "/api/v1/users/login",
            json={"username": username, "password": password},
        )
        body = resp.json()
        if int(body.get("code", -1)) != 0:
            raise DataCenterError(int(body.get("code", -1)), str(body.get("message") or "登录失败"))
        token = (body.get("data") or {}).get("token")
        if not token:
            raise DataCenterError(500, "登录响应缺少 token")
        return str(token)


def _unwrap(payload: dict[str, Any]) -> Any:
    if "code" in payload and "data" in payload:
        if int(payload.get("code", -1)) != 0:
            raise DataCenterError(int(payload.get("code", -1)), str(payload.get("message") or "error"))
        return payload.get("data")
    return payload


async def _fetch_project_tree(token: str, project_id: str) -> set[str]:
    base = datacenter_base()
    async with httpx.AsyncClient(
        base_url=base,
        timeout=httpx.Timeout(60.0, connect=15.0),
        proxy=http_proxy(),
        verify=ssl_verify(),
        trust_env=False,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        resp = await client.get(f"/api/v1/projects/{project_id}/tree")
        if resp.status_code >= 400:
            raise DataCenterError(resp.status_code, f"tree HTTP {resp.status_code}: {resp.text[:300]}")
        data = _unwrap(resp.json())
    paths: set[str] = set()

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes or []:
            if node.get("type") == "file":
                lp = str(node.get("logicalPath") or "").replace("\\", "/").strip("/")
                if lp:
                    paths.add(lp)
            walk(node.get("children") or [])

    walk(data.get("tree") or [])
    return paths


def _collect_local_files(project_root: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    if not project_root.is_dir():
        return out
    for path in sorted(project_root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(project_root).as_posix()
            out.append((path, rel))
    return out


@dataclass
class SyncReport:
    project_id: str
    uploaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)


async def _upload_file(client: DataCenterClient, mapped_ref: SemanticFileRef, path: Path, file_name: str) -> None:
    content = path.read_bytes()
    ref = SemanticFileRef(
        project_id=mapped_ref.project_id,
        module_code=mapped_ref.module_code,
        file_stage=mapped_ref.file_stage,
        folder_sub_path=mapped_ref.folder_sub_path,
        file_name=file_name,
    )
    await client.upload_file(ref, content, file_name)


async def _sync_org_assets(
    client: DataCenterClient,
    remote_paths: set[str],
    *,
    dry_run: bool,
    overwrite: bool,
    report: SyncReport,
) -> None:
    root = org_assets_root()
    if not root.is_dir():
        report.skipped.append("org-assets: no local directory")
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = f"org-assets/{path.relative_to(root).as_posix()}"
        mapped = org_assets_relative(rel)
        if mapped is None:
            report.unmapped.append(rel)
            continue
        if rel in remote_paths and not overwrite:
            report.skipped.append(f"exists: {rel}")
            continue
        if dry_run:
            report.uploaded.append(f"[dry-run] {rel}")
            continue
        try:
            await _upload_file(client, mapped.ref, path, path.name)
            report.uploaded.append(rel)
        except Exception as exc:
            report.failed.append(f"{rel}: {exc}")


async def run_sync(
    project_id: str,
    *,
    local_root: Path | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
    include_org_assets: bool = False,
    token: str | None = None,
    username: str = "",
    password: str = "",
) -> SyncReport:
    report = SyncReport(project_id=project_id)
    if not token:
        if username and password:
            token = await _login(username, password)
        else:
            token = os.environ.get("DC_TOKEN", "").strip() or None
    if not token:
        raise SystemExit("需要 --token / DC_TOKEN 或 --username + --password 登录")

    project_root = local_root or (BUSINESS_ROOT / "projects" / project_id)
    remote_paths = await _fetch_project_tree(token, project_id)
    client = DataCenterClient(token)

    for path, rel in _collect_local_files(project_root):
        mapped = map_project_relative(project_id, rel)
        if mapped is None:
            report.unmapped.append(rel)
            continue
        logical = mapped.logical_path
        if logical in remote_paths and not overwrite:
            report.skipped.append(f"exists: {logical}")
            continue
        file_name = mapped.ref.file_name or path.name
        if dry_run:
            report.uploaded.append(f"[dry-run] {logical}")
            continue
        try:
            await _upload_file(client, mapped.ref, path, file_name)
            report.uploaded.append(logical)
        except Exception as exc:
            report.failed.append(f"{logical}: {exc}")

    if include_org_assets:
        org_remote = {p for p in remote_paths if p.startswith("org-assets/")}
        await _sync_org_assets(client, org_remote, dry_run=dry_run, overwrite=overwrite, report=report)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local project files to datacenter")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--local-root", default="", help="Override projects/{id} root")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--include-org-assets", action="store_true")
    parser.add_argument("--token", default="")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--report", default="", help="Output JSON report path")
    args = parser.parse_args()

    local_root = Path(args.local_root).resolve() if args.local_root else None
    try:
        report = asyncio.run(
            run_sync(
                args.project_id,
                local_root=local_root,
                dry_run=args.dry_run,
                overwrite=args.overwrite,
                include_org_assets=args.include_org_assets,
                token=args.token.strip() or None,
                username=args.username.strip() or os.environ.get("DC_USERNAME", "").strip(),
                password=args.password or os.environ.get("DC_PASSWORD", ""),
            )
        )
    except (DataCenterError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    out_path = (
        Path(args.report)
        if args.report
        else _REPO / "data" / f"sync-dc-report-{args.project_id}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "projectId": report.project_id,
        "uploaded": report.uploaded,
        "skipped": report.skipped,
        "failed": report.failed,
        "unmapped": report.unmapped,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nReport: {out_path}")
    if report.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
