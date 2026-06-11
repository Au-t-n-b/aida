"""
模板 · skill-as-tool（会话唤起）。复制为 agent/tools/run_<name>.py。

标准模式（范式 §3.5 两形态一底座 / TOOL-DEVELOPMENT §5）：
  - 工具 execute **只返回唤起意图**（即时返回，符合工具同步语义）
  - ❌ 不在 execute 里跑 LangGraph（会阻塞、无 SSE）
  - 真正长流程由 /agent/<name>/start + /stream 承接
  - chat_engine 识别 action="launch_<name>" → yield skill_launch → 前端启动并订阅进度

全局替换：xxx → skill id；Xxx → 类名前缀。
注册：加入 agent/tools/__init__.py 的 DEFAULT_TOOLS。
"""
from __future__ import annotations
from typing import Any

from .base import Tool


class RunXxxTool(Tool):
    @property
    def name(self) -> str:
        return "run_xxx"                       # ✏️ 必改

    @property
    def description(self) -> str:               # ✏️ 必改：决定模型召回，写清「何时调用」
        return (
            "启动 <模块> Agent 全流程（… → … → …），并在会话中实时展示推进。"
            "当用户要求「…」时调用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_code": {"type": "string", "description": "项目编码", "minLength": 1},
                # <按需增加业务参数>
            },
            "required": ["project_code"],
        }

    def execute(self, project_code: str, **_: Any) -> Any:
        try:
            # 读真实步骤结构（类属性，不实例化 / 不读 SKILL.md / 不碰 LLM）
            from agent.skills.xxx.skill import XxxSkill   # ✏️ 必改
            steps = [{"step": s.key, "name": s.name} for s in XxxSkill.steps]
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"读取 xxx 流程失败：{e}"}

        return {
            "ok": True,
            "action": "launch_xxx",            # ✏️ 必改：chat_engine 据此 yield skill_launch
            "skill": "xxx",                    # ✏️ 必改
            "project_code": project_code,
            "steps": steps,
            "note": f"<模块>流程已就绪（{len(steps)} 步），正在为 {project_code} 启动；"
                    f"请在会话中的进度卡查看实时推进。",
        }
