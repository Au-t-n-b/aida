# skill2langgraph 流水线 · 文档库条目

> 本文是 skill2langgraph 系统并入 **AIDA 文档库（文档孪生）** 的模块条目，供**开发者对齐**与**开发 agent 取上下文**。
> 一句话：把"业务专家写的低确定性 skill"编译成"在 AIDA 上确定运行的 LangGraph skill 模块"，并在真实 AIDA 底座上验证后交付。
> 📍 **仓内落点**：本文档集位于 `docs/skill2langgraph/`（§10 索引为仓库根相对路径）；运行时契约去重——以仓内既有 [`AIDA-RUNTIME-CONTRACT.md`](../31_手写规范/AIDA-RUNTIME-CONTRACT.md) 为权威源。与既有 [`接入/`](../31_手写规范/接入/接入-Skill与LangGraph接入规范.md)（接入契约·路径B）互补：本集讲「如何产线化生产 skill」，接入规范讲「skill 合入既有模块的保真红线」。

---

## 1. 定位

skill2langgraph 是 AIDA 的 **skill 生产流水线**。它把业务专家脑中低确定性的隐性流程，经引导收敛为合规业务契约，再编译成可在 AIDA 运行时执行的**确定性 skill 模块**（`BaseSkill` + steps + SDUI 投影器 + 必要的新工具），在**真实 AIDA 底座**上通过三类验证后交付并注册。

系统由两个解耦子系统组成，仅通过一份交付契约相连：

| 子系统 | 形态 | 人在环 | 产出 |
|---|---|---|---|
| **引导编写（前门）** | 对话式独立程序，业务专家侧，自带模型 | build-time，HITL 密集 | `SKILL.md` + `assumptions.json` |
| **编译流水线** | 开发者 / CI 侧，可无头 | 仅 observer | skill 模块 + 验证报告 + 交付包 |

> 确定性来自**被生成并验证过的 LangGraph**，而非生成它的 agent——所以编译期的 build agent 是 agent-中立的（Codex / Claude Code / Cursor 可插拔）。

---

## 2. 核心概念（术语对齐）

| 概念 | 含义 |
|---|---|
| **Raw Skill** | 业务契约（《可编译业务 Skill 编写规范》§22 模板），非代码实现 |
| **已确认假设清单** `assumptions.json` | 逐条记录每处"模糊→确定"的决定 + 业务作者确认。语义真源 = 草稿 + 此清单 |
| **SkillIR** | Raw Skill 的结构化执行表示，Graph 与契约测试的输入 |
| **skill 模块（Graph）** | 编译产物 = 一个 AIDA skill：`agent/skills/<name>/{skill.py, steps/, sdui.py}` + `SKILL.md` |
| **测试底座** | 以**真实 AIDA 容器**为测试沙箱（非复刻 Harness）；测试通过 ≡ 在 AIDA 上通过 |
| **镜像 digest 钉死** | 对齐 ≡ 测试镜像 digest == 生产镜像 digest |
| **工具解析** | 复用 toolbox 已有 > 自实现新工具 > 注册回 toolbox |
| **SDUI 投影器** | skill 的 `project(state)→dict` 纯函数，把运行态投影成节点树（复用固定组件库） |

---

## 3. 端到端流水线

```text
业务专家
  │  前门 S1–S10（讲真实案例 → 边界扰动 → 规则/LLM/人工三分 → 文档库接地消歧 → 逐节填写 → HARD-GATE → 作者终审）
  ▼
SKILL.md + assumptions.json ──[ 唯一接缝：写文件 ]──▶ Session 0 契约复核闸门
                                                          │
                                                          ▼
                              编译：SkillIR → skill 模块（steps + sdui 投影器 + 新工具）+ 行为/契约测试
                                                          │
                                                          ▼
                              测试底座：一次性真实 AIDA 容器（同生产镜像 digest）执行
                              · provider/外部工具端点 → 回放服务（确定性）
                              · 外发强制 dry-run；run 态在容器内
                                                          │
                                                          ▼
                              三类验证：行为 ∧ 契约 ∧ 运行稳定性  →  交付包
                                                          │
                                                          ▼
                              新工具注册回 toolbox · skill 随镜像部署 · 记录"已验证 digest"
```

