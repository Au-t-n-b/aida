# proposal table_gen_release 实施计划

> **For agentic workers:** 实现本计划时仅修改 `agent/skills/**`、`agent/tests/test_*langgraph*`、`docs/30_skill开发/proposal-langgraph-io.md`；**不修改** `agent/proposal/`、`frontend/`、上游 step 实现。  
> **SSOT：** `需求开发/05-数据目录与平台规范.md` v1.17 + `agent/skills/early_io/contracts.py`

**Goal:** 在不动 AIDA 其他业务模块、不改上游 step 的前提下，完成 `table_gen_release`（`解析结果` → HITL → `输出结果` promote）及 IPO 路径补齐，并产出本地交接文档供其他开发对接。

**Architecture:** LangGraph `proposal_gen` 最后一步 `table_gen_release` 作为规范定义的 **promote 层**：只读各上游 step 按 SSOT 写入的 `解析结果/`（及已存在的 `输出结果/` 片段），经 HITL 确认后，将 §4.2 逻辑表统一落盘为 `早期介入/交付预案/输出结果/*.xlsx`。不读写 REST 内部的 `解析结果/预案草稿/`。可 **import** `agent.proposal.chapter_excel.export_chapter_xlsx` 做 xlsx 序列化，但不改其源码。

**Tech Stack:** Python 3.10、LangGraph BaseSkill、openpyxl（经 chapter_excel）、pytest

---

## 文件结构（本计划涉及）

| 文件 | 职责 |
|------|------|
| `agent/skills/early_io/output_tables.py` | §4.2 输出表注册：逻辑表名、xlsx 文件名、解析来源目录、chapter 映射 |
| `agent/skills/early_io/promote.py` | 从 `解析结果/` 读 JSON → 写 `输出结果/*.xlsx` |
| `agent/skills/early_io/paths.py` | 扩展 `EarlyIoPaths`：全部 parse/out 子路径 |
| `agent/skills/proposal_gen/steps/table_gen_release.py` | promote + HITL + resume 后执行 |
| `agent/skills/proposal_gen/skill.py` | `apply_resume_payload` / `build_resume_init_state` |
| `agent/tests/test_table_gen_promote.py` | promote 层单测（tmp 目录） |
| `docs/30_skill开发/proposal-langgraph-io.md` | 修正「预案草稿」表述，对齐 SSOT |
| `docs/30_skill开发/proposal-langgraph-交接.local.md` | **本地交接文档（不提交 git）** |

---

## Phase 0：文档与契约对齐

### Task 0.1：修正设计文档

**Files:**
- Modify: `docs/30_skill开发/proposal-langgraph-io.md`

- [ ] 删除/替换「`解析结果/预案草稿/2.设备配置信息.json`」表述
- [ ] `assemble_device_table` 输出改为 `输出结果/设备信息表.xlsx`（与 `contracts.py` 一致）
- [ ] 补充 `table_gen_release` 数据流：`解析结果/*` → HITL → `输出结果/*`
- [ ] 增加「上游对接」章节指针 → 交接文档

### Task 0.2：扩展 `contracts.py` 中 table_gen_release 说明

**Files:**
- Modify: `agent/skills/early_io/contracts.py`

- [ ] 为 `table_gen_release` 增加 `description` 细化：读取哪些 parse 目录、写出哪些 out xlsx（引用 `output_tables.py`）

---

## Phase 1：IPO 路径与输出表注册

### Task 1.1：新建 `output_tables.py`

**Files:**
- Create: `agent/skills/early_io/output_tables.py`

- [ ] 定义 `OutputTableSpec` dataclass：
  - `logical_name`：如「设备信息表」
  - `xlsx_name`：如 `设备信息表.xlsx`
  - `parse_dirs`：可读的 `解析结果` 子目录列表（相对 `交付预案/解析结果`）
  - `parse_glob`：如 `*.json`
  - `chapter_key`：对接 `chapter_registry` 的 key（用于 `export_chapter_xlsx`）
  - `rows_envelope`：`rows` | `cases` | `items`（解析 JSON 的外壳约定，**由上游保证**）
- [ ] 导出 `PROPOSAL_OUTPUT_TABLES: tuple[OutputTableSpec, ...]`，覆盖 §4.2 目录树 252–268 行全部表：

