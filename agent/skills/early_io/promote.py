"""解析结果 → 输出结果 promote · 对齐 IPO SSOT。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agent.proposal.chapter_excel import export_chapter_xlsx
from agent.proposal.chapter_registry import CHAPTER_BY_KEY

from .output_tables import PROPOSAL_OUTPUT_TABLES, OutputTableSpec, RowsEnvelope
from .paths import EarlyIoPaths


@dataclass
class PromoteResult:
    xlsx_name: str
    status: Literal["written", "skipped", "empty", "error"]
    path: str = ""
    row_count: int = 0
    message: str = ""


def load_parse_rows(path: Path, envelope: RowsEnvelope) -> tuple[list[dict[str, Any]], str]:
    """从解析 JSON 读取行列表。返回 (rows, error_message)。"""
    if not path.is_file():
        return [], f"文件不存在: {path}"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return [], f"JSON 读取失败: {e}"

    if envelope == "array":
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)], ""
        return [], "期望 JSON 数组"

    if envelope == "cases":
        if isinstance(raw, dict) and isinstance(raw.get("cases"), list):
            return [r for r in raw["cases"] if isinstance(r, dict)], ""
        return [], "期望 {\"cases\": [...]}"

    if envelope == "rows":
        if isinstance(raw, dict) and isinstance(raw.get("rows"), list):
            return [r for r in raw["rows"] if isinstance(r, dict)], ""
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)], ""
        return [], "期望 {\"rows\": [...]} 或数组"

    # auto
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)], ""
    if isinstance(raw, dict):
        for key in ("rows", "cases", "items"):
            val = raw.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)], ""
    return [], "无法识别 JSON 结构（auto）"


def _latest_parse_file(io: EarlyIoPaths, spec: OutputTableSpec) -> Path | None:
    candidates: list[Path] = []
    for rel_dir in spec.parse_dirs:
        root = io.project_root / rel_dir.replace("\\", "/")
        if not root.is_dir():
            continue
        candidates.extend(sorted(root.glob(spec.parse_glob)))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _chapter_spec(chapter_key: str | None):
    if not chapter_key:
        return None
    return CHAPTER_BY_KEY.get(chapter_key)


def promote_table(
    io: EarlyIoPaths,
    spec: OutputTableSpec,
    *,
    proposal_version: str = "草稿",
) -> PromoteResult:
    out_path = io.proposal_output_table(spec.xlsx_name)

    if spec.upstream_writes_output and out_path.is_file():
        return PromoteResult(
            spec.xlsx_name,
            "skipped",
            path=io.rel(out_path),
            message="上游已写入输出结果，跳过",
        )

    if spec.xlsx_name == "预案版本信息表.xlsx":
        return PromoteResult(
            spec.xlsx_name,
            "skipped",
            path=io.rel(out_path) if out_path.is_file() else "",
            message="版本表由 release 分支写入",
        )

    parse_file = _latest_parse_file(io, spec)
    rows: list[dict[str, Any]] = []
    if parse_file is not None:
        rows, err = load_parse_rows(parse_file, spec.rows_envelope)
        if err and not rows:
            return PromoteResult(spec.xlsx_name, "error", message=err)

    chapter = _chapter_spec(spec.chapter_key)
    payload: dict[str, Any] = {
        "rows": rows,
        "proposalVersion": proposal_version,
    }
    if chapter:
        payload["chapterKey"] = chapter.key
        payload["chapterTitle"] = chapter.label

    try:
        export_chapter_xlsx(out_path, chapter, payload)
    except Exception as e:
        return PromoteResult(spec.xlsx_name, "error", message=str(e))

    status: Literal["written", "empty"] = "empty" if not rows else "written"
    rel = io.rel(out_path)
    return PromoteResult(
        spec.xlsx_name,
        status,
        path=rel,
        row_count=len(rows),
        message=f"来源 {parse_file.name}" if parse_file else "无解析输入，仅表头",
    )


def promote_all_tables(
    io: EarlyIoPaths,
    *,
    proposal_version: str = "草稿",
    skip_version_table: bool = True,
) -> list[PromoteResult]:
    results: list[PromoteResult] = []
    for spec in PROPOSAL_OUTPUT_TABLES:
        if skip_version_table and spec.xlsx_name == "预案版本信息表.xlsx":
            continue
        results.append(
            promote_table(io, spec, proposal_version=proposal_version)
        )
    return results
