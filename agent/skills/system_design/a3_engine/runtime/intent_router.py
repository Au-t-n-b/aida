"""
Step 0 命令校验（非识别）。

意图识别由 Claw 读取 subskills/lld-intent-recognition.code1/*.md 完成（与 agent-skill_full1 Step 0 一致），
driver 只接收已归一化的标准命令 text，校验后进入执行链。
"""

from __future__ import annotations

from dataclasses import dataclass

from command_registry import all_known_commands, get_command, get_command_spec

FAILED_MESSAGE = (
    "当前问题不属于LLD设计支持范围，请输入地址规划、互联规划、接入规划、LLD设计等相关指令。"
)
NOT_NORMALIZED_MESSAGE = (
    "当前输入尚未归一化为标准命令。请 Claw 先按 "
    "subskills/lld-intent-recognition.code1/SKILL.md（及 intent-taxonomy / aliases / keywords）"
    "完成 Step 0 意图识别，再以标准命令名传入 payload.text 后触发 run_command。"
)


@dataclass(frozen=True)
class IntentResult:
    status: str
    command: str = ""
    message: str = ""
    candidates: tuple[str, ...] = ()


def _exact_command(text: str) -> str | None:
    value = (text or "").strip()
    if not value:
        return None
    for cmd in all_known_commands():
        if value.lower() == cmd.lower():
            return cmd
    return None


def _ready_command(text: str) -> str | None:
    spec = get_command_spec(text)
    if spec is not None and spec.support_status == "ready":
        return spec.command
    if get_command(text) is not None:
        return text.strip()
    return None


def recognize(text: str) -> IntentResult:
    """
    校验 Claw Step 0 产出的标准命令（非 LLM、非 NL 识别）。

    - text 与 taxonomy 标准命令精确匹配（大小写不敏感）→ resolved
    - 否则 → failed，提示 Claw 先读 MD skill 归一化
    """
    raw = (text or "").strip()
    if not raw:
        return IntentResult(
            status="failed",
            message="请输入地址规划、互联规划、接入规划、LLD设计、ZTP 等相关指令。",
        )

    exact = _exact_command(raw)
    if exact:
        ready = _ready_command(exact)
        if ready:
            return IntentResult(status="resolved", command=ready, message=ready)
        return IntentResult(
            status="failed",
            message=f"`{exact}` 已登记但当前环境暂不可执行。",
        )

    ready = _ready_command(raw)
    if ready:
        return IntentResult(status="resolved", command=ready, message=ready)

    if any(k in raw for k in ("不属于", "无法识别", "不支持")):
        return IntentResult(status="failed", message=FAILED_MESSAGE)

    return IntentResult(status="failed", message=NOT_NORMALIZED_MESSAGE)
