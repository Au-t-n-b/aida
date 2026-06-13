from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 仓库根（D:\Code\aida）入 sys.path，使 `import agent.llm` 可解析。
# agent/__init__.py 仅含版本号，导入只拉 agent/llm.py 的依赖
# （langchain_openai + dotenv + 可选 langfuse），不拖入 langgraph。
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def get_chat_llm() -> Any | None:
    """复用项目统一 LLM 入口 agent/llm.py（ZHIPU + Langfuse）。

    精简版 ontology 原先自建一个裸 ChatOpenAI；现改为委托项目唯一批准入口
    `agent.llm.get_llm()`，统一 provider 与 Langfuse 追踪——与项目「唯一允许直接
    持有 ChatOpenAI 的文件 = agent/llm.py」规则一致。

    依赖缺失（ontology venv 未装 langchain）或未配置 ZHIPU_API_KEY 时返回 None
    —— 计划压缩回落确定性排期，行为与原精简版一致。
    """
    try:
        from agent.llm import get_llm
    except Exception as exc:  # ImportError：langchain 未装 / 仓库结构异常
        logger.warning("[plan_compression_llm] agent.llm unavailable: %s", exc)
        return None
    try:
        return get_llm(temperature=0.2)  # 进程内单例；JSON 严格决策用低温
    except Exception as exc:  # RuntimeError：ZHIPU_API_KEY 未配置
        logger.warning("[plan_compression_llm] get_llm() failed: %s", exc)
        return None
