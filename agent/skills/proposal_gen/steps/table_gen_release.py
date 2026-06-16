"""proposal_gen · table_gen_release"""
from __future__ import annotations

from typing import Any

from ...base import BaseStep, CheckResult, Emit, SkillContext, SkillState, StepResult
from ...early_io.paths import resolve_early_io_paths, resolve_project_id
from ...early_io.promote import promote_all_tables
from ..release_meta import append_release_version


class TableGenReleaseStep(BaseStep):
    key = "table_gen_release"
    name = "预案落盘与发布确认"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"ok": False, "missing": ["project_id"], "found": []}
        io.proposal_output_root.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "missing": [], "found": [io.rel(io.proposal_output_root)]}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        io = resolve_early_io_paths(ctx.project)
        if io is None:
            return {"error": "缺少 project_id"}

        pid = resolve_project_id(ctx.project)
        confirm = str((ctx.project or {}).get("release_confirm") or "").strip()

        if confirm == "save_draft":
            emit("已确认：仅保存草稿（输出结果 xlsx 已在 promote 阶段落盘）")
            return {
                "metrics": {"release_mode": "save_draft"},
                "files": dict(state.get("files") or {}),
            }

        if confirm == "release":
            emit("发布：写入预案版本信息表 …")
            try:
                row = append_release_version(
                    pid,
                    operator=str((ctx.project or {}).get("operator") or "LangGraph"),
                    change_description=str(
                        (ctx.project or {}).get("release_change_description")
                        or "proposal_gen · table_gen_release"
                    ),
                    project_name=str((ctx.project or {}).get("project_name") or ""),
                )
            except Exception as e:
                return {"error": f"版本记录写入失败: {e}"}
            ver = str(row.get("proposalVersion") or "")
            emit(f"已发布预案版本 {ver}")
            return {
                "artifacts": [f"早期介入/交付预案/输出结果/预案版本信息表.xlsx"],
                "metrics": {"release_mode": "release", "proposal_version": ver},
                "files": {"proposal_version": ver},
            }

        emit("promote：解析结果 → 输出结果/*.xlsx …")
        results = promote_all_tables(io, proposal_version="草稿")
        written = [r for r in results if r.status in ("written", "empty")]
        skipped = [r for r in results if r.status == "skipped"]
        errors = [r for r in results if r.status == "error"]

        for r in results:
            if r.status == "written":
                emit(f"  ✓ {r.xlsx_name}（{r.row_count} 行）← {r.message}")
            elif r.status == "empty":
                emit(f"  ○ {r.xlsx_name}（空表头）{r.message}")
            elif r.status == "skipped":
                emit(f"  ⊘ {r.xlsx_name}：{r.message}")
            elif r.status == "error":
                emit(f"  ✗ {r.xlsx_name}：{r.message}")

        files: dict[str, Any] = {
            "promoted_tables": [r.path for r in written if r.path],
        }
        metrics = {
            "promoted_written": len([r for r in written if r.status == "written"]),
            "promoted_empty": len([r for r in written if r.status == "empty"]),
            "promoted_skipped": len(skipped),
            "promoted_errors": len(errors),
            "table_gen_stub": False,
        }

        if errors and not written:
            return {
                "error": "全部表 promote 失败，请检查上游解析结果目录",
                "metrics": metrics,
            }

        return {
            "artifacts": [r.path for r in written if r.path],
            "files": files,
            "metrics": metrics,
            "hitl": {
                "step": self.key,
                "reason": "解析结果已 promote 至输出结果。确认生成预案并决策？",
                "need_inputs": [
                    {
                        "id": "release_confirm",
                        "label": "发布确认",
                        "options": [
                            {"id": "save_draft", "label": "仅保存草稿", "value": "save_draft"},
                            {"id": "release", "label": "生成预案并决策", "value": "release"},
                        ],
                    }
                ],
            },
        }
