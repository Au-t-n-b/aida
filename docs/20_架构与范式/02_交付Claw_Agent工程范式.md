# 交付 Claw / Agent 工程范式

> 本文是 [01_AI智能化系统架构梳理](01_AI智能化系统架构梳理.md) 第 5 节「交付 Claw / Agent」的**工程实现篇**。
> 上篇讲「是什么、角色化、消费 Wiki + 本体」；本篇讲「怎么落地」：技术选型、SKILL 范式、工具范式、开发规范。
> 已用 **智慧工勘（zhgk）** 作为标准样板端到端跑通，后续业务场景 Skill（规划设计 / 设备安装 / 部署调测）按本范式复制。

> **⚠️ 文档定位（v1.1 对齐）**：规范条文以 [`03_团队Agent开发范式`](03_团队Agent开发范式.md) 为准（六条 + §0 守门元规范）；本文是 **zhgk 项目的落地实现篇**，侧重技术选型与 A+B 落地细节。下文 §5 五条铁律、§3.2 智能分级、§3.3 SDUI 反映早期状态，**最新落地见 03 §1/§4/§6 与源码**（评测、外发统一、双 HITL、会话记忆均已 ✅）。

---

## 1. 定位

交付 Claw 是 AI 原生四层架构的**执行层**：把 Wiki 大脑的知识、DORA 本体的语义，转成「按角色、按任务、按业务动作」可执行的 Agent 能力。

本范式要解决的工程问题，是让所有业务场景 Skill 的 Agent **同一套骨架、同一套规范**生长，而不是每个模块各写一套：

- 模型怎么调（统一入口、禁止裸调）
- 能力怎么组织（SKILL 范式）
- 工具怎么定义（Tool 框架）
- 外发怎么管（邮件 / 消息统一）
- 怎么观测成本与链路（Langfuse）

一句话：**Claw 提供「可观测的确定性骨架」，模块只写业务，框架全复用。**

---

## 2. 技术选型与总体架构

### 2.1 选型一览

| 层    | 选型                     | 取舍理由                                                               |
| ---- | ---------------------- | ------------------------------------------------------------------ |
| 编排   | **LangGraph**          | 状态图天然表达「多 step + HITL 中断 + 条件路由」；`build_graph()` 按 steps 自动生成，不手搭图 |
| 服务   | **FastAPI + SSE**      | 流式推进度给前端；REST 启动 / 续跑 / 上传 / 产物下载                                  |
| 持久化  | **AsyncSqliteSaver**   | run 重启不丢；零运维，不引 Postgres                                           |
| 可观测  | **Langfuse**           | 0 改业务代码即全量捕获 trace / token / 成本                                    |
| 能力组织 | **A+B 双层 SKILL**       | A 层对接 Claude Code 生态，B 层是 LangGraph 执行代码                           |
| 工具   | **Tool 基类 + Registry** | JSON Schema 参数 + 校验 + OpenAI function 格式，受控调用                      |

### 2.2 一条关键取舍：in-process 而非 subprocess

早期 step 曾用子进程（driver）执行，靠 stdout 事件通信。**已主动迁移为 in-process LangGraph 节点**，原因是：子进程是黑盒，无法进 Langfuse trace 树。

> 取舍原则：**可观测性优先于解耦**。整条 pipeline 现在是一棵完整 trace（节点级 CHAIN span + LLM 级 GENERATION span），无子进程黑盒。

### 2.3 A+B 双层架构

```
A 层 · Claude Code Skill 门面        ~/.claude/skills/<name>/
  └ SKILL.md（frontmatter: name / description / 触发词）+ references/   ← 唯一真相(source of truth)

B 层 · LangGraph 执行                agent/skills/<name>/
  └ BaseSkill + BaseStep + run() 业务逻辑

接缝：BaseSkill 启动自动读 A 层 SKILL.md frontmatter → 注入 description，单向同步、不靠人手抄
```

---

## 3. SKILL 范式（核心）

### 3.1 一个 Skill 的组成

| 要素             | 约定                                                                            |
| -------------- | ----------------------------------------------------------------------------- |
| A 层 SKILL.md   | frontmatter（name/description/触发词）+ references 流程文档，**唯一真相**                   |
| B 层 `skill.py` | 继承 `BaseSkill`，声明 `name` + `steps: list[BaseStep]`                            |
| 每个 step        | 继承 `BaseStep`，实现 `check_inputs()`（前置校验 → 决定 HITL 中断）+ `run(ctx, state, emit)` |
| 状态             | 跨 step 共享数据走 `SkillState`，不写全局变量                                              |
| 产物             | 声明 `artifacts`，相对 work_root，可下载                                               |
| 渐进暴露           | registry 启动只挂工厂引用；`list_metadata()` 只返回 name+description，按需才实例化               |

### 3.2 智能分级（最关键的范式约定）

「确定性 pipeline」和「LLM 自主用工具」不是二选一，按需分级：

