# 02 · 模块边界图（Module Boundaries）

> **唯一真相**：AIDA 有哪些业务场景 Skill、它们的公共接口、彼此的依赖规则、加模块必碰的高冲突文件、以及绝不能碰的红线。
> **强制对齐**：本图 ↔ 代码由 [`agent/scripts/lint_module_boundaries.py`](../../../agent/scripts/lint_module_boundaries.py)（跨 skill 隔离 + 注册表↔本图）+ 每模块 [`skills/<id>/SKILL.md`](../../../skills/) 的 [`lint_skill_contract.py`](../../../agent/scripts/lint_skill_contract.py)（节点↔step.key）共同守门。
> **怎么用**：架构师跑 Workflow A/B/C 时读写本图（见 [00_ARCHITECT_SOP](00_ARCHITECT_SOP.md)）；开发者领 TASK 前读本图确认自己的「修改范围」与「红线」（见 [00_DEVELOPER_SOP](00_DEVELOPER_SOP.md)）。

---

## 1. 模块清单（已注册业务场景 Skill）

> 真相 = `agent/skills/__init__.py` 的 `registry.register(...)`。新增/删除模块时本表与注册表同步（`lint_module_boundaries` 校验每个注册 id 都在本图出现）。

| 模块 id | 中文 | 编排形态 | step 数 | 入口 | 前端 module key | A 层契约 | 状态 |
|---------|------|---------|--------|------|----------------|---------|------|
| `zhgk` | 智慧工勘 | 线性 DAG · **意图驱动** | 14 (+preflight) | `intent`（4 意图） | `survey` | [SKILL.md](../../../skills/zhgk/SKILL.md) | ✅ 端到端样板 |
| `guihua` | 规划设计（建模仿真） | 线性 DAG | 5 | `{}`（顺序执行） | `modeling` | [SKILL.md](../../../skills/guihua/SKILL.md) | ✅ |
| `xtsj` | 系统设计（网络开局） | **dispatch 分发** | 2 (+路线图) | `command`（菜单命令） | `design` | [SKILL.md](../../../skills/xtsj/SKILL.md) | ✅ PoC |
| `delivery` | 交付编排 | 待定 | 待定 | 待定 | 待定 | ❌ 待建 | 🟡 试点目标 |

> **每模块的权威节点表（step.key 逐一）在各自 `SKILL.md` 的「后端节点」列** —— 本图只聚合「数量 + 形态 + 入口」，不复制节点清单（避免第二份会漂移的真相）。要看 zhgk 的 14 个节点，读 [`skills/zhgk/SKILL.md` §A](../../../skills/zhgk/SKILL.md)。

---

## 2. 公共接口（每个模块对外暴露什么）

每个已注册模块**注册即自动拥有**同一组 HTTP 端点（`main.py` 已泛化为 `/agent/{skill}/*`，`graph.py` 按 `skill_id` 构图）。这就是模块的**公共接口契约**——前端、会话、其它系统只能经此交互，**不得越过端点直接 import 模块 Python**。

| 方法 | 路径（`{skill}` ∈ 模块 id） | 用途 | 注册即得 |
|------|------|------|:---:|
| POST | `/agent/{skill}/start` | 启动 run（body 见各 SKILL.md） | ✅ |
| GET  | `/agent/{skill}/stream/{run_id}` | SSE 事件流（含 `sdui` 树 / `done` / `error`） | ✅ |
| POST | `/agent/{skill}/resume` | HITL 续跑（文件补齐 / 确认） | ✅ |
| GET  | `/agent/{skill}/files/check` | 缺料清单对齐（`?need=`） | ✅ |
| POST | `/agent/{skill}/upload` · `/upload/batch` | 上传补料 | ✅ |
| GET  | `/agent/{skill}/status/{run_id}` | 状态快照 | ✅ |
| GET  | `/agent/{skill}/ui/{run_id}` | SDUI 快照（首屏 / 断线重连） | ✅ |
| GET  | `/agent/{skill}/artifact?path=` | 下载产物 | ✅ |
| GET  | `/agent/{skill}/runs` | 历史 run 列表 | ✅ |

> 全局（非模块级）：`GET /agent/skills`（元数据列表）· `GET /agent/skills/{name}` · `POST /agent/chat/stream`（会话）· `GET /agent/evals/*`（评测）。

**SDUI 出口**：模块经 `sdui_projector` 把 `state → UI 树` 投影，前端 `SkillAgentScreen` 零改动渲染。SDUI 协议三方（`agent/sdui/builder.py` ↔ `frontend/src/lib/sdui.ts` ↔ `SduiNodeView.tsx`）由 `lint_sdui_contract` 守门。

