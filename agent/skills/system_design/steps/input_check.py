"""
step 2 · 输入件检查（Raw Skill §6 input_check · 建模仿真→系统设计 串联点）

必需件 4 件（假设 A001）：项目信息收集表 + 007 + 001 + 004。
其中 007/001/004 是「建模仿真」产出的仿真输出件 —— 缺任一件触发 **HITL 软中断**
（check_inputs 返 missing → 框架写 state['hitl'] → router → END → resume，非 interrupt()）。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..pipelines.inputs import (
    collect_inputs, missing_required, label_of, REQUIRED_DEFAULT, FILE_CONFIG,
)
from ..pipelines.path_manifest import abs_input_dir, relpath_for_artifact


class InputCheckStep(BaseStep):
    key = "input_check"
    name = "输入件检查"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        """4 件全必选；缺件 → 文件型 HITL（need_files → FilePicker）。
        ⚠️ 此处必填件 = run/后续真正读取的件，避免 HITL 清单漂移。"""
        found = collect_inputs(ctx.work_root)
        missing = missing_required(found, REQUIRED_DEFAULT)
        if missing:
            missing_labels = [label_of(t) for t in missing]
            return {
                "ok": False,
                "missing": [str(abs_input_dir() / lbl) for lbl in missing_labels],
                "found": [str(f.path) for f in found.values()],
                "note": (
                    "系统设计需要建模仿真产出的 007/001/004 与项目信息收集表，"
                    f"缺：{('、'.join(missing_labels))}。请上传后重试。"
                ),
            }
        return {"ok": True, "missing": [], "found": [str(f.path) for f in found.values()], "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        found = collect_inputs(ctx.work_root)
        emit(f"[{self.key}] 识别到 {len(found)}/{len(REQUIRED_DEFAULT)} 个必需输入件")
        for tag, f in found.items():
            origin = "建模仿真产出" if FILE_CONFIG[tag]["from_simulation"] else "手动上传"
            emit(f"  ✓ {f.label}（{origin}）：{f.path.name}")

        return {
            "logs": [f"[input_check] 输入件齐备（{len(found)} 件）"],
            "metrics": {
                "input_found": len(found),
                "input_total": len(REQUIRED_DEFAULT),
                "input_ready": True,
                "found_tags": list(found.keys()),
            },
            "files": {f"input_{tag}": relpath_for_artifact(f.path) for tag, f in found.items()},
        }
