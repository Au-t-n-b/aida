"""contract_boq · stage2_device_table"""
from __future__ import annotations

from pathlib import Path

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths
from ..bridge import UniExBoqError, run_stage2


class Stage2DeviceTableStep(BaseStep):
    key = "stage2_device_table"
    name = "建模仿真设备信息表"
    artifacts_pattern = ["早期介入/合同/输出结果/建模仿真/建模仿真设备信息表.md"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        if io.contract_simulation_md.is_file():
            return {"ok": True, "missing": [], "found": [io.rel(io.contract_simulation_md)]}
        normalized = sorted(io.contract_boq_parse.glob("*.normalized.json"))
        if not normalized:
            return {"ok": False, "missing": ["*.normalized.json"], "found": []}
        return {"ok": True, "missing": [], "found": [io.rel(p) for p in normalized]}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "缺少 project_id"}

        sim_dir = io.contract_simulation_md.parent
        sim_dir.mkdir(parents=True, exist_ok=True)
        target_md = io.contract_simulation_md

        if target_md.is_file():
            rel = io.rel(target_md)
            emit(f"跳过 Stage2：已有 {rel}")
            return {
                "artifacts": [rel],
                "files": {"simulation_device_md": rel},
                "metrics": {"stage2_skipped": True},
            }

        run_dir_raw = (state.get("files") or {}).get("clone_boq_run_dir")
        if not run_dir_raw:
            return {"error": "缺少 clone_boq_run_dir，请先完成 stage1_parse"}

        try:
            emit("调用 uniEx clone-boq Stage2 …")
            out_md, out_json = run_stage2(Path(run_dir_raw), sim_dir)
            canonical = target_md
            if out_md != canonical:
                canonical.write_bytes(out_md.read_bytes())
        except UniExBoqError as exc:
            return {"error": str(exc)}

        rel_md = io.rel(canonical)
        rel_json = io.rel(out_json)
        emit(f"Stage2 完成：{rel_md}")
        return {
            "artifacts": [rel_md, rel_json],
            "files": {
                "simulation_device_md": rel_md,
                "simulation_device_json": rel_json,
            },
            "metrics": {"stage2_skipped": False},
        }
