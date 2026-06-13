"""
step 5 · 生成 ZTP 设计文件 + ZTP 配置文件（Raw Skill §6 ztp_generate · 确定性，无 LLM）

完整交付收尾：无论 stage_select 选「名称替换」或「直接 ZTP」，本步均顺序执行：
  1. 生成ZTP设计文件 → ZTP_LLD.xlsx（007 缺 sheet 时跳过并提示，不阻断）
  2. 生成ZTP配置文件 → {project}_ZTP配置文件_*.zip
"""
from __future__ import annotations

from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..pipelines.inputs import collect_inputs, label_of
from ..pipelines.a3_bridge import run_command, A3RunResult
from ..pipelines.path_manifest import relpath_for_artifact
from ..pipelines.path_manifest import abs_input_dir
from ..pipelines.sheet007_preflight import is_soft_skip_message

_ZTP_DESIGN_CMD = "生成ZTP设计文件"
_ZTP_CFG_CMD = "生成ZTP配置文件"


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

        warnings: list[str] = []
        ztp_file, cfg_file, auto_prereq = self._run_ztp_pair(ctx, emit, warnings)

        files: dict[str, str] = {}
        if ztp_file:
            files["ztp_file"] = relpath_for_artifact(ztp_file)
        if cfg_file:
            files["ztp_cfg_file"] = relpath_for_artifact(cfg_file)

        summary_parts = []
        if ztp_file:
            summary_parts.append(Path(ztp_file).name)
        if cfg_file:
            summary_parts.append(Path(cfg_file).name)
        summary = "、".join(summary_parts) if summary_parts else "部分 ZTP 步骤已跳过，已继续后续流程"

        if cfg_file:
            ztp_status = "ok"
        elif ztp_file:
            ztp_status = "partial"
        elif warnings:
            ztp_status = "skipped"
        else:
            ztp_status = "skipped"

        return {
            "logs": [f"[ztp_generate] {summary}"],
            "metrics": {
                "ztp_file": relpath_for_artifact(ztp_file) if ztp_file else "",
                "ztp_cfg_file": relpath_for_artifact(cfg_file) if cfg_file else "",
                "lq_open_file": "",
                "ztp_auto_prereq": auto_prereq,
                "ztp_warnings": warnings,
                "ztp_status": ztp_status,
            },
            "files": files,
            "error": "",
        }

    def _run_ztp_pair(
        self,
        ctx: SkillContext,
        emit: Emit,
        warnings: list[str],
    ) -> tuple[str, str, bool]:
        """顺序执行 ZTP 设计 + 配置；007 缺 sheet 等软跳过只记 warning，始终尝试后续命令。"""
        emit(f"[{self.key}] 调用 A3 子 skill：{_ZTP_DESIGN_CMD}")
        design = run_command(_ZTP_DESIGN_CMD, ctx.work_root, emit=emit)

        auto_prereq = False
        ztp_file = self._resolve_ztp_design(ctx, emit, design, warnings)
        if "补齐" in design.summary or "prereq" in design.log_tail.lower():
            auto_prereq = True

        emit(f"[{self.key}] 调用 A3 子 skill：{_ZTP_CFG_CMD}")
        cfg = run_command(_ZTP_CFG_CMD, ctx.work_root, emit=emit)
        cfg_file = self._resolve_ztp_cfg(emit, cfg, warnings)

        return ztp_file, cfg_file, auto_prereq

    def _resolve_ztp_design(
        self,
        ctx: SkillContext,
        emit: Emit,
        result: A3RunResult,
        warnings: list[str],
    ) -> str:
        if result.status == "ok" and result.output_files:
            picked = self._pick_ztp_design(result.output_files)
            if picked:
                emit(f"[{self.key}] → {Path(picked).name}")
                return picked

        msg = result.summary or f"{_ZTP_DESIGN_CMD} 未产出"
        if is_soft_skip_message(msg) or result.status == "skipped":
            warnings.append(msg)
            emit(f"[{self.key}] ○ {msg}，尝试使用已有 ZTP_LLD 并继续生成配置文件")
        else:
            warnings.append(msg)
            if result.errors:
                warnings.extend(result.errors[:3])
            emit(f"[{self.key}] ⚠ {msg}")

        existing = self._find_existing_ztp_lld(ctx)
        if existing:
            emit(f"[{self.key}] 使用已有 {Path(existing).name} 继续")
        return existing

    def _resolve_ztp_cfg(self, emit: Emit, result: A3RunResult, warnings: list[str]) -> str:
        if result.status == "ok" and result.output_files:
            picked = [p for p in result.output_files if p.lower().endswith(".zip")]
            out = picked[-1] if picked else result.output_files[-1]
            emit(f"[{self.key}] → {Path(out).name}")
            return out

        msg = result.summary or f"{_ZTP_CFG_CMD} 未产出"
        if is_soft_skip_message(msg) or result.status == "skipped":
            warnings.append(msg)
            emit(f"[{self.key}] ○ {msg}，已跳过并继续后续发布流程")
        else:
            warnings.append(
                f"{_ZTP_CFG_CMD}未产出 zip（请检查项目信息收集表 ZTP配置 sheet 与 ZTP_LLD）：{msg}"
            )
            emit(f"[{self.key}] ⚠ {msg}")
        return ""

    @staticmethod
    def _find_existing_ztp_lld(ctx: SkillContext) -> str:
        out = ctx.output_dir
        if not out.is_dir():
            return ""
        for p in sorted(out.rglob("ZTP_LLD.xlsx"), key=lambda x: x.stat().st_mtime):
            if p.is_file() and not p.name.startswith("~$"):
                return str(p.resolve())
        for p in sorted(out.rglob("*"), key=lambda x: x.stat().st_mtime if x.is_file() else 0, reverse=True):
            if not p.is_file() or p.name.startswith("~$"):
                continue
            upper = p.name.upper()
            if p.suffix.lower() in (".xlsx", ".xls") and "ZTP" in upper and "LLD" in upper:
                return str(p.resolve())
        return ""

    @staticmethod
    def _pick_ztp_design(paths: list[str]) -> str:
        def _is_ztp_design(p: str) -> bool:
            name = Path(p).name.upper()
            if "LLD设计" in name and "ZTP" not in name:
                return False
            return name.endswith(".XLSX") or name.endswith(".XLS")

        cands = [p for p in paths if _is_ztp_design(p)]
        return cands[-1] if cands else ""
