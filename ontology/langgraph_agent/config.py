from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# 合入说明（ontology/ · 精简版）：
# 本模块的 LLM / Langfuse / LangGraph 配置统一以项目唯一 LLM 入口 `agent/` 为事实源，
# 与同包 `langgraph_agent/llm.py` 委托 `agent.llm.get_llm()` 保持一致——不再读
# ontology/.env 的 MODEL_NAME / API_KEY / BASE_URL，避免「日志报 qwen3-max 但实际
# 调用 agent 的智谱 glm」这种漂移。
#
# 仓库根（D:\Code\aida）入 sys.path，使 `import agent.llm` 可解析；agent 的配置在
# `agent/.env`（ZHIPU_* / LANGFUSE_*）。
# __file__ = ontology/langgraph_agent/config.py → parents[2] = 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

AGENT_ENV_PATH = _REPO_ROOT / "agent" / ".env"


def load_agent_env() -> None:
    """加载 agent/.env（agent 的 LLM / Langfuse 配置事实源）。

    override=False：若进程已由 `agent.llm` 导入时加载过同一文件，则保留既有值。
    """
    if AGENT_ENV_PATH.exists():
        load_dotenv(AGENT_ENV_PATH, override=False)


# 向后兼容别名：历史调用方可能 import load_project_env；现统一指向 agent 配置。
load_project_env = load_agent_env


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return int(raw_value)


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return list(default)
    values = [item.strip() for item in raw_value.split(",")]
    return [item for item in values if item]


@dataclass(frozen=True)
class ModelConfig:
    model_name: str
    api_key: str | None
    base_url: str | None
    timeout_seconds: float
    max_retries: int
    temperature: float


@dataclass(frozen=True)
class LangfuseConfig:
    enabled: bool
    public_key: str | None
    secret_key: str | None
    base_url: str | None
    tracing_environment: str | None


@dataclass(frozen=True)
class LangGraphConfig:
    run_name: str
    recursion_limit: int
    remaining_steps_to_response: int
    version: str
    tenant_id: str
    tags: list[str]


def get_model_config() -> ModelConfig:
    """当前生效的模型配置 —— 来源 = 项目唯一 LLM 入口 `agent.llm`。

    与 langgraph_agent/llm.py 委托 `agent.llm.get_llm()` 同一事实源：这里报告的
    model / base_url / api_key 即 plan_compression 实际会调用的模型。
    依赖缺失（ontology venv 未装 langchain）或未配置 ZHIPU_API_KEY 时返回标记
    "<agent-unavailable>" 的占位配置——此时 get_chat_llm() 也返回 None、计划压缩
    回落确定性排期，二者状态一致。
    """
    load_agent_env()
    try:
        from agent.llm import get_model_info

        info = get_model_info()
    except Exception as exc:  # ImportError(langchain 未装) / RuntimeError(无 ZHIPU_API_KEY)
        logger.warning("[langgraph_agent.config] agent model config unavailable: %s", exc)
        return ModelConfig(
            model_name="<agent-unavailable>",
            api_key=None,
            base_url=None,
            timeout_seconds=60.0,
            max_retries=2,
            temperature=0.2,
        )
    return ModelConfig(
        model_name=str(info.get("model") or "<unknown>"),
        api_key=info.get("api_key"),
        base_url=info.get("base_url"),
        timeout_seconds=float(info.get("timeout") or 60),
        max_retries=int(info.get("max_retries") or 2),
        temperature=float(info.get("temperature") or 0.2),
    )


def get_langfuse_config() -> LangfuseConfig:
    """Langfuse 配置 —— 来源 = agent/.env（agent 用同一组 key 起 CallbackHandler）。

    与 `agent.llm._init_langfuse_once()` 同一组变量；未配置 pk/sk 时 enabled=False。
    """
    load_agent_env()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY") or None
    secret_key = os.getenv("LANGFUSE_SECRET_KEY") or None
    return LangfuseConfig(
        enabled=bool(public_key and secret_key),
        public_key=public_key,
        secret_key=secret_key,
        base_url=os.getenv("LANGFUSE_HOST") or None,
        tracing_environment=os.getenv("LANGFUSE_TRACING_ENVIRONMENT") or None,
    )


def get_langgraph_config() -> LangGraphConfig:
    """LangGraph 运行参数。agent/ 未定义这些变量，缺省即生效；
    如需覆盖可在 agent/.env 设 LANGGRAPH_*。"""
    load_agent_env()
    return LangGraphConfig(
        run_name=os.getenv("LANGGRAPH_RUN_NAME", "schedule_langgraph_agent"),
        recursion_limit=_int_env("LANGGRAPH_RECURSION_LIMIT", 20),
        remaining_steps_to_response=_int_env("REMAINING_STEPS_TO_RESPONSE", 2),
        version=os.getenv("LANGGRAPH_VERSION", "1.0.0"),
        tenant_id=os.getenv("LANGGRAPH_TENANT_ID", "local-schedule"),
        tags=_csv_env("LANGGRAPH_TAGS", ["schedule-langgraph"]),
    )


load_agent_env()
