# 团队 Agent 开发范式（v1）

> **本文定位**：团队级 Agent 开发规范 —— 跨项目复用的"骨架与铁律"。
> - 上承 [`01_AI智能化系统架构梳理`](01_AI智能化系统架构梳理.md) §5「交付 Claw / Agent」（角色化、消费 Wiki + 本体）。
> - 落地实例见 [`02_交付Claw_Agent工程范式`](02_交付Claw_Agent工程范式.md)（智慧工勘 zhgk = 首个端到端样板）。
> - 与前端 UX 规范（[`04_前端实现/AGENTS.md`](../../../03_前端效果/04_前端实现/AGENTS.md) + `DESIGN.md`）同构：**唯一真相 + 制品先行 + lint 守门**。
> - **工程手册**（怎么做）：[`30_skill开发/31_手写规范/`](../30_skill开发/31_手写规范/README.md)（SKILL / 工具 / SDUI / 起手式 · 唯一真相）。
>
> 一句话：**02 讲"交付 Claw 这个项目怎么写"，本文讲"团队每个 Agent 项目都怎么生长、怎么复用资产"。**

### 文档地图（避免范式与代码脱节）

**工程手册源**（唯一真相，均在 `docs/` 树内）：[`30_skill开发/31_手写规范/`](../30_skill开发/31_手写规范/README.md)（SKILL / TOOL / SDUI / START_HERE / CHECKLIST）· [`40_评测/`](../40_评测/METRICS.md)（评测）· [`90_决策ADR/`](../90_决策ADR/README.md)（ADR）

| 主题 | 范式（本文） | 权威细则 |
|------|-------------|----------|
| **新模块起手入口** ⭐ | §7 | [`START_HERE.md`](../10_快速开始/START_HERE.md) → [`AGENT_QUICKSTART.md`](../10_快速开始/AGENT_QUICKSTART.md)（agent 速查） |
| **运行时部署与对接** 🆕 | — | [`04_容器化部署与运行时架构.md`](../60_部署运维/04_容器化部署与运行时架构.md)（四层部署 + 逐层落地状态 + 对接操作地图） |
| 铁律、清单、守门 | §0–§8 | 本文 |
| SKILL 制作与执行 | §2、§4、§7 | [`SKILL-DEVELOPMENT.md`](../30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md) |
| 工具制作 | §3 | [`TOOL-DEVELOPMENT.md`](../30_skill开发/31_手写规范/TOOL-DEVELOPMENT.md) |
| 测评指标与跑法 | §6 | [`METRICS.md`](../40_评测/METRICS.md) + [`README.md`](../40_评测/README.md) |
| 提交时代码规范 | — | [`AGENTS.md`](../../AGENTS.md) |
| 非显然决策 | §2 | [`decisions/`](../90_决策ADR/README.md) |

---

## 0. 元规范：守门优先（规范靠 lint 阻断，不靠自觉）

团队范式最硬的一条不是某条规范本身，而是**每条规范都必须配一个可执行的守门检查**，违规即 `prebuild` 阻断、进不了构建。没有守门的规范会退化成 PPT。

团队两端已有先例，本范式将其制度化：

| 端        | 唯一真相                              | 守门 lint                           |
| -------- | --------------------------------- | --------------------------------- |
| 后端 Agent | `agent/llm.py`（模型唯一入口）            | `lint_no_naked_llm.py`（扫裸调，命中阻断）✅ |
| 后端外发     | `agent/mailer.py` / `notifier.py` | `lint_no_naked_send.py` ✅         |
| SKILL 契约 | `SKILL.md`「后端节点」↔ `steps[].key`   | `lint_skill_contract.py` ✅        |
| 前端 UX    | CSS token（`visual-system.css`）    | `design.md lint`（扫硬编码 hex/px）     |

> **铁律**：新增一条规范 = 同时给出它的守门检查（lint / CI / 类型）。下文每条都标注 `🚪守门` 与落地状态（✅已落地 / ⚠️部分 / ❌待补）。

---

## 1. 模型统一：唯一入口 + 智能分级（**不强制图化**）

**原则**：所有 LLM 交互经唯一入口 `llm.py`；**按确定性需求分级编排，图化是手段不是义务**。

这条修正了"所有 LLM 必须抽象为 LangGraph 状态图"的过度绝对 —— 团队的会话引擎（`chat_engine.py`）本身就是手写 ReAct stream 循环、**不是状态图**，但它完全合规（走统一入口、进 trace）。真正的不变量是"唯一入口 + 分级"，不是"一律图化"。

