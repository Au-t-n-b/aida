# assumptions.json Schema（已确认假设清单 · 草案 v0.1）

> 状态：Draft v0.1（2026-06-08）· **未冻结**
> 定位：语义真源的第二件物证。逐条记录每一次"模糊→确定"的决定 + 业务作者确认。与 `SKILL.md` 一起构成**交付契约**（见 `交付契约.md`）。
> 关联：前门设计 §8.2；`SkillIR-schema.md`（各元素以 `assumption_ref` 回指本清单的 `id`）；`校验规则集.md` R-K-08（可追溯）。

---

## 0. 顶层结构

```jsonc
{
  "schema_version": "0.1",
  "skill_name": "zhgk",                       // == SkillIR.meta.name
  "authored_at": "2026-06-08T10:00:00+08:00",
  "source_mode": "legacy_with_scripts",       // legacy | legacy_with_scripts | fresh（对应前门 S1 的 a/b/c）
  "doclib_version": "…",                       // S6 接地所基于的文档库版本（漂移时据此重校）
  "assumptions": [ /* 条目 */ ]
}
```

## 1. 每条假设的字段

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 稳定 ID（`A001`…），全 skill 唯一；SkillIR/Graph 元素以 `assumption_ref` 回指它 |
| `section` | enum | ✓ | 对应 Raw Skill 章节：`业务规则`/`流程步骤`/`工具能力需求`/`输入`/`输出`/`范围`/`LLM 使用点`/`HITL` |
| `kind` | enum | ✓ | 收紧类型（见 §2） |
| `question` | string | ✓ | 当时问作者的原始问题 |
| `options_presented` | string[] | 视情况 | 给的候选（消歧"propose 2–3 approaches"时必填） |
| `resolved_value` | string | ✓ | 最终定成什么 |
| `evidence` | object\|string | ✓ | 依据。结构化优先：`{ type: "script"\|"author"\|"doclib", ref: "risk.py:42", note: "…" }` |
| `confirmed_by` | string | ✓ | 谁确认（作者） |
| `confirmed_at` | string | 建议 | 确认时间戳 |
| `downstream` | enum? | | 回流去向：`doc_library_request` / `toolbox_self_impl` |
| `trace` | string[]? | | 本假设收紧的 SkillIR 元素 id（双向可追溯；与各元素的 `assumption_ref` 互为正反向） |

## 2. `kind` 取值（八类收紧动作）

| kind | 含义 | 典型来源阶段 |
|---|---|---|
| `threshold_pinned` | 阈值钉死（"高"=80%） | S6 |
| `branch_chosen` | 分支选定 | S4 |
| `step_kind` | 三分结论（规则/LLM/人工） | S5 |
| `capability_substituted` | 能力替代（复用 toolbox 已有工具） | S6 |
| `capability_self_impl` | 能力自实现（toolbox 没有 → 工作流自实现新工具）★新增，对齐工具解析模型 | S6/编译期 |
| `capability_gap` | 能力缺口（连自实现都不可能，需不存在的外部系统） | S6 |
| `ambiguity_resolved` | 一般消歧 | S6 |
| `scope_decision` | 范围/非目标取舍 | S3/范围讨论 |

> 与上一轮工具模型对齐：旧"缺工具即 `capability_gap`"已细分——默认是 `capability_self_impl`，`capability_gap` 仅留给真·不可实现。

## 3. 可追溯（双向）

- **正向**：SkillIR/Graph 元素带 `assumption_ref` → 指向本清单 `id`（如 `business_rules.rule_high_load.assumption_ref = "A001"`）。
- **反向**：本清单条目可选 `trace[]` 列出它治理的 IR 元素 id。
- 编译管线生成 Graph 时，凡涉及被收紧的点（阈值/分支/工具选择），都应能回溯到对应 `id`。
- 冻结后，`校验规则集.md` R-K-08 由 `warn` 升为 `error`（可追溯成硬约束）。

## 4. 示例

```jsonc
{
  "schema_version": "0.1", "skill_name": "zhgk", "source_mode": "legacy_with_scripts",
  "assumptions": [
    { "id": "A001", "section": "业务规则", "kind": "threshold_pinned",
      "question": "负载高的阈值是多少？", "options_presented": ["80%","85%","90%"], "resolved_value": "80%",
      "evidence": { "type": "script", "ref": "risk.py:42", "note": "load_rate>0.8；作者确认沿用" },
      "confirmed_by": "作者", "confirmed_at": "2026-06-08T10:12:00+08:00", "trace": ["business_rules.rule_high_load"] },
    { "id": "A002", "section": "流程步骤", "kind": "branch_chosen",
      "question": "无法判断场景时，走人工确认还是默认液冷？", "options_presented": ["人工确认","默认液冷"],
      "resolved_value": "人工确认", "evidence": { "type": "author", "note": "判断不了一定要人来定" },
      "confirmed_by": "作者", "trace": ["steps.scene_filter"] },
    { "id": "A003", "section": "工具能力需求", "kind": "capability_self_impl",
      "question": "需要解析自定义 BOQ 模板，toolbox 无现成工具", "resolved_value": "编译期自实现 boq_parse 工具",
      "evidence": { "type": "doclib", "note": "文档库查询 not_found" },
      "confirmed_by": "作者", "downstream": "toolbox_self_impl", "trace": ["tool_needs.parse_boq"] }
  ]
}
```

## 5. 待冻结项

- `evidence` 结构化字段集（`script`/`author`/`doclib` 各自子字段）。
- `trace` 引用语法与 SkillIR `ref` 语法统一。
- `id` 命名空间是否与 SkillIR 元素 id 共域（避免碰撞）。