| 级别                   | 用法                                          | 适用                            | 可控性      |
| -------------------- | ------------------------------------------- | ----------------------------- | -------- |
| **① 确定性 LLM 调用**     | step 内 `ctx.invoke_llm(messages, kind=...)` | 固定环节的评估 / 摘要 / 抽取             | 最高（人定流程） |
| **② 受控 Agent 子任务**   | 委托一个「白名单工具 + 迭代上限 + 结果 schema」的受限 agent     | 局部需要 LLM 自主选工具（如「读 doc → 摘要」） | 中（沙箱约束）  |
| ~~③ 全自主 agent loop~~ | ❌ 暂不采用                                      | —                             | 低，牺牲可预测性 |

> 受控 Agent 子任务的契约（借鉴 nanobot hybrid）：`goal` + `allowedTools[]`（白名单）+ `maxIterations` + `resultSchema` + 结果回填指定 UI 节点。**主干确定、局部智能、全程受约束。**

> **补充（03 §1）**：团队级把分级扩为 ①确定性图 / ②受控 ReAct（会话 `chat_engine`）/ ③单点 `chat_once`。⚠️ 注：会话引擎当前 `allowed` 白名单**未强制**（全量工具 + `present_choices` 软控），是范式声称与实现的已知 gap，待补。

### 3.3 SDUI · 前端零定制（灯塔目标）

业务场景 Skill 的工作台 UI **不应每个模块各写一套**。目标范式：后端 skill 通过 SSE 吐 **UI patch ops**（如 `{op:merge, target:{nodeId}, value:{...}}`），前端一个通用 `SduiView` 渲染器消费 →

> **新业务场景 Skill = 写后端 skill + 定义 UI schema，前端零改动。** 这是「灯塔项目 → 多模块复制」的终极形态。

> **现状（v1.1）**：SDUI 仍是**远期目标，尚未落地**；近期自建的评测界面 `/evals` 是传统前端（未走 SDUI）。建议把它作为**第一个 SDUI 消费者**验证灯塔。

### 3.4 新增一个 Skill 的标准流程

```
1. 建 A 层  ~/.claude/skills/<name>/SKILL.md（frontmatter + 触发词 + references）
2. 建 B 层  agent/skills/<name>/skill.py（BaseSkill：name + steps）
3. 写 steps 每个 BaseStep：check_inputs() + run()；LLM 走 ctx.invoke_llm，工具走 ctx.call_tool
4. 注册   registry.register("<name>", get_<name>_skill)
5. 验证   /agent/skills 能看到元数据；端到端 run 进 Langfuse trace
```

### 3.5 会话 Agent 与任务 Skill —— 两形态，一底座

LangGraph 不只能做「确定性流水线」，它本就是 Agent（含对话）框架。左侧 ClawRail 的**通俗会话能力**与作业 Skill 是**同一底座的两种图形态**：

|      | 任务 Skill（如 zhgk） | 通俗会话（ClawRail）                                  |
| ---- | ---------------- | ----------------------------------------------- |
| 图形态  | 固定 step 串行（人编排）  | LLM ↔ 工具的 ReAct 循环（模型自主决定：直接答 / 调工具 / 唤起 skill） |
| 目标   | 确定性产出（报告 / 基线）   | 开放问答 / 解释 / 跨页提问                                |
| 智能级别 | §3.2 ①确定性调用为主    | 受控 ReAct（工具走白名单、进 trace）                        |

**共享同一底座**：同一个 `llm.py`（模型统一）、同一个 Tool Registry（工具统一）、同一个 checkpointer（会话用 `thread_id` 存多轮记忆）、同一个 Langfuse（会话也进 trace）、同一套 SSE（token 流式打字机）。

**会话的能力来源**（呼应架构 §5.3「大模型 + Wiki + 本体」）：
- 通用闲聊 / 问答 → 模型本身
- 业务问答 → 检索 Wiki 大脑 + 读 DORA 本体（知识 Agent）
- 「帮我跑工勘 / 调排期」→ **把 Skill 当作高阶工具调用**，会话唤起对应任务图

> 一句话：**任务要确定性、会话要开放性，是两种图、一套底座**；会话还能作为入口唤起任务 Skill，形成"聊着聊着就把活干了"的体验。

---

## 4. 工具范式

### 4.1 Tool 基类 + Registry

所有工具继承统一 `Tool` 基类，由 `ToolRegistry` 管理：

| 能力                                | 说明                                                          |
| --------------------------------- | ----------------------------------------------------------- |
| `name / description / parameters` | parameters 是 **JSON Schema**（type/enum/min/max/required/嵌套） |
| `execute(**kwargs)`               | 真正执行                                                        |
| `cast_params`                     | schema 驱动的安全类型转换（"5"→5）                                     |
| `validate_params`                 | 调用前校验，错误回 LLM 让其自纠                                          |
| `to_schema`                       | 转 OpenAI function-calling 格式，喂给模型                           |
| Registry.`execute`                | cast → validate → run，出错附「换个方法重试」提示                         |

