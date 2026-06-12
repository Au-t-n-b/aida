"""
step 6 · 设备名称替换（Raw Skill §6 naming_replace · 可选步骤 · A013）

调用 a3 a3-device-naming-workflow · offline_device_naming_pipeline.py replace-lld。
无设备清单/命名映射时优雅跳过（不 HITL）。
"""
from __future__ import annotations

from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from ..pipelines.a3_bridge import run_command

_NAMING_HINTS = ("设备清单", "命名映射", "naming")


class NamingReplaceStep(BaseStep):
    key = "naming_replace"
    name = "设备名称替换"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        from agent.sdui.projector_base import collect_metrics
        m = collect_metrics(state)
        if m.get("sd_mode") in ("single", "batch"):
            emit(f"[{self.key}] 模式 {m.get('sd_mode')} → 跳过设备名称替换（仅完整交付执行）")
            return {
                "logs": ["[naming_replace] 非完整交付模式，跳过命名替换"],
                "metrics": {"naming_status": "skipped", "naming_source": ""},
            }

        # 用户在「输入执行计划」(stage_select) 选择跳过名称替换 → 直接 ZTP
        stage = (ctx.project or {}).get("stage") or {}
        if stage.get("chosen") and not stage.get("naming"):
            emit(f"[{self.key}] 用户在执行计划中选择跳过设备名称替换")
            return {
                "logs": ["[naming_replace] 用户选择跳过名称替换"],
                "metrics": {"naming_status": "skipped", "naming_source": ""},
            }

        src = None
        for d in (ctx.input_dir, ctx.output_dir):
            if d.is_dir():
                src = next(
                    (p for p in d.iterdir()
                     if p.suffix.lower() in (".xlsx", ".xls")
                     and any(h in p.name for h in _NAMING_HINTS)),
                    None,
                )
                if src:
                    break

        if src is None:
            emit(f"[{self.key}] 未提供设备清单/命名映射，可选步骤跳过")
            return {
                "logs": ["[naming_replace] 可选步骤跳过（无命名映射来源）"],
                "metrics": {"naming_status": "skipped", "naming_source": ""},
            }

        emit(f"[{self.key}] 调用 A3 子 skill：替换设备名称（来源 {src.name}）")
        result = run_command("替换设备名称", ctx.work_root, emit=emit)

        if result.status == "ok":
            emit(f"[{self.key}] ✓ {result.summary}")
            return {
                "logs": [f"[naming_replace] 已按 {src.name} 完成命名替换"],
                "metrics": {
                    "naming_status": "done",
                    "naming_source": src.name,
                    "naming_outputs": result.output_files,
                },
                "files": {f"naming_{i}": p for i, p in enumerate(result.output_files)},
            }

        emit(f"[{self.key}] ⚠ {result.summary}")
        return {
            "logs": [f"[naming_replace] 失败：{result.summary}"],
            "metrics": {
                "naming_status": "error",
                "naming_source": src.name,
            },
            "error": result.errors[0] if result.errors else result.summary,
        }
