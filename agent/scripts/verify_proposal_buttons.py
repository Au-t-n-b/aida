"""Scripted verification for proposal buttons flow.

Simulates:
1) Save Draft      -> PUT /proposal/draft
2) Release Decide  -> POST /proposal/release-and-decide

Usage:
  python -m agent.scripts.verify_proposal_buttons --project-id 56A0TXN
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from agent.config import BUSINESS_ROOT
from agent.main import app


def _project_root(project_id: str) -> Path:
    return BUSINESS_ROOT / "projects" / project_id


def _collect_snapshot(project_id: str) -> dict[str, Any]:
    root = _project_root(project_id) / "早期介入"
    proposal_parse = root / "交付预案" / "解析结果"
    proposal_out = root / "交付预案" / "输出结果"
    contract_parse = root / "合同" / "解析结果"

    parse_json = sorted(str(p.relative_to(root)) for p in proposal_parse.rglob("*.json"))
    parse_xlsx = sorted(str(p.relative_to(root)) for p in proposal_parse.rglob("*.xlsx"))
    out_json = sorted(str(p.relative_to(root)) for p in proposal_out.rglob("*.json"))
    out_xlsx = sorted(str(p.relative_to(root)) for p in proposal_out.rglob("*.xlsx"))
    contract_json = sorted(str(p.relative_to(root)) for p in contract_parse.rglob("*.json"))

    return {
        "counts": {
            "proposal_parse_json": len(parse_json),
            "proposal_parse_xlsx": len(parse_xlsx),
            "proposal_out_json": len(out_json),
            "proposal_out_xlsx": len(out_xlsx),
            "contract_parse_json": len(contract_json),
        },
        "keyPaths": {
            "proposal_parse_json": parse_json[:30],
            "proposal_out_json": out_json[:30],
            "proposal_out_xlsx": out_xlsx[:30],
        },
    }


def _api_headers(role: str, account: str) -> dict[str, str]:
    return {
        "X-User-Role": role,
        "X-User-Account": account,
    }


def _must_ok(resp, action: str) -> dict[str, Any]:
    if resp.status_code >= 400:
        raise RuntimeError(f"{action} failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError(f"{action} invalid response: {payload}")
    return payload["data"]


def verify(project_id: str, role: str, account: str) -> dict[str, Any]:
    client = TestClient(app)
    headers = _api_headers(role, account)
    base = f"/api/v1/projects/{project_id}/proposal"

    before = _collect_snapshot(project_id)

    draft_data = _must_ok(client.get(f"{base}/draft", headers=headers), "get draft")
    etag = ((draft_data.get("manifest") or {}).get("etag")) if isinstance(draft_data, dict) else None

    save_headers = dict(headers)
    if etag:
        save_headers["If-Match"] = str(etag)
    save_payload = {"manualChangeLog": draft_data.get("cumulativeChangeLog") or []}
    save_data = _must_ok(
        client.put(f"{base}/draft", headers=save_headers, json=save_payload),
        "save draft",
    )

    release_payload = {"changeRecords": []}
    release_data = _must_ok(
        client.post(f"{base}/release-and-decide", headers=headers, json=release_payload),
        "release and decide",
    )

    after = _collect_snapshot(project_id)
    new_version = release_data.get("proposalVersion")
    version_dir = _project_root(project_id) / "早期介入" / "交付预案" / "输出结果" / "预案版本" / str(new_version)
    version_files = sorted(str(p.relative_to(_project_root(project_id) / "早期介入")) for p in version_dir.rglob("*") if p.is_file()) if version_dir.exists() else []

    return {
        "projectId": project_id,
        "saveDraft": {
            "status": save_data.get("status"),
            "workingVersionLabel": save_data.get("workingVersionLabel"),
            "etag": save_data.get("etag"),
        },
        "releaseAndDecide": {
            "proposalVersion": new_version,
            "status": release_data.get("status"),
            "sideEffects": release_data.get("sideEffects") or {},
        },
        "snapshotBefore": before,
        "snapshotAfter": after,
        "newVersionFiles": version_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify proposal save/release button flow.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--role", default="td")
    parser.add_argument("--account", default="script-verify")
    args = parser.parse_args()

    result = verify(args.project_id, args.role, args.account)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
