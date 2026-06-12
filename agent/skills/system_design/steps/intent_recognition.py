"""
step 1 · 意图识别（Raw Skill §6 intent_recognition）· 严格对齐原始 a3 lld-intent-recognition

匹配链与原始 SKILL.md 一致（确定性规则优先，语义近似才上 LLM）：
  规则链（intent_taxonomy.recognize）：三级精准→LLD特殊→二级→一级→别名→关键词消歧
    → RESOLVED / CLARIFYING / FAILED
  规则耗尽（FAILED）时，再调 LLM 做「语义近似」兜底（Raw Skill §10：仅此分支需模型）：
    单一高置信候选 → RESOLVED；否则保持 FAILED 固定话术。

与原始方式对齐的关键点（本次改造）：
  - **不再降级默认命令**：NL 无法识别 → FAILED 固定话术（原 intent_router.FAILED_MESSAGE）。
  - **多候选必须追问**：CLARIFYING → 触发 HITL（ChoiceCard 候选），不得擅自选定（§13）。
  - 无 NL 输入时不再自动默认命令：输入件检查完成后挂起 plan_request，等用户在对话框输入指令后再识别。

HITL：run 阶段返回 hitl（base.execute_step 已支持 run 触发 HITL → router → END → resume）。
"""
from __future__ import annotations

import json
import re

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from .intent_taxonomy import (
    recognize as rule_recognize,
    all_commands,
    FAILED_MESSAGE,
    UNSUPPORTED_COMMANDS,
    MAX_CLARIFY_CANDIDATES,
    canonicalize_command,
)

# 无 NL 输入时不自动下发命令；输入件检查完成后等待用户在对话框选择/输入规划任务。
_PLAN_REQUEST_HINT = (
    "请在下方对话框直接描述需求并发送即可执行规划，"
    "完成多项规划后可一键生成完整 LLD。"
)


