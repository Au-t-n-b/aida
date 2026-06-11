# 0001. HITL resume 用「软中断重跑（新 thread_id）」

- **状态**: Accepted
- **日期**: 2026-06-03
- **相关**: [`agent/main.py`](../../agent/main.py) `resume_run` / `_run_graph_streaming`；[`agent/skills/base.py`](../../agent/skills/base.py) `execute_step` 路由；范式规范 4「副作用统一·HITL」

## 背景（Context）

智慧工勘的 HITL（缺前置文件等人补料）是一种**「软中断」**：`step.check_inputs()` 失败时，`execute_step` 返回 `hitl{step, reason, need_files}`，graph 的条件路由把它导向 `END`。这**不是** LangGraph 原生的 `interrupt()` 机制。

原 `resume_run`（"简化版"）的做法：把 `hitl_resume` 写入 state、清空 `hitl`，然后用**原 thread_id** 重新 `graph.astream(cur)`。

实测发现 **resume 根本没续跑**：补齐 BOQ 后调 `/resume`，后端 `status` 仍停在 `overall_progress=20, scene_filter=hitl`。根因——该 thread 的 checkpoint 已经到达 `END`，LangGraph 在已结束的 thread 上用同 thread_id 再 `astream`，不会重新执行节点。

## 考虑的选项（Options）

- **A. 迁到 LangGraph 原生 `interrupt()` + `Command(resume=…)`**：语义最正统，能真正"从中断点续"。代价：要重构所有 step 的中断机制（当前是 `check_inputs`→路由 END 的软中断），改动面大。
- **B. 干净 init + 新 thread_id 重跑整条流程**：补齐文件后，用全新 `init_state`（`steps=[]`）和新 `thread_id`（`{run_id}-r{attempt}`）重跑。`run_id` 不变，前端重新订阅即看到完整推进。代价：会重跑已完成的 step（如 preflight 的 LLM 摘要再跑一次）。
- **C. 手动从中断 step 续跑（跳过已完成）**：在软中断模型下要自己管理"哪些 step 已完成、从哪续"，状态管理复杂、易错。

## 决策（Decision）

**选 B**。`resume_run` 重置为干净 `init_state` + 新 `thread_id` 重跑；`_run_graph_streaming` 增加 `thread_id` 参数（默认 = `run_id`，resume 时传 `{run_id}-r{attempt}`）。`run_id` 保持不变，保证前端订阅/卡片一致。

理由：当前 HITL 是软中断，B 用最小改动得到可靠续跑，且复用现成的 `astream` + SSE 链路，前端零改动。文件补齐后整条流程本就能一路跑通，"重跑"在功能上等价于"续跑"。

## 后果（Consequences）

- **正面**：最小改动、可靠续跑；前端零改动（重新订阅即看完整 5 步推进）；已端到端验证（缺 BOQ→HITL→上传真 BOQ→续跑 100%）。
- **负面 / 代价**：会重跑已完成的 step（多消耗一次 preflight 等的 token/时间）；语义上是"重跑"而非真正的"断点续跑"。
- **后续 / 触发回流**：当出现"step 很多 / 重跑成本高 / 已完成 step 有副作用不可重入"时，应迁移到**选项 A**（LangGraph `interrupt()`）。届时把"标准 HITL 中断-恢复"作为底座能力沉淀，供所有 Skill 复用（呼应范式规范 2 回流）。
