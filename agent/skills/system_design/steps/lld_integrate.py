"""
step 4 · LLD 融合（Raw Skill §6 lld_integrate · 确定性，无 LLM · A008/A010）

调用 a3 a3_LLD_generate_code1 · offline_lld_generate_pipeline.py integrate 模式，
把各平面规划表融合为完整 LLD（同平面取最新 · A010）。
"""
from __future__ import annotations

import os
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from ..pipelines.a3_bridge import ensure_plane_address_repairs, rebuild_access_plan_from_outputs
from ..pipelines.delivery import has_mergeable_plane_artifacts, is_lld_delivery_intent
from ..pipelines.exec_log import append_log, extract_actionable_error
from ..pipelines.lld_artifacts import lld_rel_for_state
from ..pipelines.lld_merge import run_integrate, should_skip_integrate
from agent.sdui.projector_base import collect_metrics

_PLAN_NEXT_OPTIONS = [
    {"label": "生成完整 LLD 设计", "value": "生成完整LLD设计"},
    {"label": "带外管理互联规划", "value": "带外管理互联规划"},
    {"label": "网络接入规划", "value": "网络接入规划"},
    {"label": "网络互联规划", "value": "网络互联规划"},
]


def _no_merge_hitl(reason: str) -> dict:
    return {
        "step": "plane_planning",
        "reason": reason,
        "need_files": [],
        "need_inputs": [{
            "id": "plan_next",
            "label": "下一步：继续规划任务，或生成完整 LLD 设计",
            "options": list(_PLAN_NEXT_OPTIONS),
        }],
    }


