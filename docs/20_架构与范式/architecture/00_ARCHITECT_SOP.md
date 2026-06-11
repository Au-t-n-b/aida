# 架构师 SOP（Chief Architect）

> **角色**：守两张地图（[01 系统架构](01_system_architecture.md) + [02 模块边界](02_module_boundaries.md)），把需求拆成有护栏的 TASK，用 lint 守一致性。
> **铁律**：架构师**不写业务 step 代码**——只维护地图、生成 TASK、审 RFC、跑审查。业务实现是开发者的事（[00_DEVELOPER_SOP](00_DEVELOPER_SOP.md)）。
> **四条工作流**：A 需求→TASK · B 一致性审查 · C 基线重置 · RFC 审批。

---

## 工作流路由（什么时候跑哪条）

```
首次部署 / 文档严重脱节 ──────────────► C 基线重置（以代码为准刷新两张地图）
收到新需求 ────────────────────────► A 需求分析（拆出 TASK_<名>.md）
开发者提 PR / 里程碑检查 ─────────────► B 一致性审查（跑 lint + 语义抽查）
开发者提交 RFC（缺跨模块接口）────────► RFC 审批（更新边界图 / 派底座改动 + ADR）
```

---

## Workflow A · 需求分析（需求 → TASK）

**输入**：一句需求（如「新增交付编排模块」）。**输出**：`tasks/TASK_<需求简写>.md`。

1. **影响速查** —— 对照 [02 §1/§4/§5](02_module_boundaries.md)，回答四问：
   - 涉及哪些模块 / 哪几层？是**新模块**还是改既有模块？
   - 是否动到 **§4 高冲突文件**（注册表 / `module.tsx` / `modules-data.ts`）？→ 必然动（加模块都要）→ 在 TASK 里写**行级范围**。
   - 是否需要碰 **§5 红线区**（`main.py`/`graph.py`/`base.py`/前端通用件）？→ 若是，**先停**，走 RFC 评估，别塞进普通 TASK。
   - 是否需要一个现有模块没有的**底座能力 / 跨模块接口**？→ 标记为 RFC 前置依赖。
2. **更新地图（如需要）** —— 新模块在 [02 §1 模块清单](02_module_boundaries.md) 加一行（id / 形态 / 前端 key / 状态=待建）；新依赖规则进 §3。
3. **WBS 拆解** —— 把需求拆成**子任务**，每个子任务**只动一个模块的文件集**；高冲突文件的改动单列、给行级范围。
4. **写验收（AC）** —— 必须**客观可验**：lint 全绿 + eval 阈值 + 端到端 run 到 `done`。禁止「质量好」这类不可测表述。

### TASK 模板（复制到 `tasks/TASK_<名>.md`）

