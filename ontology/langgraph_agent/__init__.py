"""Lightweight LangGraph agent package — plan-compression recommender only.

合入说明（ontology/ · 精简版）：
本服务只恢复「计划压缩推荐」(plan_compression) 所需的最小闭包
——`config` + `llm` + `recommenders`。其中 `llm` 与 `config` 均已收敛到项目
唯一 LLM 入口 `agent/`：`llm.get_chat_llm()` 委托 `agent.llm.get_llm()`，
`config` 以 `agent/.env`（ZHIPU_* / LANGFUSE_*）+ `agent.llm.get_model_info()`
为单一事实源，不再读 ontology/.env 的 MODEL_NAME/API_KEY/BASE_URL。

原仓库的 `langgraph_agent/__init__.py` 会 eager import `graph` / `service`
（完整二号 LangGraph agent）。本 Ontology 服务已按精简方案丢弃该二号 agent，
故此处**不再** eager import，避免拖入 langgraph / langchain 运行时。

`data_connector.execute_plan_compression_decision` 仍按原本体方式调用
`recommenders.plan_compression.try_llm_recommend_plan_compression`；
当 agent 未配置 ZHIPU_API_KEY（或 ontology venv 未装 langchain）时
`get_chat_llm()` 返回 None，自动回落到确定性排期逻辑。
"""

__all__: list[str] = []