class LldIntegrateStep(BaseStep):
    key = "lld_integrate"
    name = "LLD 融合"
    artifacts_pattern: list[str] = []

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        m = collect_metrics(state)
        route = str(state.get("route_to") or "")
        intent_cmd = str(
            m.get("intent_command")
            or (ctx.project or {}).get("text")
            or ""
        ).strip()
        force_lld = route == "lld_integrate" or is_lld_delivery_intent(intent_cmd)
        force_integrate = force_lld or os.environ.get("AIDA_LLD_FORCE_INTEGRATE", "").strip() in ("1", "true", "yes")
        if m.get("sd_mode") in ("single", "batch") and not force_lld:
            emit(f"[{self.key}] 模式 {m.get('sd_mode')} → 跳过 LLD 融合（仅完整交付执行）")
            return {
                "logs": ["[lld_integrate] 非完整交付模式，跳过 LLD 融合"],
                "metrics": {"lld_planes_merged": 0, "lld_file": "", "lld_warnings": [],
                            "lld_status": "skipped"},
            }

        # 已有可融合平面表时跳过地址补跑（plane_planning 刚跑完或历史产物仍在 Output），
        # 避免 LLD 融合前重复执行整批地址规划导致长时间等待 stage_select 弹框。
        if has_mergeable_plane_artifacts(ctx.work_root):
            emit(f"[{self.key}] 已有可融合平面表 → 跳过地址规划补跑，直接融合 LLD")
            repair_results = []
        else:
            repair_results = ensure_plane_address_repairs(ctx.work_root, emit=emit)
            rebuild_access_plan_from_outputs(ctx.work_root, emit=emit)
        repair_errors = [r for r in repair_results if r.status == "error"]
        if repair_errors:
            msg = (
                "参数面/超平面地址规划补跑失败，无法融合完整 LLD。"
                f"\n{repair_errors[0].summary or repair_errors[0].errors[:1]}"
            )
            append_log(ctx.work_root, msg, level="ERROR", command="融合完整LLD设计")
            emit(f"[{self.key}] {msg}")
            return {
                "current_step": self.key,
                "logs": [f"[lld_integrate] {msg}"],
                "metrics": {
                    "lld_planes_merged": 0,
                    "lld_file": "",
                    "lld_warnings": [msg],
                    "lld_status": "error",
                },
                "error": msg,
                "steps": [self.make_record(
                    "failed", ended_at=self._now(),
                    log_tail=[msg],
                    metrics={"lld_status": "error"},
                )],
            }

        if not has_mergeable_plane_artifacts(ctx.work_root):
            msg = (
                "未找到可融合的平面规划表（各平面可能因 007 缺少对应 sheet 已跳过）。"
                "请检查 007 输入件或先执行地址规划，再生成完整 LLD。"
            )
            append_log(ctx.work_root, msg, level="INFO", command="融合完整LLD设计")
            emit(f"[{self.key}] ○ {msg}")
            return {
                "current_step": self.key,
                "logs": [f"[lld_integrate] {msg}"],
                "metrics": {
                    "lld_planes_merged": 0,
                    "lld_file": "",
                    "lld_warnings": [msg],
                    "lld_status": "skipped_no_input",
                },
                "hitl": _no_merge_hitl(msg),
                "steps": [self.make_record(
                    "completed", ended_at=self._now(),
                    log_tail=[msg],
                    metrics={"lld_status": "skipped_no_input"},
                )],
            }

        cmd = "融合完整LLD设计"
        skip, skip_reason = should_skip_integrate(ctx.work_root, force=force_integrate)
        if skip:
            from ..pipelines.lld_merge import canonical_lld_state_files

            files = canonical_lld_state_files(ctx.work_root)
            lld_rel = files.get("lld_file", "")
            emit(f"[{self.key}] ○ {skip_reason}")
            return {
                "logs": [f"[lld_integrate] {skip_reason}"],
                "metrics": {
                    "lld_planes_merged": 0,
                    "lld_file": lld_rel,
                    "lld_warnings": [],
                    "lld_status": "skipped_unchanged",
                },
                "files": files,
                "route_to": "",
            }

        emit(f"[{self.key}] 调用 A3 子 skill：{cmd}")
        result = run_integrate(ctx.work_root, emit=emit, force=force_integrate)

        warnings: list[str] = []
        lld_file = ""
        merged = 0

        if result.status == "ok" and result.output_files:
            lld_file = lld_rel_for_state(result.output_files[0])
            merged = len([p for p in result.output_files if "A3" in Path(p).name or "LLD" in Path(p).name])
            emit(f"[{self.key}] 融合产物：{Path(lld_file).name}")
        else:
            warnings.append(result.summary)
            if result.errors:
                warnings.extend(result.errors[:3])
            emit(f"[{self.key}] ⚠ {result.summary}")

        metrics: dict = {
            "lld_planes_merged": merged,
            "lld_file": lld_file,
            "lld_warnings": warnings,
        }

        if result.status == "error":
            err_msg = extract_actionable_error(log_tail=result.log_tail, errors=result.errors)
            if "未找到可融合" in err_msg or "未找到可融合" in (result.summary or ""):
                msg = (
                    f"{err_msg}\n\n请检查 Output 下是否有 A3 平面规划表，"
                    "或先完成地址规划后再生成完整 LLD。"
                )
                append_log(ctx.work_root, f"LLD 融合跳过：{result.summary}", level="INFO", command=cmd, detail=err_msg)
                emit(f"[{self.key}] ○ {msg}")
                return {
                    "current_step": self.key,
                    "logs": [f"[lld_integrate] 跳过 · {result.summary}"],
                    "metrics": {**metrics, "lld_status": "skipped_no_input"},
                    "hitl": _no_merge_hitl(msg),
                    "steps": [self.make_record(
                        "completed", ended_at=self._now(),
                        log_tail=[result.summary, err_msg],
                        metrics={**metrics, "lld_status": "skipped_no_input"},
                    )],
                }

            detail = err_msg
            if result.log_tail and result.log_tail not in detail:
                detail = f"{err_msg}\n--- log_tail ---\n{result.log_tail}"
            append_log(
                ctx.work_root,
                f"LLD 融合失败：{result.summary}",
                level="ERROR",
                command=cmd,
                detail=detail,
            )
            emit(f"[{self.key}] ❌ {err_msg}")
            return {
                "error": err_msg,
                "hitl": {},
                "logs": [f"[lld_integrate] 失败 · {result.summary}", f"[lld_integrate] {err_msg}"],
                "metrics": {**metrics, "lld_status": "failed"},
                "files": {},
                "steps": [self.make_record(
                    "failed", ended_at=self._now(),
                    log_tail=[result.summary, err_msg],
                    metrics=metrics,
                )],
            }

        return {
            "logs": [f"[lld_integrate] {result.summary}"],
            "metrics": {**metrics, "lld_status": "ok", "lld_warnings": []},
            "files": {"lld_file": lld_file} if lld_file else {},
            "route_to": "",
        }
