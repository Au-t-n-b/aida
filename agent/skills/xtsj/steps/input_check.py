"""input_check 命令 handler · a3 sd_query_inputs /「检查输入件是否妥当」。

dispatch 模式下被 _dispatch 按 command="input_check" 路由命中。
业务逻辑走进程内 pipeline 模块（pipelines/input_check.py）—— 不 subprocess、不进
DEFAULT_TOOLS（铁律②解法，见 A3-MIGRATION-PLAN §2），与 zhgk step 范式一致。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from ..pipelines.input_check import (
    collect_inputs, missing_required, label_of, REQUIRED_DEFAULT,
)


class InputCheckStep(BaseStep):
    key = "input_check"
    name = "输入件检查"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        found = collect_inputs(ctx.work_root)
        missing = missing_required(found, REQUIRED_DEFAULT)
        ready = not missing

        emit(f"[input_check] 扫描 ProjectData → 识别 {len(found)} 个输入件")
        for _tag, f in found.items():
            emit(f"  ✓ {f.label}")
        for tag in missing:
            emit(f"  ○ 缺：{label_of(tag)}")

        return {
            "logs": [f"[input_check] {'输入件齐备' if ready else f'缺 {len(missing)} 项必需件'}"],
            "metrics": {
                "input_found": len(found),
                "input_missing": len(missing),
                "input_ready": ready,
                "missing_labels": [label_of(t) for t in missing],
                "found_tags": list(found.keys()),
            },
            # 已识别输入件落 state.files（projector / 后续命令可读）
            "files": {f"input_{tag}": str(f.path) for tag, f in found.items()},
        }
