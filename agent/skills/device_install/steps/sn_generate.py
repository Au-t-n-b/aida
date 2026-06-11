"""
sn_generate · SN 扫码表生成

command: build 专属

run：从 sn_pool.json（plan_receive 解析的全量 SN）按「计划下发」勾选的管理单元过滤，
按（机房, 设备大类）分组生成 SN 扫码表 xlsx，落 sn_tables.json 供 ESN 在线填写。
"""
from __future__ import annotations

import json

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._command_guard import should_skip
from ._io import refresh_task_metrics, tasks_state_path
from ..services._common import as_str
from ..services.dispatch_plan_parser import load_sn_pool, group_sn_rows_to_tables
from ..services.sn_builder import generate_sn_xlsx
from ..services.task_store import load_tasks_state


class SnGenerateStep(BaseStep):
    key = "sn_generate"
    name = "SN扫码表生成"
    artifacts_pattern = ["ProjectData/Output/SN扫码表_*.xlsx"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        pool_path = ctx.runtime_dir / "sn_pool.json"
        if not pool_path.is_file():
            return {
                "ok": False,
                "missing": ["ProjectData/RunTime/sn_pool.json"],
                "note": "缺少 SN 全量池，请先完成「接收实施计划」。",
            }
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        state_path = str(tasks_state_path(ctx))
        st = load_tasks_state(state_path)
        dispatch_tasks = [
            t for t in (st.get("last_dispatch_tasks") or []) if isinstance(t, dict)
        ]

        if not dispatch_tasks:
            emit("[sn_generate] 未找到计划下发勾选记录，请先完成「计划下发」并勾选任务")
            metrics = {"sn_tables": 0, "sn_devices": 0}
            metrics.update(refresh_task_metrics(ctx))
            return {"metrics": metrics}

        dispatched_units = {
            as_str(t.get("unit")) for t in dispatch_tasks if as_str(t.get("unit"))
        }
        # 任务级范围：勾选任务的计划行ID（= 管理单元::活动ID）
        selected_plan_ids = {
            as_str(t.get("id")) for t in dispatch_tasks if as_str(t.get("id"))
        }
        pool_path = ctx.runtime_dir / "sn_pool.json"
        all_sn = load_sn_pool(pool_path)

        def _row_plan_ids(r: dict) -> set[str]:
            return {p for p in as_str(r.get("关联计划行ID")).split(";") if p}

        # 优先按「关联计划行ID」做任务级过滤；旧版文件无此列时回退到管理单元级
        filtered = []
        used_task_level = False
        for r in all_sn:
            pids = _row_plan_ids(r)
            if pids:
                used_task_level = True
                if pids & selected_plan_ids:
                    filtered.append(r)
            elif as_str(r.get("所属管理单元")) in dispatched_units:
                filtered.append(r)

        if not filtered:
            scope_label = (
                f"勾选下发任务（{', '.join(sorted(selected_plan_ids)[:4])}"
                f"{'…' if len(selected_plan_ids) > 4 else ''}）"
                if used_task_level
                else f"勾选下发管理单元（{', '.join(sorted(dispatched_units)[:4])}"
                     f"{'…' if len(dispatched_units) > 4 else ''}）"
            )
            emit(f"[sn_generate] SN 全量池中未匹配到{scope_label}，跳过 SN 扫码表生成")
            meta_path = ctx.runtime_dir / "sn_tables.json"
            ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(
                json.dumps({"dispatch_tasks": dispatch_tasks, "tables": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            metrics = {"sn_tables": 0, "sn_devices": 0}
            metrics.update(refresh_task_metrics(ctx))
            return {"metrics": metrics}

        tables = group_sn_rows_to_tables(filtered)
        if not tables:
            emit("[sn_generate] 过滤后无 SN 设备行，跳过 SN 扫码表生成")
            meta_path = ctx.runtime_dir / "sn_tables.json"
            ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(
                json.dumps({"dispatch_tasks": dispatch_tasks, "tables": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            metrics = {"sn_tables": 0, "sn_devices": 0}
            metrics.update(refresh_task_metrics(ctx))
            return {"metrics": metrics}

        artifacts: list[str] = []
        for tbl in tables:
            out = generate_sn_xlsx(tbl, str(ctx.output_dir))
            if out:
                artifacts.append(ctx.rel(out))

        meta_path = ctx.runtime_dir / "sn_tables.json"
        ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(
                {"dispatch_tasks": dispatch_tasks, "tables": tables},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        n_rows = sum(len(t.get("rows", [])) for t in tables)
        n_tasks = len(dispatch_tasks)
        scope_word = "任务级" if used_task_level else "管理单元级"
        emit(
            f"[sn_generate] ✓ 已按勾选下发范围（{scope_word}）生成 {len(tables)} 张 SN 扫码表，"
            f"共 {n_rows} 台设备（来自 {n_tasks} 条下发任务 / {len(dispatched_units)} 个管理单元）"
        )
        emit("[sn_generate] 下一步「ESN信息填写」仅对上述勾选任务对应的设备逐台填写 ESN")

        metrics = {"sn_tables": len(tables), "sn_devices": n_rows, "dispatch_scope_tasks": n_tasks}
        metrics.update(refresh_task_metrics(ctx))
        return {"artifacts": artifacts, "metrics": metrics}
