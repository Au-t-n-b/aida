"""
ZhgkSkill v4 · 智慧工勘（意图驱动单流水线）

4 个意图共享一条线性流水线；每个 step 调用 _intent_guard.should_skip()
决定是否跳过，从而在无需 dispatch_mode 的情况下实现多意图路由。

意图:
  scene_suggest  — 快速场景建议
  survey_work    — 全流程工勘（建表 → 勘测 → 评估 → 复勘闭环 → 报告分发）
  supplement     — 补充闭环（已有结果表 → 评估 → 补充/复勘闭环 → 报告分发）
  report_gen     — 报告生成
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from ..base import BaseSkill
from ... import zhgk_files as _zhgk_files
from .pipelines.resume import resolve_resume_route_to
from .sdui import project as _sdui_project
from .steps import (
    PreflightStep,
    IntentSelectStep,
    SceneSuggestRunStep,
    DetermineGenStep,
    FilterBuildStep,
    MethodSplitStep,
    DataAppendStep,
    ConfirmTableStep,
    TaskDispatchStep,
    WaitSurveyStep,
    AssessStep,
    IssueListStep,
    ResurveyGateStep,
    SupplementRunStep,
    ReportGenRunStep,
    ReportDistributeStep,
)


def _normalize_assignees(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("surveyor_name") or item.get("姓名") or "").strip()
        code = str(item.get("surveyor_code") or item.get("工号") or "").strip()
        if name and code:
            out.append({"surveyor_name": name, "surveyor_code": code})
    return out


def _latest_completed_index(steps: list[Any], keys: list[str]) -> int:
    best = -1
    for rec in steps or []:
        if not isinstance(rec, dict):
            continue
        if rec.get("status") != "completed":
            continue
        key = str(rec.get("key") or "")
        if key in keys:
            best = max(best, keys.index(key))
    return best


def _step_has_terminal_record(steps: list[Any], step_key: str) -> bool:
    for rec in reversed(steps or []):
        if not isinstance(rec, dict):
            continue
        if str(rec.get("key") or "") != step_key:
            continue
        return rec.get("status") in {"completed", "hitl", "failed"}
    return False


def _resume_route_from_previous_state(prev: dict[str, Any], keys: list[str]) -> str:
    if not keys:
        return ""
    try:
        resurvey_idx = keys.index("resurvey_gate")
    except ValueError:
        resurvey_idx = -1

    steps = list(prev.get("steps") or [])
    completed_idx = _latest_completed_index(steps, keys)
    current = str(prev.get("current_step") or "").strip()
    current_idx = keys.index(current) if current in keys else -1

    if current in keys and not _step_has_terminal_record(steps, current):
        return current

    if completed_idx >= 0 and completed_idx + 1 < len(keys):
        return keys[completed_idx + 1]

    if resurvey_idx >= 0 and max(completed_idx, current_idx) >= resurvey_idx:
        return "resurvey_gate"

    if current in keys:
        return current

    return ""


class ZhgkSkill(BaseSkill):
    name = "zhgk"
    description = (
        "智慧工勘 v4 · 意图驱动单流水线。支持 4 种意图：\n"
        "  scene_suggest（场景建议）/ survey_work（全流程工勘）/ "
        "supplement（补充闭环）/ report_gen（报告生成）"
    )
    # ── 步骤顺序 = 最长流水线顺序（每步内部按意图决定是否跳过）──
    steps = [
        PreflightStep(),        # internal=True，不受契约约束
        IntentSelectStep(),     # 意图选择（HITL ChoiceCard）
        DetermineGenStep(),     # 代际制冷识别（须在 scene_suggest_run 之前）
        SceneSuggestRunStep(),  # scene_suggest 专属
        SupplementRunStep(),    # 补充入口准备（supplement 专属）
        FilterBuildStep(),      # 底表过滤 + 建全量勘测结果表
        MethodSplitStep(),      # 现场/数据分流
        DataAppendStep(),       # 数据类条目追加
        ConfirmTableStep(),     # 勘测表确认（HITL）
        TaskDispatchStep(),     # GKCLAW 任务下发（survey_work 首轮 / 复勘闭环）
        WaitSurveyStep(),       # 等待现场上传（HITL）
        AssessStep(),           # AI 五值评估
        IssueListStep(),        # 问题清单生成
        ResurveyGateStep(),     # 复勘检查门控（HITL）
        ReportGenRunStep(),     # 工勘报告生成（9 表 Word）
        ReportDistributeStep(), # 审批与分发
    ]
    # SDUI 投影器
    sdui_projector = staticmethod(_sdui_project)
    # assess / report_distribute 支持单步重试（不重跑前序 LLM 步骤）

    step_retry_keys = [
        "task_dispatch",
        "wait_survey",
        "assess",
        "issue_list",
        "resurvey_gate",
        "report_gen_run",
        "report_distribute",
    ]
    # 文件补齐 HITL 处理器
    file_handler = _zhgk_files

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        """补 zhgk v4 演示默认值。"""
        p = dict(payload or {})
        p.setdefault("project_code", "K1903")
        p.setdefault("project_name", "智算 Q3 · 客户甲一期")
        p.setdefault("room_name", "A 机房")
        p.setdefault("activity_id", "ACT001")
        # intent 留空：由 intent_select step HITL 填充
        return p

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        """resume 时把 HITL 用户选择写入 project。

        支持的 HITL 门：
          intent_select   → project["intent"] = choice
          determine_gen   → project["generation_cooling"] = choice（用户手动指定时）
          data_append     → project["data_append_choice"] = choice（追加/跳过）
          confirm_table   → project["table_confirmed"] = True / redo 仅清 table_confirmed
          task_dispatch   → project["dispatch_decision"] = choice（下发/跳过）；
                            表单 rows → project["assignees"]
          wait_survey     → 文件型 HITL
          resurvey_gate   → project["resurvey_decision"] = resurvey/skip_resurvey；
                            project["resurvey_dispatch_decision"] = dispatch/skip
          supplement_run  → project["supplement_choice"] = choice（追加/跳过）
          report_gen_run   → project["report_review_choice"] = download/send_approval
          report_distribute → project["approval_*"] = 审批邮件表单
        """
        project = dict(project)
        choice = payload.get("choice", "")

        if hitl_step == "intent_select" and choice:
            project["intent"] = choice

        elif hitl_step == "report_distribute" and choice:
            project["approval_decision"] = choice
        elif hitl_step == "report_distribute" and isinstance(payload.get("approval_mail"), dict):
            mail = payload.get("approval_mail") or {}
            project["approval_email"] = str(mail.get("approval_email") or "").strip()
            project["approval_subject"] = str(mail.get("approval_subject") or "").strip()
            project["approval_body"] = str(mail.get("approval_body") or "").strip()

        elif hitl_step == "report_gen_run" and choice:
            project["report_review_choice"] = choice

        elif hitl_step == "determine_gen" and choice:
            project["generation_cooling"] = choice

        elif hitl_step == "data_append" and choice:
            project["data_append_choice"] = choice

        elif hitl_step == "supplement_run" and choice:
            project["supplement_choice"] = choice

        elif hitl_step == "task_dispatch":
            if choice:
                project["dispatch_decision"] = choice
            assignees = _normalize_assignees(
                payload.get("assignees") or payload.get("gkclaw_assignees")
            )
            if assignees:
                project["assignees"] = assignees

        elif hitl_step == "confirm_table":
            if choice == "confirm":
                project["table_confirmed"] = True
            elif choice == "redo":
                # 仅清确认标记，保留代际制冷（从 project_info.json 缓存恢复）
                project.pop("table_confirmed", None)
                project.pop("data_append_choice", None)  # 重建表需重新选择数据追加
                project.pop("dispatch_decision", None)   # 重建表后须重新决策是否下发

        elif hitl_step == "wait_survey":
            # 文件型 HITL；复勘标记由 wait_survey 成功合并后清理，避免续跑前误判已有旧结果。
            pass

        elif hitl_step == "resurvey_gate" and choice:
            if choice in {"resurvey", "skip_resurvey"}:
                project["resurvey_decision"] = choice
                project.pop("resurvey_dispatch_decision", None)
                project.pop("resurvey_gkclaw_task_id", None)
            elif choice in {"dispatch", "skip"}:
                project["resurvey_decision"] = "resurvey"
                project["resurvey_dispatch_decision"] = choice

        return project

    def build_resume_init_state(
        self,
        prev: dict[str, Any],
        project: dict[str, Any],
        hitl_step: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        route = resolve_resume_route_to(
            hitl_step=hitl_step,
            project=project,
            payload=payload or {},
            prev_state=prev,
        )
        if route:
            return {"route_to": route}, project

        # 有 HITL 续跑上下文时禁止走兜底，避免 route_to 指回已完成/当前 HITL 步
        if hitl_step:
            return {}, project

        route_to = _resume_route_from_previous_state(prev, [s.key for s in self.steps])
        if route_to:
            return {"route_to": route_to}, project
        return {}, project


def get_zhgk_skill() -> ZhgkSkill:
    """单例工厂 · 延迟加载 llm_factory"""
    from ...llm import get_llm
    from .bridge import get_zhgk_root
    return ZhgkSkill(work_root=Path(get_zhgk_root()), llm_factory=get_llm)
