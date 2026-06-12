"""
SystemDesignSkill · 系统设计（A3 智能网络开局）· 规划设计项目第二段

「规划设计」= 建模仿真（guihua，线性 5 段）+ 系统设计（本 skill）。
本 skill 把 Raw Skill《系统设计模块》的 happy-path 业务流程落成**线性 DAG**，
串联在建模仿真之后 —— 第一步 input_check 消费建模仿真产出的
001/004/007 仿真输出件（见 steps/input_check.py），形成「建模仿真 → 系统设计」链路。
单命令 dispatch 能力由 `a3_bridge.run_command()` 提供，整包编排由 `run_dispatch()` 提供。

steps[] 顺序即 DAG（build_graph 自动建图，无需手写 graph.py）：
  input_check → intent_recognition → exec_confirm → plane_planning
    → lld_integrate → ztp_generate → naming_replace → publish

运行时对齐（见 agent/docs/AIDA-RUNTIME-CONTRACT.md）：
- 节点返回 state 差量；steps/logs 走 reducer 累加。
- HITL = 软中断：check_inputs 返 missing → 框架写 state['hitl'] → router → END → resume。
- 工具失败返回 'Error:' 字符串（不抛异常）；LLM 无原生结构化输出（适配层 prompt 注入 schema + json 解析）。
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any, ClassVar


# 计划工期（天）· 任务时间规划安排默认排期；正式环境应由项目管理系统下发覆盖。
_PLANNED_DURATION_DAYS = 21

# 多任务分隔符（对齐设计稿 pick_commands：用户一次可输入多个规划任务）。
# 仅按显式分隔符切分（不切空格，避免拆散「生成完整 LLD 设计」这类含空格的标准命令）。
_CMD_SEP = re.compile(r"[、,，;；/／\n]+")


def _split_commands(text: str) -> list[str]:
    """把用户输入按显式分隔符切分为多个命令（去空白、去空项）。
    单命令返回单元素列表；多命令（如「网络接入规划、网络互联规划」）返回多元素列表。"""
    return [s.strip() for s in _CMD_SEP.split(str(text or "")) if s.strip()]


def _default_schedule() -> dict[str, str]:
    """锚定本次 run 真实启动日的默认排期（非设计稿 mock 日期）。
    planned_start = 今日；planned_end = 今日 + 工期；actual_start = 今日（实际开工）。"""
    today = datetime.date.today()
    end = today + datetime.timedelta(days=_PLANNED_DURATION_DAYS)
    iso = "%Y-%m-%d"
    return {
        "planned_start": today.strftime(iso),
        "planned_end": end.strftime(iso),
        "actual_start": today.strftime(iso),
    }

from ..base import BaseSkill
from ... import system_design_files as _sd_files
from .sdui import project as _sdui_project
from .pipelines.a3_paths import get_a3_root
from .sd_context import as_sd_context
from .pipelines.path_manifest import reload_manifest
from .steps import (
    IntentRecognitionStep,
    InputCheckStep,
    ExecConfirmStep,
    PlanePlanningStep,
    LldIntegrateStep,
    StageSelectStep,
    NamingReplaceStep,
    ZtpGenerateStep,
    PublishConfirmStep,
    PublishStep,
)

# 确认型 HITL 门：hitl_step → project.confirmations 键（对齐 GuihuaSkill 范式）
_CONFIRM_GATE_OF_STEP = {
    "exec_confirm": "exec",
    "publish_confirm": "publish",
}


def _get_system_design_root() -> Path:
    """系统设计工作区根 = project_paths.json → data_root（不自动 mkdir）。"""
    return get_a3_root()


class SystemDesignSkill(BaseSkill):
    name = "system_design"
    description = "系统设计（A3 智能网络开局）· 规划设计第二段：意图识别→输入检查→平面规划→LLD 融合→ZTP→命名替换→发布"
    # A 层 SKILL.md 随 skill 目录走（自描述，免依赖 ~/.claude 部署）
    skill_md_path = Path(__file__).resolve().parent / "SKILL.md"

    # 顺序即 DAG 顺序（线性串行；HITL/error 由 build_graph 的 router 路由到 END）
    # 对齐《系统设计工作台-周二版》交互流程：在规划前 / LLD 后 / 发布前插入确认门，
    # 并把「设备名称替换」调到「ZTP」之前（设计稿 STEP_BLUEPRINT s4=名称替换 → s5=ZTP）。
    steps = [
        InputCheckStep(),        # 输入件检查（设计稿 file_request → confirm_inputs）
        IntentRecognitionStep(), # 用户指令 → 意图识别（设计稿 user_command / disambiguate）
        ExecConfirmStep(),       # 确认执行计划（设计稿 confirm_request · 意图识别之后）
        PlanePlanningStep(),
        LldIntegrateStep(),
        StageSelectStep(),       # 输入执行计划（设计稿 next_stage）
        NamingReplaceStep(),     # 设备名称替换（可选 · 调到 ZTP 之前）
        ZtpGenerateStep(),
        PublishConfirmStep(),    # 检查测试用例 / 确认发布（设计稿 finalize + test_check）
        PublishStep(),
    ]
    sdui_projector = staticmethod(_sdui_project)
    # 文件型 HITL：input_check/plane_planning/ztp_generate 缺件 → /upload/batch + /resume
    file_handler = _sd_files
    # 补传输入件后仅重跑 input_check；publish_confirm 仅重跑本步（检查测试用例 / 确认发布），
    # 避免 full_restart 重跑 LLD 融合等前置步骤。
    step_retry_keys: ClassVar[list[str]] = ["input_check", "publish_confirm"]

    @property
    def work_root(self) -> Path:
        return _get_system_design_root()

    @work_root.setter
    def work_root(self, _value: Path) -> None:
        pass  # 始终读 project_paths.json → data_root

    def execute_step(self, step, state, ctx):
        return super().execute_step(step, state, as_sd_context(ctx))

    def build_graph(self, checkpointer=None):
        reload_manifest()
        return super().build_graph(checkpointer)

    def prepare_work_root(self) -> None:
        """数据根走 project_paths.json 绝对路径，不在 work_root 下创建 ProjectData/。"""
        return

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        """把 start 请求体映射为 project；预置默认值。
        text / command 透传给 intent_recognition 做意图归一化。"""
        p = dict(payload or {})
        p.setdefault("project_name", "规划设计 · 系统设计")
        # 用户自然语言指令（可选）：intent_recognition 据此归一化标准命令
        p.setdefault("text", str(p.get("text") or p.get("command") or "").strip())
        # 确认型 HITL 门状态（确认执行计划 / 确认发布）+ 执行计划选择（名称替换 / ZTP）
        p.setdefault("confirmations", {})
        p.setdefault("stage", {})
        # 对话轮次日志（问答模式）：每次用户输入/选择的指令按时序追加，跨 full_restart 存活，
        # 供 SDUI 投影渲染「用户提问 → 系统回答」聊天流（见 sdui._build_conversation）。
        chat = list(p.get("chat") or [])
        if p["text"] and not chat:
            chat.append({"role": "user", "text": p["text"]})
        p["chat"] = chat
        # 多任务队列（对齐设计稿 pick_commands + queue）：用户首次输入若含多个任务，
        # 首条留作意图识别（project.text），其余入 plan_queue，由 plane_planning 串行执行。
        parts = _split_commands(p["text"])
        if len(parts) > 1:
            p["text"] = parts[0]
            p["plan_queue"] = parts[1:]
        else:
            p.setdefault("plan_queue", [])
        # 任务时间规划安排（对齐设计稿「任务时间规划安排」卡）：
        # 锚定本次 run 的真实起始日（非 mock 演示日），计划工期默认 21 天；
        # actual_start = 启动当日（工单实际开工日）。剩余天数/状态由前端按当日派生。
        p.setdefault("schedule", _default_schedule())
        return p

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        """HITL 续跑：把用户选择并回 project（跨 full_restart 存活）。

        - intent_recognition：CLARIFYING 选候选 / FAILED 重输 → 回填 project['text']。
        - exec_confirm / publish_confirm：确认门 → project.confirmations[gate]=True。
        - stage_select：执行计划选择 → project.stage = {chosen:True, naming:bool}。"""
        p = dict(project or {})
        payload = payload or {}

        def _append_chat(text: str) -> None:
            """把用户本轮输入的指令追加到对话轮次日志（去重相邻重复）。"""
            t = str(text or "").strip()
            if not t:
                return
            chat = list(p.get("chat") or [])
            if not (chat and chat[-1].get("role") == "user" and chat[-1].get("text") == t):
                chat.append({"role": "user", "text": t})
            p["chat"] = chat

        def _set_cmd(raw: str) -> None:
            """把用户本轮指令写回 project：完整文本入对话流；按分隔符拆队列，
            首条 → project.text（供意图识别），其余 → project.plan_queue（plane_planning 串行执行）。
            每次都重置 plan_queue，避免上一轮残留队列被误重跑。"""
            t = str(raw or "").strip()
            if not t:
                return
            _append_chat(t)
            parts = _split_commands(t)
            p["text"] = parts[0] if parts else t
            p["plan_queue"] = parts[1:] if len(parts) > 1 else []

        # 无 HITL 门（含执行失败后）：用户直接输入新规划指令 → full_restart 续跑
        if not hitl_step:
            retry = str(
                payload.get("text") or payload.get("choice")
                or payload.get("command") or ""
            ).strip()
            if retry and not retry.startswith("/"):
                _set_cmd(retry)
                p["reselect_pending"] = False
                return p

        if hitl_step == "intent_recognition":
            result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            # 多选消歧（对齐设计稿 confirm_disambiguate · commands[]）
            raw_choices = payload.get("choices") or payload.get("commands")
            if isinstance(raw_choices, list):
                picked = [str(c).strip() for c in raw_choices if str(c).strip()]
                if picked:
                    _set_cmd("、".join(picked))
                    return p
            choice = (
                payload.get("choice") or payload.get("value")
                or payload.get("intent_command") or payload.get("text")
                or payload.get("command")
                or result.get("selected") or result.get("value") or result.get("text")
            )
            if choice:
                _set_cmd(str(choice).strip())
            return p

        # 确认型门（确认执行计划 / 确认发布）
        gate = _CONFIRM_GATE_OF_STEP.get(hitl_step)
        if gate:
            choice = str(
                payload.get("choice") or payload.get("value") or payload.get("text") or ""
            ).strip()
            confs = dict(p.get("confirmations") or {})

            # 确认执行计划门
            if hitl_step == "exec_confirm":
                # 取消 / 重新选择（设计稿 cancel_confirm）：清确认 + 清意图与队列，
                # 回到「选择规划任务」（前端 composer 可重新点选 / 输入）。
                if choice in ("cancel", "重新选择规划任务", "重新选择", "取消"):
                    confs.pop("exec", None)
                    p["confirmations"] = confs
                    p["text"] = ""
                    p["plan_queue"] = []
                    p["reselect_pending"] = True
                    return p
                confs["exec"] = True
                p["confirmations"] = confs
                p["reselect_pending"] = False
                # 用户输入/选择的是具体规划指令（非「确认」占位）→ 作为新意图写回。
                if choice and choice not in ("confirm", "确认执行计划", "确认执行", "确认"):
                    _set_cmd(choice)
                return p

            # 确认发布门（设计稿 finalize + test_check）。
            # request_test_check → 弹出 TestCheckCard；check → publish_checked；
            # confirm → publish。
            if hitl_step == "publish_confirm":
                if choice in ("request_test_check", "检查测试用例"):
                    from .pipelines.publish_helpers import (
                        copy_test_case_to_output,
                        output_rel_path,
                        TEST_CASE_ARTIFACT_ID,
                    )
                    confs["publish_test_check_pending"] = True
                    p["confirmations"] = confs
                    dest = copy_test_case_to_output(self.work_root)
                    if dest:
                        rel = output_rel_path(self.work_root, dest)
                        p["test_case_output"] = rel
                    p["request_outputs_view"] = int(p.get("request_outputs_view") or 0) + 1
                    p["highlight_artifacts"] = [TEST_CASE_ARTIFACT_ID]
                    return p
                if choice in ("check", "confirm_test_check", "已检查测试用例"):
                    confs["publish_checked"] = True
                    confs["publish_test_check_pending"] = False
                    p["confirmations"] = confs
                    p["highlight_artifacts"] = []
                    # 测试用例确认后引导右侧页签回到「进度」（FinalizeCard / 确认发布）
                    p["request_progress_view"] = int(p.get("request_progress_view") or 0) + 1
                    return p
                if choice in ("confirm", "确认发布", "确认"):
                    confs["publish_checked"] = True
                    confs["publish_test_check_pending"] = False
                    confs["publish"] = True
                    p["confirmations"] = confs
                    return p
                return p

            confs[gate] = True
            p["confirmations"] = confs
            return p

        # 规划循环门（plane_planning 完成单/批次后停在 LLD 生成）：
        # 用户所选/输入的下一步指令写回 project.text → full_restart 重跑 → intent 识别后执行对应子 skill。
        # 选「生成完整LLD设计」→ full 模式 → 融合 LLD 并进入交付收尾；选其它规划任务 → 继续累积。
        if hitl_step == "plane_planning":
            choice = str(
                payload.get("choice") or payload.get("value")
                or payload.get("text") or payload.get("command") or ""
            ).strip()
            if choice:
                _set_cmd(choice)
            return p

        # 输入执行计划：rename_ztp → 执行名称替换；skip_ztp → 跳过名称替换
        if hitl_step == "stage_select":
            choice = str(payload.get("choice") or payload.get("value") or "rename_ztp").lower()
            stage = dict(p.get("stage") or {})
            stage["chosen"] = True
            stage["naming"] = "rename" in choice  # rename_ztp → True；skip_ztp → False
            p["stage"] = stage
            return p

        return p

    def build_resume_init_state(
        self,
        prev: dict[str, Any],
        project: dict[str, Any],
        hitl_step: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """LLD 完成后续跑 ZTP / 发布：route_to 跳过规划+融合，保留 files/metrics。"""
        from .pipelines.delivery import resolve_resume_route_to

        route = resolve_resume_route_to(
            hitl_step=hitl_step,
            project=project,
            payload=payload or {},
            prev_state=prev,
            work_root=self.work_root,
        )
        extras: dict[str, Any] = {"files": dict(prev.get("files") or {})}
        tc_rel = str((project or {}).get("test_case_output") or "").strip()
        if tc_rel:
            extras["files"]["test_case_file"] = tc_rel
            extras["files"][f"out::{tc_rel}"] = tc_rel
        if not route:
            return extras, project

        extras["route_to"] = route
        extras["logs"] = list(prev.get("logs") or [])[-4:] + [
            f"[resume] 交付续跑 · 跳过前置步骤 → {route}",
        ]
        # 跳过 plane_planning 时仍需 sd_mode=full，供 ztp_generate / naming 判断
        m: dict[str, Any] = dict(prev.get("metrics") or {})
        for step in reversed(prev.get("steps") or []):
            m.update(step.get("metrics") or {})
        m.setdefault("sd_mode", "full")
        if route == "lld_integrate":
            m["intent_command"] = str(
                (project or {}).get("text") or "生成完整LLD设计"
            ).strip() or "生成完整LLD设计"
        if not m.get("lld_file"):
            m["lld_file"] = str(extras["files"].get("lld_file") or "")
        extras["metrics"] = m
        return extras, project


def get_system_design_skill():
    """单例工厂 · 延迟加载 llm + work_root。注册见 agent/skills/__init__.py。"""
    from ...llm import get_llm
    skill = SystemDesignSkill(work_root=_get_system_design_root(), llm_factory=get_llm)
    # 旧实例可能在 __dict__ 里缓存了 work_root，会遮蔽 @property
    skill.__dict__.pop("work_root", None)
    return skill
