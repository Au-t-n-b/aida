"""
step 5 · 生成 ZTP 设计文件（Raw Skill §6 ztp_generate · 确定性，无 LLM）

调用 a3 a3-generate-ztp-lld-workflow · offline_generate_ztp_lld_pipeline.py
（含 prerequisite_runner 自动补齐前置 · A009）。
"""
from __future__ import annotations

from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..pipelines.inputs import collect_inputs, label_of
from ..pipelines.a3_bridge import run_command
from ..pipelines.path_manifest import relpath_for_artifact
from ..pipelines.path_manifest import abs_input_dir


class ZtpGenerateStep(BaseStep):
    key = "ztp_generate"
    name = "生成 ZTP 设计文件"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        # ② 单命令 / 批次模式：不需要 ZTP（仅完整交付才生成）→ 放行，run 内自跳过
        found = collect_inputs(ctx.work_root)
        if "Location_Information" not in found:
            lbl = label_of("Location_Information")
            return {
                "ok": False,
                "missing": [str(abs_input_dir() / lbl)],
                "found": [str(f.path) for f in found.values()],
                "note": f"生成 ZTP 设计文件需要 {lbl}。",
            }
        return {"ok": True, "missing": [], "found": [], "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        from agent.sdui.projector_base import collect_metrics
        m = collect_metrics(state)
        if m.get("sd_mode") in ("single", "batch"):
            emit(f"[{self.key}] 模式 {m.get('sd_mode')} → 跳过 ZTP 生成（仅完整交付执行）")
            return {
                "logs": ["[ztp_generate] 非完整交付模式，跳过 ZTP 生成"],
                "metrics": {"ztp_file": "", "ztp_auto_prereq": False, "ztp_warnings": [],
                            "ztp_status": "skipped"},
            }
        emit(f"[{self.key}] 调用 A3 子 skill：生成ZTP设计文件")
        result = run_command("生成ZTP设计文件", ctx.work_root, emit=emit)

        warnings: list[str] = []
        ztp_file = ""
        auto_prereq = False

        if result.status == "ok" and result.output_files:
            def _is_ztp_product(p: str) -> bool:
                name = Path(p).name.upper()
                if "LLD设计" in name and "ZTP" not in name:
                    return False
                return "ZTP" in name or name.endswith(".ZIP") or name.endswith(".JSON")

            ztp_candidates = [p for p in result.output_files if _is_ztp_product(p)]
            ztp_file = ztp_candidates[-1] if ztp_candidates else ""
            if ztp_file:
                emit(f"[{self.key}] → {Path(ztp_file).name}")
        else:
            auto_prereq = "补齐" in result.summary or "prereq" in result.log_tail.lower()
            warnings.append(result.summary)
            if result.errors:
                warnings.extend(result.errors[:3])
            emit(f"[{self.key}] ⚠ {result.summary}")

        # ── step6 其余开局产物（对齐原始 skill sd_step6_ztp_cfg / sd_step6_lq_open）──
        # 生成ZTP配置文件 → ZTP 配置文件 zip；生成灵衢开局文件 → api_request.json。
        # 二者均以 ZTP_LLD.xlsx 为输入，故仅在 ZTP 设计文件生成成功后链式补齐；
        # 任一失败/跳过只记 warning，不阻断完整交付主流程（与原始 skill 三选一并列产物对齐）。
        cfg_file = ""
        lq_open_file = ""
        if result.status == "ok" and ztp_file:
            cfg_file = self._run_followup(
                ctx, emit, "生成ZTP配置文件", suffixes=(".zip",), warnings=warnings,
            )
            lq_open_file = self._run_followup(
                ctx, emit, "生成灵衢开局文件", suffixes=(".json", ".zip"), warnings=warnings,
            )

        files: dict[str, str] = {}
        if ztp_file:
            files["ztp_file"] = relpath_for_artifact(ztp_file)
        if cfg_file:
            files["ztp_cfg_file"] = relpath_for_artifact(cfg_file)
        if lq_open_file:
            files["lq_open_file"] = relpath_for_artifact(lq_open_file)

        return {
            "logs": [f"[ztp_generate] {result.summary}"],
            "metrics": {
                "ztp_file": relpath_for_artifact(ztp_file) if ztp_file else "",
                "ztp_cfg_file": relpath_for_artifact(cfg_file) if cfg_file else "",
                "lq_open_file": relpath_for_artifact(lq_open_file) if lq_open_file else "",
                "ztp_auto_prereq": auto_prereq,
                "ztp_warnings": warnings,
            },
            "files": files,
            **({"error": result.errors[0]} if result.status == "error" else {}),
        }

    def _run_followup(
        self,
        ctx: SkillContext,
        emit: Emit,
        command: str,
        *,
        suffixes: tuple[str, ...],
        warnings: list[str],
    ) -> str:
        """链式执行 step6 后续开局命令（best-effort）：返回首个匹配后缀的产物路径，失败仅记 warning。"""
        emit(f"[{self.key}] 调用 A3 子 skill：{command}")
        res = run_command(command, ctx.work_root, emit=emit)
        if res.status == "ok" and res.output_files:
            picked = [p for p in res.output_files if p.lower().endswith(suffixes)]
            out = picked[-1] if picked else res.output_files[-1]
            emit(f"[{self.key}] → {Path(out).name}")
            return out
        warnings.append(f"{command}：{res.summary}")
        emit(f"[{self.key}] ⚠ {command} {res.status}：{res.summary}")
        return ""
