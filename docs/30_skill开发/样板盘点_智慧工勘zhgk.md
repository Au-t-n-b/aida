# 样板盘点 · 智慧工勘（zhgk）完成度

> **用途**：zhgk 是团队**首个端到端跑通的 Agent 业务场景 Skill**，是规划设计 / 设备安装 / 部署调测复制的样板。本文盘点它**真实完成到哪、哪些可白拿、哪些是债**，供规划设计同事与后端 owner 一起推进 Agent 时做复制基线。
> **依据**：v4 源码盘点（`agent/skills/zhgk/`·15-step + `base.py` + A 层 `skills/zhgk/SKILL.md`）。历史参考：v3 实测 run `run-e051b76b1c`（2026-06-04，5-step 老流水线，**已废弃**）。
> **关联**：范式见 [`02`](../20_架构与范式/02_交付Claw_Agent工程范式.md)/[`03`](../20_架构与范式/03_团队Agent开发范式.md)；部署见 [`04`](../60_部署运维/04_容器化部署与运行时架构.md)。

---

## 0. 一句话结论

**功能链路与工程范式 = 生产级跑通（✅ 可作样板）；v4 已升级为 15-step 意图驱动单流水线；技术债集中在「底座未迁三级隔离」一处（复制前需先处理）。**

---

## 1. v4 流水线（当前实现）

zhgk v4 以**单条 15-step 线性流水线**支撑 4 种意图；每 step 内部调用 `_intent_guard.should_skip()` 决定是否跳过，无需 dispatch_mode。

| # | Step key | 中文 | HITL | 意图 |
|---|----------|------|------|------|
| — | `preflight` | 环境预检（internal=True，豁免契约） | — | 所有 |
| 1 | `intent_select` | 意图选择 | ChoiceCard | 所有 |
| 2 | `scene_suggest_run` | 场景建议生成 | — | scene_suggest |
| 3 | `determine_gen` | 代际制冷识别 | ChoiceCard（BOQ 解析失败时） | survey_work / supplement / report_gen |
| 4 | `filter_build` | 底表过滤 + 建全量勘测结果表 | — | survey_work |
| 5 | `method_split` | 现场 / 数据分流 | — | survey_work |
| 6 | `data_append` | 数据类条目追加 | ChoiceCard | survey_work |
| 7 | `confirm_table` | 勘测表确认 | ChoiceCard（确认 / 重新生成） | survey_work |
| 8 | `wait_survey` | 等待现场上传 | FilePicker | survey_work |
| 9 | `assess` | AI 五值评估 | — | survey_work / report_gen |
| 10 | `issue_list` | 问题清单生成 | — | survey_work / report_gen |
| 11 | `resurvey_gate` | 复勘检查门控 | ChoiceCard（复勘 / 跳过） | survey_work |
| 12 | `supplement_run` | 补充勘测处理 | — | supplement |
| 13 | `report_gen_run` | 工勘报告生成（9 表 Word） | — | report_gen |
| 14 | `report_distribute` | 审批与分发 | — | report_gen |

> 权威来源：[`agent/skills/zhgk/skill.py`](../../agent/skills/zhgk/skill.py)（steps 列表） + [`skills/zhgk/SKILL.md`](../../skills/zhgk/SKILL.md)（端点/意图/HITL 设计）。**本文不再手抄 step 枚举，以上表以源码为准。**

### 1.1 历史参考：v3 实测数据（5-step，已废弃）

> ⚠️ 下表是 **v3 老流水线**（`preflight → scene_filter → survey_build → report_gen → report_distribute`）的 2026-06-04 实测结果，仅供量级参考，**不代表当前 v4 实现**。

| 维度 | v3 实测值 |
|------|----------|
| Run ID | `run-e051b76b1c` |
| Step 完成 | 5/5 completed，overall_progress=100 |
| 场景 / 制冷 | 新址新建 / 液冷_A3_下接管 |
| 勘测填写率 | 53.9%（69/128） |
| LLM 评估 | 89 项（满足 62 / 不满足 21） |
| 风险识别 | 命中 8 / 风险库 32 |
| 分发干系人 | 3 |
| 模型 / 成本 | glm-4-flash / ≈¥0 |
| 前端 | IdleScreen → 启动 → SSE → SDUI 全树渲染 ✅ |

---

## 2. 范式落地度（对照 03 六条）

| # | 范式条 | 状态 | 证据 |
|---|--------|------|------|
| 1 | 模型统一 + 智能分级 | ✅ | `base.py` `invoke_llm` 唯一入口、自动打 Langfuse metadata/tags；zhgk = 15-step 单流水线（意图驱动跳过） |
| 2 | 能力资产化 + 定制回流 | ✅ | `base.py` 532 行底座；`decisions/` 4 条 ADR（resume/vite/外发/契约 lint） |
| 3 | 工具规范（契约化受控） | ✅ | `ctx.call_tool` → `execute_traced` 进 trace；工勘专用工具 `zhgk_bridge` 等 |
| 4 | 副作用统一 + HITL | ✅ | 分发走 `mailer`（dry-run+留痕）；`check_inputs()` 失败→软中断→`/resume` 续跑 |
| 5 | 契约先行（唯一真相制品） | ✅ | A 层 `skills/zhgk/SKILL.md` 已对齐 v4 实现；14 业务步骤表 + preflight 注释 |
| 6 | 可观测 → 评测闭环 | ✅ | `eval_zhgk.py` + golden fixture + 数十次 results（6/3–6/4）+ CI |

**结论**：六条全 ✅。（历史债 D1 SKILL.md 滞后已于 v4 迁移时修复。）

---

## 3. 代码资产盘点 ★规划设计最该看这节

### 3.1 可白拿的通用底座（复制 = 零成本复用）

