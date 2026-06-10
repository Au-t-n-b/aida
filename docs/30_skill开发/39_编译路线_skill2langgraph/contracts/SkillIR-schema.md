# SkillIR Schema（执行真源 · 草案 v0.3）

> 状态：Draft v0.3（2026-06-09）· **未冻结**
> v0.2→v0.3（device_install_mini walking skeleton 实跑回填）：①`state` 字段增 `binding`（channel/runtime_file）——SkillState 内置 channel 固定，自定义跨步态必须落盘(R1)；②`llm_points` 不得作统计真源(R2)。
> v0.1→v0.2（device_install 压测回填 G1–G8）：补 `error_handling` 字段表(G1)；HITL 增 `form_submit` 类型+`writes`+`cancel_to`(G2/G3)；step 增 `branches`(G4)；`state` 允许自定义分组(G5)；output 增 `cardinality`/`name_template`(G6)；`tool_needs.self_impl` 内联新工具契约(G7)；`meta.requires_llm`(G8)。
> 定位：Raw Skill 的**结构化执行表示**。会话 A 产出它；会话 C（Graph）、D（契约测试）以它为输入。是范式的"执行真源"。
> 关联：目标产物规格 `../可编译业务Skill编写规范.md`（§22 十五节、§21 检查清单）；运行时契约 `docs/30_skill开发/31_手写规范/AIDA-RUNTIME-CONTRACT.md`；校验规则 `校验规则集.md`（对本 schema 跑完整性+一致性）。
> 设计原则：① 一切用**稳定字符串 ID** 互相引用（这是一致性校验和可追溯的前提）；② 每处"被收紧的点"带 `assumption_ref` 回指 `assumptions.json`；③ 字段语义对齐 AIDA 运行时（SkillState / 软中断 HITL / allowed_tools / reducer）。

---

## 0. 顶层结构

```jsonc
{
  "schema_version": "0.1",
  "meta": { ... },              // 基本信息（§22.1）
  "scope": { ... },             // 适用范围/非目标（§22.3）
  "inputs": [ ... ],            // 输入（§22.4）
  "outputs": [ ... ],           // 输出（§22.5）
  "state": { ... },             // 状态字段（§22.11，对齐 SkillState）
  "steps": [ ... ],             // 流程步骤（§22.6）★核心
  "business_rules": [ ... ],    // 业务规则（§22.7）
  "tool_needs": [ ... ],        // 工具能力需求（§22.9）
  "llm_points": [ ... ],        // LLM 使用点（§22.10）
  "hitl": [ ... ],              // 人工观察者/HITL（§22.8）
  "error_handling": [ ... ],    // 错误/重试/警告（§22.12）
  "success_criteria": [ ... ],  // 成功标准（§22.13）
  "test_scenarios": [ ... ],    // 测试场景（§22.14）
  "sdui": { ... },              // 呈现投影提示（可选；多数自动）
  "provenance": { ... }         // 来源与可追溯
}
```

---

## 1. `meta`（基本信息）

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `name` | string | ✓ | 稳定 ID（小写英文/拼音下划线），全局唯一；用于 graph/run/report/注册 |
| `title` | string | ✓ | 中文展示名 |
| `version` | string | ✓ | 业务流程版本 |
| `owner` | string | ✓ | 负责人/团队 |
| `domain` | string | ✓ | 业务领域 |
| `description` | string | ✓ | 一句话目的 |
| `requires_llm` | bool | ✓ | 本 skill 是否用 LLM；**纯规则 skill 显式置 `false`**（避免下游把 `llm_points:[]` 误判为漏填）(G8) |

## 2. `scope`

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `in_scope` | string[] | ✓ | 适用范围 |
| `non_goals` | string[] | ✓ | 非目标（`scope_decision` 类假设常落在此） |

## 3. `inputs[]`（输入）

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 稳定 ID，如 `boq_file` |
| `name` | string | ✓ | 展示名 |
| `required` | bool | ✓ | 是否必需 |
| `source` | string | ✓ | 业务对象（`object_id`，如 `project_asset`）/ `user_upload` / `prev_step` |
| `format` | string | ✓ | 如 `.xlsx` / `json` |
| `on_missing` | enum | ✓ | `hitl_supply` / `fail` / `warn` |
| `assumption_ref` | string? | | 关联假设 ID |

