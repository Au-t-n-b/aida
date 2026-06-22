# 01 · 系统架构（活层 · Code-Synced）

> **定位**：这是与代码同步的**活快照**——只放「当前注册了哪些模块、运行时泛化到什么程度」。
> **叙述性真相另有其文**：系统**为什么这么设计**看 [`docs/01_AI智能化系统架构梳理`](../01_AI智能化系统架构梳理.md)（四层能力逻辑）；**怎么部署运行**看 [`docs/04_容器化部署与运行时架构`](../../60_部署运维/04_容器化部署与运行时架构.md)（运行时四层）。本文不复制它们，只维护代码现状。
> **刷新**：由架构师 [Workflow C 基线重置](00_ARCHITECT_SOP.md#workflow-c-架构基线重置) 从代码反向刷新。

---

## 1. 运行时四层（模块在哪一层跑）

业务场景 Skill（Skill）位于**执行层**（交付 Claw / Agent），运行时与三方交互：

```
┌─────────────┐   登录鉴权 + 拉起独立 Claw 容器（零拷贝挂载 Skill/项目/会话）
│  Manager    │ ─────────────────────────────────────────────────┐
└─────────────┘                                                   ▼
┌─────────────┐   取项目文件 / 评估底表          ┌──────────────────────────┐
│ DataCenter  │ ◄───────────────────────────── │  Claw / Agent（执行层）    │
│ 数据中心     │ ── runs/<runId>/ 产物 ────────► │  LangGraph + 智谱 GLM      │
└─────────────┘                                 │  ⟵ 你写的业务场景 Skill在这层    │
       ▲                                        └──────────────────────────┘
       │ 直连取数刷新界面                                   │ SSE 推进度 + SDUI 树
┌─────────────┐                                            ▼
│  Frontend   │ ◄──────────────────────── 异步通知 + 作业进度 ──────────────┘
│ War Room    │   SkillAgentScreen 通用渲染（SDUI 零改）
└─────────────┘
```

> owner 分工与各层部署状态见 [`docs/00_开发者地图` §4](../../00_开发者地图.md)。

---

## 2. 当前已注册模块（代码快照 · 2026-06-07）

> 真相 = `agent/skills/__init__.py`。详细接口/依赖/红线见 [02 模块边界图](02_module_boundaries.md)。

| 模块 id | 形态 | step 数 | 前端 module key | 状态 |
|---------|------|--------|----------------|------|
| `zhgk` 智慧工勘 | 线性 DAG · 意图驱动 | 14 (+preflight) | `survey` | ✅ 端到端样板 |
| `guihua` 规划设计 | 线性 DAG | 5 | `modeling` | ✅ |
| `xtsj` 系统设计 | dispatch 分发 | 2 (+路线图) | `design` | ✅ PoC |
| `device_install` 设备安装 | 线性 DAG | 待定 | `install` | 🟡 B 层可选注册 |
| `software_deployment` 部署调测 | 线性 DAG + resume 单步 | 13 | `deploy` | ✅ E2E |
| `delivery` 交付编排 | 待定 | 待定 | 待定 | 🟡 试点目标（待建） |

---

## 3. 运行时泛化程度（1→N · 注册即得）

| 能力 | 泛化状态 | 锚点 |
|------|---------|------|
| HTTP 端点 `/agent/{skill}/*`（10 个） | ✅ 注册即得，零改 `main.py` | `agent/main.py` |
| LangGraph 构图（按 `skill_id`） | ✅ 零改 `graph.py` | `agent/graph.py` |
| SDUI 渲染（投影器 → 前端递归） | ✅ 前端零改 | `SkillAgentScreen` + `SduiNodeView` |
| HITL 软中断（缺料/确认 → 补料续跑） | ✅ `check_inputs` + 钩子 | `agent/skills/base.py` |
| Langfuse trace（run→step→LLM/tool） | ✅ 0 改业务代码全捕获 | `build_graph` 默认 callbacks |
| 评测四维（质/成功/成本/延迟 + golden） | ✅ 模板化 | `agent/evals/` |

> 这就是「为什么加模块只碰 [02 §6 事实表](02_module_boundaries.md) 那几个文件、其余零改」的根因——运行时已把单模块的一切抽象成可注册的钩子。

---

## 4. 编排形态分级（不强制图化）

模块按「确定性需求」选编排形态（[范式 §1](../03_团队Agent开发范式.md)）：

| 级别 | 形态 | 代表模块 |
|------|------|---------|
| ① 确定性流水线 | LangGraph 线性 DAG（`BaseSkill` 串 `BaseStep`） | `zhgk` / `guihua` |
| ① · 分发变体 | dispatch（菜单命令路由，`dispatch_mode=True`） | `xtsj` |
| ② 受控 ReAct | LLM↔工具循环（白名单 + 上限 + trace） | `chat_engine`（会话 · 现作降级） |
| ③ 单点调用 | `chat_once` / `chat_stream` | 固定摘要/抽取 |

> **通用对话引擎（v1.1）**：前端 ClawRail 通用对话（`/agent/chat/stream`）默认改走 **nanobot AgentLoop**（容器内 :8900，agent 经 `run_nanobot_chat_async` 代理；`AIDA_CHAT_VIA_NANOBOT=1` 默认开）。`chat_engine` ReAct 保留为 **降级路径**（标志关闭或 nanobot 不可达时启用），不再是通用对话主引擎。
> - **skill 启动**：nanobot 经 `aida_agent` 工具调 `/agent/<skill>/start`（本进程建 run）；endpoint 在本轮结束 diff 出新 run，还原 `skill_launch` 事件（带 `run_id`），前端**采纳 run_id 并订阅**（不再二次 `/start`）。
> - **行为差异**：`present_choices` 确认卡 / 敏感工具 `tool_approval` 为 chat_engine 专属，nanobot 路径下不再从通用对话触发；当前项目/页面上下文由 system 注入改为**折叠进 user 消息**（nanobot API 仅收单条 message + session）。

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.1 | 2026-06-22 | 通用对话引擎切到 nanobot AgentLoop（chat_engine 降级）；skill_launch 经 aida_agent + run 还原桥接 |
| v1.0 | 2026-06-07 | 基线重置：运行时四层 + zhgk/guihua/xtsj 快照 + 泛化程度 + 编排分级 |
