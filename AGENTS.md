# AIDA 工程开发指南（AI agent 起手总入口）

> 本文件是整个 `aida` 仓的开发**总入口与红线**。**只保留行为准则 + 核心模块原则 + 命令速查；细节以 `docs/` 为准**（每节给链接，不复制）。当前阶段重点见 [ROADMAP](ROADMAP.md)。

## 0 · 项目概述

AIDA = 智能交付编排系统。四层架构（前端 / Manager / 数据中心 / Claw 执行引擎），业务能力以 **业务场景 Skill** 承载；运行时 1→N 已泛化（注册即得全套端点）。全局导航与"我该看哪"见 [00 开发者地图](docs/00_开发者地图.md)。

## 1 · 真相源文档（本文件不复制，细节看这里）

| 你要 | 看 |
|---|---|
| 全局导航 / 我该看哪 | [docs/00_开发者地图.md](docs/00_开发者地图.md) |
| 团队范式 · 六铁律 + §0 守门 | [docs/20_架构与范式/03_团队Agent开发范式.md](docs/20_架构与范式/03_团队Agent开发范式.md) |
| 开发 / 迁移 skill 起手式 | [docs/10_快速开始/START_HERE.md](docs/10_快速开始/START_HERE.md) |
| 数据落点 / IPO 三层 / 数据中心接口 | [docs/50_数据与接口/](docs/50_数据与接口/业务数据规范.md) |
| 评测标准与四维指标 | [docs/40_评测/](docs/40_评测/METRICS.md) |
| 任务 / 计划（唯一真相） | [ROADMAP.md](ROADMAP.md) |

## 2 · 核心模块通用原则 ★（可扩展框架：新核心模块往这加一行）

> 每个核心模块 = **一个统一入口（唯一真相）+ 一条铁律 + 一个守门**。绕过统一入口 = 红线。
> 「模块」列括号内是给新人的大白话说明——不熟概念先看它。

| 模块 | 统一入口（唯一真相） | 铁律 | 守门 | 细则 |
|---|---|---|---|---|
| **模型调用**<br>（skill 要用大模型(LLM)做判断/生成时从哪调） | `agent/llm.py`（skill 内 `ctx.invoke_llm`；handler `chat_once`/`chat_stream`） | 禁裸调（`import openai/anthropic/litellm`、`requests/httpx` 直打端点、`langchain_openai` 除 `llm.py` 白名单）；一律走统一入口、自动进 Langfuse trace | `lint_no_naked_llm` ✅ | — |
| **数据调用**<br>（skill 读写项目文件/数据时走哪） | 项目文件工作区 `ProjectData/` + 数据中心 API | 读写走数据中心接口 / 规范，不在业务代码里散落直连磁盘 / 库 | 〔待建〕 | **设计原则**（落点 / IPO 三层 / 握手 / 命名版本）→ [业务数据规范](docs/50_数据与接口/业务数据规范.md)　·　**调 API 直接查**（逐接口入参 / 出参 / 鉴权 / 错误码）→ [数据中心 API 调用规范](docs/50_数据与接口/数据中心API调用规范.md) |
| **Skill 编写**<br>（怎么把一个业务做成能自己跑的 skill） | A/B 双层（A=`skills/<name>/SKILL.md` · B=`agent/skills/<name>/`）+ START_HERE 流程 | **开发 / 迁移业务场景 skill 必先读 START_HERE 按其流程执行（A 从头 / B 搬入改造），不要自由发挥**；新能力 = 新 Skill（不写散函数）；A 层「后端节点」表 **≡** B 层 `step.key`；跨 step 数据走 `SkillState` | `lint_skill_contract` ✅ | 起手三件套（`docs/10_快速开始/`）：① [START_HERE](docs/10_快速开始/START_HERE.md)（流程中心·抽象模型 + A/B 分流，第一站）→ ② [AGENT_QUICKSTART](docs/10_快速开始/AGENT_QUICKSTART.md)（照抄细则·碰 9 文件 + step 代码骨架 + HITL）；环境前置 [SETUP](docs/10_快速开始/SETUP.md) |
| **外发副作用**<br>（skill 发邮件/IM 等对外操作走哪 · 避免测试误发真消息） | `agent/mailer.py`（邮件）· `agent/notifier.py` / `send_welink` 工具（IM） | 一切对外副作用走唯一出口 + 留痕，默认 dry-run | `lint_no_naked_send` ✅ | — |
| **作业界面 SDUI**<br>（skill 怎么「不写前端」就有网页作业界面 · 后端吐界面树→前端通用渲染） | 投影器 `agent/skills/<name>/sdui.py` · `project(state)→UI 树` | 后端投影、前端零改；协议三方一致（`builder.py`↔`sdui.ts`↔`SduiNodeView`） | `lint_sdui_contract` ✅ | [SDUI.md](docs/30_skill开发/31_手写规范/SDUI.md)（投影器规范）· [SDUI 组件库 v4](docs/30_skill开发/31_手写规范/SDUI%20组件库%20v4.html)（视觉版组件目录 · 浏览器打开；区别于 builder 派生的 sdui-gallery.html） |

