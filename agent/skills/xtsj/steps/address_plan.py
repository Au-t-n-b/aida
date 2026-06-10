"""address_plan 命令 handler · a3「地址批规划」各平面顺序执行。

dispatch 模式下被 _dispatch 按 command="address_plan" 路由命中。
业务逻辑走进程内 pipeline 模块（pipelines/address_plan.py）—— 不 subprocess、
每平面结果写 state.metrics → projector 投影成 PlaneMatrix。
"""
from __future__ import annotations

from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from ..pipelines.address_plan import PLANE_SPECS, run_address_plan, PlaneResult


def _plane_status(r: PlaneResult) -> str:
    return r.status  # pending / running / done / error / skipped


class AddressPlanStep(BaseStep):
    key = "address_plan"
    name = "地址批规划"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        work_root = ctx.work_root

        emit(f"[address_plan] 工作区：{work_root}")
        emit(f"[address_plan] 待规划平面：{', '.join(s.label for s in PLANE_SPECS)}")

        results: list[PlaneResult] = run_address_plan(work_root)

        # ── 汇总 ──────────────────────────────────────────────────────────────
        done_planes   = [r for r in results if r.status == "done"]
        error_planes  = [r for r in results if r.status == "error"]
        skip_planes   = [r for r in results if r.status in ("skipped", "pending")]
        output_files  = {r.spec.key: r.output_file for r in done_planes}

        for r in results:
            icon = {"done": "✓", "error": "✗", "skipped": "○", "pending": "○", "running": "→"
                    }.get(r.status, "?")
            msg = r.note or r.error or ""
            emit(f"  {icon} {r.spec.label} ({r.status}){' — ' + msg if msg else ''}")

        if error_planes:
            summary = (
                f"地址规划完成 {len(done_planes)}/{len(results)} 个平面，"
                f"{len(error_planes)} 个出错：" +
                "；".join(r.spec.label + ": " + r.error[:60] for r in error_planes)
            )
        elif done_planes:
            summary = f"地址规划完成 {len(done_planes)} 个平面，产物已写入 ProjectData/Output/AddressPlan/"
        else:
            summary = (
                f"地址规划 {len(skip_planes)} 个平面已跳过（缺少输入文件或 a3 源码）。"
                "请确保 ProjectData/Input/ 含 007 端口连线表和资源需求表，并配置 A3_ROOT。"
            )

        emit(f"[address_plan] {summary}")

        return {
            "logs": [
                f"[address_plan] {r.spec.label}: {r.status}{' — ' + (r.note or r.error or '') if (r.note or r.error) else ''}"
                for r in results
            ],
            "metrics": {
                "address_plan_total":    len(results),
                "address_plan_done":     len(done_planes),
                "address_plan_error":    len(error_planes),
                "address_plan_skipped":  len(skip_planes),
                "address_plan_summary":  summary,
                # 各平面状态，projector 用于 PlaneMatrix
                "plane_statuses": {r.spec.key: _plane_status(r) for r in results},
                "plane_notes":    {r.spec.key: (r.note or r.error or "") for r in results},
            },
            "files": output_files,
        }
