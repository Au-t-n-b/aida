"""
RunSurveyTool · 把「智慧工勘 Skill」包装成会话可调用的工具（skill-as-tool）

会话 ReAct 里说「帮我跑工勘」→ 模型自主调用本工具 → 唤起 zhgk。

职责边界（§3.5 两形态一底座）：
  - 本工具是「返回唤起意图 + 流程计划」（即时返回，符合工具同步语义）
  - 真正的异步长流程（5 step / astream / SSE）由 /agent/zhgk/start 承接、/agent/zhgk/stream 推进
  - 缝合方式：工具返回 action="launch_zhgk"，chat_engine 据此 yield 一个 skill_launch 事件，
    前端收到后拿真 run_id 启动并订阅 zhgk 进度流 —— 于是「聊着聊着把工勘跑了」。

这里读取 zhgk 的**真实**步骤结构（非 mock），既证明会话与 Skill 已打通，
也让模型能把"会经过哪几步"如实告诉用户。
"""
from __future__ import annotations

from typing import Any

from .base import Tool


class RunSurveyTool(Tool):
    @property
    def name(self) -> str:
        return "run_survey"

    @property
    def description(self) -> str:
        return (
            "启动智慧工勘 Agent 全流程（环境预检 → 场景筛选 → 勘测汇总 → 评估报告 → 审批分发），"
            "并在会话中实时展示推进。当用户要求「跑工勘 / 启动工勘 / 评估机房 / 生成工勘报告」时调用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_code": {"type": "string", "description": "项目编码，如 K1903", "minLength": 1},
                "project_name": {"type": "string", "description": "项目名称（可选）"},
                "scenario_run": {"type": "string", "description": "作业场景，如 训推一体（可选）"},
            },
            "required": ["project_code"],
        }

    def execute(
        self,
        project_code: str,
        project_name: str = "",
        scenario_run: str = "训推一体",
        **_: Any,
    ) -> Any:
        try:
            # 读 zhgk 真实步骤（类属性，不实例化 / 不读 SKILL.md / 不碰 LLM）
            from agent.skills.zhgk.skill import ZhgkSkill
            steps = [{"step": s.key, "name": s.name} for s in ZhgkSkill.steps]
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"读取 zhgk 流程失败：{e}"}

        return {
            "ok": True,
            "action": "launch_zhgk",   # ← chat_engine 据此 yield skill_launch，前端启动并订阅进度
            "skill": "zhgk",
            "project_code": project_code,
            "project_name": project_name,
            "scenario_run": scenario_run,
            "steps": steps,
            "note": f"智慧工勘流程已就绪（{len(steps)} 步），正在为 {project_code} 启动；"
                    f"请在会话中的工勘卡片查看实时推进。",
        }