---

## 3. 依赖规则（模块之间能/不能依赖什么）

**铁律：业务场景 Skill之间零依赖。** 模块只能向下依赖通用底座，绝不能横向 import 另一个模块。共享只走两条合法通道：① 通用底座（`base`/`llm`/`tools`/`mailer`）；② 运行时数据中心 `runs/<runId>/`。

| `agent/skills/<模块>/` 可以依赖 | 形态 | 不可以依赖 |
|------|------|------|
| `..base`（BaseSkill/BaseStep/SkillContext） | 通用底座 | ❌ **另一个业务场景 Skill** `..zhgk` / `..guihua` / `..xtsj`（横向耦合） |
| `...llm`（经 `ctx.invoke_llm` / `chat_once`） | LLM 唯一入口 | ❌ 裸 `import openai/anthropic/litellm`（`lint_no_naked_llm`） |
| `...tools`（经 `ctx.call_tool`） | 受控工具库 | ❌ 绕过 registry 直调工具 |
| `...mailer` / `...notifier` | 外发唯一出口 | ❌ 裸 `smtplib` / `httpx.post` 外发（`lint_no_naked_send`） |
| `agent/sdui/projector_base` | SDUI 投影基类 | ❌ 直接构造前端能识别外的 UI 节点 |
| 磁盘产物 `ctx.runtime_dir` / `ctx.output_dir` + `state`/`metrics` 小字段 | 跨 step 衔接 | ❌ 把大文件塞 `SkillState` |

**依赖矩阵**（行依赖列，✅ 允许 / ❌ 禁止 / — 自身）：

| ↓依赖 \ 被依赖→ | base | llm | tools | mailer | sdui | zhgk | guihua | xtsj |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **zhgk** | ✅ | ✅ | ✅ | ✅ | ✅ | — | ❌ | ❌ |
| **guihua** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | — | ❌ |
| **xtsj** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | — |

> 🚪 **守门**：`lint_module_boundaries.py` 扫 `agent/skills/<A>/` 下任意 `.py` 是否 import 另一个已注册模块 `<B>`，命中即阻断。

---

## 4. 高冲突文件登记表 ⭐（加模块必碰 · 并行开发的冲突面）

AIDA 运行时已 1→N 泛化（注册即得图+端点），消除了改 `main.py`/`graph.py` 的需要 —— 但把「加一个模块」的改动**挤压到了 3 个共享注册/路由文件**上。多人并行做 delivery / 新模块时，**这 3 个文件就是 AI 互相打架的地方**。每个 TASK 必须把对它们的改动写成**行级范围**，由架构师统一合并。

| 共享文件 | 改什么 | 位置锚点 | 冲突级别 | 合并协议 |
|---------|--------|---------|:---:|---------|
| `agent/skills/__init__.py` | `_register_all()` 内加 `import` + `registry.register("<id>", get_<id>_skill)` | 函数体内追加 2 行 | 🔴 高 | 各 TASK 在函数末尾追加，架构师合并 |
| `frontend/src/routes/module.tsx` | `MODULE_TO_SKILL` 加 `<moduleKey>: '<id>'` | 对象字面量（约 L12–16） | 🔴 高 | 各 TASK 加 1 行键值 |
| `frontend/src/data/modules-data.ts` | `MODULE_SCHEMAS` 加 `<moduleKey>: {…}` 一条 | 对象字面量（现有键 survey/modeling/job） | 🔴 高 | 各 TASK 加 1 条 schema 块 |
| `agent/tools/run_<id>.py` + `chat_engine`（可选） | skill-as-tool 会话唤起 | 新文件 + 分发分支 | 🟡 中 | 仅做会话唤起时碰 |

