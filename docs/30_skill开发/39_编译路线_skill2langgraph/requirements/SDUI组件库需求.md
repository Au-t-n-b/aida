# SDUI 组件库配合需求

> 状态：Draft v1（2026-06-08）
> 提出方：skill2langgraph 流水线
> 面向：SDUI 组件库维护者（AIDA 前端 + `agent/sdui`）
> 关联：AIDA `agent/sdui/builder.py`、`agent/sdui/projector_base.py`、`frontend/src/components/sdui/*`、`frontend/src/lib/sdui.ts`、`lint_sdui_contract`；设计：`docs/skill2langgraph/测试底座对齐方案.md` §2.2

## 0. 背景

SDUI 是 AIDA 的**呈现投影层**：skill 的 `sdui.py::project(state)→dict`（纯函数）把运行态投影成节点树，前端 `SduiNodeView` 通用递归渲染，每次 state diff 经 SSE 流式推送。**组件库（节点词汇表 + 渲染器 + projector_base 通用 builder）是已实现、有专人维护的固定平台资产。**

skill2langgraph 编译管线会**生成 skill 的投影器**。因组件库固定、**不能自造组件**，编译器必须知道"能拼哪些组件、怎么拼、缺什么"。本文是给组件库维护者的**轻量需求**：把已有组件库暴露成编译器可查询的契约。**不要求开发新组件。**

## 1. 与 Toolbox 的关键区别（定位）

| | Toolbox 工具 | SDUI 组件 |
|---|---|---|
| 缺了怎么办 | 复用 > **自实现** > 注册回流（可增长集） | 复用 > **不能自实现** > 报缺口给维护者（封闭集） |
| 为什么 | 后端 Python `execute`，工作流可生成可注册 | 需前端渲染器（三方一致），工作流改不了运行中的固定前端 |

→ 编译器对 SDUI 是**复用-only**：缺组件只能降级用现有组件表达，或提缺口等维护者补齐，**绝不自造**。

<a id="sdui-components"></a>

## 2. 需求清单

### R1 · 机器可读「可用组件清单 + props 契约」★核心
**要求**：提供一份机器可读清单（JSON/YAML 或可导出），列出当前组件库**所有可用节点类型**及各自：
- 稳定 node type ID（如 `stack`/`card`/`stepper`/`donutChart`/`table`/`statisticRow`/`artifactGrid`/`choiceCard`/`filePicker`…）；
- props/字段 schema（名 / 类型 / 必需性 / 取值域）；
- 容器型节点的 `children` 规则；
- 语义说明（该组件用于呈现什么）；
- 版本（随组件库/前端 digest）。
**来源**：现有 `agent/sdui/builder.py` 节点定义 + `lib/sdui.ts` 类型 + 各 `Sdui*.tsx`——导出为**单一结构化清单**（三方一致已由 `lint_sdui_contract` 保证）。
**验收**：编译器能据清单**枚举可用组件**、并校验生成的投影器只用清单内节点及合法 props。

### R2 · projector_base 通用 builder 的输入契约
**要求**：把 `projector_base` 通用 builder（`build_header`/`build_stepper`/`build_metrics_card`/`build_artifacts`/`build_summary_card`/`build_hitl`）的**输入约定**（各自从 state 的哪些标准字段投影）文档化/结构化，使编译器能"给定标准 `state.json` schema → 自动复用通用段"。
**验收**：给定标准 state（`steps`/`metrics`/`outputs`/`hitl`/`files`），能自动产出 header/stepper/进度/产物/HITL 段。

### R3 · 组件缺口承接通道
**要求**：提供轻量收口（工单/目录 + 模板），让"现有组件无法表达某业务呈现"的缺口能提给维护者，至少含：想呈现什么、来源 skill、现有组件为何不够、期望交互。闭环：新组件发布后更新 R1 清单版本，受影响 skill 据版本重投影/再验证。
**验收**：一个组件缺口能被记录、被维护者消费、补齐后清单版本 +1。

### R4 · 实时更新机制定调 ★需拍板
**现状（AIDA `04` §5.1 已知矛盾）**：实时更新有三种说法——现代码推**完整 `sdui_doc`**（`{"event":"sdui"}`）/ 数据中心 README 说 **state.json 增量** / Claw 对比画板说 **node patch ops**。
**要求**：维护者**定一个**并文档化。
**建议**：投影器契约只管 `state → 完整树`（纯函数、最简、可生成可测）；增量/patch 作为渲染器/SSE 层**内部优化**，**不进投影器契约**。
**验收**：投影器输入输出契约确定且稳定，编译器据此生成、测试据此取证。

## 3. 与其他模块的接缝

| 接缝 | 对端 | 说明 |
|---|---|---|
| 据清单生成投影器 / 校验 / 报缺口 | 编译器（我方） | R1/R2/R3 |
| 投影器过 `lint_sdui_contract` 作为注入前验收 | AIDA Agent | 测试底座 `01_AIDA-Agent模块需求.md` §R4 |
| sdui SSE 事件纳入证据、`sduiCompliance` 校验投影合规 | 测试底座 | 运行稳定性验证一项 |
| 组件库随镜像/前端 digest 钉死，清单版本随之 | CI 镜像 | `测试底座/04_CI镜像与DevOps模块需求.md` |

## 4. 落地状态参考

| 能力 | 现状 |
|---|---|
| SDUI 组件库（词汇表 + 渲染器 + projector_base） | ✅ 已实现、专人维护 |
| `lint_sdui_contract` 三方守门 | ✅ 已有 |
| 机器可读组件清单（供编译器） | ❌ 待导出（本文 R1） |
| 实时更新机制收敛 | ⚠️ 未定（本文 R4 / `04` §5.1） |