| xlsx | parse 来源（优先顺序） | 备注 |
|------|------------------------|------|
| 预案版本信息表.xlsx | — | release 时写 metadata |
| 项目背景信息表.xlsx | HLD解析结果/ | 上游 HLD step |
| 设备信息表.xlsx | — | **上游** `assemble_device_table` 直写 `输出结果`；promote 仅 pass-through |
| 智算部件配置信息表.xlsx | TBD 解析目录 | 上游 |
| 软件配置信息表.xlsx | TBD | 上游 |
| 共平面类型表.xlsx | TBD | 上游 |
| 网络平面配置信息表.xlsx | TBD | 上游 |
| 网管服务器配置表.xlsx | TBD | 上游 |
| 集群设备清单表.xlsx | TBD | 上游 |
| 预集成预验证需求信息表.xlsx | TBD | 上游 |
| 服务配置表.xlsx | 合同/服务BOQ 或 解析中间物 | 上游 assemble |
| 服务内容表.xlsx | 同上 | 上游 |
| 维保策略表.xlsx | 合同/服务BOQ | 上游 |
| 维保SLA表.xlsx | 维保建议书解析结果/ | 上游 |
| 项目责任矩阵.xlsx | TBD | 上游 |
| 验收策略.xlsx | 验收策略解析结果/、服务建议书解析结果/ | 上游 parse_tech |
| 测试用例.xlsx | 测试用例解析结果/ | 上游 parse_testcases |

- [ ] 对尚无上游的表：`promote` 时若 parse 空且 out 不存在 → 写**仅表头** xlsx（调用 chapter 模板）

### Task 1.2：扩展 `paths.py`

**Files:**
- Modify: `agent/skills/early_io/paths.py`

- [ ] `EarlyIoPaths` 增加：
  - `proposal_parse_root`
  - `proposal_output_root`
  - `proposal_acceptance_parse`（验收策略解析结果）
  - `proposal_tech_proposal_parse`（技术建议书解析结果 — 若与现有字段区分）
  - `proposal_hld_parse`
  - `proposal_maint_proposal_parse`（维保建议书解析结果）
  - `proposal_output_table(name)` 辅助方法
- [ ] 保持与 `proposal_paths()` / §05 目录树一致

### Task 1.3：单测 — 路径与表注册

**Files:**
- Create: `agent/tests/test_table_gen_promote.py`（部分）

- [ ] `test_output_tables_cover_spec()`：17 张表名称与 §4.2 一致
- [ ] `test_early_io_paths_resolve()`：parse/out 路径拼接正确

---

## Phase 2：Promote 层实现

### Task 2.1：新建 `promote.py`

**Files:**
- Create: `agent/skills/early_io/promote.py`

- [ ] `load_parse_rows(path: Path, envelope: str) -> list[dict]`：读 JSON；支持 `{"rows":[]}`、裸数组、`{"cases":[]}`（只读，不修正上游格式错误，失败时返回明确 error）
- [ ] `promote_table(io: EarlyIoPaths, spec: OutputTableSpec, *, proposal_version: str = "草稿") -> PromoteResult`：
  - 若 `输出结果/{xlsx}` 已存在且上游标记 pass-through → 跳过
  - 否则扫描 `parse_dirs` 下最新 `*.json`
  - 调 `export_chapter_xlsx(out_path, chapter_spec, {"rows": rows, "proposalVersion": ...})`
- [ ] `promote_all_tables(io, *, mode: "draft"|"release", proposal_version: str) -> list[PromoteResult]`
- [ ] **不**调用 `draft_store` / `save_chapter_*_draft`

### Task 2.2：单测 — promote

**Files:**
- Modify: `agent/tests/test_table_gen_promote.py`

- [ ] 用 `tmp_path` 构造最小 `解析结果/测试用例解析结果/foo.json` + `{"cases":[...]}` → 断言生成 `输出结果/测试用例.xlsx`
- [ ] 空 parse → 表头-only xlsx
- [ ] 已存在 out xlsx + pass-through spec → 不覆盖

---

## Phase 3：`table_gen_release` Step

### Task 3.1：实现 `table_gen_release.py`

**Files:**
- Modify: `agent/skills/proposal_gen/steps/table_gen_release.py`

- [ ] `check_inputs`：检查 `proposal_output_root` 可写；列出缺失的 parse 目录（**warning 不 fail**，除 project_id 缺失）
- [ ] `run` 第一阶段（自动）：
  - `emit` 逐表 promote 进度
  - 调 `promote_all_tables(..., mode="draft")`
  - 汇总 `artifacts` / `files` / `metrics`（写了哪些 xlsx、跳过了哪些）
  - 返回 HITL：`save_draft` | `release`