---

## 4. 产物与契约

### 4.1 输入（接缝，唯一）
- `SKILL.md`：《编写规范》§22 十五节模板。
- `assumptions.json`：已确认假设清单（每条含 `id/section/kind/question/options/resolved_value/evidence/confirmed_by`）。
- 流水线接受**任何来源**的合规 Raw Skill：前门产出的，或懂《编写规范》的开发者手写的。

### 4.2 输出（skill 模块 + 交付包）
- **skill 模块**（生成物，进 AIDA 镜像）：
  - `agent/skills/<name>/skill.py`（`<Name>Skill(BaseSkill)`：`name` + `steps[]` + 工厂 + 钩子）
  - `agent/skills/<name>/steps/*.py`（每 step：`key`/`name` + `check_inputs()` HITL + `run()`）
  - `agent/skills/<name>/sdui.py`（`project(state)→dict` 投影器，复用 `projector_base`）
  - `SKILL.md`（节点 ↔ step.key 契约）+ `__init__.py` 注册
  - 必要时随包的**新工具**实现
- **交付包**：Graph 文档 + 行为检测报告 + 契约检测报告 + 运行稳定性摘要 + "已验证镜像 digest"。

### 4.3 验收闸门
生成物注入测试容器前必须过 AIDA 守门 lint：`lint_skill_contract` / `lint_runtime_contract` / `lint_sdui_contract` / `lint_tools` / `lint_no_naked_llm` / `lint_no_naked_send`。

---

## 5. 与 AIDA 各模块的集成契约

| 模块 | skill2langgraph 依赖它 | skill2langgraph 产出给它 |
|---|---|---|
| **AIDA Agent 运行时** | `SkillContext.invoke_llm`、工具运行时、`SkillState`（reducer 累加）、软中断 HITL、`build_graph` 契约 | 符合上述契约的 skill 模块 |
| **数据中心（项目云空间）** | files API 读输入 / 写产物；项目/用户（测试租户） | skill 运行时产物经 `POST /files/upload` 回传 |
| **Toolbox（工具运行时+注册）** | 复用查询已有工具 | 通过验证的新工具注册回 toolbox |
| **文档库（文档孪生）** | S6 能力接地（工具/数据中心 API/业务对象的结构化镜像） | 本条目 + 能力缺口回流 |
| **SDUI 组件库** | 固定组件库 + 可用组件清单契约 | 复用现有组件的投影器；缺口报维护者 |
| **Manager** | 按 digest 拉一次性测试容器、注入 skill、work_root↔REST 桥接 | 测试调用 |
| **CI / 镜像** | 不可变镜像（test==prod 同 digest）、回放服务、再验证流水线 | "已验证 digest" 标记 |

> 运行时行为以 `AIDA-RUNTIME-CONTRACT.md` 为权威源：provider 无原生 `output_schema`（结构化输出靠适配器层）；工具失败返回 `"Error:"` 字符串不抛异常；HITL 软中断（写 `state["hitl"]`→END→resume），非 `interrupt()`；node 返回 state diff、`steps/logs` 走 reducer 累加。

---

<a id="pipeline-toolreuse"></a>

## 6. 工具解析（复用 > 自实现 > 注册回流）

编译管线对每个工具能力需求三步解析：

1. **复用**：优先复用 toolbox 已有工具（经文档库能力查询命中）。
2. **自实现**：toolbox 没有 → 自行实现新工具，作为生成物随 skill 打包，在测试底座一同验证。新工具满足 AIDA `Tool` 基类契约（`name`/`description`/`parameters` JSON Schema/`execute` 同步；失败返回 `Error`/`{ok:false}`）。
3. **注册回流**：全流程通过后注册回 toolbox（幂等/去重/版本/provenance），供未来复用。