**两层不变量**：
- **(a) 唯一入口**：禁 `import openai/anthropic/litellm`、禁 `requests/httpx` 直打 chat/completions、禁 `langchain_openai`（除 `llm.py` 白名单）。
- **(b) 智能分级**（按可控性选编排形态）：

| 级别             | 形态                                    | 适用                 | 落地锚点                   |
| -------------- | ------------------------------------- | ------------------ | ---------------------- |
| ① 确定性流水线       | LangGraph 图（`BaseSkill` 串 `BaseStep`） | 固定环节、要确定性产出（报告/基线） | `skills/zhgk` 5 step 图 |
| ② 受控 ReAct     | LLM↔工具循环（白名单 + 迭代上限 + 进 trace）        | 开放问答、会话、局部自主选工具    | `chat_engine.py`       |
| ③ 单点调用         | `chat_once` / `chat_stream`           | 固定摘要/抽取/分类         | `llm.py`               |
| ~~④ 全自主 loop~~ | ❌ 不采用                                 | —                  | 牺牲可预测性                 |

**🚪守门**：`lint_no_naked_llm.py`（挂 prebuild）✅已落地。

---

## 2. 能力资产化：通用底座 + 工具复用 + 定制回流

**原则**：构建 Agent 先选用**通用底座 + 通用工具**，再按业务定制；定制改动**文档化落库**，定期复盘，把高频定制**回流成底座能力**，让后续项目"选型→初步构建"走团队资产快车道。

**通用底座（已有）**：

| 资产                                        | 作用                                       | 锚点                                     |
| ----------------------------------------- | ---------------------------------------- | -------------------------------------- |
| `BaseSkill` / `BaseStep`                  | Skill = steps 编排，自动建图                    | `skills/base.py` ✅                     |
| `Tool` / `ToolRegistry` / `DEFAULT_TOOLS` | 工具基类 + 注册表，会话与 step 共享                   | `tools/` ✅                             |
| `SkillContext`                            | 注入 LLM / 路径 / `call_tool` / `invoke_llm` | `skills/base.py` ✅                     |
| checkpointer / ConversationStore          | 任务记忆(thread_id) / 会话记忆(conv_id)          | `graph.py` / `conversation_store.py` ✅ |

**定制回流机制（✅已启动）**：
- 载体：每个项目 `decisions/`，ADR 风格（背景 / 选项 / 决策 / 后果）。见 [`decisions/`](../90_决策ADR/README.md)。
- 触发：每个 Skill 交付后回填「定制清单」——改了底座什么、为什么。
- 节奏：复盘把**高频定制回流成底座**（缺能力→加 Tool/Step，呼应 01§7 Agent 闭环）。
- 已入库 ADR（zhgk 实战）：0001 resume 软中断重跑；0002 前端 vite；0003 外发统一；0004 SKILL 契约 lint。

**🚪守门**：`decisions/` 非空 ✅；每个 Skill 目录「定制清单」段（可加 CI）⚠️部分。

---

## 3. 工具规范：契约化的"受控能力库"（面向工具大量增长）

> 团队后续会为**通用会话 + 业务 SKILL** 造大量工具 —— 工具是增长最快的资产，必须从第一天就上规范，否则迅速劣化为一堆裸函数。

**原则**：新增工具 = 继承 `Tool` + 注册 `Registry`；参数必须 JSON Schema；调用一律走 `ctx.call_tool` / `execute_traced`（进 trace）。

**工具契约（每个工具必备）**：
- `name`（小写下划线，全局唯一）/ `description`（给模型看，决定召回）/ `parameters`（JSON Schema：type/enum/min/max/required）。
- `cast_params`（"5"→5 安全转换）+ `validate_params`（调用前校验，错误回模型自纠）。
- `to_schema()`（OpenAI function 格式）。

