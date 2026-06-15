"""
SoftwareDeploymentSkill · 软件部署与调测

计划 1～3 → CloudOps 4～6 → Toolkit 7～8 →（工作台调度）init_install 四条命令 → 报告 13

编排：
  · 步骤 1～8 线性 DAG，在 toolkit_import 完成后结束（不自动串行四条调测命令）。
  · 步骤 9～12 与报告 13 仅通过 resume/run_step 单步调度（可反复执行同一条命令）。
  · start.entry_mode=commission 且 Toolkit 前置满足时，可直接进入命令调测工作台。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, ClassVar

from ..base import BaseSkill, SkillState, SkillContext
from ... import software_deployment_files as _sd_files
from .sdui import project as _sdui_project, SD_STEP_NAMES, SD_STEP_ORDER
from .steps import (
    PlanReceiveStep,
    PlanSplitStep,
    PlanDispatchStep,
    CloudopsInitStep,
    CloudopsSupplementStep,
    CloudopsFullStep,
    ToolkitExecutorStep,
    ToolkitImportStep,
    CommissionScopeStep,
    ConnectionStep,
    LqConnectionStep,
    WeakLightStep,
    HccsWeakLightStep,
    CommissionReportStep,
)
from .steps._sd_ops import INIT_INSTALL_COMMANDS, _chain


from .bridge import get_sd_root as _get_software_deployment_root


# 线性段止于 toolkit_import；其后为命令调测调度区
LINEAR_STEP_KEYS: tuple[str, ...] = (
    "plan_receive",
    "plan_split",
    "plan_dispatch",
    "cloudops_init",
    "cloudops_supplement",
    "cloudops_full",
    "toolkit_executor",
    "toolkit_import",
)

COMMISSION_STEP_KEYS: tuple[str, ...] = INIT_INSTALL_COMMANDS
DISPATCH_STEP_KEYS: tuple[str, ...] = ("commission_scope",) + COMMISSION_STEP_KEYS + ("commission_report",)

# deploy_chain.json 时间戳 → 线性步骤 key（用于 Agent 重启后从磁盘恢复）
_CHAIN_AT_BY_STEP: tuple[tuple[str, str], ...] = (
    ("plan_receive", "step1_plan_receive_at"),
    ("plan_split", "step2_plan_split_at"),
    ("plan_dispatch", "step3_plan_dispatch_at"),
    ("cloudops_init", "step4_cloudops_init_at"),
    ("cloudops_supplement", "step5_cloudops_supplement_at"),
    ("cloudops_full", "step6_cloudops_full_at"),
    ("toolkit_executor", "step7_executor_config_at"),
    ("toolkit_import", "step8_toolkit_import_at"),
)


class SoftwareDeploymentSkill(BaseSkill):
    name = "software_deployment"
    description = (
        "软件部署与调测 · 计划→CloudOps→Toolkit→"
        "init_install(连线/弱光)×4→调测报告"
    )
    steps = [
        PlanReceiveStep(),
        PlanSplitStep(),
        PlanDispatchStep(),
        CloudopsInitStep(),
        CloudopsSupplementStep(),
        CloudopsFullStep(),
        ToolkitExecutorStep(),
        ToolkitImportStep(),
        CommissionScopeStep(),
        ConnectionStep(),
        LqConnectionStep(),
        WeakLightStep(),
        HccsWeakLightStep(),
        CommissionReportStep(),
    ]
    sdui_projector = staticmethod(_sdui_project)
    file_handler = _sd_files
    # resume 确认后沿主线自动串联（见 main._run_single_step_streaming chain_linear）
    LINEAR_STEP_KEYS: ClassVar[tuple[str, ...]] = LINEAR_STEP_KEYS

    # 全部步骤 HITL 走 step_retry，避免确认后 full_restart 重放 1～8 步
    step_retry_keys: list[str] = [s.key for s in steps]  # type: ignore[misc]
    dispatch_step_keys: list[str] = list(DISPATCH_STEP_KEYS)

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        p = dict(payload or {})
        p.setdefault("project_id", "nanobot-local")
        p.setdefault("scope", "all")
        p.setdefault("confirmations", {})
        p.setdefault("commission", {})
        return p

    def commission_preconditions_met(self) -> tuple[bool, str]:
        """Toolkit 导入完成即可进入命令调测工作台。"""
        chain = _chain(self.work_root)
        if chain.get("step8_toolkit_import_at"):
            return True, ""
        return False, "需先完成 Toolkit 导入（toolkit_import）"

    def build_commission_entry_state(self, run_id: str, project: dict[str, Any]) -> dict[str, Any]:
        """entry_mode=commission：跳过线性 1～8，直接进入命令调测工作台。"""
        ok, reason = self.commission_preconditions_met()
        if not ok:
            return {"error": reason}

        steps_out: list[dict[str, Any]] = []
        for key in LINEAR_STEP_KEYS:
            step = next(s for s in self.steps if s.key == key)
            steps_out.append(
                step.make_record(
                    "completed",
                    ended_at=step._now(),
                    progress=100,
                    log_tail=[f"[{key}] 前置已满足（直达调测）"],
                )
            )

        proj = dict(project or {})
        proj["commission_mode"] = True
        chain = _chain(self.work_root)
        self._hydrate_recovered_step_metrics(steps_out, chain)
        self._hydrate_step_artifacts(steps_out)
        return {
            "run_id": run_id,
            "skill_id": self.name,
            "project": proj,
            "steps": steps_out,
            "current_step": COMMISSION_STEP_KEYS[0],
            "overall_progress": int(100 * len(LINEAR_STEP_KEYS) / len(SD_STEP_ORDER)),
            "logs": [f"[start] 前置已满足，进入命令调测工作台 · run {run_id}"],
            "hitl": {},
        }

    def build_disk_recovery_state(self, run_id: str) -> dict[str, Any] | None:
        """Agent 内存 run 丢失时，据 deploy_chain.json 重建进度（刷新/重启后 rejoin）。"""
        chain = _chain(self.work_root)
        if not any(chain.get(at) for _, at in _CHAIN_AT_BY_STEP):
            return None

        if chain.get("step8_toolkit_import_at"):
            return self.build_commission_entry_state(run_id, self.initial_project({}))

        steps_out: list[dict[str, Any]] = []
        confirmations: dict[str, bool] = {}
        current: str | None = None
        last_done: str | None = None

        for key, at_key in _CHAIN_AT_BY_STEP:
            step = next(s for s in self.steps if s.key == key)
            if chain.get(at_key):
                steps_out.append(
                    step.make_record(
                        "completed",
                        ended_at=str(chain.get(at_key) or step._now()),
                        progress=100,
                        log_tail=[f"[{key}] 已从磁盘恢复为已完成"],
                    )
                )
                confirmations[key] = True
                last_done = key
            elif current is None:
                current = key
                break

        if not current:
            return self.build_commission_entry_state(run_id, self.initial_project({}))

        ctx = SkillContext(
            skill_id=self.name,
            work_root=self.work_root,
            run_id=run_id,
            project={"confirmations": confirmations},
            llm_factory=self.llm_factory,
        )
        step_obj = next(s for s in self.steps if s.key == current)
        check = step_obj.check_inputs(ctx)
        hitl: dict[str, Any] = {}
        if not check.get("ok"):
            missing = check.get("missing") or []
            need_inputs = check.get("need_inputs") or []
            note = check.get("note") or f"{step_obj.name} 待处理"
            hitl = {
                "step": current,
                "reason": note,
                "need_files": missing,
                "need_inputs": need_inputs,
                "need_edit": check.get("need_edit"),
            }
            steps_out.append(
                step_obj.make_record(
                    "hitl",
                    ended_at=step_obj._now(),
                    log_tail=[f"[{current}] 已从磁盘恢复，等待确认或补料"],
                )
            )

        progress = self._step_progress_pct(last_done) if last_done else 0
        self._hydrate_recovered_step_metrics(steps_out, chain)
        self._hydrate_step_artifacts(steps_out)
        return {
            "run_id": run_id,
            "skill_id": self.name,
            "project": {
                **self.initial_project({}),
                "confirmations": confirmations,
            },
            "steps": steps_out,
            "current_step": current,
            "overall_progress": progress,
            "logs": [
                f"[rejoin] Agent 重启后从 deploy_chain 恢复 · 当前步骤 {current} · run {run_id}",
            ],
            "hitl": hitl,
            "error": "",
        }

    def _hydrate_recovered_step_metrics(
        self,
        steps_out: list[dict[str, Any]],
        chain: dict[str, Any],
    ) -> None:
        """rejoin 后从磁盘产物回填 step.metrics，供 SDUI 计划/设备页签展示（投影器只读 metrics）。"""
        import json

        from .steps._preview_metrics import (
            device_stats,
            slim_device_tasks,
            slim_scene_spec,
            slim_third_tasks,
        )

        root = self.work_root
        by_key = {str(s.get("key") or ""): s for s in steps_out if s.get("key")}

        if by_key.get("plan_receive", {}).get("status") == "completed":
            tc = chain.get("step1_task_count")
            if tc:
                by_key["plan_receive"].setdefault("metrics", {})["task_count"] = tc

        if by_key.get("plan_split", {}).get("status") == "completed":
            metrics = by_key["plan_split"].setdefault("metrics", {})
            scene_path = root / "ProjectData/plan/RunTime/scene.json"
            if scene_path.is_file():
                try:
                    scene = json.loads(scene_path.read_text(encoding="utf-8"))
                    if isinstance(scene, dict):
                        metrics["scene_spec"] = slim_scene_spec(scene)
                except Exception:
                    pass
            tree_path = root / "ProjectData/plan/Output/plan_display_tree.json"
            third_path = root / "ProjectData/plan/Output/third_level_tasks.json"
            if tree_path.is_file():
                try:
                    raw = json.loads(tree_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        metrics["second_count"] = raw.get("secondCount") or chain.get("step1_task_count") or 0
                        metrics["third_count"] = raw.get("thirdCount") or chain.get("step2_third_task_count") or 0
                        rows = raw.get("rows") or []
                        if rows:
                            metrics["third_tasks_preview"] = slim_third_tasks(rows)
                except Exception:
                    pass
            elif third_path.is_file():
                try:
                    raw = json.loads(third_path.read_text(encoding="utf-8"))
                    tasks = raw.get("tasks") if isinstance(raw, dict) else []
                    if isinstance(tasks, list):
                        metrics["third_count"] = len(tasks)
                        metrics["third_tasks_preview"] = slim_third_tasks(tasks)
                except Exception:
                    pass
            if not metrics.get("second_count") and chain.get("step1_task_count"):
                metrics["second_count"] = chain["step1_task_count"]
            if not metrics.get("third_count") and chain.get("step2_third_task_count"):
                metrics["third_count"] = chain["step2_third_task_count"]

        if by_key.get("plan_dispatch", {}).get("status") == "completed":
            metrics = by_key["plan_dispatch"].setdefault("metrics", {})
            base_path = root / "ProjectData/plan/Output/device_base_table.json"
            if base_path.is_file():
                try:
                    raw = json.loads(base_path.read_text(encoding="utf-8"))
                    tasks = raw.get("tasks") if isinstance(raw, dict) else []
                    if isinstance(tasks, list):
                        metrics["device_rows"] = len(tasks)
                        metrics["device_tasks_preview"] = slim_device_tasks(tasks)
                        metrics["device_stats"] = device_stats(tasks)
                except Exception:
                    pass

        if by_key.get("toolkit_import", {}).get("status") == "completed":
            metrics = by_key["toolkit_import"].setdefault("metrics", {})
            receipt = root / "ProjectData/plan/RunTime/toolkit_import.json"
            if receipt.is_file():
                try:
                    raw = json.loads(receipt.read_text(encoding="utf-8"))
                    refresh = raw.get("refresh") if isinstance(raw.get("refresh"), dict) else {}
                    if refresh.get("devicesRefreshed") is not None:
                        metrics["refreshed_devices"] = refresh["devicesRefreshed"]
                    if refresh.get("rowsRefreshed") is not None:
                        metrics["refreshed_rows"] = refresh["rowsRefreshed"]
                    metrics["toolkit_imported"] = True
                except Exception:
                    pass

        from ._preview_metrics import build_commission_record

        _commission_cmds = (
            ("connection", "connection"),
            ("lq_connection", "lq_connection"),
            ("weak_light", "weak_light"),
            ("hccs_weak_light", "hccs_weak_light"),
        )
        for step_key, cmd in _commission_cmds:
            result_dir = root / f"ProjectData/results/{cmd}"
            if not result_dir.is_dir():
                continue
            try:
                has_output = any(result_dir.iterdir())
            except OSError:
                has_output = False
            if not has_output:
                continue
            rec = by_key.get(step_key)
            if not rec:
                rel = str(result_dir.relative_to(root)).replace("\\", "/")
                steps_out.append({
                    "key": step_key,
                    "name": step_key,
                    "status": "completed",
                    "metrics": {
                        f"{cmd}_ok": True,
                        "command": cmd,
                        "result_dir": rel,
                        "commission_record": build_commission_record(
                            step_key,
                            {"ok": True, "message": "已从磁盘恢复", "result_dir": rel},
                        ),
                    },
                })
                by_key[step_key] = steps_out[-1]
                continue
            metrics = rec.setdefault("metrics", {})
            if not metrics.get(f"{cmd}_ok"):
                metrics[f"{cmd}_ok"] = True
            if not metrics.get("result_dir"):
                metrics["result_dir"] = str(result_dir.relative_to(root)).replace("\\", "/")
            if not metrics.get("commission_record"):
                metrics["commission_record"] = build_commission_record(
                    step_key,
                    {
                        "ok": True,
                        "message": "已从磁盘恢复",
                        "result_dir": metrics["result_dir"],
                    },
                )

    def _hydrate_step_artifacts(self, steps_out: list[dict[str, Any]]) -> None:
        """rejoin 后从磁盘扫各步 artifacts_pattern，补全项目文档页签。"""
        from ..base import SkillContext

        ctx = SkillContext(
            skill_id=self.name,
            work_root=self.work_root,
            run_id="<hydrate>",
            llm_factory=self.llm_factory,
        )
        by_key = {str(s.get("key") or ""): s for s in steps_out if s.get("key")}
        for step_def in self.steps:
            rec = by_key.get(step_def.key)
            if not rec or rec.get("status") != "completed":
                continue
            arts = list(step_def.collect_existing_artifacts(ctx))
            metrics = rec.get("metrics") or {}
            if isinstance(metrics, dict):
                rd = str(metrics.get("result_dir") or "").strip().replace("\\", "/")
                if rd:
                    if "ProjectData/" in rd:
                        rd = rd[rd.index("ProjectData/") :]
                    full = ctx.work_root / rd
                    if full.is_file():
                        if rd not in arts:
                            arts.append(rd)
                    elif full.is_dir():
                        for child in sorted(full.iterdir()):
                            if child.is_file() and child.suffix.lower() in {".xlsx", ".xls", ".json", ".csv", ".txt"}:
                                rel = str(child.relative_to(ctx.work_root)).replace("\\", "/")
                                if rel not in arts:
                                    arts.append(rel)
            rec["artifacts"] = arts

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        p = dict(project or {})
        confirmations = dict(p.get("confirmations") or {})
        target = str(payload.get("command") or hitl_step or "").strip()
        choice = payload.get("choice")

        if payload.get("rerun") and target:
            confirmations.pop(target, None)

        comm = dict(p.get("commission") or {})
        scope_step = hitl_step == "commission_scope" or target == "commission_scope"
        cmd_from_payload = str(payload.get("command") or "").strip()
        if scope_step or cmd_from_payload:
            if payload.get("scope_direct") and cmd_from_payload:
                from .steps.scope_parse import normalize_parsed, format_scope_summary

                parsed = normalize_parsed({
                    "scope": payload.get("scope") or "all",
                    "pod_ids": payload.get("pod_ids"),
                    "devices": payload.get("devices"),
                    "task_no": payload.get("task_no"),
                    "only_installed": payload.get("only_installed", True),
                })
                if parsed:
                    comm["pending_command"] = cmd_from_payload
                    comm["parsed"] = dict(parsed)
                    comm["summary"] = format_scope_summary(parsed)
                    comm["phase"] = "ready"
                    comm.pop("scope_text", None)
                    comm.pop("parse_error", None)
            elif cmd_from_payload:
                comm["pending_command"] = cmd_from_payload
                comm["phase"] = "scope_input"
                for k in ("parsed", "preview", "parse_error", "summary", "scope_text"):
                    comm.pop(k, None)
                if payload.get("rerun"):
                    confirmations.pop(cmd_from_payload, None)
            if isinstance(choice, str) and choice.strip() and choice not in ("confirm", "back"):
                comm["scope_text"] = choice.strip()
                comm.pop("parse_error", None)
            if choice == "confirm" and comm.get("phase") == "scope_confirm":
                comm["phase"] = "ready"
            if choice == "back":
                comm["phase"] = "scope_input"
                for k in ("parsed", "preview", "scope_text", "parse_error", "summary"):
                    comm.pop(k, None)
            p["commission"] = comm

        if choice == "confirm" and target and target != "commission_scope":
            confirmations[target] = True
        p["confirmations"] = confirmations

        if payload.get("reconfigure_executor"):
            p["reconfigure_executor"] = True
            try:
                from .bridge import get_sd_root, ensure_runtime
                root = get_sd_root()
                ensure_runtime(root)
                from toolkit_executor import load_executor_config  # noqa: WPS433

                cfg = load_executor_config(root)
                for key in ("base_url_ip", "secret_key", "base_url_port"):
                    if cfg.get(key) and not p.get(key):
                        p[key] = cfg[key]
            except Exception:
                pass

        if hitl_step == "toolkit_executor":
            raw_cfg: dict[str, Any] = {}
            if isinstance(choice, str) and choice.strip() and choice != "confirm":
                raw_cfg = _parse_executor_payload(choice)
            for key in ("base_url_ip", "secret_key", "base_url_port"):
                value = payload.get(key) or raw_cfg.get(key)
                if value:
                    p[key] = value
            if raw_cfg or payload.get("base_url_ip") or payload.get("secret_key"):
                p.pop("reconfigure_executor", None)

        for key in ("base_url_ip", "secret_key", "base_url_port", "project_id", "scope", "task_no"):
            if payload.get(key):
                p[key] = payload[key]
        scope = payload.get("scope")
        if isinstance(scope, str) and scope.strip():
            p["scope"] = scope.strip()
        if payload.get("pod_ids") is not None:
            raw_pods = payload.get("pod_ids")
            if isinstance(raw_pods, list):
                p["pod_ids"] = [int(x) for x in raw_pods if str(x).strip() != ""]
        if payload.get("devices") is not None:
            raw_devs = payload.get("devices")
            if isinstance(raw_devs, list):
                p["devices"] = [str(x).strip() for x in raw_devs if str(x).strip()]
        if payload.get("only_installed") is not None:
            p["only_installed"] = bool(payload.get("only_installed"))
        return p

    def build_graph(self, checkpointer=None):
        """线性 1～8；命令调测 9～13 仅单步调度，不在图中串行。"""
        import os
        from langgraph.graph import StateGraph, START, END
        from ..base import SkillContext, _get_run_push, default_checkpoint_db

        g = StateGraph(SkillState)
        ctx = SkillContext(
            skill_id=self.name,
            work_root=self.work_root,
            run_id="<init>",
            llm_factory=self.llm_factory,
        )
        ctx.ensure_dirs()

        def make_node(s):
            def _node(state: SkillState) -> dict:
                run_id = str(state.get("run_id", "<no-run>"))
                local_ctx = SkillContext(
                    skill_id=self.name,
                    work_root=self.work_root,
                    run_id=run_id,
                    project=state.get("project") or {},
                    llm_factory=self.llm_factory,
                    emit_push=_get_run_push(run_id),
                )
                return self.execute_step(s, state, local_ctx)

            return _node

        for step in self.steps:
            g.add_node(step.key, make_node(step))

        linear = [s for s in self.steps if s.key in LINEAR_STEP_KEYS]
        if linear:
            g.add_edge(START, linear[0].key)
            for i, step in enumerate(linear):
                next_key = linear[i + 1].key if i + 1 < len(linear) else None
                g.add_conditional_edges(
                    step.key,
                    self._make_router(step.key, next_key),
                    self._route_map(next_key),
                )

        # 调测 / 报告节点：仅 run_step 触发，图中无边
        for step in self.steps:
            if step.key not in LINEAR_STEP_KEYS:
                g.add_conditional_edges(
                    step.key,
                    self._make_router(step.key, None),
                    self._route_map(None),
                )

        if checkpointer is None:
            ckpt_mode = os.environ.get("AIDA_CHECKPOINT", "sqlite").strip().lower()
            if ckpt_mode == "memory":
                from langgraph.checkpoint.memory import MemorySaver

                checkpointer = MemorySaver()
            else:
                from langgraph.checkpoint.sqlite import SqliteSaver
                import sqlite3

                db_path = default_checkpoint_db()
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(db_path, check_same_thread=False)
                checkpointer = SqliteSaver(conn)

        return g.compile(checkpointer=checkpointer)

    def _next_step_key(self, current: str) -> str:
        """线性 8 完成后进入命令调测首命令（与 build_commission_entry_state / rejoin 对齐）。"""
        if current == "toolkit_import":
            return COMMISSION_STEP_KEYS[0]
        return super()._next_step_key(current)

    def _step_progress_pct(self, step_key: str) -> int:
        try:
            idx = SD_STEP_ORDER.index(step_key)
        except ValueError:
            return super()._step_progress_pct(step_key)
        return int(100 * (idx + 1) / len(SD_STEP_ORDER))


def _parse_executor_payload(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    out: dict[str, Any] = {}
    aliases = {"ip": "base_url_ip", "sk": "secret_key", "port": "base_url_port"}
    for line in text.replace(",", "\n").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = aliases.get(k.strip(), k.strip())
        if key in {"base_url_ip", "secret_key", "base_url_port"} and v.strip():
            out[key] = v.strip()
    return out


def get_software_deployment_skill():
    from ...llm import get_llm

    return SoftwareDeploymentSkill(work_root=_get_software_deployment_root(), llm_factory=get_llm)
