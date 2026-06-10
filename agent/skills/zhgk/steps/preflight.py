"""
preflight · 环境预检 v4

扫描所有 step 的前置文件，生成预检报告 + LLM 友好摘要。
internal=True → 豁免 SKILL.md 契约约束。
"""
from __future__ import annotations

import json
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult


class PreflightStep(BaseStep):
    key = "preflight"
    name = "环境预检"
    artifacts_pattern = []
    internal = True

    # ── v4 前置文件清单（支持 glob 模式，含 * 时用 glob 扫描）──────────────
    REQUIRED: dict[str, list[str]] = {
        "filter_build": [
            "ProjectData/Template/入场评估标准表.xlsx",
        ],
        "report_gen_run": [
            "ProjectData/Template/新版项目工勘报告模板.docx",
            "ProjectData/Template/工勘常见高风险库.xlsx",
        ],
        "report_distribute": [
            # 实际文件名含 ACT001_ 前缀，使用 glob 模式匹配
            "ProjectData/Output/*工勘报告*.docx",
        ],
    }

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": [], "found": [], "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit("[preflight] 扫描前置文件…")

        summary_lines: list[str] = []
        all_missing: list[str] = []
        details: list[str] = []

        for step_key, files in self.REQUIRED.items():
            found, miss = [], []
            for rel in files:
                if "*" in rel:
                    # glob 模式：文件名可能含 ACT001_ 等前缀
                    matches = list(ctx.work_root.glob(rel))
                    if matches:
                        found.append(rel)
                    else:
                        miss.append(rel)
                else:
                    full = ctx.work_root / rel
                    (found if full.exists() else miss).append(rel)
            flag = "✓" if not miss else "⚠"
            summary_lines.append(f"  {flag} {step_key}: {len(found)} ok / {len(miss)} miss")
            details.append(f"### {step_key}\n  已有: {found}\n  缺失: {miss}")
            all_missing.extend(miss)

        # BOQ 特殊扫描
        boq_files = list(ctx.input_dir.glob("*BOQ*.xlsx")) if ctx.input_dir.exists() else []
        if boq_files:
            summary_lines.append(f"  ✓ BOQ: 检测到 {boq_files[0].name}")
        else:
            summary_lines.append("  ⚠ BOQ: ProjectData/Input/*BOQ*.xlsx 未发现")
            all_missing.append("ProjectData/Input/*BOQ*.xlsx")

        # project_info.json 状态
        info_path = ctx.runtime_dir / "project_info.json"
        if info_path.exists():
            try:
                info = json.loads(info_path.read_text(encoding="utf-8"))
                gc = info.get("generation_cooling", "")
                if gc:
                    summary_lines.append(f"  ✓ 代际制冷: {gc}（缓存于 project_info.json）")
            except Exception:
                pass

        for line in summary_lines:
            emit(line)

        # LLM 友好摘要（失败不阻断）
        try:
            proj = ctx.project
            prompt = (
                f"你是 AIDA 智慧工勘 v4 Agent。当前项目：\n"
                f"- 名称: {proj.get('project_name', '未知')}\n"
                f"- 编码: {proj.get('project_code', '未知')}\n"
                f"- 意图: {proj.get('intent', '待选择')}\n\n"
                f"前置检查结果：\n" + "\n".join(details) + "\n\n"
                f"BOQ: {'已就绪' if boq_files else '待上传'}\n"
                f"缺失件总数: {len(all_missing)}\n\n"
                f"请用 2-3 句中文给出预检结论：\n"
                f"1. 整体状态（一句话）\n"
                f"2. 最关键的缺失项（如有）+ 为何关键\n"
                f"3. 建议接下来做什么\n"
                f"不要加标号，不要客套。"
            )
            resp = ctx.invoke_llm(
                [
                    ("system", "你是华为智算 ICT 交付工勘 AI，回答精炼直接。"),
                    ("human", prompt),
                ],
                step_key=self.key,
                run_name=f"{ctx.skill_id}.{self.key}.summary",
                extra_tags=["kind:summary"],
            )
            ai_text = resp.content if isinstance(resp.content, str) else str(resp.content)
            emit("🤖 AI 摘要：")
            for line in ai_text.splitlines():
                emit(f"  {line}")
        except Exception as e:
            emit(f"⚠ LLM 摘要跳过（{e}）")

        return {
            "logs": [],
            "metrics": {
                "missing_count": len(all_missing),
                "boq_found": bool(boq_files),
                "template_ready": not any(
                    "Template" in m for m in all_missing
                ),
            },
        }
