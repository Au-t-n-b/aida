# Skill / 工具评测指标体系（v1）

> 《团队 Agent 开发范式》规范 6「可观测 → 评测闭环」的**指标定义**。
> Langfuse 提供**原材料**（成本/延迟/token）；本文定义把"原材料 + 产物"变成**信号**的指标、断言与契约。

## 1. 评测闭环

```
观测(Langfuse 自动)  →  评测(本文指标+断言)  →  呈现(定制界面)  →  AI 分析(CC/Cursor)  →  优化  →  回流(decisions/ADR)
 cost/latency/token       质量断言 + 四维打分        四维趋势+偏离高亮      读"基线vs本次+偏离点"      改 skill/工具
```

**分工**：成本/延迟/token = Langfuse 自动有；**质量、成功率 = 评测脚本读产物算出 → 写回 Langfuse score**。两者汇到同一个 run，呈现与 AI 分析都从这一个源拿。

## 2. 四维总分

| 维 | 含义 | 主数据源 | 落地 |
|---|---|---|---|
| **质量** | golden 断言通过率 | 产物（skill_result.json） | ✅ eval 脚本 |
| **成功率** | 跑到 done / 总 run | `execution.steps` / `state.hitl` | ✅ eval 脚本 |
| **成本** | ¥/run、按 step 拆 | Langfuse GENERATION | ✅ `langfuse_eval.fetch_run_metrics` |
| **延迟** | p50/p95、按 step 拆 | Langfuse span latency | ✅ `langfuse_eval.fetch_run_metrics` |

## 3. SKILL 指标

| 指标 | 定义 | 数据源 | 优化信号 |
|---|---|---|---|
| 端到端成功率 | 完成 done 的 run 占比 | execution.steps | 低→流程脆弱 |
| HITL 触发率 | 卡 hitl 的 run 占比 | state.hitl | 高→前置数据缺口大 |
| step 延迟分布 | 各 step 耗时 p50/p95 | Langfuse CHAIN span | 定位瓶颈 step |
| step 成本/token | 各 step LLM 消耗 | Langfuse GENERATION | 定位贵 step |
| 产物质量 | completion_rate / mandatory_fill_rate / open_issues | skill_result.json | 业务完成度 |

## 4. 工具指标（面向工具大量增长，最该测）

| 指标 | 定义 | 数据源 | 优化信号 |
|---|---|---|---|
| **自纠率** ⭐ | 调用前 validate 失败→模型重试的比例 | Langfuse（同 tool 连续调用 / Error 返回） | **高→description/schema 不清**，最高价值信号 |
| 成功率 | execute 不返回 Error/不抛异常 | tool span output | 低→工具不稳 |
| 延迟 p50/p95 | execute 耗时 | tool span（execute_traced 已计时） | 高→工具慢 |
| 调用热度 | 被调次数（按 skill/scope） | Langfuse 聚合 | 指导优先优化哪个 |

> 工具的「自纠率」是团队工具库健康度的核心体检项：工具一多，难用的工具会拉低整个会话/Skill 的成本与成功率，而自纠率能精确点名是哪个工具的 `description`/`parameters` 需要打磨。

**落地**：`eval_tools.py` ✅ — 纯函数 `aggregate()`/`evaluate()` 对工具调用记录算自纠率/成功率/p50/p95 + 基线断言；
数据源 live 优先（`langfuse_eval.fetch_tool_spans`，metadata.kind=="tool"）、`fixtures/tools-golden.json` 回退（CI/离线）。
基线见脚本 `BASELINE`：自纠率 ≤ 0.30、成功率 ≥ 0.70、p95 ≤ 5000ms、样本 < 3 不下结论。

## 5. Golden 断言（zhgk · 基线来自 CONTRACT.md 样例 run-demo-0001）

| 断言 | 基线 | 含义 |
|---|---|---|
| `completion_rate ≥ 45` | 样例 53.9 | 勘测完成度不塌方 |
| `mandatory_fill_rate ≥ 0.40` | 样例 23/46=0.50 | 强制项填充达标 |
| `open_issues ≤ 80` | 样例 59 | 遗留问题不爆炸 |
| `step[scene_filter,survey_build] = completed` | — | 关键路径跑通 |

> 基线随业务确认演进（CONTRACT.md 的 `@confirm` 口径定了之后同步）。断言用"区间/阈值"而非精确等值，容忍正常波动、只抓塌方。

## 6. 评测结果契约（`evals/results/{skill}-{ts}.json`）

给「呈现界面」和「AI 分析」消费的统一结构：

```jsonc
{
  "skill": "zhgk",
  "evaluated_at": "2026-06-03T...",
  "quality_score": 1.0,        // 质量维：断言通过率
  "success": true,             // 成功率维：本次是否全过
  "cost_cny": null,            // 成本维：Langfuse（待集成）
  "latency_ms": null,          // 延迟维：Langfuse（待集成）
  "metrics": { "completion_rate": 53.9, "mandatory_fill_rate": 0.5, "open_issues": 59, ... },
  "checks": [ { "name": "...", "pass": true, "detail": "..." } ]
}
```

## 7. AI 分析输入格式（喂 CC / Cursor）

**不要丢原始 trace**。导出「基线 vs 本次 + 偏离点」让 AI 给可执行建议：

