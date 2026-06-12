"""Step 2 · 拆分调测计划。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._sd_ops import _chain, op_plan_split, scene_is_multi_pods, slot_missing
from ._hitl import confirm_gate


class PlanSplitStep(BaseStep):
    key = "plan_split"
    name = "拆分调测计划"
    artifacts_pattern = [
        "ProjectData/plan/Output/third_level_tasks.json",
        "ProjectData/plan/Output/plan_display_tree.json",
    ]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        missing: list[str] = []
        if not _chain(ctx.work_root).get("step1_plan_receive_at"):
            missing.append("ProjectData/plan/Input/second_level_tasks.json（需先 plan_receive）")
        missing.extend(slot_missing(ctx.work_root, "testcase"))
        if scene_is_multi_pods(ctx.work_root):
            missing.extend(slot_missing(ctx.work_root, "pod_map"))
        if missing:
            return {"ok": False, "missing": missing, "found": [], "note": "需验收用例 Word；多 Pod 场景需 Pod 映射表"}
        return confirm_gate(
            ctx.project,
            self.key,
            "确认拆分调测计划",
            note="材料已齐备，请确认执行拆分调测计划。",
            description="将生成 third_level_tasks.json 与 plan_display_tree.json。",
        )

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 拆分调测计划…")
        proj_id = str((ctx.project or {}).get("project_id") or "nanobot-local")
        result = op_plan_split(ctx.work_root, project_id=proj_id)
        if not result.get("ok"):
            return {"error": result.get("error") or "拆分失败"}
        emit(f"[{self.key}] 三级 {result.get('third_count')} 条（二级 {result.get('second_count')} 条）")
        skipped = result.get("skipped_no_device") or []
        missing_mappings = result.get("missing_mappings") or []
        if skipped:
            emit(f"[{self.key}] 跳过无设备清单 {len(skipped)} 项")
        if missing_mappings:
            preview = "、".join(str(x) for x in missing_mappings[:3])
            suffix = "…" if len(missing_mappings) > 3 else ""
            emit(f"[{self.key}] 未命中 second_to_third 映射 {len(missing_mappings)} 项：{preview}{suffix}")
        return {
            "metrics": {
                "second_count": result.get("second_count", 0),
                "third_count": result.get("third_count", 0),
                "skipped_no_device_count": len(skipped),
                "missing_mapping_count": len(missing_mappings),
                "step": "split",
                "scene_spec": result.get("scene_spec") or {},
                "third_tasks_preview": result.get("third_tasks_preview") or [],
            }
        }