> 📌 **front-end module key ≠ skill id**：前端用 `survey/modeling/design` 等 UI key，经 `MODULE_TO_SKILL` 映射到 `zhgk/guihua/xtsj`。加 delivery 时两边都要登记（见 [§8 漂移](#8-已知漂移与待办)）。

---

## 5. 零改白拿 · 红线区（绝不在 TASK 内修改）

以下是**运行时已泛化的通用底座**，注册一个模块即自动复用。**碰它们 = 改架构，不是做模块** → 必须走 RFC（[00_DEVELOPER_SOP §D2](00_DEVELOPER_SOP.md)）由架构师评估，禁止在普通模块 TASK 里顺手改。

| 层 | 红线文件 | 为什么不能碰 |
|----|---------|------------|
| 后端路由 | `agent/main.py` | FastAPI 端点已泛化 `/agent/{skill}/*`，加模块零改 |
| 后端构图 | `agent/graph.py` | 按 `skill_id` 经 registry 自动构图 |
| 后端基类 | `agent/skills/base.py` | `BaseSkill`/`BaseStep`/`SkillContext`/`build_graph` + 钩子 |
| 前端工作台 | `frontend/src/components/screens/survey-agent.tsx`（`SkillAgentScreen`） | 通用模块运行器，所有模块共用 |
| 前端流 | `frontend/src/hooks/useSduiStream.ts` | SSE + REST 流处理 |
| 前端渲染 | `frontend/src/components/sdui/*`（`SduiNodeView` 等）· `frontend/src/lib/sdui.ts` | SDUI 协议递归渲染 |

> 钩子全集（在 `BaseSkill` 上设、都可选、默认有合理行为）：`sdui_projector` · `step_retry_keys` · `file_handler` · `initial_project` · `apply_resume_payload`。**要定制行为靠覆盖钩子，不靠改红线文件。**

---

## 6. 加一个模块 · 碰这些边界（事实表 · 其余零改）

> 这是 [AGENTS.md「新业务场景 Skill·碰这些文件」](../../../AGENTS.md) 的边界视角投影。完整可操作版见 [`AGENT_QUICKSTART.md`](../../10_快速开始/AGENT_QUICKSTART.md) + [`START_HERE.md`](../../10_快速开始/START_HERE.md)。

```
NEW（只属于你的模块 · 别人不碰）
  agent/skills/<id>/**            skill.py + steps/*.py + sdui.py
  skills/<id>/SKILL.md            A 层契约（＋ ~/.claude/skills/<id>/SKILL.md 双部署）
  agent/evals/eval_<id>.py        + fixtures/<id>-golden.json（可选）
  agent/tools/run_<id>.py         skill-as-tool（可选）

MODIFY（高冲突共享 · 行级范围 · 架构师合并 —— 见 §4）
  agent/skills/__init__.py
  frontend/src/routes/module.tsx
  frontend/src/data/modules-data.ts

零改（红线 · 见 §5）
  agent/main.py · graph.py · base.py · 前端 SkillAgentScreen/useSduiStream/SduiNodeView
```

---

## 7. 运行时数据边界（模块间唯一的数据共享面）

模块间**不通过内存/import 共享数据**，只通过数据中心的运行时目录（物理隔离）：

```
ProjectData/  （或数据中心 runs/<runId>/ 三级隔离）
  Template/   ← 底表/模板（只读）
  Input/      ← 用户上传（HITL 补料落点）
  Output/     ← 产物（报告/清单/结题）
  RunTime/    ← 中间 json（project_info / device_list …）
  Images/     ← 现场照片
  skill_result.json  ← 含 run_id，评测/链路读取
```

> 跨 step 数据走磁盘产物 + `state`/`metrics` 小字段；跨模块协作走数据中心目录，**不得**让模块 A 直接读模块 B 的内存状态。

---

## 8. 已知漂移与待办

> 本图的价值之一就是**让漂移可见**。以下为基线重置（2026-06-07）时扫出的不一致，记录在此供架构师跟踪。

| # | 漂移 | 现状（文件级） | 影响 | 建议 |
|---|------|--------------|------|------|
| D1 | 前端 module key ↔ skill 映射不齐 | `MODULE_TO_SKILL` = {survey→zhgk, modeling→guihua, **design**→xtsj}；`MODULE_SCHEMAS` 键 = {survey, modeling, **job**} | `design` 模块跑 xtsj 但无 schema → 标题回退成原始 key「design」；`job` 有 schema 但无 skill → 走 mock 占位 | 统一命名：要么 `design` 补 schema、要么 `job` 接 skill；二选一对齐 |
| D2 | `delivery` 尚未建 | 仅前端在合产品 UI（`feat/merge-delivery-frontend`），后端无 `delivery` skill | 试点目标，非缺陷 | 走 Workflow A 生成 `TASK_delivery.md` 后开建 |

---

## 强制与维护

- 🚪 **守门**：`python agent/scripts/lint_module_boundaries.py`（跨 skill 隔离 + 注册表↔本图）+ `lint_skill_contract.py`（SKILL.md↔step.key）。两者全绿是 Workflow B 通过的必要条件。
- 🔄 **刷新**：模块增删、接口变更后由架构师跑 [Workflow C](00_ARCHITECT_SOP.md#workflow-c-架构基线重置) 刷新 §1/§2/§8，并重跑守门。

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-07 | 基线重置：zhgk/guihua/xtsj 三模块边界 + 依赖矩阵 + 高冲突登记 + 红线区 + 漂移 D1/D2 |