**面向规模增长的约定**：
- **白名单调用**：受控 ReAct / 受控子任务只能用 `allowed=[...]` 内的工具（`get_definitions(allowed)`）。
- **分类与命名**：按能力域前缀（`fs_` / `doc_` / `web_` / `mail_` / `survey_` …），避免命名碰撞、便于召回。
- **会话工具 vs 业务工具**：通用工具进 `DEFAULT_TOOLS`（会话+step 共享）；业务专用工具按 skill 局部注册，避免污染全局召回。
- **skill-as-tool**：Skill 可被包成高阶工具供会话唤起（`run_survey` → 启动 zhgk），实现"聊着把活干了"。
- **工具评测**：纳入第 6 条；细则见 [`TOOL-DEVELOPMENT.md`](../30_skill开发/31_手写规范/TOOL-DEVELOPMENT.md) §7。

**🚪守门**：`lint_no_naked_llm` ✅；`lint_no_naked_send` ✅；`lint_tools.py`（未注册 / 缺 Schema）✅。  
**状态**：框架 ✅；工具评测 ✅（`eval_tools.py`、自纠率、`/evals` 工具 tab、CI）。

---

## 4. 副作用统一：外发唯一出口 + 人在回路（HITL）

> 你的五条规范全是"LLM/工具/观测"，漏了**副作用治理**。Agent 会发邮件、写文件、调外部系统 —— 这些不统一会失控。

**原则**：所有**对外副作用**走唯一出口 + 留痕；所有**需人决策的中断**走标准 HITL。

- **外发统一**：邮件/消息/外部写操作经唯一出口（`mailer.py` 默认 dry-run + 统一 SMTP + 留痕），照 `llm.py` 范式。✅已落地（邮件）。
- **人在回路（HITL）**：缺料/审批走"中断—补料—续跑"标准模式（详见 [`SKILL-DEVELOPMENT.md`](../30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md) §5）：
  - 中断：`step.check_inputs()` 失败 → 返回 `hitl{step, reason, need_files}` → 路由 END（**软中断**，非 LangGraph `interrupt()`）。
  - 补料：`/files/check?need=` 对齐清单 → `/upload/batch`（带 `need`）→ `/resume`。
  - 续跑：默认 **`full_restart`**（新 `thread_id` 全流程）；`report_distribute` 支持 **`step_retry`**（仅重试该步）。ADR [0001](../90_决策ADR/0001-resume-soft-interrupt-rerun.md)。
  - 呈现：`ZhgkProgressCard`（清单按 `need_files`，禁止用五件套冒充 Step4 缺失项）。
  - ✅已落地（zhgk）。

**🚪守门**：`lint_no_naked_send.py` ✅。

---

## 5. 契约先行：唯一真相制品 + UX 先行

**原则**：Agent 接入 UX 设计后，代码实现严格参照**一组带版本的工程制品**（契约），而非口头约定。**先冻契约，前后端各自实现。**

这条把"唯一事实来源"从模糊的五项收敛为**可版本化的工程制品**（架构/API契约/类型/代码规范），把"用户痛点/代码品味"归位为**决策输入**（依据，非 contract）。

**团队两端都已有"契约先行"雏形**：

| 制品        | 唯一真相                   | 镜像/契约                                                                                                                       |
| --------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 前端视觉      | CSS token              | `DESIGN.md`（改 token 再同步文档 + `design.md lint`）                                                                               |
| 后端读模型     | `SkillState` 投影        | [`CONTRACT.md`](../../../aida-datacenter/skills/zhgk/CONTRACT.md)（`ZhgkState v1 FROZEN` + 版本号 + `@confirm`）+ 机器形态 `zhgk.ts` |
| Skill 元数据 | `SKILL.md` frontmatter | `BaseSkill` 启动读取覆盖 description（代码不重复写）                                                                                      |

**约定**：
- **契约带版本**：变更走版本号（v1→v2），消费方按 `schemaVersion` 兼容。
- **待定项显式标注**：`@confirm` 标业务待定口径，确认后移除即冻结。
- **UX 先行**：UX/交互设计 → 冻 `state` 读契约 → 后端投影、前端 render 并行。

**🚪守门**：CONTRACT.md 有版本号 + 类型文件同步（可加校验）⚠️部分（zhgk 有，未通用化）。

---

## 6. 可观测 → 评测闭环（原规范三 + 五合并）

**原则**：Langfuse 全程 trace 是**原材料**；在其上建**评测**，把原材料变成"基线 + 回归 + 优化信号"。

**可观测（✅已落地）**：
- `get_llm()` 挂 Langfuse callbacks，0 改业务代码全量捕获。
- 三级嵌套 trace：`run → CHAIN(step) → GENERATION(LLM)`；工具调用 span 走 `execute_traced`（会话与 step 共用）。
- 每次调用持有：prompt/response、model、token、成本、延迟、元数据（skill/step/kind/run_id/scope）。