### 4.2 工具是「受控能力」，不是「自由调用」

- step 内 / 受控子任务内统一经 `ctx.call_tool(name, params)` 调用 → 进 trace
- 受控子任务只能用 `allowedTools` 白名单内的工具
- 工具清单（可复用能力库）：`filesystem` / `shell` / `web` / `doc_text`(文档抽取) / `mcp`(MCP 接入) / `user_upload` / `site_survey`(工勘专用) 等

---

## 5. 开发规范（五条铁律 · 守门式）

> **📌 已演进**：这五条是 zhgk 早期版；团队级已升级为 [`03_团队Agent开发范式`](03_团队Agent开发范式.md) 的**六条 + §0 守门元规范**（松绑图化、新增工具/副作用规范、可观测→评测合并）。本节保留作落地对照，**规范以 03 为准**。
> 规范不靠自觉，靠 **lint 守门**：违规即 `prebuild` 阻断，进不了构建。

### 铁律 ① 模型接口统一
所有 LLM 调用经 `agent/llm.py` 唯一接入点，仅 3 个合法入口：
```python
ctx.invoke_llm(messages, step_key=..., kind=...)   # 推荐 · 99% 场景，自动带元数据
ctx.llm.invoke(...)                                 # 需 stream / 特殊 config
from agent.llm import chat_once, chat_stream        # 脱离 SkillContext 时（FastAPI handler）
```

### 铁律 ② 禁止新增接口调 LLM
- ❌ `from openai import` / `from anthropic import` / `import litellm`
- ❌ `from langchain_openai import`（除 `llm.py` 白名单）
- ❌ `requests/httpx` 直打 `chat/completions` / `open.bigmodel.cn`
- ✅ 守门：`scripts/lint_no_naked_llm.py` 挂 `prebuild`，命中即阻断

### 铁律 ③ 邮件 / 外发统一（✅ 已落地）
唯一出口 `agent/mailer.py`（`send_mail` 默认 dry-run + 统一 SMTP + 留痕）+ `tools/send_welink.py`（即时消息）；守门 `lint_no_naked_send.py` 扫 `smtplib / win32com / 裸 SMTP`。会话发邮件/消息前先调 `present_choices` 向用户确认。详见 [03 §4 副作用统一](03_团队Agent开发范式.md) + ADR 0003。

### 铁律 ④ SKILL 规范
A+B 双层；SKILL.md 是唯一真相（代码不重复写 metadata）；新增能力 = 新增 Skill（不写散落函数）；状态走 SkillState；智能调用按 §3.2 分级。

### 铁律 ⑤ 工具规范
新增工具 = 继承 `Tool` + 注册 Registry；参数必须 JSON Schema；调用走 `ctx.call_tool` 进 trace；受控子任务只用白名单工具。

---

## 6. 可观测与成本（Langfuse）

- **0 改业务代码**：`ChatOpenAI(callbacks=langfuse)` 一次性挂上，所有调用自动捕获
- **三级嵌套 trace**：`run → CHAIN(step) → GENERATION(LLM)`
- **每次调用持有**：prompt / response 原文、model、token、成本(CNY)、延迟、元数据（skill/step/kind/run_id/project）、标签
- **Dashboard 可做**：按 run 看链路、按 step 拆延迟、按 kind 拆成本、跨 run 看 skill 总成本、模型切换前后对比
- **实测（zhgk 一次 run · glm-5.1）**：11 个 step span / 11 次 LLM 调用 / 总成本 ¥0.0249 / token in 5559 out 8008

> **评测闭环（✅ 已落地）**：可观测只是原材料；其上已建四维评测（质量/成功率/成本/延迟）+ 工具自纠率 + 回归闸（`npm run eval` + CI）+ AI 分析导出（`export_deviations` → cursor-*.md）。见 [03 §6](03_团队Agent开发范式.md) 与 [`METRICS.md`](../40_评测/METRICS.md)。

---

## 7. 闭环机制（对齐架构梳理 §7.3 Agent 闭环）

Agent 在执行交付任务时暴露的能力缺口，按本范式沉淀回框架：

```
缺能力 → 加 Tool（继承 Tool + 注册）
缺流程 → 加 Step / 加 Skill（BaseStep / BaseSkill）
缺界面 → 加 SDUI schema（前端零改动）
缺知识 → 回流 Wiki 大脑 / 丰富 DORA 本体
```

> 即架构梳理所说：让系统从「能回答」走向「能协同完成交付」，工程上靠的就是「能力缺口标准化沉淀」。

---

## 8. 一句话总结

**交付 Claw 以 A+B 双层 SKILL 承接角色化任务，以 LangGraph 可观测骨架保证确定性，以「确定性调用 / 受控子任务」分级智能，以统一的模型 / 工具 / 外发入口 + lint 守门保证规范不发散，以 SDUI 实现新模块零前端复制——智慧工勘是第一个跑通的样板。**
