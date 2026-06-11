"""
intent_select · 意图选择

HITL ChoiceCard：让用户从 4 个意图中选择要执行的工作流。
选择结果写入 state["project"]["intent"]，后续步骤据此路由。

意图卡片（与 services/types.py Intent 对齐）:
  scene_suggest  — 场景建议（快速推荐，不做建表）
  survey_work    — 全流程工勘（建表 → 勘测 → 评估 → 复勘）
  supplement     — 补充勘测（追加数据条目到已有表）
  report_gen     — 生成报告（基于已完成勘测结果表）
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult

# 4 个意图选项（label/value/description 对齐 SDUI ChoiceCard）
INTENT_OPTIONS = [
    {
        "label": "全流程工勘",
        "value": "survey_work",
        "description": "从 BOQ 识别代际制冷 → 建勘测表 → 现场勘测 → AI 评估 → 问题清单 → 复勘",
    },
    {
        "label": "生成工勘报告",
        "value": "report_gen",
        "description": "基于已完成的全量勘测结果表，生成三件套 + Word 工勘报告",
    },
    {
        "label": "场景建议",
        "value": "scene_suggest",
        "description": "快速给出当前项目的勘测场景推荐（不建表、不做评估）",
    },
    {
        "label": "补充勘测",
        "value": "supplement",
        "description": "向已有勘测结果表追加数据类条目或自定义勘测项",
    },
]


class IntentSelectStep(BaseStep):
    key = "intent_select"
    name = "意图选择"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        """如果 intent 已在 project 里，跳过 HITL；否则要求用户选择。"""
        intent = ctx.project.get("intent", "")
        if intent:
            return {"ok": True, "missing": []}
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [
                {
                    "id": "intent_choice",
                    "label": "请选择本次工勘任务类型",
                    "options": INTENT_OPTIONS,
                }
            ],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        intent = ctx.project.get("intent", "")
        if not intent:
            emit("[intent_select] 等待用户选择意图（HITL）…")
            return {
                "hitl": {
                    "step": self.key,
                    "reason": "请选择本次工勘任务类型",
                    "need_inputs": [
                        {
                            "id": "intent_choice",
                            "label": "请选择本次工勘任务类型",
                            "options": INTENT_OPTIONS,
                        }
                    ],
                }
            }

        label_map = {o["value"]: o["label"] for o in INTENT_OPTIONS}
        emit(f"[intent_select] 意图已确认: {label_map.get(intent, intent)}")
        return {
            "metrics": {"intent": intent},
        }
