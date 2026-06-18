"""report_gen_run · 工勘报告生成（本地 mock 报告）."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..path_config import get_input_dir, get_output_dir, get_parse_dir, get_template_dir
from ._intent_guard import should_skip


def _get_survey_table(ctx: SkillContext) -> str | None:
    info_path = get_parse_dir() / "project_info.json"
    if info_path.exists():
        try:
            path = json.loads(info_path.read_text(encoding="utf-8")).get("survey_table_path", "")
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
    tables = sorted(get_output_dir().glob("*全量勘测结果表*.xlsx")) if get_output_dir().exists() else []
    return str(tables[0]) if tables else None


def _get_generation_cooling(ctx: SkillContext) -> str:
    gc = ctx.project.get("generation_cooling", "")
    if gc:
        return gc
    info_path = get_parse_dir() / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8")).get("generation_cooling", "")
        except Exception:
            pass
    return ""


def _read_project_info(ctx: SkillContext) -> dict:
    info_path = get_parse_dir() / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_project_info(ctx: SkillContext, info: dict) -> None:
    get_parse_dir().mkdir(parents=True, exist_ok=True)
    (get_parse_dir() / "project_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _mock_report_source(ctx: SkillContext) -> Path | None:
    patterns = [
        "*工勘报告*.pdf",
        "*工勘报告*.docx",
        "*report*.pdf",
        "*report*.docx",
    ]
    for folder in (get_input_dir(), get_output_dir(), get_template_dir()):
        if not folder.exists():
            continue
        for pat in patterns:
            matches = sorted(folder.glob(pat))
            if matches:
                return matches[0]
    return None


def _mock_report_output_path(ctx: SkillContext, source: Path) -> Path:
    activity = str(ctx.project.get("activity_id") or "ACT001").strip() or "ACT001"
    project = str(ctx.project.get("project_name") or "智算 Q3 · 客户甲一期").strip()
    room = str(ctx.project.get("room_name") or "A 机房").strip()
    suffix = source.suffix or ".pdf"
    safe = f"{activity}_{project}_{room}_工勘报告{suffix}"
    for ch in '<>:"/\\|?*':
        safe = safe.replace(ch, "_")
    return get_output_dir() / safe


_REPORT_REVIEW_INPUT = {
    "id": "report_review_choice",
    "label": "工勘报告已生成",
    "options": [
        {
            "label": "下载附件查看",
            "value": "download",
            "description": "报告已作为产物提供下载，确认后进入审批分发",
        },
        {
            "label": "直接发送审批",
            "value": "send_approval",
            "description": "不查看附件，直接进入审批邮件编辑",
        },
    ],
}


class ReportGenRunStep(BaseStep):
    key = "report_gen_run"
    name = "报告生成"
    artifacts_pattern = [
        "输出结果/*工勘报告*.pdf",
        "输出结果/*工勘报告*.docx",
    ]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        missing = []
        if _get_survey_table(ctx) is None and ctx.project.get("intent") != "report_gen":
            missing.append("输出结果/*全量勘测结果表*.xlsx")
        if _mock_report_source(ctx) is None:
            missing.append("输入文件/*工勘报告*.pdf")

        if missing:
            return {
                "ok": False,
                "missing": missing,
                "note": "mock 报告未就绪，请先放入本地工勘报告附件",
            }

        info = _read_project_info(ctx)
        if ctx.project.get("report_review_choice") or info.get("mock_report_path"):
            return {"ok": True, "missing": []}

        return {
            "ok": False,
            "missing": [],
            "need_inputs": [_REPORT_REVIEW_INPUT],
            "note": "撰写工勘报告已 mock：将使用本地已放好的工勘报告作为生成结果。",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        source = _mock_report_source(ctx)
        if source is None:
            raise RuntimeError("report_gen_run: 本地 mock 工勘报告不存在")

        get_output_dir().mkdir(parents=True, exist_ok=True)
        report_path = _mock_report_output_path(ctx, source)
        if source.resolve() != report_path.resolve():
            shutil.copy2(source, report_path)
        choice = str(ctx.project.get("report_review_choice") or "download")
        emit(f"[report_gen_run] mock 撰写工勘报告：{source.name}")
        emit(f"[report_gen_run] ✓ 工勘报告已就绪：{report_path.name}")
        if choice == "download":
            emit("[report_gen_run] 用户选择下载附件查看，报告已作为产物提供")
        else:
            emit("[report_gen_run] 用户选择直接发送审批，进入审批邮件编辑")

        info = _read_project_info(ctx)
        info.update({
            "mock_report_path": str(report_path),
            "mock_report_source": str(source),
            "mock_report_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_review_choice": choice,
        })
        _write_project_info(ctx, info)

        return {
            "metrics": {
                "report_mock": True,
                "report_review_choice": choice,
                "report_path": str(report_path),
            },
            "artifacts": [
                ctx.rel(report_path),
            ],
        }
