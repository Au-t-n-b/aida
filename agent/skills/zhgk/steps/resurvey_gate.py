"""
resurvey_gate · 复勘检查门控

意图: survey_work 专属

流程:
  1. get_items_needing_resurvey() — 找出「不满足/无法识别/未勘测」条目
  2. 若无需复勘 → 直接放行
  3. 若有需复勘条目 → HITL ChoiceCard（进行复勘 / 跳过）
  4. "resurvey" → wait_survey 重新触发（apply_resume_payload 清 resurvey_decision 以激活复勘）
  5. "skip_resurvey" / 其他 → 直接进入下一步
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


class ResurveyGateStep(BaseStep):
    key = "resurvey_gate"
    name = "复勘检查门控"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        # 已经有门控决策
        if ctx.project.get("resurvey_decision"):
            return {"ok": True, "missing": []}

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}

        # 检查是否有需要复勘的条目
        from ..services.resurvey_manager import get_items_needing_resurvey
        try:
            items = get_items_needing_resurvey(survey_table)
        except Exception:
            items = []

        if not items:
            # 全部满足/不涉及，无需复勘
            return {"ok": True, "missing": []}

        count = len(items)
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [
                {
                    "id": "resurvey_choice",
                    "label": f"发现 {count} 条条目需要关注",
                    "options": [
                        {
                            "label": f"安排复勘（{count} 条）",
                            "value": "resurvey",
                            "description": "重新上传已复勘的结果表后继续评估",
                        },
                        {
                            "label": "跳过，直接进入下一步",
                            "value": "skip_resurvey",
                            "description": "接受当前评估结果，继续生成报告",
                        },
                    ],
                }
            ],
            "note": f"以下 {count} 条勘测项的评估结论为「不满足/无法识别/未勘测」",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        survey_table = _get_survey_table(ctx)
        decision = ctx.project.get("resurvey_decision", "")

        # 若 check_inputs 直接放行（无需复勘）
        if not decision:
            if survey_table:
                from ..services.resurvey_manager import get_items_needing_resurvey
                try:
                    items = get_items_needing_resurvey(survey_table)
                except Exception:
                    items = []
                if not items:
                    emit("[resurvey_gate] ✓ 无需复勘，全部条目满足/不涉及")
                    return {"metrics": {"resurvey_needed": False, "resurvey_count": 0}}
            emit("[resurvey_gate] ✓ 跳过复勘门控")
            return {"metrics": {"resurvey_needed": False}}

        # 有 resurvey 决策
        resurvey_count = 0
        if survey_table:
            from ..services.resurvey_manager import get_items_needing_resurvey
            try:
                resurvey_count = len(get_items_needing_resurvey(survey_table))
            except Exception:
                pass

        if decision == "resurvey":
            emit(f"[resurvey_gate] ✓ 安排复勘：{resurvey_count} 条待复勘项")
            emit("[resurvey_gate] 请上传复勘结果表后 resume 继续")
        else:
            emit(f"[resurvey_gate] ✓ 跳过复勘（decision={decision}），继续后续流程")

        return {
            "metrics": {
                "resurvey_needed": decision == "resurvey",
                "resurvey_count": resurvey_count,
                "resurvey_decision": decision,
            }
        }