**评测（✅已落地 v1 —— 指标权威文档另附）**：

> **指标定义（必读）**：[`METRICS.md`](../40_评测/METRICS.md)  
> **操作指南**：[`README.md`](../40_评测/README.md)  
> 教训：resume/HITL 清单类问题应用 **回归 + METRICS §10 体验指标** 兜住，避免仅靠手测。

- **四维**：质量（golden 断言）/ 成功率 / 成本 / 延迟（Langfuse + `eval_zhgk` / `eval_tools`）。
- **工具维**：**自纠率**为核心（description/schema 质量信号）。
- **呈现**：`/evals?mode=latest|overview`；工勘 done / 会话工具后自动 `refresh`。
- **回归闸**：`npm run eval` + `.github/workflows/agent-evals.yml`（含 `lint_skill_contract`）。

**🚪守门**：CI 跑 `evals/` ✅；新 Skill 须在 METRICS 增断言表或 `fixtures/*-golden.json`。

---

## 7. 新 Agent 选型与初始化清单（团队资产快车道）

新建一个 Agent 项目，按团队资产走以下清单，避免重复造轮子：

```
□ 选型     复用 llm.py / BaseSkill / Tool+Registry / checkpointer / mailer / trace 底座
□ 读手册   docs/30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md + TOOL-DEVELOPMENT.md
□ 建 A 层   ~/.claude/skills/<name>/SKILL.md（frontmatter + 触发词 + HTTP 端点表）
□ 建 B 层   agent/skills/<name>/skill.py（BaseSkill: name + steps）
□ 写 steps  每个 BaseStep: check_inputs()（决定 HITL）+ run()；LLM 走 ctx.llm，工具走 ctx.call_tool
□ 冻契约    CONTRACT.md + types/<name>.ts；lint_skill_contract 通过
□ 注册      registry.register("<name>", ...)；会话唤起 → skill-as-tool（见 TOOL-DEVELOPMENT §5）
□ 观测      Langfuse：run→step→LLM/tool；conv_id / run_id  metadata
□ 评测      METRICS.md 增断言；evals/fixtures + eval_<name>.py；npm run eval
□ 守门      lint_no_naked_llm + lint_no_naked_send + lint_skill_contract
□ 落库      decisions/ ADR；交付后回填定制清单
```

---

## 8. 一句话总结

**团队以「唯一入口 + 智能分级」统一模型、以「通用底座 + 契约化工具」复用能力、以「副作用统一 + HITL」治理风险、以「契约先行」对齐前后端、以「可观测→评测」驱动迭代，以「lint 守门 + ADR 回流」保证规范不发散、资产滚雪球 —— 智慧工勘是第一个跑通全部六条的样板。**

---

## 9. 规范版本与维护

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-03 | 初版六条 + 守门元规范 |
| v1.1 | 2026-06-03 | 对齐 aida 落地：评测 ✅、工具评测 ✅、工程手册链出、HITL/resume/step_retry 更新 |

**维护约定**：范式条文变更时直接改源（`docs/30_skill开发/31_手写规范/` / `docs/40_评测/` / `docs/90_决策ADR/` / `AGENTS.md`）；落地状态以 **METRICS §8 表格** 与 **CI** 为准，不以本文勾选为准。

---

### 附：本范式相对你的初版五条规范的变化

| 你的初版             | 本范式            | 变化                            |
| ---------------- | -------------- | ----------------------------- |
| 一 禁裸调 + 必须状态图    | 1 唯一入口 + 智能分级  | **松绑图化**（会话 ReAct 合规）         |
| 二 底座复用 + 定制文档化   | 2 能力资产化 + 定制回流 | 补**载体**（decisions/ADR + 复盘节奏） |
| 三 可观测            | 6 可观测→评测       | **与五合并**                      |
| 四 UX 先行 + 唯一事实来源 | 5 契约先行         | 收敛为**可版本化制品**，痛点/品味归位为输入      |
| 五 评测（写一半）        | 6 评测闭环         | **补全**四维回归                    |
| —（缺）             | 0 守门元规范        | **新增**（范式精髓）                  |
| —（缺）             | 3 工具规范         | **新增**（面向工具大量增长）              |
| —（缺）             | 4 副作用统一        | **新增**（外发 + HITL）             |