- [ ] **不在此步**调 `release_and_decide`（属 REST 内部；规范侧 release 写版本号进 `预案版本信息表.xlsx` + manifest 记录 — 见 Task 3.3）

### Task 3.2：`ProposalGenSkill` resume

**Files:**
- Modify: `agent/skills/proposal_gen/skill.py`

- [ ] `apply_resume_payload`：
  - `hitl_step == "table_gen_release"` 且 `choice == "save_draft"` → `project["release_confirm"] = "save_draft"`
  - `choice == "release"` → `project["release_confirm"] = "release"`
- [ ] `build_resume_init_state`：`route_to` 仍为 `table_gen_release`（二次进入执行 release 分支）
- [ ] `table_gen_release.run` 检测 `project.get("release_confirm")`：
  - `save_draft`：已完成 promote，清 HITL，step completed
  - `release`：写 `预案版本信息表` 记录（本地 JSON records + xlsx，可 import `version_info_store` **只读调用**）；`proposal_version` 生成 `V{x.y}_{ts}` 简化规则；**不**调 `release_and_decide`

### Task 3.3：版本信息落盘（规范侧，非 REST）

**Files:**
- Modify: `agent/skills/early_io/promote.py` 或 `proposal_gen/release_meta.py`（新建小模块）

- [ ] `append_version_record(project_id, operator, change_description)` → 写 `输出结果/预案版本信息表.records.json` 并 sync xlsx（import `version_info_store.sync_xlsx` 若可用；否则最小实现）
- [ ] 字段对齐 §4.2.2：项目ID、预案版本号、创建人、修改人、修改描述等

---

## Phase 4：测试与验证

### Task 4.1：集成测试（Skill 图）

**Files:**
- Modify: `agent/tests/test_proposal_langgraph_io.py`

- [ ] `table_gen_release` step 可 import；mock `promote_all_tables` 验证 HITL 结构

### Task 4.2：手工验证清单

- [ ] 环境：`UNIEX_BENCH_ROOT`、`AIDA_BUSINESS_ROOT`
- [ ] 项目：`70e5ca737ae5433e9f0f3134d216acf7`（磁盘 UUID；manifest 内 business id 为 `56A0TXN`）
- [ ] 在 `解析结果/测试用例解析结果/` 放置合规 JSON（上游格式）
- [ ] `POST /agent/proposal_gen/run` + resume HITL
- [ ] 检查 `输出结果/*.xlsx` 新增/更新

### Task 4.3：`contract_boq` 回归

- [ ] 对含 BOQ xlsx 的项目跑 `contract_boq`；确认 `normalized.json` + 建模仿真 md

---

## Phase 5：交接文档（不提交 git）

### Task 5.1：撰写并维护交接文档

**Files:**
- Create: `docs/30_skill开发/proposal-langgraph-交接.local.md`
- Optional: 在 `.gitignore` 追加 `*.local.md` 或该文件路径

- [ ] 见交接文档模板（同目录已创建初版）
- [ ] 每完成一个 Phase 更新「实现状态」与「上游对接清单」勾选

---

## 明确不做（本计划范围外）

| 项 | 负责方 |
|----|--------|
| 修改 `assemble_device_table` 等上游 step | 上游开发 |
| 修改 `agent/proposal/router.py`、前端 | 交付预案产品组 |
| DOCX 全文导出 | 待 `export.py` 或独立 skill |
| `draft_store` / `预案草稿` 对齐 | 不纳入；REST 遗留 |
| 项目 ID `56A0TXN` ↔ UUID 映射 | 平台/配置中心 |
| DataCenter `upload_file` 全量迁移 | 后续 v0.3 |

---

## 建议执行顺序与时间

| 阶段 | 预估 | 产出 |
|------|------|------|
| Phase 0 | 0.5d | 文档一致 |
| Phase 1 | 1d | output_tables + paths |
| Phase 2 | 1.5d | promote.py + 单测 |
| Phase 3 | 1.5d | table_gen_release + resume |
| Phase 4 | 1d | 测试 + 手工验证 |
| Phase 5 | 0.5d | 交接文档定稿 |

**合计约 6 人日**（单人串行）。

---

## 完成定义（Definition of Done）

- [ ] `table_gen_release` 非 stub：能 promote 至少「测试用例」「验收策略」两表（给定合规 parse JSON）
- [ ] HITL save_draft / release 可 resume 完成
- [ ] release 写入 `预案版本信息表` 记录
- [ ] 单测全绿；不修改 `agent/proposal` 源码
- [ ] 交接文档反映最终实现与上游待办清单
