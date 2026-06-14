"""
preflight · 环境预检（internal=True，豁免 SKILL.md 契约）

检查 ProjectData/Input 是否已有上游《交付计划表.xlsx》（+《设备位置表》《到货信息表》），
作为「生成责任人信息表 / 生成设备安装实施计划」的输入源。
"""
from __future__ import annotations

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._io import (
    refresh_task_metrics,
    tasks_state_path,
    is_pipeline_replay,
    find_delivery_plan,
    find_position_table,
    find_arrival_table,
)
from ..path_config import get_upstream_input_dir
from ..services.task_store import get_tasks


class PreflightStep(BaseStep):
    key = "preflight"
    name = "环境预检"
    artifacts_pattern = []
    internal = True

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        return {"ok": True, "missing": [], "found": [], "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        ctx.ensure_dirs()
        reset_info = ctx.project.get("_last_reset")
        if isinstance(reset_info, dict) and reset_info.get("ok"):
            n = reset_info.get("removed_count", 0)
            emit(f"[preflight] 已重置会话：清除 {n} 个历史产物/运行态文件")

        if is_pipeline_replay(ctx.project):
            emit("[preflight] 扫描设备安装环境与上游交付计划表…")
        else:
            emit("[preflight] 正在扫描设备安装环境…")
            emit("[preflight] 正在校验上游交付计划表…")

        delivery = find_delivery_plan(ctx)
        position = find_position_table(ctx)
        arrival = find_arrival_table(ctx)
        plan_ok = bool(delivery)
        tasks_n = len(get_tasks(str(tasks_state_path(ctx))))

        emit(f"  输入目录：{get_upstream_input_dir(ctx.project)}")
        emit(f"  {'✓' if delivery else '✗'} 交付计划表: {'已就绪' if delivery else '缺失'}")
        emit(f"  {'✓' if position else '✗'} 设备位置表: {'已就绪' if position else '缺失（SN 扫码表需要）'}")
        emit(f"  {'✓' if arrival else '✗'} 到货信息表: {'已就绪' if arrival else '缺失（设备大类映射需要）'}")
        if not plan_ok:
            emit("  期望文件：交付计划表.xlsx（置于上游输入目录）")

        command = (ctx.project or {}).get("command", "") or "build"
        emit(f"[preflight] 当前命令: {command}")

        # full_restart 重放（用户已在下游 HITL 交互过）时跳过纯展示用的 LLM 摘要：
        # 该调用约 19s 且无业务作用，重放期间会阻塞整条流水线、让前端冻结数十秒（=「卡住」）。
        is_replay = is_pipeline_replay(ctx.project)
        ai_text = ""
        if is_replay:
            emit("[preflight] 重放续跑，跳过 LLM 预检摘要")
        else:
            try:
                prompt = (
                    "你是华为智算 ICT 交付「设备安装」模块的 AI 助手。\n"
                    f"项目：{ctx.project.get('project_name', '未知')}\n"
                    f"当前命令：{command}\n"
                    f"输入目录：{get_upstream_input_dir(ctx.project)}\n"
                    f"交付计划表：{'已就绪' if delivery else '缺失'}；"
                    f"设备位置表：{'已就绪' if position else '缺失'}；"
                    f"到货信息表：{'已就绪' if arrival else '缺失'}\n"
                    f"已解析任务数：{tasks_n}\n\n"
                    "说明：主建设流程解析《交付计划表》生成责任人信息表与设备安装实施计划"
                    "（结合设备位置表/到货信息表），再进入勾选下发。\n"
                    "请用 2-3 句中文给出预检结论：整体状态 + 最关键的缺失项 + 建议下一步。"
                    "不要加标号，不要客套。"
                )
                resp = ctx.invoke_llm(
                    [
                        ("system", "你是设备安装交付 AI，回答精炼直接。"),
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
            except Exception as e:  # noqa: BLE001
                ai_text = ""
                emit(f"⚠ LLM 摘要跳过（{e}）")

        metrics: dict = {
            "source_dir": str(get_upstream_input_dir(ctx.project)),
            "dispatch_plan_ready": plan_ok,
            "parsed_tasks": tasks_n,
        }
        if ai_text:
            metrics["ai_summary"] = ai_text.strip()
        metrics.update(refresh_task_metrics(ctx))
        return {"metrics": metrics}
