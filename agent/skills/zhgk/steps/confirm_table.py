"""
confirm_table · 勘测表确认

意图: survey_work 专属

HITL ChoiceCard：展示全量勘测结果表统计摘要，等待用户确认或要求重新生成。
  - confirm → project["table_confirmed"] = True，继续流程
  - redo    → 清空 table_confirmed，full_restart 从 filter_build 重新建表
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


def _get_survey_table(ctx: SkillContext) -> str | None:
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            path = json.loads(info_path.read_text(encoding="utf-8")).get("survey_table_path", "")
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
    tables = sorted(ctx.output_dir.glob("*全量勘测结果表*.xlsx")) if ctx.output_dir.exists() else []
    return str(tables[0]) if tables else None


def _survey_table_stats(survey_table_path: str) -> dict:
    """读取表格：统计行数和细分场景列表"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(survey_table_path, read_only=True, data_only=True)
        ws = wb.active
        rows = 0
        scenes: set[str] = set()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                break
            rows += 1
            if row[1]:  # 细分场景 (col index 1)
                scenes.add(str(row[1]).strip())
        wb.close()
        return {"rows": rows, "scenes": sorted(scenes)}
    except Exception:
        return {"rows": 0, "scenes": []}


class ConfirmTableStep(BaseStep):
    key = "confirm_table"
    name = "勘测表确认"
    artifacts_pattern = ["*勘测任务包*.zip"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        # 已经确认（HITL confirm 路径）
        if ctx.project.get("table_confirmed"):
            return {"ok": True, "missing": []}

        # 勘测表尚未生成
        survey_table = _get_survey_table(ctx)
        if not survey_table:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}

        # 生成摘要提示
        stats = _survey_table_stats(survey_table)
        scenes_preview = ", ".join(stats["scenes"][:3])
        if len(stats["scenes"]) > 3:
            scenes_preview += f"… 共 {len(stats['scenes'])} 个"
        note = (
            f"全量勘测结果表已生成：{stats['rows']} 条勘测项"
            + (f" / 细分场景: {scenes_preview}" if scenes_preview else "")
        )

        return {
            "ok": False,
            "missing": [],
            "need_inputs": [
                {
                    "id": "table_confirm_choice",
                    "label": "确认全量勘测结果表",
                    "options": [
                        {
                            "label": "✓ 确认，开始现场勘测",
                            "value": "confirm",
                            "description": note,
                        },
                        {
                            "label": "↩ 重新生成勘测表",
                            "value": "redo",
                            "description": "回退重新生成全量勘测结果表（保持代际制冷不变）",
                        },
                    ],
                }
            ],
            "note": note,
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        survey_table = _get_survey_table(ctx)
        stats = _survey_table_stats(survey_table) if survey_table else {"rows": 0, "scenes": []}

        emit("[confirm_table] ✓ 用户已确认全量勘测结果表")
        emit(f"[confirm_table] 总条目: {stats['rows']}")
        if stats["scenes"]:
            emit(f"[confirm_table] 细分场景: {stats['scenes']}")

        # v4：生成勘测任务包（供视频勘测下发 / 现场勘测下载，设计文档 Step 7a/7b）
        package_path = None
        if survey_table:
            try:
                from ..services.survey_task_package import (
                    build_survey_task_package, collect_on_site_items,
                )
                info: dict = {}
                info_path = ctx.runtime_dir / "project_info.json"
                if info_path.exists():
                    try:
                        info = json.loads(info_path.read_text(encoding="utf-8"))
                    except Exception:
                        info = {}
                on_site = collect_on_site_items(survey_table)
                package_path = build_survey_task_package(
                    survey_table,
                    str(ctx.output_dir),
                    project_name=info.get("项目名称", ""),
                    room_name=info.get("机房名称", ""),
                    activity_id=info.get("工勘活动ID", "") or info.get("activity_id", ""),
                    on_site_items=on_site,
                )
                emit(f"[confirm_table] ✓ 勘测任务包已生成：{os.path.basename(package_path)}"
                     f"（现场勘测 {len(on_site)} 条）")
            except Exception as e:  # noqa: BLE001
                emit(f"[confirm_table] [提示] 勘测任务包生成失败：{e}")

        return {
            "metrics": {
                "confirmed_rows": stats["rows"],
                "confirmed_scenes": stats["scenes"],
                "task_package": os.path.basename(package_path) if package_path else "",
            }
        }
