"""
DeviceInstallSkill · 设备安装（新范式 · 单流水线 + 命令路由）

主建设流水线（command=build，线性）：
  preflight → plan_receive → task_dispatch → sn_generate → esn_fill
辅助流（独立 command，经命令守卫跳过其余步骤）：
  progress_report（progress_select + progress_apply）/ progress_query
  / plan_query / plan_adjust / device_overview

无 intent_select HITL：command 由 /start 启动载荷给定，每步 _command_guard.should_skip 决定跳过。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import BaseSkill
from . import files as _di_files
from .sdui import project as _sdui_project
from .steps import (
    PreflightStep,
    PlanReceiveStep,
    TaskDispatchStep,
    SnGenerateStep,
    EsnFillStep,
    ProgressSelectStep,
    ProgressApplyStep,
    ProgressQueryStep,
    PlanQueryStep,
    DeviceOverviewStep,
    PlanAdjustStep,
)


class DeviceInstallSkill(BaseSkill):
    name = "device_install"
    skill_md_path = Path(__file__).resolve().parents[3] / "skills" / "device_install" / "SKILL.md"
    description = (
        "设备安装（新范式 · 单流水线）。主建设流程：接收上游实施计划→计划下发→"
        "SN扫码表生成→ESN填写；辅助流：进展反馈/进展查询/计划查询/"
        "计划调整/设备总览（由启动载荷 command 路由，无意图选择卡）。"
    )
    steps = [
        PreflightStep(),
        PlanReceiveStep(),
        TaskDispatchStep(),
        SnGenerateStep(),
        EsnFillStep(),
        ProgressSelectStep(),
        ProgressApplyStep(),
        ProgressQueryStep(),
        PlanQueryStep(),
        DeviceOverviewStep(),
        PlanAdjustStep(),
    ]
    sdui_projector = staticmethod(_sdui_project)
    step_retry_keys: list[str] = []
    file_handler = _di_files

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        p = dict(payload or {})
        if p.pop("reset_workspace", None):
            summary = _di_files.reset_workspace(self.work_root)
            p["_last_reset"] = summary
        p.setdefault("project_code", "")
        p.setdefault("project_name", "")
        p.setdefault("command", "build")
        # 新会话不携带旧 HITL 编辑态
        for key in (
            "principal_rows", "tasks_rows", "tasks_confirmed",
            "dispatch_rows", "dispatch_confirmed", "esn_rows",
            "reporting_task_id", "reporting_status",
        ):
            p.pop(key, None)
        return p

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        """resume 时把 HITL 用户选择 / 在线编辑结果写入 project。"""
        project = dict(project)
        choice = payload.get("choice", "")
        rows = payload.get("rows")

        if hitl_step == "esn_fill":
            project["esn_rows"] = rows or []

        elif hitl_step == "task_dispatch":
            submitted = rows or []
            project["dispatch_rows"] = submitted

            def _sel(r: dict) -> bool:
                v = r.get("selected")
                if isinstance(v, bool):
                    return v
                if isinstance(v, str):
                    return v.lower() in ("true", "1", "yes", "on")
                return bool(v)

            has_sel = any(isinstance(r, dict) and _sel(r) for r in submitted)
            if has_sel:
                project["dispatch_confirmed"] = True
            else:
                project.pop("dispatch_confirmed", None)
                project.pop("dispatch_rows", None)

        elif hitl_step == "progress_select" and choice:
            project["reporting_task_id"] = choice

        elif hitl_step == "progress_apply" and choice:
            project["reporting_status"] = choice

        return project


def get_device_install_skill() -> DeviceInstallSkill:
    from ...llm import get_llm
    from .bridge import get_device_install_root
    return DeviceInstallSkill(
        work_root=Path(get_device_install_root()), llm_factory=get_llm
    )
