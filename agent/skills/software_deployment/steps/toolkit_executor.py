"""Step 7 · 配置调测设备。"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..bridge import ensure_runtime
from ._sd_ops import _chain, op_toolkit_executor
from ._hitl import executor_config_input, is_confirmed


class ToolkitExecutorStep(BaseStep):
    key = "toolkit_executor"
    name = "配置调测设备"
    artifacts_pattern = ["ProjectData/plan/RunTime/toolkit_executor.json"]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if not _chain(ctx.work_root).get("step6_cloudops_full_at"):
            return {
                "ok": False,
                "missing": ["ProjectData/plan/Output/CloudOps完整配置文件.xlsx（需先 cloudops_full）"],
                "found": [],
                "note": "",
            }
        ensure_runtime(ctx.work_root)
        from toolkit_executor import load_executor_config  # noqa: WPS433

        cfg = load_executor_config(ctx.work_root)
        proj = ctx.project or {}
        # 磁盘上已有 IP/SK 也须本 run 内确认，避免步骤 6 后静默跳过步骤 7。
        if proj.get("reconfigure_executor") or not is_confirmed(proj, self.key):
            ip = str(cfg.get("base_url_ip") or proj.get("base_url_ip") or "").strip()
            note = "步骤 7：请填写调测设备 IP/SK"
            if ip:
                note = f"步骤 7：请确认调测设备配置（当前 IP {ip}）"
            if proj.get("reconfigure_executor"):
                note = "修改调测设备 IP/SK（将写入 toolkit_executor.json）"
            return {
                "ok": False,
                "missing": [],
                "found": [],
                "note": note,
                "need_inputs": executor_config_input(),
            }
        if (cfg.get("base_url_ip") and cfg.get("secret_key")) or (
            proj.get("base_url_ip") and proj.get("secret_key")
        ):
            return {"ok": True, "missing": [], "found": [], "note": ""}
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": "步骤 7 需填写调测设备 IP/SK",
            "need_inputs": executor_config_input(),
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 写入调测设备配置…")
        proj = ctx.project or {}
        cfg = {
            "base_url_ip": str(proj.get("base_url_ip") or "").strip(),
            "secret_key": str(proj.get("secret_key") or "").strip(),
            "base_url_port": str(proj.get("base_url_port") or "28880").strip(),
        }
        result = op_toolkit_executor(ctx.work_root, config=cfg if cfg["base_url_ip"] else None)
        if not result.get("ok"):
            return {"error": result.get("error") or "配置失败"}
        emit(f"[{self.key}] 执行机 {result.get('base_url_ip')}")
        return {"metrics": {"executor_ip": result.get("base_url_ip", "")}}