## 4. `outputs[]`（输出）

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 稳定 ID，如 `report_docx` |
| `name` / `type` / `owner` / `purpose` | string | ✓ | 展示名 / 类型 / 归属 / 用途 |
| `success_ref` | string[] | ✓ | 关联的 `success_criteria.id`（输出必须可验证） |
| `on_fail` | enum | ✓ | `fail` / `warn`（失败但流程可继续时） |
| `cardinality` | enum | ✓ | `single` / `list`（N 张同构产物，如按机房×设备大类的 SN 表）(G6) |
| `name_template` | string? | | `cardinality=list` 时的命名模板，如 `SN扫码表_{机房}_{设备大类}.xlsx`(G6) |

## 5. `state`（状态字段，对齐 SkillState）

声明跨 step 需保存的字段。对齐契约 §3 `SkillState`（`steps`/`logs` 走 reducer 累加由运行时保证；此处声明业务态）。

```jsonc
"state": {
  "project":      { "project_id": "string", "project_name": "string" },
  "inputs":       { "boq_file": "file", "presets": "file" },
  "intermediate": { "scene_type": "string", "risks": "list", "survey_summary": "object" },
  "outputs":      { "report_docx": "file", "risk_table": "file" },
  "hitl":         { "step": "string", "reason": "string" }
}
```
> 约束：被任何 `step.reads`/`step.writes`/`hitl.writes` 引用的字段，必须在此声明（见规则 R-K-03）。
> **分组开放（G5）**：`state` 顶层分组名**不固定**——可用 `project/inputs/intermediate/outputs/hitl`，也可按真身自定义（如 device_install 的 `session`/`tasks_state`）。校验只要求"语义覆盖"（项目/输入/中间/输出/hitl 概念各有归属），不要求组名精确匹配（见规则 R-C-10 v0.2）。

### 5.1 `binding`：通道 vs 落盘（v0.3 · walking skeleton 实跑发现 R1）★

**关键真相**：AIDA 运行时 `StateGraph(SkillState)` 只为 `SkillState` 声明的**固定内置 channel** 建通道——`run_id/skill_id/project/steps/logs/current_step/overall_progress/files/hitl/hitl_resume/metrics/error`。**node 返回 diff 里任何"自定义顶层键"会被 LangGraph 静默丢弃。** 所以 SkillIR 声明的跨步中间态（如 `intermediate.install_tasks`）**不能直接当 state channel 用**。

每个 state 字段须标 `binding`：

| `binding` | 含义 | 落点 |
|---|---|---|
| `channel` | SkillState 内置 channel | 直接走 state（仅限上面那批固定键，如 `files`/`metrics`/`hitl`/`error`） |
| `runtime_file` | 自定义跨步中间态 | **落 `ProjectData/RunTime/<name>.json`，下游读回**（device_install_mini 的 install_tasks/plan_summary 即此） |
| `read_model` | 供 SDUI 投影的只读派生 | 发布到 `metrics` channel（声明内）供 `project(state)` 读 |

```jsonc
"state": {
  "intermediate": {
    "install_tasks": { "type": "list", "binding": "runtime_file" },
    "plan_summary":  { "type": "object", "binding": "runtime_file" }
  },
  "outputs": { "summary_docx": { "type": "file", "binding": "channel" } }   // 经 files channel
}
```
> 校验：自定义跨步态若标 `channel` 而非内置键 → R-A-06 报错（运行时会丢）。

## 6. `steps[]`（流程步骤）★核心

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 稳定 ID（小写下划线），如 `scene_filter` |
| `name` | string | ✓ | 展示名 |
| `goal` | string | ✓ | 单一业务动作 |
| `depends_on` | string[] | ✓ | 上游 step id（构成 DAG；可空=入口） |
| `reads` | ref[] | ✓ | 读取的 `input.id` 或上游 `step.id.outputs` 或 `state` 字段（**符号引用，非自由文本**） |
| `writes` | ref[] | ✓ | 写入的 `state` 字段 / `output.id` |
| `kind` | enum | ✓ | `rule` / `llm` / `hitl`（S5 三分结论） |
| `guard` | object? | | 进入前置校验（→ 运行时 `check_inputs`）：`{ requires: ref[], on_fail: "hitl_supply"\|"fail" }` |
| `on_fail` | enum | ✓ | `retry` / `fail` / `warn`（失败处理） |
| `retry_scope` | string? | | `on_fail=retry` 时必填：重试范围 |
| `llm_ref` | string? | | `kind=llm` 时指向 `llm_points.id` |
| `hitl_ref` | string? | | `kind=hitl` 时指向 `hitl.id` |
| `branches` | object[]? | | **运行期路由（G4）**：`[{ when: <条件,引用 input/state>, goto: <step.id 或 "skip"> }]`；二选一分支用此显式表达，不塞进 `goal` |
| `assumption_ref` | string? | | 关联假设（分支/三分等） |

