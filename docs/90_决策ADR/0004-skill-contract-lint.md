# 0004. SKILL.md ↔ steps 契约守门（lint_skill_contract）

- **状态**: Accepted
- **日期**: 2026-06-03
- **相关**: `agent/scripts/lint_skill_contract.py`；`agent/skills/base.py`（BaseStep.internal）；`agent/skills/zhgk/steps/preflight.py`；团队范式规范 0（守门）+ 规范 5（契约先行）；ADR [0003](0003-unified-outbound-layer.md) 同属守门族

## 背景（Context）

A+B 双层架构里，A 层 `SKILL.md` 用「后端节点」列声明业务步骤（如 `scene_filter` /
`survey_build` / `report_gen` / `report_distribute`），B 层 `agent/skills/<name>/` 用 Python
`steps` 实现。两者的对应关系**靠人工维护**——只有 frontmatter 的 description 会被
`load_skill_md` 单向同步，正文里的步骤映射没有任何机制保证与代码一致。

漂移场景：工程师在 Python 加/删/改 step 却忘了改 SKILL.md（或反之），文档与执行就对不上。
demo 现场被同事质疑「SKILL.md 是不是装饰、皮骨会不会分离」时，这是真实缺口。

## 考虑的选项（Options）

**A. 不守门，靠 code review 人工对齐**
- 优：零成本
- 劣：违背团队「规范 0：守门优先（违规即阻断）」；review 会漏；正是这次被质疑的点。

**B. 把契约结构化进 frontmatter（如 `steps: [...]` YAML）让 loader 直接读**
- 优：单一真相，无需解析正文表格
- 劣：改变 SKILL.md 格式；frontmatter 与 Claude Code 表层语义耦合；正文那张人读的 SOP 表仍可能漂移。

**C. lint 校验正文「后端节点」列 ↔ `skill.steps`（选定）**
- 优：复用现有 SKILL.md 约定（无格式变更）；双向 + 顺序校验；挂 prebuild 即阻断；纯函数核心易测。
- 劣：依赖正文表格有「节点」列；lint 需 import `agent.skills`（拉重依赖），缺 venv 时只能 SKIP。

## 决策（Decision）

选 C。`lint_skill_contract.py` 对每个注册 skill 校验：
1. SKILL.md 必须有含「节点」的表格列；
2. 文档节点 ⊆ 真实 `step.key`（文档→代码）；
3. 业务 `step.key` ⊆ 文档节点（代码→文档）；
4. 文档顺序 == 代码业务步骤顺序。

**基础设施步骤豁免**：`BaseStep.internal: bool = False`（底座新增字段），`PreflightStep.internal = True`。
`internal=True` 的步骤不要求出现在业务流程表中——`preflight` 是环境预检，不是业务 SOP 步骤。

挂 `package.json` prebuild：`lint:skill-contract`。

## 后果（Consequences）

- 正面：皮骨一致进守门，demo 可宣称「连 SKILL.md↔代码 的契约都有 lint 阻断」（呼应规范 0/5）。
- 正面：纯函数 `check_contract` / `parse_backend_nodes` 无 IO、无 agent import，可被 evals 直接单测。
- 负面：lint import `agent.skills` 会拉 openpyxl / langchain 等；**缺 venv 依赖时 SKIP 返回 0**（不阻断构建，但失去守门）。→ 建议 prebuild 用 `agent/.venv` 的 python 跑；后续可在 CI 固定 venv。
- 负面：解析依赖正文有「节点」列；新 skill 脚手架须含该表，否则报「缺『后端节点』列」。这是有意为之（强制契约表存在）。
- 后续 / 触发回流：若第 2 个 skill 出现「一个文档节点对应多个 step」或「子步骤（3-A/3-B）」需声明，再扩展解析为支持嵌套；届时更新本 ADR。
