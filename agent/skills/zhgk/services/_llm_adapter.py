"""
_llm_adapter · 将 aida SkillContext.invoke_llm() 包装成 smart_survey LLMCallable

smart_survey services 期望的签名:
    LLMCallable = Callable[[str, str], str]  # (system_prompt, user_prompt) -> str

aida SkillContext.invoke_llm() 接受:
    messages: list[tuple[str, str]]          # [("system", ...), ("human", ...)]
    ...关键字参数...
    返回 BaseMessage（.content 是字符串）

用法（在 step 的 run() 里）:
    from ..services._llm_adapter import make_llm_adapter
    llm = make_llm_adapter(ctx, step_key=self.key)
    result = some_service_func(path, llm_call=llm)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .types import LLMCallable

if TYPE_CHECKING:
    from ...base import SkillContext


def make_llm_adapter(ctx: "SkillContext", step_key: str = "zhgk") -> LLMCallable:
    """
    返回一个符合 LLMCallable 签名的函数，内部走 ctx.invoke_llm。

    参数:
        ctx:      当前 SkillContext（提供 invoke_llm + Langfuse trace）
        step_key: 对应的 step key，写入 Langfuse metadata
    """
    def _llm_call(system_prompt: str, user_prompt: str) -> str:
        resp = ctx.invoke_llm(
            [("system", system_prompt), ("human", user_prompt)],
            step_key=step_key,
        )
        # invoke_llm 返回 BaseMessage 或其子类
        content = resp.content if hasattr(resp, "content") else str(resp)
        return content if isinstance(content, str) else str(content)

    return _llm_call
