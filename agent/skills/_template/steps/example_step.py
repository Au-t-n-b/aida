"""
模板 · 一个业务 step。复制为 agent/skills/<name>/steps/<your_step>.py。

要点（对应 START_HERE §4 / AGENT_QUICKSTART §4 step 骨架）：
  - key / name / artifacts_pattern 三件套
  - check_inputs() 决定 HITL 软中断：missing 非空 → 框架写 hitl.need_files → 路由 END
  - run() 业务：emit 日志 / ctx.invoke_llm 调模型 / ctx.call_tool 调工具 / 写产物 / 返回 metrics
  - ⚠️ check_inputs 的必填路径 = run 真正读的路径（否则 HITL 清单漂移，SKILL-DEV §9）
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult


class ExampleStep(BaseStep):
    key = "example_step"          # ✏️ 必改：小写下划线；必须与 SKILL.md「后端节点」表一致
    name = "示例步骤"              # ✏️ 必改：中文显示名
    artifacts_pattern = [          # 可选：相对 work_root 的产物路径（可下载）
        # "ProjectData/Output/<your_output>.xlsx",
    ]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        """前置文件校验。missing 非空即触发 HITL 软中断。"""
        required = [
            # "ProjectData/Input/<your_input>.xlsx",
        ]
        found, missing = [], []
        for rel in required:
            (found if (ctx.work_root / rel).exists() else missing).append(rel)
        return {"ok": not missing, "missing": missing, "found": found,
                "note": "<给用户的补料提示>"}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 开始 {self.name}…")

        # ── 业务逻辑（按需）──
        # 输入目录： ctx.input_dir / ctx.start_dir ；产物写： ctx.runtime_dir / ctx.output_dir
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        # ── 调 LLM（统一入口，自动进 Langfuse；禁裸 import openai/anthropic）──
        # resp = ctx.invoke_llm(
        #     [("system", "你是…"), ("human", "…")],
        #     step_key=self.key,
        # )
        # text = resp.content if isinstance(resp.content, str) else str(resp.content)

        # ── 调工具（统一入口，自动进 trace；禁绕过 registry）──
        # out = ctx.call_tool("read_file", {"path": "..."}, step_key=self.key, emit=emit)

        emit(f"[{self.key}] 完成")
        return {
            "metrics": {
                # "<业务指标>": ...,
            },
        }