> 顺序：默认按 `depends_on` 拓扑序。**分支两种表达**：① 条件进入（缺料）用 `guard`；② 运行期二选一路由（如"两表已传→确认 vs 补传"、"无位置表→跳过 SN"）用 `branches[]`，条件引用真实 input/state。

## 7. `business_rules[]`

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 如 `rule_high_load` |
| `statement` | string | ✓ | "配电负载率 > 80% → 风险等级高" |
| `quantified` | bool | ✓ | 能量化的必须量化（false 时须 `kind≠rule`） |
| `applies_to` | string | ✓ | 关联 `step.id` |
| `kind` | enum | ✓ | `rule` / `llm` / `hitl` |
| `assumption_ref` | string? | | 阈值/分支多由此来 |

## 8. `tool_needs[]`（工具能力需求）

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 如 `read_boq` |
| `capability` | string | ✓ | 业务能力词，如 "读取 Excel"（**不强行写工具名**） |
| `resolution` | enum | ✓ | `reuse`（复用 toolbox 已有）/ `self_impl`（自实现新工具）/ `gap`（连自实现都不可能） |
| `tool_id` | string? | | `reuse` 时解析到的工具 ID（取值域见 toolbox/§2.4） |
| `assumption_ref` | string? | | `capability_substituted`/`capability_gap` 假设 |
| `downstream` | string? | | `gap` 时回流去向（`doc_library_request`）/ `self_impl` 时（`toolbox_self_impl`） |
| `self_impl_contract` | object? | | **`resolution=self_impl` 时必填（G7）**：内联新工具契约 `{ name, params(JSON Schema), execute_desc }`，供会话 C 落地、过 `lint_tools`、通过后注册回 toolbox |

## 9. `llm_points[]`

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 关联 `step.llm_ref` |
| `purpose` | string | ✓ | 用途 |
| `output_schema` | object | ✓ | **必须声明输出结构**（结构化在适配器层实现，见契约 §1.3） |
| `requires_rationale` | bool | ✓ | 高风险判断必须 `true`（要求给依据） |
| `not_authoritative_for` | string[]? | | **不得作真源的量（v0.3·R2）**：计数/统计/可验证事实。LLM 自由文本只可复述，统计真源必须由 rule 步骤派生。device_install_mini 实跑教训：LLM 摘要写"40 任务"，规则实为 29——见 R-K-09 |

## 10. `hitl[]`（软中断）

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 关联 `step.hitl_ref` |
| `type` | enum | ✓ | `file_supply` / `business_confirm` / `form_submit` / `failure_recovery` / `warning_ack`（`form_submit`=嵌入式编辑器提交结构化表格，G2） |
| `trigger` | object | ✓ | 触发条件，引用真实 `input.id`/`step.id`（见 R-K-04） |
| `need_files` / `need_inputs` | string[] | | 缺什么 |
| `writes` | ref[] | ✓(form_submit) | **提交 payload 落到的 state 字段（G2）**；使"编辑器返回值"成为可被下游 `reads` 的合法产出（修 R-K-01）。可附 `payload_schema` |
| `resume_mode` | enum | ✓ | `full_restart`（默认）/ `step_retry` |
| `cancel_to` | string? | | **取消时定向回跳的 `step.id`（G3）**，区别于整体重启/本步重试（如 SN 取消→回实施计划编辑） |

> 运行时表达：写 `state["hitl"]` → router 到 END → resume（**非** `interrupt()`，契约 §4）。`form_submit` 的 `writes` 在 resume 时由 `apply_resume_payload` 并入 state。

## 10b. `error_handling[]`（错误/重试/警告 · G1 补字段表）

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 如 `eh_esn_invalid` |
| `scope` | string | ✓ | 作用域：`step.id` 或 `*工具类*` |
| `condition` | string | ✓ | 触发条件（"存在空 ESN 或重复 ESN"） |
| `action` | enum | ✓ | `retry` / `fail` / `warn`（与 `step.on_fail` 取值域一致） |
| `message` | string | ✓ | 给观察者/agent 的提示 |
| `retry_scope` | string? | | `action=retry` 时必填 |
| `assumption_ref` | string? | | 关联假设 |

> 覆盖要求（R-C-11）：至少覆盖"必需输入缺失 / 可选缺失 / LLM 或工具失败"。

## 11. `success_criteria[]`

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 如 `sc_report_exists` |
| `statement` | string | ✓ | 不得只写"结果正确" |
| `maps_to` | ref | ✓ | 落到可验证目标：`output.id` / `state` 字段 / `step.id` 状态（见 R-K-02） |