> **零改白拿**：`agent/main.py` / `agent/graph.py` 已泛化（注册即得 `/agent/<name>/{start,stream,resume,ui,artifact,runs}`）；前端 `SkillAgentScreen` / `useSduiStream` / `SduiNodeView` 通用递归渲染。**别去改。**

## 3 · 行为准则（硬规则；完整范式见 [03](docs/20_架构与范式/03_团队Agent开发范式.md)）

1. **先想后写**：有歧义先问，不静默假设；更简方案存在就指出。
2. **最简优先**：只做被要求的，不加推测性功能。
3. **手术式修改**：只改该改的，匹配现有风格，清理自己产生的死代码（预存的不动）。
4. **契约先行 · 单一真相**：每类内容只有一个权威位置，改源不改副本；待定项 `@confirm` 标注。
5. **守门优先**：规范靠 lint 阻断、不靠自觉；**新增一条规范 = 同时给出它的守门**。
6. **验证先于完成**：声称"完成 / 修复 / 通过"前必须跑守门并给证据。

## 4 · 版本节奏（任务以 ROADMAP.md 为唯一真相）

- 在commit前，先对照ROADMAP.md中当前版本的路标是否完成，并标记记录。并且根据守门评测的结果，分析下一版本的开发需求与技术债，写入ROADMAP.md。
- 任务 / 计划的增删改**只改 [`ROADMAP.md`](ROADMAP.md)**，不在本文件 / issue / 聊天里另建任务清单。
- **push 前确认门**：commit 后向用户确认（守门全绿 + 相关文档已同步）再 push；**不自主 push**。

## 5 · 前端开发规范（Vite + React + TypeScript）

> 详档：设计真相 [DESIGN.md](docs/80_设计UX/DESIGN.md) + [UI 视觉规范](docs/80_设计UX/UI视觉规范.md)；组件库 `frontend/src/components/`（`ui/` · `primitives.tsx` · `sdui/`）+ [SDUI 组件目录](docs/site/sdui-gallery.html)；上手 [frontend/README](frontend/README.md)。

- `strict: true`；**禁新增 `@ts-nocheck`**（守门 `npm run lint:no-ts-nocheck`，`prebuild` 阻断）；改挂着 nocheck 的旧文件时优先去掉并补类型。
- 数据层用 `as const satisfies T[]`（**非** `as`，避免绕过结构检查）；共享 Props→`src/types/components.ts`，业务模型→`domain.ts`，环境声明→`global.d.ts`。
- 视觉走 **DESIGN token + 复用组件库**，不散落硬编码 hex/px。
- 命令：`cd frontend && npm run typecheck / lint:no-ts-nocheck / build / dev`（dev port 5173）。

## 6 · 命令速查（后端 · 需先激活 `agent/.venv`）

```bash
# 启动
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload

# 守门（提交前必跑 · 全绿才提交）
python agent/scripts/lint_no_naked_llm.py     # 禁裸 LLM 调用
python agent/scripts/lint_no_naked_send.py    # 禁裸外发
python agent/scripts/lint_skill_contract.py   # A 层「后端节点」↔ step.key 契约
python agent/scripts/lint_tools.py            # 工具 name/desc/schema 契约
python agent/scripts/lint_sdui_contract.py    # SDUI 协议三方一致 builder↔sdui.ts↔NodeView
python agent/scripts/lint_sdui_gallery.py     # SDUI 组件目录 HTML ≡ 契约（派生新鲜度）
python agent/scripts/lint_docs_site.py        # 开发者文档站 HTML ≡ MD 源（派生新鲜度）
python agent/scripts/lint_team_portal.py      # 团队门户 HTML ≡ portal.json（派生新鲜度）
python agent/scripts/lint_runtime_contract.py # 运行时契约 ≡ 代码（DEFAULT_TOOLS/is_tool_error）
python agent/scripts/lint_module_boundaries.py # 跨 skill 零横向依赖 + 已入边界图

# 改了源后重新生成派生制品（再提交）
python agent/scripts/gen_sdui_gallery.py      # builder.py 改了 → 派生 docs/site/sdui-gallery.html
python agent/scripts/gen_docs_site.py         # docs/ 的 MD 改了 → 派生 docs/site/index.html
python agent/scripts/gen_team_portal.py       # docs/onboarding/portal.json 改了 → 派生 docs/site/portal.html

# Skill 元数据 / 评测
curl http://127.0.0.1:7401/agent/skills
python agent/evals/eval_zhgk.py --fixture     # CI 离线回归
python agent/evals/eval_tools.py --fixture
```

## 7 · 不要做（红线）

- ❌ 用 `subprocess` 调 Python 脚本规避 LLM 限制 → 走 Skill 重写
- ❌ 在 `Tool.execute()` 里跑 LangGraph → 长流程走 skill-as-tool（见 [SKILL-DEV §6](docs/30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md)）
- ❌ 引 PostgresCheckpointer → 用 AsyncSqliteSaver，零运维
- ❌ 改 `agent/main.py` / `agent/graph.py`（已泛化，注册即得端点）
- ❌ 把契约正文复制到本文件或别处（单一真相，只链接）