新工具说明此前的 skill 没有该调用需求，故注册回流与镜像 digest 推进之间的时序**不影响现有 AIDA 运行**。

---

## 7. SDUI（生成投影器，复用-only）

SDUI 是呈现投影层，**不是工具、不存数据中心**：skill 的 `project(state)→dict` 纯函数，SSE 层每次 state diff 调用并流式推前端，前端通用渲染器递归渲染。

- 组件库（节点词汇表 + 渲染器 + `projector_base`）是**固定、专人维护**的平台资产；编译器**复用-only，不自造组件**，缺则报缺口给维护者。
- 编译期：通用段（header/stepper/进度/产物/HITL）从标准 `state.json` schema 自动复用 `projector_base`；业务段（KPI/风险表/摘要）从 Raw Skill 的输出/风险/状态字段派生；过 `lint_sdui_contract` 方可注入。
- 前门 Raw Skill **不设计 UI**，呈现自动投影、风格走"领导汇报视角"设计偏好。

---

## 8. 测试与版本对齐

- **以 AIDA 本体为测试底座**：生成的 skill 注入一次性真实 AIDA 容器执行，删除"第二套实现"——测试通过 ≡ 在 AIDA 上通过。
- **确定性**：LLM 与外部工具端点经端点重定向走回放服务；外发强制 dry-run；本地文件工具靠种子 fixture；run 态（`state.json`/checkpoint）在容器内。
- **取证**：读容器内 `state.json` + checkpoint + Langfuse，喂行为/契约/运行稳定性三类验证。
- **始终对齐**：对齐 ≡ 测试镜像 digest == 生产镜像 digest；AIDA 发新 digest 时无头批量重验所有已部署 skill，仅提升仍绿者。

---

## 9. 给开发 agent 的上下文要点（精炼）

读到本条目的开发 agent，需要记住：

1. skill2langgraph = **两系统**（前门写契约 + 流水线编译），唯一接缝是 `SKILL.md + assumptions.json`。
2. **零静默决策**：每处"模糊→确定"都进假设清单、经作者确认；编译期不替业务拍板。
3. 生成物是**标准 AIDA skill 模块**，遵循 `AGENTS.md` 的 skill 结构与守门 lint。
4. **存储分工**：run 态→容器、skill+新工具→镜像、项目文件→数据中心 files API。
5. **工具可增长**（复用>自实现>注册），**SDUI 组件封闭**（复用-only，缺则报缺口）。
6. **测试在真实 AIDA 上跑**，版本靠**镜像 digest 钉死**，不维护任何 AIDA 复刻品。
7. skill-as-tool（`run_survey`/`zhgk_bridge`）是历史妥协产物，**不属于本范式最终形态**。

---

## 10. 详细设计索引

| 主题 | 文档 |
|---|---|
| ★ 执行手册（给 coding agent 的编译操作手册 · 一句话接住） | `docs/skill2langgraph/skill2langgraph执行手册.md` |
| 契约层（机器可校验 · v0.3，agent 编译时取用） | `docs/skill2langgraph/contracts/`（SkillIR-schema / 校验规则集 / assumptions-schema / skill打包契约 / 交付契约） |
| 实现路线图（设计→实现总纲 · 要建什么 / 分阶段 P0–P3） | `docs/skill2langgraph/实现路线图.md` |
| 前门引导编写流程（S1–S10、HARD-GATE、假设清单） | `docs/skill2langgraph/引导编写流程-完整设计.md` |
| 目标产物规格（§21 检查清单 / §22 模板） | `docs/skill2langgraph/可编译业务Skill编写规范.md` |
| 运行时契约 | `docs/30_skill开发/31_手写规范/AIDA-RUNTIME-CONTRACT.md` |
| 测试底座对齐方案（最终形态） | `docs/skill2langgraph/测试底座对齐方案.md` |
| 跨模块配合需求 | `docs/skill2langgraph/requirements/`（测试底座/ · Toolbox · 文档库 · SDUI 组件库） |