class IntentRecognitionStep(BaseStep):
    key = "intent_recognition"
    name = "意图识别"

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        from ..pipelines.delivery import should_skip_step

        route = str(state.get("route_to") or "")
        if route and should_skip_step(self.key, route):
            emit(f"[{self.key}] 交付续跑 · 跳过（→{route}）")
            return {"logs": [f"[intent_recognition] 交付续跑跳过（→{route}）"]}

        raw = str((ctx.project or {}).get("text") or "").strip()

        # 输入件检查完成后等待用户指令（对齐设计稿 confirm_inputs → plan_request）
        if not raw:
            emit(f"[{self.key}] 等待用户选择/输入规划任务")
            return self._plan_request(emit=emit)

        # ① 确定性规则链（原始 Step 0）
        m = rule_recognize(raw)
        if m.status == "resolved":
            emit(f"[{self.key}] 规则命中（{m.source}）：{m.command}")
            return self._resolved(m.command, source=m.source, emit=emit)

        if m.status == "clarifying":
            emit(f"[{self.key}] 多候选并列，追问：{m.candidates}")
            return self._clarifying(m.candidates, m.message, raw, emit=emit)

        # ② 规则 FAILED 且非别名/关键词的「不支持范围」→ 语义近似 LLM 兜底
        #    （命中不支持范围 source=unsupported 时不兜底，直接失败）
        if m.source != "unsupported":
            cmd, status, cands = self._llm_semantic(ctx, raw, emit)
            if status == "resolved":
                emit(f"[{self.key}] 语义近似命中：{cmd}")
                return self._resolved(cmd, source="llm", emit=emit)
            if status == "clarifying" and len(cands) > 1:
                cands = cands[:MAX_CLARIFY_CANDIDATES]
                emit(f"[{self.key}] 语义近似多候选，追问：{cands}")
                return self._clarifying(cands, "", raw, emit=emit)

        # ③ 无法识别 → FAILED 固定话术（不降级默认命令）
        emit(f"[{self.key}] 无法识别为标准命令，返回失败话术")
        return self._failed(m.message or FAILED_MESSAGE, emit=emit)

    # ── 语义近似 LLM 兜底（Raw Skill §10 唯一 LLM 分支）──
    def _llm_semantic(self, ctx: SkillContext, raw: str, emit: Emit) -> tuple[str, str, list[str]]:
        cmds = all_commands()
        schema = (
            '{"command": "<标准命令，必须来自候选列表；无法判断填空字符串>", '
            '"status": "resolved|clarifying|failed", '
            '"candidates": ["<clarifying 时的并列候选>"], '
            '"confidence": <0~1>}'
        )
        try:
            resp = ctx.invoke_llm(
                [
                    ("system",
                     "你是 A3 网络开局意图分类器，仅做『语义近似』归一化（精准/别名/关键词已在规则层处理）。\n"
                     f"候选命令（只能从中选，禁止自造）：{', '.join(cmds)}\n"
                     "规则：单一高置信候选才 resolved；多候选竞争 status=clarifying 并列出 candidates；"
                     "完全不属于网络开局范围（如闲聊/天气/写诗）status=failed。\n"
                     "单独『LLD』不算命令；含『生成』+『LLD』→『生成完整LLD设计』；含『融合』+『LLD』→『融合完整LLD设计』。\n"
                     f"只输出符合此 JSON Schema 的 JSON：{schema}"),
                    ("human", f"用户指令：{raw}\n请输出 JSON："),
                ],
                step_key=self.key,
            )
            content = resp.content if hasattr(resp, "content") else str(resp)
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            return self._parse_llm(str(content))
        except Exception as e:  # noqa: BLE001 — LLM 不可用 → 维持 FAILED（不降级）
            emit(f"[{self.key}] LLM 不可用（{type(e).__name__}），维持失败话术")
            return "", "failed", []

    def _parse_llm(self, text: str) -> tuple[str, str, list[str]]:
        mt = re.search(r"\{.*\}", text, re.S)
        if not mt:
            return "", "failed", []
        try:
            obj = json.loads(mt.group(0))
        except Exception:
            return "", "failed", []
        cmd = str(obj.get("command") or "").strip()
        status = str(obj.get("status") or "failed").strip()
        cands = [str(c).strip() for c in (obj.get("candidates") or []) if str(c).strip()]
        valid = set(all_commands())
        cands = [c for c in cands if c in valid and c not in UNSUPPORTED_COMMANDS]
        if status == "resolved":
            if cmd in valid and cmd not in UNSUPPORTED_COMMANDS:
                return canonicalize_command(cmd), "resolved", []
            return "", "failed", []  # 自造/不支持命令 → 失败（不降级）
        if status == "clarifying" and len(cands) > 1:
            return "", "clarifying", cands
        return "", "failed", []

    # ── 结果构造 ──
    def _plan_request(self, *, emit: Emit) -> StepResult:
        """选择规划任务（对齐设计稿 plan_request · 输入件检查完成后）。"""
        return {
            "current_step": self.key,
            "steps": [self.make_record(
                "hitl", ended_at=self._now(),
                log_tail=[f"[{self.key}] 等待规划任务"],
                metrics={"intent_status": "awaiting_command"},
            )],
            "logs": ["[intent_recognition] 等待用户选择规划任务"],
            "metrics": {"intent_status": "awaiting_command"},
            "hitl": {
                "step": self.key,
                "ui": "plan_request",
                "title": "选择规划任务",
                "reason": _PLAN_REQUEST_HINT,
                "need_files": [],
                "need_inputs": [],
            },
        }

    def _resolved(self, command: str, *, source: str, emit: Emit) -> StepResult:
        command = canonicalize_command(command)
        return {
            "logs": [f"[intent_recognition] command={command} status=resolved source={source}"],
            "metrics": {
                "intent_command": command,
                "intent_status": "resolved",
                "intent_source": source,
                "intent_note": "",
            },
            "files": {"intent_command": command, "intent_status": "resolved"},
        }

    # 消歧追问（对齐设计稿 DisambiguateCard · 最多 3 项最相关候选 · 支持多选）
    _CLARIFY_HINT = (
        "请勾选需要执行的规划任务（支持多选）；也可在左侧输入框用「、」分隔输入其它标准指令。"
    )

    def _clarifying(
        self,
        candidates: list[str],
        message: str,
        query: str,
        *,
        emit: Emit,
    ) -> StepResult:
        candidates = list(candidates)[:MAX_CLARIFY_CANDIDATES]
        q = str(query or "").strip()
        lead = (
            f"「{q}」可能对应以下多个规划任务，请勾选你需要执行的项（已按相关度展示最相关的 {len(candidates)} 项）。"
            if q else
            f"您的指令可能对应多个规划任务，请勾选需要执行的项（已展示最相关的 {len(candidates)} 项）。"
        )
        msg = message or self._default_clarify(candidates)
        reason = f"{lead}\n{self._CLARIFY_HINT}"
        return {
            "current_step": self.key,
            "steps": [self.make_record(
                "hitl", ended_at=self._now(),
                log_tail=[f"[{self.key}] CLARIFYING · {candidates}"],
                metrics={"intent_status": "clarifying", "intent_candidates": candidates},
            )],
            "logs": [f"[intent_recognition] status=clarifying candidates={candidates}"],
            "metrics": {
                "intent_status": "clarifying",
                "intent_candidates": candidates,
                "intent_query": q,
                "intent_note": reason,
            },
            "hitl": {
                "step": self.key,
                "reason": reason,
                "query": q,
                "need_files": [],
                "candidates": list(candidates),
                "need_inputs": [{
                    "id": "intent_command",
                    "label": lead,
                    "multi": True,
                    "max_selections": MAX_CLARIFY_CANDIDATES,
                    "options": [{"label": c, "value": c} for c in candidates],
                }],
            },
        }

    def _failed(self, message: str, *, emit: Emit) -> StepResult:
        return {
            "current_step": self.key,
            "steps": [self.make_record(
                "hitl", ended_at=self._now(),
                log_tail=[f"[{self.key}] FAILED · {message}"],
                metrics={"intent_status": "failed"},
            )],
            "logs": [f"[intent_recognition] status=failed · {message}"],
            "metrics": {"intent_status": "failed", "intent_note": message},
            "hitl": {
                "step": self.key,
                "reason": message,
                "need_files": [],
                "need_inputs": [{
                    "id": "intent_command",
                    "label": "请输入支持的标准指令（如：计算带外管理地址规划 / 地址规划 / 生成完整LLD设计）",
                    "options": [],
                }],
            },
        }

    @staticmethod
    def _default_clarify(candidates: list[str]) -> str:
        if len(candidates) <= 1:
            return "请确认要执行的标准命令。"
        head = "、".join(candidates[:-1])
        return f"请问您要做{head}还是{candidates[-1]}？"
