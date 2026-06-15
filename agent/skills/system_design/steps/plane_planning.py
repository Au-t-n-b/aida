"""
step 3 · 平面规划（Raw Skill §6 plane_planning · 确定性计算，无 LLM · A008）

按 intent_command 决定执行模式（②单命令 dispatch）：
  - single ：单条 L3 命令（菜单式触发）→ run_command 直执该命令
  - batch  ：L1/L2 批次 → ① run_dispatch 走 a3 编排器 plan + 进程内执行
  - full   ：完整交付 → run_dispatch（地址规划批次），后续 step 继续 LLD/ZTP/命名

执行经 pipelines/a3_bridge（vendored a3 subskills，进程内 runpy，无 subprocess）。
下游 step 读 metrics["sd_mode"] 决定是否自跳过（single/batch 跑完即发布）。
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from .intent_taxonomy import recognize as rule_recognize, canonicalize_command
from ..pipelines.inputs import collect_inputs, missing_required, label_of, PLANNING_REQUIRED
from ..pipelines.planes import PLANE_SPECS
from ..pipelines.a3_bridge import (
    run_command, run_dispatch,
    resolve_dispatch_anchor, resolve_execution_mode,
    ensure_access_plan, intent_needs_access_plan, access_plan_exists,
    ensure_plane_address_repairs, rebuild_access_plan_from_outputs,
)
from ..pipelines.delivery import has_mergeable_plane_artifacts
from ..pipelines.exec_log import append_log, extract_actionable_error
from ..pipelines.path_manifest import abs_artifacts_dir, abs_input_dir
from agent.sdui.projector_base import collect_metrics


# 规划覆盖账本（仅内存 · 从 state.steps metrics 恢复）：累积「已执行规划指令 → 产出文件名」。
# 设计稿规划覆盖矩阵的点亮逻辑 = 执行了哪个指令 + 输出路径中读到对应产物文件 → 点亮该指令框。
# 每次 plane_planning 重跑把本批次成功且产出文件的指令并入账本，再按「文件是否仍在输出路径」
# 校验剔除已删除产物的指令，最终落入 metrics.plan_commands 供 SDUI 精确点亮（不再粗粒度聚合）。
_COVERAGE_LEDGER = "plan_coverage.json"  # 历史名；不再落盘
# 接入底表为多个平面规划共用副产物，不应写入单平面指令的覆盖账本（避免误点亮）
_SHARED_PLAN_OUTPUTS = frozenset({"A3网络设备接入规划.xlsx", "网络设备接入规划.xlsx"})
# 仅 L1 全量地址批次 / 完整交付才触发 007 sheet 补跑（避免「只跑超平面」时连带补跑参数面）
_BROAD_REPAIR_INTENTS = frozenset({"地址规划", "生成完整LLD设计", "融合完整LLD设计"})


def _load_coverage_ledger(state: SkillState) -> dict[str, dict]:
    """从本 run 已有 plane_planning metrics 恢复账本（不写磁盘）。"""
    ledger: dict[str, dict] = {}
    for rec in reversed(state.get("steps") or []):
        if rec.get("key") != "plane_planning":
            continue
        m = rec.get("metrics") or {}
        for item in (m.get("plan_commands") or []):
            if not isinstance(item, dict):
                continue
            cmd = str(item.get("command") or "").strip()
            files = [f for f in (item.get("files") or []) if f and f not in _SHARED_PLAN_OUTPUTS]
            if cmd and files:
                ledger[cmd] = {"status": item.get("status") or "ok", "files": files}
        break
    return ledger


def _build_plan_commands(ctx, results, ledger: dict[str, dict]) -> list[dict]:
    """累积本批次成功指令到账本，并按「产物文件仍在输出路径」校验后返回 plan_commands。"""
    for r in results:
        if r.status == "ok" and r.output_files:
            files = [
                os.path.basename(str(f))
                for f in r.output_files
                if os.path.basename(str(f)) not in _SHARED_PLAN_OUTPUTS
            ]
            if not files:
                continue
            ledger[r.command] = {
                "status": "ok",
                "files": files,
            }
    # 严格对齐设计稿：仅保留产物仍可在输出路径读到的指令才点亮
    out_dir = ctx.output_dir
    existing: set[str] = (
        {p.name for p in out_dir.rglob("*") if p.is_file()} if out_dir.is_dir() else set()
    )
    cleaned: dict[str, dict] = {}
    plan_commands: list[dict] = []
    for cmd, info in ledger.items():
        files = [f for f in (info.get("files") or []) if f in existing]
        if not files:
            continue
        cleaned[cmd] = {"status": "ok", "files": files}
        plan_commands.append({"command": cmd, "status": "ok", "files": files})
    return plan_commands

def _normalize_queue(queue_raw: list[str]) -> tuple[list[str], list[str]]:
    """把队列里的原始任务文本逐条归一为标准命令（对齐意图识别规则链）。
    可识别 → 标准命令；不可识别 → 记 warning 并跳过（不阻断已识别任务执行）。"""
    norm: list[str] = []
    warnings: list[str] = []
    for raw in queue_raw:
        r = rule_recognize(raw)
        if r.status == "resolved" and r.command:
            cmd = canonicalize_command(r.command)
            if cmd not in norm:
                norm.append(cmd)
        else:
            warnings.append(f"队列任务「{raw}」无法识别为标准规划命令，已跳过")
    return norm, warnings


# 循环 HITL 的「下一步」候选（对齐设计稿 composer chips + 生成完整 LLD）
_NEXT_PLAN_OPTIONS = [
    {"label": "生成完整 LLD 设计", "value": "生成完整LLD设计"},
    {"label": "带外管理互联规划", "value": "带外管理互联规划"},
    {"label": "网络接入规划", "value": "网络接入规划"},
    {"label": "网络互联规划", "value": "网络互联规划"},
]


def _scan_output_files(ctx) -> dict[str, str]:
    """扫描 ProjectData/Output 下全部已生成文件（跨命令累积 · 相对 work_root 路径）。
    键 out::<relpath> 稳定，重复扫描覆盖同键不产生重复；供前端展示「全部已生成文件」。"""
    out: dict[str, str] = {}
    try:
        base = ctx.output_dir
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if not p.is_file():
                    continue
                try:
                    rel = ctx.rel(p)
                except Exception:
                    rel = str(p)
                out[f"out::{rel}"] = rel
    except Exception:
        pass
    return out


def _round_error_message(results) -> str:
    """本批次首条可展示错误（去噪后优先 ERROR/失败原因类说明）。"""
    for r in results:
        if r.status != "error":
            continue
        msg = extract_actionable_error(log_tail=r.log_tail, errors=r.errors)
        if msg and msg != "执行失败（详见执行日志）":
            return msg
        if r.summary:
            return str(r.summary).strip()
    return "规划执行失败"


def _match_plane_statuses(results) -> tuple[dict, dict, dict, int]:
    """把 A3 执行结果按 PLANE_SPECS 标签映射到平面矩阵状态。"""
    plane_statuses: dict[str, str] = {}
    plane_notes: dict[str, str] = {}
    output_files: dict[str, str] = {}
    for spec in PLANE_SPECS:
        key_hint = spec.label.replace("面", "")
        matched = [
            r for r in results
            if key_hint in r.command or spec.plane_name in r.command
        ]
        if not matched:
            plane_statuses[spec.key] = "skipped"
            plane_notes[spec.key] = "本批次未包含该平面命令"
            continue
        last = matched[-1]
        if last.status == "ok":
            plane_statuses[spec.key] = "done"
            plane_notes[spec.key] = last.summary
            if last.output_files:
                output_files[spec.key] = last.output_files[-1]
        elif last.status == "skipped":
            plane_statuses[spec.key] = "skipped"
            plane_notes[spec.key] = last.summary
        else:
            plane_statuses[spec.key] = "error"
            plane_notes[spec.key] = (last.errors[0] if last.errors else last.summary)[:120]
    done = sum(1 for s in plane_statuses.values() if s == "done")
    return plane_statuses, plane_notes, output_files, done


class PlanePlanningStep(BaseStep):
    key = "plane_planning"
    name = "平面规划"
    artifacts_pattern = [str(abs_artifacts_dir())]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        found = collect_inputs(ctx.work_root)
        missing = missing_required(found, PLANNING_REQUIRED)
        if missing:
            labels = [label_of(t) for t in missing]
            return {
                "ok": False,
                "missing": [str(abs_input_dir() / lbl) for lbl in labels],
                "found": [str(f.path) for f in found.values()],
                "note": f"平面规划需要：{('、'.join(labels))}。",
            }
        return {"ok": True, "missing": [], "found": [str(f.path) for f in found.values()], "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        from ..pipelines.delivery import should_skip_step

        route = str(state.get("route_to") or "")
        if route and should_skip_step(self.key, route):
            emit(f"[{self.key}] 交付续跑 · 跳过（→{route}）")
            return {"logs": [f"[plane_planning] 交付续跑跳过（→{route}）"]}

        m = collect_metrics(state)
        intent_cmd = canonicalize_command(str(m.get("intent_command") or "生成完整LLD设计"))
        mode = resolve_execution_mode(intent_cmd)
        emit(f"[{self.key}] 意图「{intent_cmd}」→ 执行模式：{mode}")

        # 接入规划前置：底表 A3网络设备接入规划.xlsx 由地址规划副产物生成（原始 skill 业务逻辑）。
        # 缺失则先跑地址规划批次补齐，避免每条接入查询 FileNotFoundError 导致整步失败。
        prereq_results: list = []
        if intent_needs_access_plan(intent_cmd) and not access_plan_exists(ctx.work_root):
            emit(f"[{self.key}] 接入规划依赖地址规划底表，缺失 → 先补齐地址规划")
            prereq_results = ensure_access_plan(ctx.work_root, emit=emit)
            if not access_plan_exists(ctx.work_root):
                msg = (
                    "接入规划依赖 A3网络设备接入规划.xlsx，地址规划前置补齐后仍未生成该底表，"
                    f"无法执行「{intent_cmd}」。请先执行「地址规划」或检查 007/资源表输入件。"
                )
                append_log(ctx.work_root, msg, level="ERROR", command=intent_cmd)
                emit(f"[{self.key}] {msg}")
                return {
                    "error": msg,
                    "hitl": {},
                    "logs": [f"[plane_planning] {msg}"],
                    "metrics": {
                        "intent_command": intent_cmd,
                    },
                    "steps": [self.make_record(
                        "failed", ended_at=self._now(),
                        log_tail=[msg],
                        metrics={
                            "intent_command": intent_cmd,
                        },
                    )],
                }

        # 多任务队列（对齐设计稿 pick_commands + queue）：仅 single/batch 串行追加执行，
        # full（完整 LLD）为终态批次，忽略队列。队列任务先归一为标准命令，逐条 run_command。
        queue_raw = [
            str(x).strip()
            for x in ((ctx.project or {}).get("plan_queue") or [])
            if str(x).strip()
        ]
        queued_cmds: list[str] = []
        queue_warnings: list[str] = []
        if queue_raw and mode in ("single", "batch"):
            queued_cmds, queue_warnings = _normalize_queue(queue_raw)
            for w in queue_warnings:
                emit(f"[{self.key}] {w}")
            if queued_cmds:
                emit(f"[{self.key}] 多任务队列：共 {len(queued_cmds)} 项 → {('、'.join(queued_cmds))}")

        plan_meta: dict = {}
        queue_progress: list[dict] = []
        if mode == "single":
            # ② 单命令 dispatch：首条 + 队列逐条直执，逐项记录进度
            emit(f"[{self.key}] 单命令模式：直执「{intent_cmd}」")
            r0 = run_command(intent_cmd, ctx.work_root, emit=emit)
            results = [r0]
            queue_progress.append({"command": intent_cmd, "status": r0.status})
            total_q = len(queued_cmds)
            for i, cmd in enumerate(queued_cmds, 1):
                emit(f"[{self.key}] 队列 {i}/{total_q}：执行「{cmd}」")
                rq = run_command(cmd, ctx.work_root, emit=emit)
                results.append(rq)
                queue_progress.append({"command": cmd, "status": rq.status})
        else:
            # ① 批次 / 完整：走 a3 编排器 plan + 进程内执行
            anchor = resolve_dispatch_anchor(intent_cmd)
            results, plan = run_dispatch(anchor, ctx.work_root, emit=emit, keep_going=True)
            plan_meta = {
                "dispatch_anchor": plan.get("anchor_intent", anchor),
                "dispatch_phases": [
                    {
                        "l2": ph.get("l2_intent"),
                        "strategy": ph.get("l2_strategy"),
                        "status": ph.get("status"),
                        "tasks": [
                            {"intent": t.get("intent"), "status": t.get("status")}
                            for t in (ph.get("tasks") or [])
                        ],
                    }
                    for ph in (plan.get("phases") or [])
                ],
                "dispatch_errors": plan.get("errors") or [],
            }
            # batch 模式：队列里的额外任务作为独立命令串行追加（full 模式不追加）
            if mode == "batch" and queued_cmds:
                total_q = len(queued_cmds)
                for i, cmd in enumerate(queued_cmds, 1):
                    emit(f"[{self.key}] 队列 {i}/{total_q}：执行「{cmd}」")
                    rq = run_command(cmd, ctx.work_root, emit=emit)
                    results.append(rq)
            queue_progress = [{"command": r.command, "status": r.status} for r in results]

        # 前置补齐的地址规划结果并入本次结果（产物展示 / 覆盖点亮 / 成败统计）
        if prereq_results:
            results = [*prereq_results, *results]

        # 007 含参数面/超平面 sheet 但批次误跳过或未产出 → 仅全量地址批次 / 完整交付时补跑
        if mode == "full" or intent_cmd in _BROAD_REPAIR_INTENTS:
            repair_results = ensure_plane_address_repairs(ctx.work_root, emit=emit)
            if repair_results:
                results.extend(repair_results)
            # 地址规划副产物：A3网络设备接入规划.xlsx（CSM 等 emit_for_plane 写入）
            if not access_plan_exists(ctx.work_root):
                rebuild_access_plan_from_outputs(ctx.work_root, emit=emit)
                if not access_plan_exists(ctx.work_root):
                    append_log(
                        ctx.work_root,
                        "地址规划完成后仍缺少 A3网络设备接入规划.xlsx（接入底表）",
                        level="WARN",
                        command=intent_cmd,
                    )
                    emit(
                        f"[{self.key}] 警告：缺少 A3网络设备接入规划.xlsx（接入底表），"
                        "后续「接入规划」步骤将不可用"
                    )

        ok_n = sum(1 for r in results if r.status == "ok")
        err_n = sum(1 for r in results if r.status == "error")
        skip_n = sum(1 for r in results if r.status == "skipped")

        plane_statuses, plane_notes, output_files, done = _match_plane_statuses(results)
        summary = (
            f"A3 子 skill 执行完成（{mode}）：{ok_n} 成功 / {err_n} 失败 / {skip_n} 跳过"
            f"（平面矩阵 {done}/{len(PLANE_SPECS)} 点亮）"
        )
        emit(f"[{self.key}] {summary}")

        errors = [
            f"{r.command}: {e}"
            for r in results
            if r.status == "error" and r.errors
            for e in r.errors
        ]
        skip_notes = [
            str(r.summary).strip()
            for r in results
            if r.status == "skipped" and str(r.summary or "").strip()
        ]
        if errors:
            append_log(
                ctx.work_root,
                f"平面规划批次存在 {len(errors)} 条错误（意图「{intent_cmd}」）",
                level="ERROR",
                command=intent_cmd,
                detail="\n".join(errors[:20]),
            )
        elif skip_notes:
            append_log(
                ctx.work_root,
                f"本批次 {len(skip_notes)} 项因 007 sheet 缺失或不可用已跳过（意图「{intent_cmd}」）",
                level="INFO",
                command=intent_cmd,
                detail="\n".join(skip_notes[:20]),
            )

        # 规划覆盖账本：累积「已执行指令 + 输出路径产出文件」（跨命令/跨 full_restart 存活），
        # 供 SDUI 规划覆盖矩阵按指令名精确点亮对应任务框。
        plan_commands = _build_plan_commands(ctx, results, _load_coverage_ledger(state))

        metrics: dict = {
            "plane_total": len(PLANE_SPECS),
            "plane_done": done,
            "plane_skipped": sum(1 for s in plane_statuses.values() if s == "skipped"),
            "plane_statuses": plane_statuses,
            "plane_notes": plane_notes,
            "plane_summary": summary,
            "plan_commands": plan_commands,
            "sd_mode": mode,
            "a3_commands_run": len(results),
            "a3_commands_ok": ok_n,
            "a3_commands_error": err_n,
            "command_results": [
                {
                    "command": r.command,
                    "status": r.status,
                    "errors": (r.errors or [])[:3],
                    "summary": r.summary,
                }
                for r in results
            ],
        }
        if queue_progress:
            metrics["queue_progress"] = queue_progress
        if queue_warnings:
            metrics["queue_warnings"] = queue_warnings
        if skip_notes:
            metrics["plane_skip_notes"] = skip_notes[:20]
        metrics.update(plan_meta)

        # 产物文件：本批次平面产物（plane_<key>）+ 全量扫描 Output（跨命令累积，供前端展示全部）
        files_out: dict[str, str] = {f"plane_{k}": v for k, v in output_files.items()}
        files_out.update(_scan_output_files(ctx))

        out: StepResult = {
            "logs": [f"[plane_planning] {summary}"],
            "metrics": metrics,
            "files": files_out,
        }

        def _fail_round(err_msg: str) -> StepResult:
            append_log(
                ctx.work_root, err_msg, level="ERROR", command=intent_cmd,
                detail="\n".join(errors[:20]) if errors else summary,
            )
            out["error"] = err_msg
            out["hitl"] = {}
            out["steps"] = [self.make_record(
                "failed", ended_at=self._now(),
                log_tail=[summary, err_msg, *errors[:5]],
                metrics=metrics,
            )]
            return out

        # 单命令 / 批次：任一步失败 → 向前端返回具体错误并结束本轮（不进入 plane_planning 循环 HITL）
        if mode in ("single", "batch") and err_n > 0:
            return _fail_round(_round_error_message(results))

        def _plan_loop_hitl(reason: str) -> StepResult:
            plane_rec = self.make_record(
                "completed", ended_at=self._now(), progress=100,
                artifacts=list(output_files.values()),
                log_tail=[summary], metrics=metrics,
            )
            out["steps"] = [plane_rec]
            out["current_step"] = self.key
            out["hitl"] = {
                "step": self.key,
                "reason": reason,
                "need_files": [],
                "need_inputs": [{
                    "id": "plan_next",
                    "label": "下一步：继续规划任务，或生成完整 LLD 设计",
                    "options": list(_NEXT_PLAN_OPTIONS),
                }],
            }
            return out

        is_error = bool(err_n and ok_n == 0)
        if is_error:
            return _fail_round(_round_error_message(results))

        # 全部跳过（007 缺 sheet / 格式不可用）
        if ok_n == 0 and skip_n > 0 and err_n == 0:
            if mode == "full":
                warn = (
                    f"地址规划批次 {skip_n} 项因 007 缺少对应 sheet 或格式不可用已跳过。"
                    "将继续尝试 LLD 融合（可沿用 Output 历史平面表）。"
                )
                metrics["plane_warnings"] = [warn, *skip_notes[:8]]
                out["metrics"] = metrics
                emit(f"[{self.key}] {warn}")
                out["logs"].append(f"[plane_planning] {warn}")
                return out
            emit(
                f"[{self.key}] 本批次 {skip_n} 项因 007 sheet 缺失或不可用已跳过，"
                "未生成平面规划产物"
            )
            return _plan_loop_hitl(
                f"本批次 {skip_n} 项因 007 缺少对应 sheet 或格式不可用已跳过，"
                "未生成平面规划产物。可更换输入件后重试，"
                "或继续选择其它规划任务（可用「、」分隔一次输入多个），"
                "或选择「生成完整 LLD 设计」尝试融合已有产物。"
            )

        # 单命令 / 批次有成功项 → 停在 LLD 生成阶段，等待下一步
        if mode in ("single", "batch") and ok_n > 0:
            done_cmds = [
                qp["command"] for qp in queue_progress if qp.get("status") == "ok"
            ] or [intent_cmd]
            done_label = "、".join(done_cmds)
            emit(f"[{self.key}] 模式 {mode} → 已完成「{done_label}」，停在 LLD 生成阶段，等待下一步选择")
            return _plan_loop_hitl(
                f"已完成「{done_label}」规划，结果已生成（见「规划覆盖 / 输出件」）。\n"
                "尚未生成完整 LLD 设计文件。可继续选择其它规划任务累积规划"
                "（可用「、」分隔一次输入多个任务），"
                "或选择「生成完整 LLD 设计」融合并进入交付收尾（设备名称替换 / ZTP / 发布）。"
            )

        return out
