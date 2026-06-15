"""LangGraph 节点 · 命令调测设备范围采集（scope_input → 解析 → 预览 → scope_confirm → ready）。"""
from __future__ import annotations

from typing import Any

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..scope_preview import preview_commission_scope
from ._sd_ops import COMMAND_LABELS, _chain
from ._hitl import (
    commission_state,
    scope_confirm_input,
    scope_input_hitl,
    apply_parsed_to_project,
    is_scope_ready_for,
)
from .scope_parse import format_scope_summary, parse_commission_scope_text, normalize_parsed


class CommissionScopeStep(BaseStep):
    key = "commission_scope"
    name = "设备范围确认"
    internal = True

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        chain = _chain(ctx.work_root)
        if not chain.get("step8_toolkit_import_at"):
            return {
                "ok": False,
                "missing": ["Toolkit 导入完成标记（需先 toolkit_import）"],
                "found": [],
                "note": "",
            }

        comm = commission_state(ctx.project)
        cmd = str(comm.get("pending_command") or "").strip()
        if not cmd:
            return {
                "ok": False,
                "missing": [],
                "found": [],
                "note": "未指定调测命令",
                "need_inputs": scope_input_hitl("调测命令", "请从右侧调度区选择要执行的命令。"),
            }

        phase = str(comm.get("phase") or "scope_input")
        label = COMMAND_LABELS.get(cmd, cmd)

        if phase == "ready" and is_scope_ready_for(ctx.project, cmd):
            return {"ok": True, "missing": [], "found": [], "note": ""}

        if phase == "scope_confirm":
            parsed = normalize_parsed(comm.get("parsed"))
            preview = comm.get("preview") if isinstance(comm.get("preview"), dict) else {}
            summary = str(comm.get("summary") or (format_scope_summary(parsed) if parsed else ""))
            count = preview.get("device_count")
            desc = summary
            if count is not None:
                desc = f"{summary}\n预计设备 {count} 台"
            if preview.get("message"):
                desc = f"{desc}\n{preview['message']}"
            return {
                "ok": False,
                "missing": [],
                "found": [],
                "note": f"确认「{label}」设备范围",
                "need_inputs": scope_confirm_input(cmd, label, desc),
            }

        # scope_input：已有待解析文本则放行 run() 做解析
        if phase == "scope_input" and str(comm.get("scope_text") or "").strip():
            return {"ok": True, "missing": [], "found": [], "note": ""}

        err = str(comm.get("parse_error") or "").strip()
        note = f"请填写「{label}」的设备范围"
        if err:
            note = f"{note}\n{err}"
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": note,
            "need_inputs": scope_input_hitl(cmd, label, err),
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        comm = commission_state(ctx.project)
        cmd = str(comm.get("pending_command") or "").strip()
        label = COMMAND_LABELS.get(cmd, cmd)
        phase = str(comm.get("phase") or "scope_input")

        if phase == "ready" and is_scope_ready_for(ctx.project, cmd):
            emit(f"[{self.key}] 范围已确认，准备执行 {label}")
            project = apply_parsed_to_project(dict(ctx.project or {}))
            confirmations = dict(project.get("confirmations") or {})
            confirmations[cmd] = True
            project["confirmations"] = confirmations
            emit(f"[{self.key}] 已确认范围：{comm.get('summary') or ''}")
            return {
                "project": project,
                "metrics": {"commission_scope_ready": True, "commission_command": cmd},
                "route_to": cmd,
            }

        # scope_input → 解析 + 干跑预览
        text = str(comm.get("scope_text") or "").strip()
        if not text:
            return self._scope_input_hitl_result(ctx.project, comm, label, "请填写设备范围")

        parsed_result = parse_commission_scope_text(text)
        if not parsed_result.get("ok") or not parsed_result.get("parsed"):
            err = str(parsed_result.get("error") or "解析失败")
            comm["parse_error"] = err
            comm.pop("parsed", None)
            comm.pop("preview", None)
            return self._scope_input_hitl_result(ctx.project, comm, label, err)

        parsed = parsed_result["parsed"]
        summary = str(parsed_result.get("summary") or format_scope_summary(parsed))
        preview = preview_commission_scope({
            "step_key": cmd,
            "command": cmd,
            **parsed,
        })
        comm["parsed"] = dict(parsed)
        comm["summary"] = summary
        comm["preview"] = preview
        comm["phase"] = "scope_confirm"
        comm.pop("parse_error", None)

        emit(f"[{self.key}] 已解析：{summary}")
        if preview.get("ok"):
            emit(f"  预计设备 {preview.get('device_count', 0)} 台")
        else:
            emit(f"  预览：{preview.get('error') or preview.get('message') or '不可用'}")

        desc = summary
        if preview.get("device_count") is not None:
            desc = f"{summary}\n预计设备 {preview['device_count']} 台"
        if not preview.get("ok"):
            desc = f"{desc}\n预览：{preview.get('error') or '设备解析暂不可用，仍可确认执行'}"

        return {
            "current_step": self.key,
            "project": {**dict(ctx.project or {}), "commission": comm},
            "hitl": {
                "step": self.key,
                "reason": f"确认「{label}」设备范围",
                "need_inputs": scope_confirm_input(cmd, label, desc),
            },
        }

    def _scope_input_hitl_result(
        self,
        project: dict[str, Any],
        comm: dict[str, Any],
        label: str,
        err: str,
    ) -> StepResult:
        cmd = str(comm.get("pending_command") or "")
        comm["phase"] = "scope_input"
        return {
            "current_step": self.key,
            "project": {**dict(project or {}), "commission": comm},
            "hitl": {
                "step": self.key,
                "reason": f"请填写「{label}」的设备范围" + (f"\n{err}" if err else ""),
                "need_inputs": scope_input_hitl(cmd, label, err),
            },
        }