```markdown
# TASK_<需求简写>  ·  <一句话目标>
> 架构师：<名>　日期：<YYYY-MM-DD>　关联地图：02 §1 已登记 <id>

## 0. 影响速查
- 模块：<新建 `<id>` / 改 `<id>`>　层：执行层（Claw/Agent）
- 高冲突文件：是（§4 三处，行级范围见 3.x）
- 红线区：否（如需碰 → 转 RFC，不在本 TASK）
- RFC 前置：<无 / RFC_<日期>_<接口>>

## 1. 子任务（WBS）
| # | 子任务 | 修改范围（NEW / MODIFY:行） | 依赖 |
|---|--------|---------------------------|------|
| 3.1 | 脚手架 | NEW `agent/skills/<id>/**` | — |
| 3.2 | 业务 steps | NEW `agent/skills/<id>/steps/*.py` | 3.1 |
| 3.3 | SDUI 投影 | NEW `agent/skills/<id>/sdui.py` | 3.2 |
| 3.4 | A 层契约 | NEW `skills/<id>/SKILL.md` ＋ `~/.claude/skills/<id>/SKILL.md` | 3.2 |
| 3.5 | 注册接线 | MODIFY `agent/skills/__init__.py`（+2 行）· `frontend/src/routes/module.tsx`（+1）· `frontend/src/data/modules-data.ts`（+1 条）【高冲突·架构师合并】 | 3.1 |
| 3.6 | 评测 | NEW `agent/evals/eval_<id>.py` + `fixtures/<id>-golden.json` | 3.2 |

## 2. 红线（零改 · 见 02 §5）
agent/main.py · graph.py · base.py · 前端 SkillAgentScreen/useSduiStream/SduiNodeView

## 3. 验收（AC · 客观可验）
- [ ] 6 lint + `lint_module_boundaries` 全绿
- [ ] `lint_skill_contract`：SKILL.md 节点 ↔ step.key 逐一一致
- [ ] `curl /agent/skills` 见 `<id>`；`POST /agent/<id>/start` 跑到 `done`
- [ ] `eval_<id>` 阈值通过（如 completion_rate ≥ 0.5）
- [ ] `git diff --name-only` ⊆ 本 TASK 修改范围；高冲突文件仅在分配行内改动
```

---

## Workflow B · 一致性审查（= 跑守门，不写 prompt）

> **AIDA 的审查是可执行的，不是对话式的。** vibe-template 的「AI 扫代码出审查报告」在 AIDA 里**降级为辅助**——主审查是 lint，lint 覆盖不到的语义才人工抽查。

**① 跑全套守门**（全绿是通过的必要条件）：

```bash
cd D:/aida
agent/.venv/Scripts/python agent/scripts/lint_no_naked_llm.py        # 禁裸 LLM
agent/.venv/Scripts/python agent/scripts/lint_no_naked_send.py       # 禁裸外发
agent/.venv/Scripts/python agent/scripts/lint_skill_contract.py      # SKILL.md ↔ step.key
agent/.venv/Scripts/python agent/scripts/lint_tools.py               # 工具 name/desc/schema
agent/.venv/Scripts/python agent/scripts/lint_sdui_contract.py       # SDUI 三方一致
agent/.venv/Scripts/python agent/scripts/lint_runtime_contract.py    # 运行时契约 ≡ 代码
agent/.venv/Scripts/python agent/scripts/lint_module_boundaries.py   # 跨 skill 隔离 + 注册表↔边界图
agent/.venv/Scripts/python agent/evals/eval_zhgk.py --fixture        # 评测回归（离线）
```

**② lint 盖不到的语义抽查**（人工 / AI 辅助）：

| 检查 | 怎么看 | 对应红 |
|------|--------|--------|
| `check_inputs` 声明的必填路径 == `run` 真正读的路径 | 读该 step 两处路径 | HITL 清单漂移 |
| SKILL.md 触发词质量（召回率） | 触发词是否覆盖真实说法 | 召回不到 |
| `git diff --name-only` ⊆ TASK 修改范围 | 比对 diff 与 TASK §1 | 越界 |
| 高冲突文件只在分配行改动 | 看 §4 三文件的 diff | 并行冲突 |
| 新模块未横向 import 其它模块 | `lint_module_boundaries` 已覆盖 | 横向耦合 |

**③ 出结论**：`✅ 完全合规`（合并）/ `⚠️ 存在漂移`（登记 02 §8 + 限期修）/ `❌ 存在违规`（打回，附违规条目）。

---

## Workflow C · 架构基线重置（以代码为准刷新地图）

**触发**：首次部署 / 地图与代码严重脱节 / 大重构后。**方向**：**代码 → 文档**（与 A/B 相反）。

1. **扫注册表**：`agent/skills/__init__.py` 的 `registry.register(...)` → 得到当前模块 id 全集。
2. **扫每模块**：各 `skills/<id>/SKILL.md` 的「后端节点」+ `agent/skills/<id>/steps/` → 核对 step 数 / 形态 / 入口。
3. **刷新 [02 §1/§2](02_module_boundaries.md)**：模块清单、公共接口对齐代码现状。
4. **扫漂移**：前端 `MODULE_TO_SKILL` ↔ `MODULE_SCHEMAS` 键、注册表 ↔ 边界图 → 不一致登记 [02 §8](02_module_boundaries.md)。
5. **刷新 [01 活层](01_system_architecture.md)**：已注册模块快照。
6. **验证**：跑 Workflow B 全套 lint，确保刷新后文档 ≡ 代码。

---

## RFC 审批（开发者申请跨模块接口 / 底座能力）

**触发**：收到 `rfc/RFC_<日期>_<接口>.md`（开发者在 D2 阻碍时生成）。

1. **评估**：申请的接口/能力是否符合 [02 §3 依赖规则](02_module_boundaries.md)？是否该放进通用底座（高频）还是模块内（一次性）？
2. **决策**：批准 / 驳回 / 改方案。批准 → ② 更新 [02 边界图](02_module_boundaries.md)（新接口 / 新底座能力）；③ 若改了 §5 红线底座，**必写一条 [`decisions/`](../../90_决策ADR/README.md) ADR**（背景/选项/决策/后果）——这是 [范式 §2 定制回流](../03_团队Agent开发范式.md) 的落地。
3. **通知**：接口已批准 → 开发者把 Mock 换成真实调用。

> **RFC ↔ ADR**：RFC 是**开工前的阻塞申请**（前向、未决）；ADR 是**已决定的记录**（事后、入库）。RFC 批准并改了底座 → 产出一条 ADR。

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-07 | 初版：A/B/C + RFC，Workflow B 焊到 7 个 lint + eval |