```jsonc
{
  "skill": "zhgk",
  "trend": { "quality_score": [1.0, 0.8, 1.0], "cost_cny": [0.025, 0.031], "p95_ms": {...} },
  "deviations": [
    { "target": "step:report_gen", "metric": "p95_ms", "baseline": 8000, "current": 12000, "delta": "+50%" },
    { "target": "tool:read_file", "metric": "自纠率", "value": 0.30, "threshold": 0.10 }
  ]
}
```

prompt 要点：「以下是 <skill> 的评测偏离项，结合 `skills/<skill>` 源码，指出每个偏离的根因与具体改法（改 prompt / 改 schema / 拆 step / 加缓存），按 ROI 排序」。

## 8. 落地状态

| 能力 | 落地 | 说明 |
|---|---|---|
| Skill 质量/成功率 | ✅ | `eval_zhgk.py` 产物断言；fixture 回退（CI 离线可跑） |
| 成本/延迟 | ✅ | `langfuse_eval.fetch_run_metrics(run_id=...)`，**按 run_id 精确对齐**（无 run_id 回退最近 trace 并标 `approx-latest`） |
| 产物自带 run_id | ✅ | `scene_filter` 写产物时标记 `run_id`，评测据此精确对齐 |
| 质量/成功率写回 Langfuse | ✅ | `write_scores` 写 `eval.quality` / `eval.success` 到 trace |
| 工具评测 | ✅ | `eval_tools.py`（自纠率/成功率/p95 + 基线断言） |
| 回归闸（有牙） | ✅ | eval `main()` 在 `success=False` 时**非零退出**；`npm run eval` 串两评测（fixture 模式） |
| CI | ✅ | `.github/workflows/agent-evals.yml`：装 venv → skill-contract 真校验 → `npm run eval` |
| 定制看板 | ✅ | `frontend` `/evals`（SKILL+工具 live；Langfuse 大盘仍 mock） |
| 双视图（本次/总体） | ✅ | URL `?mode=latest|overview`；API `GET .../report?mode=`、`GET .../tools/report?mode=` |
| 按次对齐 refresh | ✅ | `POST /agent/evals/refresh?run_id=&conv_id=`；工勘 done 服务端 + 前端双触发 |
| 工具调用明细 | ✅ | `eval_tools` 落盘 `records[]`；本次视图展示明细表 |
| 会话 conv_id 追踪 | ✅ | `execute_traced` metadata.conv_id；`fetch_tool_spans(conv_id=...)` 过滤 |
| AI 分析（偏离导出） | ✅ | `export_deviations.py` → `deviations-*.json` + `cursor-skill/tools-*.md`；API `/agent/evals/deviations/*` |

## 9. 呈现界面双视图

| 模式 | SKILL tab | 工具 tab |
|---|---|---|
| **本次执行** `mode=latest` | 单次四维 + 断言 + run_id/trace + step 耗时 | 评测上下文 + 断言 + **调用明细表** + 聚合 |
| **总体情况** `mode=overview` | 趋势/漏斗/历次表 | 散点/排行/注册表 |

**自动评测触发**（无需手点「跑评测」）：

- 工勘 LangGraph 真完成（非 HITL）：服务端 `_trigger_eval_background(run_id=...)`
- 工勘卡 SSE `done`：前端 `refreshEvals({ run_id })`（60s 防抖）
- 会话含 `tool_call` 且流结束：服务端线程跑 eval + 前端 `refreshEvals({ conv_id })`
- **无 Langfuse**：`execute_traced` 写 `evals/results/session_logs/{conv_id}.jsonl`，评测优先读本地日志

> 运行：`npm run eval`（CI/本地回归闸，fixture 离线）｜ `python agent/evals/eval_zhgk.py --run-id <id>`｜ `python agent/evals/eval_tools.py --conv-id <id>`｜ 界面 `/evals?mode=latest`。

## 10. HITL / 体验回归指标（v1.1 · 建议纳入手测与后续自动化）

> 对应范式 §4、[`SKILL-DEVELOPMENT.md`](../30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md) §5。工勘实战暴露：清单与 `need_files` 脱节、resume 误重跑 LLM。

| 指标 / 用例 | 定义 | 期望 | 数据源 |
|-------------|------|------|--------|
| HITL 清单一致性 | 上传后 `check` 与 `hitl.need_files` 一致 | Step4 仅缺人员表时清单 **≠** 五件套 | `/upload/batch` + `need`；前端手测 |
| 人员表落盘名 | 上传别名 xlsx | 磁盘为 `Start/远近一体化人员信息.xlsx` | `zhgk_files` + 磁盘 |
| resume 模式 | `report_distribute` HITL 后续跑 | `resume.mode=step_retry`，不重跑 report_gen | API 响应 + 日志 |
| 全量 resume 语义 | 其他 step HITL | `mode=full_restart`，前端文案明示 | API + UI |
| project_info 产物 | survey_build / scene_filter 后 | `RunTime/project_info.json` 存在 | 磁盘断言 |
| SKILL 契约 | SKILL.md 节点列 | 与 `steps[].key` 一致 | `lint_skill_contract.py` CI |

**自动化状态**：磁盘/契约项可逐步迁入 `eval_zhgk.py` 或 E2E；当前以 **手测清单 + CI 契约 lint** 为主。
