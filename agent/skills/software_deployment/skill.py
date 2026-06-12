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

from ..base import BaseSkill, SkillState
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
DISPATCH_STEP_KEYS: tuple[str, ...] = COMMISSION_STEP_KEYS + ("commission_report",)


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

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        p = dict(project or {})
        confirmations = dict(p.get("confirmations") or {})
        target = str(payload.get("command") or hitl_step or "").strip()
        choice = payload.get("choice")

        if payload.get("rerun") and target:
            confirmations.pop(target, None)

        if choice == "confirm" and target:
            confirmations[target] = True
        p["confirmations"] = confirmations

        if hitl_step == "toolkit_executor":
            raw_cfg: dict[str, Any] = {}
            if isinstance(choice, str) and choice.strip() and choice != "confirm":
                raw_cfg = _parse_executor_payload(choice)
            for key in ("base_url_ip", "secret_key", "base_url_port"):
                value = payload.get(key) or raw_cfg.get(key)
                if value:
                    p[key] = value

        for key in ("base_url_ip", "secret_key", "base_url_port", "project_id", "scope"):
            if payload.get(key):
                p[key] = payload[key]
        scope = payload.get("scope")
        if isinstance(scope, str) and scope.strip():
            p["scope"] = scope.strip()
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
