"""
resurvey_gate · 复勘检查门控

意图: survey_work 专属

流程:
  1. get_items_needing_resurvey() — 找出「不满足/无法识别/未勘测」条目
  2. 若无需复勘 → 直接放行
  3. 若有需复勘条目 → HITL ChoiceCard（进行复勘 / 跳过）
  4. "resurvey" → 再选择复勘方式（下发到 App / 本地人工上传）
  5. "dispatch" → task_dispatch 重新下发复勘任务；"skip" → wait_survey 等待本地上传
  6. "skip_resurvey" / 其他 → 直接进入下一步
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

        decision = ctx.project.get("resurvey_decision")
        if decision == "resurvey" and not ctx.project.get("resurvey_dispatch_decision"):
            count = len(items)
            return {
                "ok": False,
                "missing": [],
                "need_inputs": [
                    {
                        "id": "resurvey_dispatch_decision",
                        "label": f"选择复勘方式（{count} 条）",
                        "options": [
                            {
                                "label": "下发复勘任务到现场 App",
                                "value": "dispatch",
                                "description": "仅将需复勘条目打包为新任务，经邮件链路回传后自动合并",
                            },
                            {
                                "label": "本地人工复勘（上传表）",
                                "value": "skip",
                                "description": "现场填写复勘后的全量勘测结果表，再人工上传继续评估",
                            },
                        ],
                    }
                ],
                "note": f"复勘方式需要确认：本轮共有 {count} 条待复勘项",
            }

        # 已经有完整门控决策
        if decision:
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
                            "description": "下一步选择复勘方式：下发到现场 App 或本地人工上传",
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
            method = str(ctx.project.get("resurvey_dispatch_decision") or "").strip()
            if method == "dispatch":
                emit("[resurvey_gate] 复勘方式：下发到现场 App")
                route_to = "task_dispatch"
            else:
                emit("[resurvey_gate] 复勘方式：本地人工上传")
                route_to = "wait_survey"
            return {
                "current_step": route_to,
                "route_to": route_to,
                "metrics": {
                    "resurvey_needed": True,
                    "resurvey_count": resurvey_count,
                    "resurvey_decision": decision,
                    "resurvey_dispatch_decision": method or "skip",
                },
            }
        else:
            emit(f"[resurvey_gate] ✓ 跳过复勘（decision={decision}），继续后续流程")

        return {
            "metrics": {
                "resurvey_needed": decision == "resurvey",
                "resurvey_count": resurvey_count,
                "resurvey_decision": decision,
            }
        }
