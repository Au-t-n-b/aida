"""
将源 PDF 加工为项目演示工勘报告，并可选同步到 ZHGK 工作区 Input/。

真相源（随项目 push Gitea）：
  {AIDA_BUSINESS_ROOT}/projects/{project_id}/交付作业/智慧工勘/输入文件/本地工勘报告.pdf

用法（仓库根目录）：
  python agent/scripts/sync_zhgk_mock_report.py
  python agent/scripts/sync_zhgk_mock_report.py --project-name "京东3期" --dest-workspace
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC = REPO_ROOT.parent / "工勘报告.pdf"
DEFAULT_OLD_NAME = "字节跳动"

sys.path.insert(0, str(REPO_ROOT))
from agent.config import BUSINESS_ROOT  # noqa: E402
from agent.skills.zhgk.demo_assets import (  # noqa: E402
    DEFAULT_DEMO_PROJECT_ID,
    MOCK_REPORT_FILENAME,
    mock_report_manifest_path,
    mock_report_project_path,
    seed_mock_report_to_workspace,
)


def _zhgk_input_dir() -> Path:
    raw = os.environ.get("ZHGK_ROOT", "").strip()
    root = Path(raw).expanduser().resolve() if raw else Path.home() / ".nanobot" / "workspace" / "skills" / "zhgk"
    return root / "ProjectData" / "Input"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _replace_project_name(src: Path, dest: Path, *, old_name: str, new_name: str) -> int:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("需要 PyMuPDF：pip install pymupdf") from exc

    doc = fitz.open(src)
    replaced = 0
    for page in doc:
        rects = page.search_for(old_name)
        for rect in rects:
            page.add_redact_annot(rect, fill=(1, 1, 1))
        if rects:
            page.apply_redactions()
            for rect in rects:
                page.insert_text(
                    (rect.x0, rect.y1 - 2),
                    new_name,
                    fontsize=11,
                    fontname="china-s",
                    color=(0, 0, 0),
                )
                replaced += 1

    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dest, garbage=4, deflate=True)
    doc.close()
    return replaced


def _write_manifest(
    *,
    src: Path,
    project_pdf: Path,
    project_id: str,
    project_name: str,
    replaced: int,
    workspace_copy: Path | None,
) -> None:
    payload = {
        "artifact": MOCK_REPORT_FILENAME,
        "role": "zhgk report_gen_run 演示工勘报告（随项目 demo 数据入库）",
        "scope": "project",
        "project_id": project_id,
        "project_path": str(project_pdf.relative_to(BUSINESS_ROOT)).replace("\\", "/"),
        "runtime_path": "ProjectData/Input/本地工勘报告.pdf",
        "source_pdf": str(src),
        "project_name": project_name,
        "replaced_from": DEFAULT_OLD_NAME,
        "replacements": replaced,
        "fixture_sha256": _sha256(project_pdf),
        "fixture_bytes": project_pdf.stat().st_size,
        "workspace_copy": str(workspace_copy) if workspace_copy else None,
        "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sync_script": "agent/scripts/sync_zhgk_mock_report.py",
        "note": "入场评估标准表、工勘常见高风险库为组织资产，不随项目打包，由 filter_build HITL 自行上传。",
    }
    manifest = mock_report_manifest_path(project_id)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="同步 zhgk 演示工勘报告到项目 demo 数据")
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="源 PDF 路径")
    ap.add_argument("--project-id", default=DEFAULT_DEMO_PROJECT_ID, help="演示项目 UUID")
    ap.add_argument("--project-name", default="京东3期", help="写入 PDF 的项目名称")
    ap.add_argument("--old-name", default=DEFAULT_OLD_NAME, help="源 PDF 中被替换的项目名")
    ap.add_argument(
        "--dest-workspace",
        action="store_true",
        help="同时复制到 ZHGK_ROOT/ProjectData/Input/",
    )
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.is_file():
        print(f"[sync-mock-report] 源文件不存在: {src}")
        return 1

    project_pdf = mock_report_project_path(args.project_id)
    replaced = _replace_project_name(
        src,
        project_pdf,
        old_name=args.old_name,
        new_name=args.project_name,
    )
    print(f"[sync-mock-report] 项目演示资产已写入: {project_pdf}")
    print(f"[sync-mock-report] 项目名 {args.old_name!r} → {args.project_name!r}（{replaced} 处）")

    workspace_copy: Path | None = None
    if args.dest_workspace:
        workspace_copy = seed_mock_report_to_workspace(
            _zhgk_input_dir(),
            project_id=args.project_id,
        )
        if workspace_copy:
            print(f"[sync-mock-report] 工作区已同步: {workspace_copy}")

    _write_manifest(
        src=src,
        project_pdf=project_pdf,
        project_id=args.project_id,
        project_name=args.project_name,
        replaced=replaced,
        workspace_copy=workspace_copy,
    )
    print(f"[sync-mock-report] 追踪清单: {mock_report_manifest_path(args.project_id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
