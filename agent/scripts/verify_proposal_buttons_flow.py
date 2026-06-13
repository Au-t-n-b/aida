"""Scripted verification for proposal buttons flow.

Simulates:
1) Save Draft  (PUT /proposal/draft)
2) Release and Decide (POST /proposal/release-and-decide)

Outputs a JSON report including API responses and directory snapshots.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib import error, request

from agent.config import BUSINESS_ROOT


def _api(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None
    req_headers = dict(headers)
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = request.Request(url=url, method=method, headers=req_headers, data=data)
    try:
        with request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, json.loads(payload)
    except error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        return exc.code, parsed


def _snapshot_dir(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "jsonCount": 0, "xlsxCount": 0, "files": []}
    files = [str(p.relative_to(path)).replace("\\", "/") for p in sorted(path.rglob("*")) if p.is_file()]
    return {
        "exists": True,
        "jsonCount": sum(1 for f in files if f.endswith(".json")),
        "xlsxCount": sum(1 for f in files if f.endswith(".xlsx")),
        "files": files,
    }


def _build_snapshot(project_id: str) -> dict[str, Any]:
    base = BUSINESS_ROOT / "projects" / project_id / "早期介入"
    proposal_parse = base / "交付预案" / "解析结果"
    proposal_out = base / "交付预案" / "输出结果"
    contract_parse = base / "合同" / "解析结果"
    return {
        "proposalParse": _snapshot_dir(proposal_parse),
        "proposalOutput": _snapshot_dir(proposal_out),
        "contractParse": _snapshot_dir(contract_parse),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify proposal save->release flow.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:7401")
    parser.add_argument("--role", default="td")
    parser.add_argument("--account", default="script-verify")
    parser.add_argument("--report-path", default="")
    args = parser.parse_args()

    project_id = args.project_id
    base = args.base_url.rstrip("/")
    root = f"{base}/api/v1/projects/{project_id}/proposal"
    headers = {
        "X-User-Role": args.role,
        "X-User-Account": args.account,
    }

    before = _build_snapshot(project_id)

    save_status, save_payload = _api(
        "PUT",
        f"{root}/draft",
        headers=headers,
        body={
            "manualChangeLog": [
                {"chapter": "2", "changeDescription": "脚本化验证保存草稿"},
            ]
        },
    )

    release_status, release_payload = _api(
        "POST",
        f"{root}/release-and-decide",
        headers=headers,
        body={
            "changeRecords": [
                {"seq": 1, "chapter": "2", "description": "脚本化验证发布"},
            ]
        },
    )

    after = _build_snapshot(project_id)
    report = {
        "projectId": project_id,
        "saveDraft": {"status": save_status, "payload": save_payload},
        "releaseAndDecide": {"status": release_status, "payload": release_payload},
        "snapshotBefore": before,
        "snapshotAfter": after,
    }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