## 12. `test_scenarios[]`

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | |
| `kind` | enum | ✓ | `happy` / `missing_input` / `business_branch` / `warning` / `hitl`（至少前四类，有 HITL 加第五） |
| `inputs` | object | ✓ | 场景输入 |
| `expected` | object | ✓ | 期望（关联 `success_criteria.id` / 期望 HITL 等） |

## 13. `sdui`（可选 · 呈现投影提示）

多数自动从 state 投影（复用固定组件库）。仅当作者有业务高度的呈现取舍时填：
```jsonc
"sdui": { "highlight_metrics": ["fill_pct","risk_hit"], "risk_table_from": "intermediate.risks" }
```

## 14. `provenance`（可追溯）

| 字段 | 说明 |
|---|---|
| `raw_skill_hash` | 来源 Raw Skill 的哈希 |
| `assumptions_ref` | `assumptions.json` 引用（条目通过各 `assumption_ref` 回指） |
| `doclib_version` | S6 接地所基于的文档库版本 |
| `build_agent` | 产出本 IR 的 BuildAgent（codex/claude/cursor） |
| `contract_schema_version` | 本 schema 版本 |

---

## 15. 精简示例（zhgk 片段）

```jsonc
{
  "schema_version": "0.1",
  "meta": { "name": "zhgk", "title": "智慧工勘", "version": "1.0", "owner": "交付业务组", "domain": "数据中心交付", "description": "据项目资料生成工勘评估报告并识别风险" },
  "scope": { "in_scope": ["数据中心智慧工勘场景"], "non_goals": ["不替代人工现场勘测"] },
  "inputs": [
    { "id": "boq_file", "name": "BOQ 文件", "required": true, "source": "project_asset", "format": ".xlsx", "on_missing": "hitl_supply" }
  ],
  "outputs": [
    { "id": "report_docx", "name": "工勘报告", "type": ".docx", "owner": "项目输出资产", "purpose": "提交评审", "success_ref": ["sc_report_exists"], "on_fail": "fail" }
  ],
  "state": { "intermediate": { "scene_type": "string", "risks": "list" }, "outputs": { "report_docx": "file" } },
  "steps": [
    { "id": "scene_filter", "name": "场景筛选", "goal": "判断工勘场景", "depends_on": [],
      "reads": ["boq_file"], "writes": ["intermediate.scene_type"], "kind": "llm",
      "guard": { "requires": ["boq_file"], "on_fail": "hitl_supply" },
      "on_fail": "retry", "retry_scope": "本步重跑", "llm_ref": "llm_scene", "assumption_ref": "A002" }
  ],
  "business_rules": [
    { "id": "rule_high_load", "statement": "配电负载率 > 80% → 风险等级高", "quantified": true, "applies_to": "report_gen", "kind": "rule", "assumption_ref": "A001" }
  ],
  "tool_needs": [
    { "id": "read_boq", "capability": "读取 Excel", "resolution": "reuse", "tool_id": "doc_read_xlsx" }
  ],
  "llm_points": [
    { "id": "llm_scene", "purpose": "判断工勘场景", "output_schema": { "scene_type": "string", "reason": "string" }, "requires_rationale": true }
  ],
  "hitl": [
    { "id": "hitl_boq", "type": "file_supply", "trigger": { "missing": ["boq_file"] }, "need_files": ["boq_file"], "resume_mode": "full_restart" }
  ],
  "success_criteria": [
    { "id": "sc_report_exists", "statement": "工勘报告文件存在且含风险章节", "maps_to": "report_docx" }
  ],
  "test_scenarios": [
    { "id": "ts_happy", "kind": "happy", "inputs": { "boq_file": "present" }, "expected": { "satisfies": ["sc_report_exists"] } },
    { "id": "ts_missing_boq", "kind": "missing_input", "inputs": { "boq_file": "absent" }, "expected": { "hitl": "hitl_boq" } }
  ],
  "provenance": { "raw_skill_hash": "…", "assumptions_ref": "assumptions.json", "doclib_version": "…", "build_agent": "claude", "contract_schema_version": "0.1" }
}
```

---

## 16. 待冻结项（与规则集/编译管线对齐后定）

- `ref` 引用语法的精确形式（`step.id.outputs` 点路径 vs 显式 `{step,field}`；含 `state` 自定义分组下的路径）。
- ~~`self_impl` 内联工具契约~~ → v0.2 已加 `self_impl_contract`（待与 `lint_tools` 字段对齐）。
- `branches[].when` 条件表达式语法（与 `guard.requires` 统一）。
- `hitl.writes.payload_schema` 与 `form_submit` 编辑器的对齐。
- `sdui` 提示与 SDUI 组件清单（维护者 R1）的字段对齐。
- 与 `assumptions.json` schema 的 `id` 命名空间统一。