| 资产 | 提供能力 | 文件 |
|------|---------|------|
| `SkillState` | 全 Skill 共用的 LangGraph state（steps/logs/metrics/hitl…） | `base.py` |
| `SkillContext` | work_root 路径工具 + `invoke_llm`（自动 trace）+ `call_tool` | `base.py` |
| `BaseStep` | `check_inputs()`（决定 HITL）+ `run()` 抽象 + `artifacts_pattern` | `base.py` |
| `BaseSkill.build_graph()` | **自动建图**：每 step 一节点 + 串行边 + HITL/error 路由 + checkpointer 选择 | `base.py` |
| HITL 软中断机制 | check 失败→`hitl` diff→router 到 END→`/resume` | `base.py` `execute_step` |
| 意图守卫 | `_intent_guard.should_skip()` 按 intent 字段跳过不相关 step | `zhgk/steps/_intent_guard.py` |
| 外发层 | `mailer` / `notifier`（统一出口 + dry-run + 留痕） | `agent/` |
| 评测框架 | `eval_<name>.py` + `fixtures/*-golden.json` 模式 | `agent/evals/` |

> **含义**：规划设计模块**不用碰**建图/HITL/checkpointer/trace/外发——这些 `base.py` 全包了。**只写业务 step + skill 装配 + A 层 SKILL.md**。

### 3.2 zhgk 专用（复制时要改写为本模块业务）

| 专用件 | zhgk 内容 | 规划设计要替换成 |
|--------|----------|-----------------|
| **14 个业务 step**（steps/*.py，共 ~2,080 行） | 代际制冷识别/底表过滤/勘测上传/AI 五值评估/报告生成/分发 | 建模业务：BOQ 来源/实例/拓扑等 |
| `sdui.py` 投影器（545 行） | 工勘 KPI/风险/产物分栏布局 | 建模 KPI（BOQ·实例·节点·边）+ 拓扑嵌入 |
| A 层 SKILL.md | 工勘触发词/意图/4 HITL 门/端点 | 建模触发词/流程 |
| 工勘专用工具 | `zhgk_bridge` / `site_survey` | 建模专用工具 |
| 意图守卫配置 | 4 意图×15 step 跳过矩阵 | 建模意图结构（或改 dispatch_mode，如 xtsj） |

> 对照「Claw 对比画板」三模块 schema 差异表：survey/modeling/job 的 HITL 决策、子任务、黄金指标、嵌入视图、产物**各不同**——这些就是 §3.2 要改的部分。

---

## 4. 已知技术债（复制前必读）

| # | 债 | 影响 | 建议 |
|---|----|------|------|
| ~~D1~~ | ~~A 层 SKILL.md 正文滞后~~ | — | ✅ **已修复**（v4 迁移时更新，当前 SKILL.md 对齐实现） |
| ~~D2~~ | ~~agent 多副本未收敛~~ | — | ✅ **已收敛**（`aida/agent` 为唯一真相） |
| D3 | **底座路径仍旧单例**：`SkillContext` 用 `work_root/ProjectData/{Start,Input,RunTime,Output}`，未迁数据中心三级隔离 `runs/<runId>/` | 多租户化时要改底座 | 与规划设计一起推进时，把 `SkillContext` 升级为 `runs/<runId>/` 结构（04 §3/§8） |
| D4 | `_template` 脚手架太薄（71 行空壳） | 不足以引导复制 | **以 zhgk 本身为样板**比 `_template` 更实用；可后续把 v4 结构烘入模板 |

---

## 5. 规划设计（modeling）复制路线

> 基于 zhgk 样板 + `base.py` 底座 + 03 §7 清单 + SKILL.md G 节，规划设计模块的最短路径：

```
第1步 · 数据中心建定义   aida-datacenter/skills/modeling/（SKILL.md+module.json+dashboard.template+assets）
第2步 · 写 steps         agent/skills/modeling/steps/*.py（继承 BaseStep；照 zhgk/steps/ 写法）
第3步 · 装配 skill       agent/skills/modeling/skill.py（BaseSkill: name+description+steps）→ 注册 registry
第4步 · 冻 state 契约     modeling 的 state.json 形状（metrics: BOQ/实例/节点/边）；带 schemaVersion
第5步 · SDUI 投影        照 zhgk/sdui.py 写 modeling 投影器（含拓扑嵌入 embed）
第6步 · A 层 SKILL.md     复制 zhgk 的，改触发词/流程/端点前缀 /agent/modeling/
第7步 · 评测             eval_modeling.py + fixtures/modeling-golden.json；纳入 CI
第8步 · 守门             lint_no_naked_llm + lint_no_naked_send + lint_skill_contract 全过
```

**复用率预估**：底座（建图/HITL/checkpointer/trace/外发/评测框架）≈ 零改动复用；新写量集中在 step 业务逻辑 + SDUI 投影 + A 层文档，与 zhgk 的 ~2,080+545 行同量级。

---

## 6. 给"一起推进"的建议

1. **D3（三级隔离迁移）建议作为共同里程碑**：zhgk 和 modeling 都受益；趁两模块并行时一次性把 `SkillContext` 升级到 `runs/<runId>/`，避免各迁一次。
2. **意图模式 vs dispatch 模式**：若 modeling 子任务互斥度高（不同建模目标差异大），可参考 xtsj 的 dispatch_mode 而非 zhgk 的意图守卫，按需选型。

---

## 版本

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-04 | 初版：v3 实测 run-e051b76b1c + 源码盘点，给规划设计复制基线 |
| v1.1 | 2026-06-08 | 更新为 v4（15-step 意图驱动）；退役废弃的 5-step 叙事；step 表指向源码；修复 D1/D2 已解状态；更新代码量 |
