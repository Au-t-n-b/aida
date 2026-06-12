"""
step 7 · 发布完成（Raw Skill §6 publish）

汇总产物 → 写执行摘要 → 回写进度。无对外通知（A014：本模块仅大盘 + 产物发布）。
warning（降级 xlsx / 跳过平面 / 自动补齐）从前序 step 的记录里汇总展示。
"""
from __future__ import annotations

import json

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from ..pipelines.path_manifest import abs_artifacts_dir, ensure_parent_dir


class PublishStep(BaseStep):
    key = "publish"
    name = "发布完成"
    artifacts_pattern = [str(abs_artifacts_dir() / "执行摘要.md")]

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        out_dir = ctx.output_dir

        # 扫描产物（真实落盘文件；目录不存在则视为空）
        artifacts = (
            [p for p in out_dir.rglob("*")
             if p.is_file() and not p.name.startswith("~$") and p.name != "执行摘要.md"]
            if out_dir.is_dir() else []
        )
        xlsx_n = sum(1 for p in artifacts if p.suffix.lower() == ".xlsx")
        manifest_n = sum(1 for p in artifacts if p.suffix.lower() == ".json")

        # 汇总前序 step 的 warning（state.steps 累加自 reducer）
        warnings: list[str] = []
        for rec in state.get("steps", []) or []:
            m = rec.get("metrics") or {}
            for key in ("lld_warnings", "ztp_warnings"):
                warnings.extend(m.get(key) or [])
        if manifest_n:
            warnings.append(
                f"{manifest_n} 个产物为 JSON manifest 降级（需新增工具 doc_write_xlsx 以产出正式 .xlsx）"
            )

        # 执行摘要
        lines = ["# 系统设计 · 执行摘要", "",
                 f"- 项目：{(ctx.project or {}).get('project_name', '规划设计 · 系统设计')}",
                 f"- 产物文件：{len(artifacts)} 个（xlsx {xlsx_n} · manifest {manifest_n}）", ""]
        if artifacts:
            lines.append("## 产物清单")
            lines += [f"- {p.relative_to(ctx.work_root)}" for p in sorted(artifacts)]
            lines.append("")
        if warnings:
            lines.append("## 警告（非阻断）")
            lines += [f"- {w}" for w in warnings]
        summary_path = out_dir / "执行摘要.md"
        ensure_parent_dir(summary_path)
        summary_path.write_text("\n".join(lines), encoding="utf-8")

        # 结构化结果（供 evals 读 · 阈值断言用）。state.steps 为前序记录，本步追加为 completed。
        agg: dict = {}
        exec_steps: list[dict] = []
        for rec in state.get("steps", []) or []:
            exec_steps.append({"step": rec.get("key"), "name": rec.get("name"),
                               "status": rec.get("status")})
            agg.update(rec.get("metrics") or {})
        exec_steps.append({"step": self.key, "name": self.name, "status": "completed"})
        total = len(exec_steps)
        completed = sum(1 for s in exec_steps if s["status"] == "completed")
        plane_total = int(agg.get("plane_total", 0) or 0)
        skill_result = {
            "skill": "system_design",
            "run_id": state.get("run_id", ""),
            "execution": {"steps": exec_steps},
            "completion_rate": round(completed / total, 4) if total else 0.0,
            "metrics": {
                "plane_done": int(agg.get("plane_done", 0) or 0),
                "plane_total": plane_total,
                "plane_coverage": round(int(agg.get("plane_done", 0) or 0) / plane_total, 4) if plane_total else 0.0,
                "lld_planes_merged": int(agg.get("lld_planes_merged", 0) or 0),
                "artifact_count": len(artifacts),
                "warning_count": len(warnings),
            },
        }
        result_path = out_dir / "skill_result.json"
        ensure_parent_dir(result_path)
        result_path.write_text(json.dumps(skill_result, ensure_ascii=False, indent=2), encoding="utf-8")
        emit(f"[{self.key}] 已发布 {len(artifacts)} 个产物，写出执行摘要 + skill_result.json；回写交付进度")

        return {
            "logs": [f"[publish] 发布完成：{len(artifacts)} 个产物，{len(warnings)} 条警告"],
            "metrics": {
                "publish_artifact_count": len(artifacts),
                "publish_xlsx_count": xlsx_n,
                "publish_manifest_count": manifest_n,
                "publish_warnings": warnings,
            },
            "files": {"exec_summary": str(summary_path)},
        }
