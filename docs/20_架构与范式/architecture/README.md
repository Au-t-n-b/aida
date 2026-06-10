# 治理骨架 · docs/architecture/

> **这是 AIDA 团队 Vibe-Coding 的「治理回路」入口。** 区别于 [`30_skill开发/31_手写规范/`](../../30_skill开发/31_手写规范/README.md)（工程手册：一个 Skill 怎么做），本目录回答 **团队如何协同开发多个模块**：谁守地图、谁跑工作流、改动被约束在哪、一致性谁来强制。
>
> 定位：把 [vibe-coding-template](../../../) 的「地图驱动 + 护栏约束 + 对话生成」嫁接到 AIDA 既有的「六铁律 + lint 守门 + zhgk 样板」之上 —— **不照搬，按 AIDA 实际改造**（审查焊到 lint 而非 prompt，红线复用「零改白拿」，模块接口复用 SKILL.md）。

---

## 这一层有什么

| 文件 | 是什么 | 给谁 |
|------|--------|------|
| [01_system_architecture.md](01_system_architecture.md) | 系统架构**活层**：运行时四层 + 当前已注册模块快照（Workflow C 刷新） | 所有人 |
| [02_module_boundaries.md](02_module_boundaries.md) ⭐ | **模块边界图**：全模块公共接口 + 依赖规则 + **高冲突文件登记** + 零改白拿红线 | 架构师守、开发者读 |
| [03_doc_health_diagnosis.md](03_doc_health_diagnosis.md) | **文档健康诊断**：可用性/时效性体检 + gated/porous 根因 + 6 项整改路线（**时点快照**，非常青） | 架构师 / 文档维护者 |
| [00_ARCHITECT_SOP.md](00_ARCHITECT_SOP.md) | **架构师 SOP**：需求→TASK（A）/ 一致性审查（B，跑 lint）/ 基线重置（C）/ RFC 审批 | 架构师 |
| [00_DEVELOPER_SOP.md](00_DEVELOPER_SOP.md) | **开发者 SOP**：领 TASK 开发（D1）/ 阻碍 RFC（D2）/ pull 同步（D3）/ PR 自检（D4）+ 制止话术 | 开发者 |
| `tasks/TASK_<需求>.md` | 架构师按需生成的**实例化任务单**（WBS + 修改范围 + 红线 + 验收） | 开发者领取 |
| `rfc/RFC_<日期>_<接口>.md` | 开发者遇跨模块阻碍时的**接口申请**（批准后回流 [`decisions/`](../../90_决策ADR/README.md) ADR） | 架构师审批 |

> 这两张地图（01 + 02）是**唯一真相**：所有 TASK 的修改范围、红线、验收，都从地图推导；地图与代码由 `lint_module_boundaries.py` + 既有一组守门 lint（清单见 [AGENTS.md](../../../AGENTS.md)）强制对齐。

---

## 两条主路径

**🧭 架构师**（守地图 · 不写业务代码）
`02 边界图` → `00_ARCHITECT_SOP` → 收到需求跑 **A**（生成 TASK）→ PR 来时跑 **B**（lint 审查）→ 文档脱节时跑 **C**（基线重置）

**🤖 开发者**（护栏内生成）
领 `TASK_<需求>.md` → `00_DEVELOPER_SOP` → **D1** 标准起手式（@01 @02 @TASK）→ 缺接口走 **D2/RFC** → pull 后 **D3** → 完工 **D4** 自检（跑 lint + diff 范围核对）
> 单模块的工程做法（A+B 双层 / BaseStep / HITL / SDUI）仍以 [`30_skill开发/31_手写规范/`](../../30_skill开发/31_手写规范/README.md) 为准；本层只管「团队怎么协同、边界谁来守」。

---

## 与既有文档的关系

- **总入口**：[`docs/00_开发者地图.md`](../../00_开发者地图.md)（角色×任务路由，已链到本层）
- **铁律**：[`docs/03_团队Agent开发范式.md`](../03_团队Agent开发范式.md)（六铁律 + 守门元规范 —— 本层是它在「团队协同」维度的展开）
- **工程手册**：[`START_HERE.md`](../../10_快速开始/START_HERE.md) · [`AGENT_QUICKSTART.md`](../../10_快速开始/AGENT_QUICKSTART.md)（单模块怎么建）
- **红线**：[`AGENTS.md`](../../../AGENTS.md)（提交时 lint 守门）

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-07 | 初版：治理骨架（边界图 + 两份 SOP + 系统活层 + lint_module_boundaries） |
| v1.1 | 2026-06-08 | 加 [03 文档健康诊断](03_doc_health_diagnosis.md)（可用性/时效性体检 + 整改路线） |
