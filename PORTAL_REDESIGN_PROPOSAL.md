# 团队门户「模块开发者」门 · 重构方案（skill2langgraph 转换流水线 · 渐进式施工流）

> **状态**：提案 / 待审（v2 · 范式已确认为 **skill2langgraph 转换流水线**，非手搓 skill.py）。本文件只是方案，不改任何现有文件。
> **为什么放在仓库根**：`gen_docs_site.py` 用 `rglob("*.md")` 扫 `docs/` 全树，方案若放进 `docs/` 会让 `docs/site/index.html` 过期、`lint_docs_site` 变红。放根目录则三个派生守门都不扫，零副作用。
> **落地追踪**：本提案是 [ROADMAP](ROADMAP.md) 「文档治理 backlog · portal 对齐」一项的施工蓝本；范式模型已先行吸收进 [START_HERE §4](docs/10_快速开始/START_HERE.md)。
> **审定后的落地动作**：照本文 §7 重组 `docs/onboarding/portal.json` → `python agent/scripts/gen_team_portal.py` 重生成 → `python agent/scripts/lint_team_portal.py` 守门。**生成器零改**。落地完成后本文件可删除或归档。

---

## 1. 目标与设计原则

**一句话目标**：开发者把代码拉到本地后，门户引导他**逐层渐进**地让 coding agent 把一个业务场景**经 skill2langgraph 编译成可在 AIDA 上确定运行的 skill 模块（graph.py + sdui.py）并验证交付**——每一步喂给 agent 的上下文都裁到最小必要集。

**设计原则（5 条）**：

1. **转换范式，不是手搓**：开发者门引导的是「Raw Skill + 页面设计素材 →（coding agent 编译）→ graph + SDUI → 真实容器验证 → 注册」这条流水线，**不是**让人亲手写 `skill.py`/`steps/`。
2. **产出导向，不是理解导向**：每个里程碑的终点是一个**可客观验证的转换产物 + 闸门**（HARD-GATE / 守门 lint / Final Gate / digest），不是「能复述 / 能画图」。
3. **上下文预算分层**：每步只暴露当前必需的最小内容。长规范不再无条件整篇 `@`，改为「撞到某个问题，才读那一份的那一节」（§5 触发式深读映射）。
4. **角色接力**：业务专家（前门）产 Raw Skill；开发者 + coding agent（编译侧）接手编译与验证。里程碑在 M1→M2 之间有一道交接闸门（Session 0 契约复核）。
5. **以目标形态为北极星**：主线按 skill2langgraph 全自动最终形态写；当前未就位的环节（测试底座 / 数据中心测试租户）仅在里程碑里做**极简现状标注**，不打断主线。

---

## 2. 病灶速查（重构要解决的）

| # | 病灶 | 证据 |
|---|------|------|
| 1 | 旧门户把 skill2langgraph **当可选旁注移出主线** | 原第③步只让"了解两条路线"，转换流水线没成为开发主轴 |
| 2 | 步骤过载，"理解"与"动手"混编 | 开发者门 8 步，①②③④ 全是读/准备 |
| 3 | **上下文炸裂**——每步挂整篇长文档 | 原第⑥步一步 `@业务数据规范(636)+数据中心API(1553)=2189 行`；全门 `@` ≈ **4000+ 行** |
| 4 | 链接是"开网页给人看"而非"喂本地文件给 agent" | `read` 链接全部 `target=_blank` 指向 Gitea 渲染页 |
| 5 | 提示词"讲解型"、完成标志不可自动验证 | ①②③＝「讲清三件事」「带我读懂」；done＝「能复述」「能画出」 |

---

## 3. 范式：开发者门 = 一条「双支线汇流」的转换流水线

开发者门引导的不是写代码清单，而是一条流水线。**两个角色接力，两条支线汇流**：

```text
【业务专家 · 前门】
  引导编写 S1–S10 ──▶ Raw Skill = SKILL.md + assumptions.json
                                  │  过 HARD-GATE(S8) + 作者终审(S9)
                                  ▼
                        ┌─ Session 0 契约复核闸门（交接：业务专家 → 开发者）─┐
                                  ▼
【开发者 + coding agent · 编译侧】
   ┌──────────────── 业务逻辑支线 ────────────────┐   ┌────────── 页面设计支线（并行）──────────┐
   Raw Skill → SkillIR → graph.py + 行为/契约测试        设计素材(html/截图/代码) + 呈现规划
                                                          → coding agent 结合现有 SDUI 组件库
                                                          → sdui.py 投影器；缺组件→需求提示词→金涛
   └───────────────────────┬──────────────────────┘   └───────────────────┬───────────────────┘
                           └──────────── 汇流为一个标准 AIDA skill 模块 ─────┘
                                  ▼
                   真实 AIDA 容器执行（输入/产物走数据中心 files API）
                   三类验证：行为 ∧ 契约 ∧ 运行稳定性 → Final Gate
                                  ▼
                   注册交付（随镜像 · 工具回流 toolbox · 组件缺口由金涛合入 · 钉死 digest）
```

**这正好是你那句话的 IPO**：输入＝业务逻辑（M1）+ 页面设计（M3）；输出＝graph.py（M2）+ SDUI（M3）；执行＝数据中心（M4）。M2 与 M3 是**两条并行支线**，对应"graph.py **以及** SDUI 呈现"两个并行产出。

---

## 4. 产出导向里程碑（M0–M5）

> 每个里程碑 = 一个**可客观验证的转换产物**。「现状」列按你定的"目标形态为准"做极简标注：🟢 已通 / 🟡 半手工 / 🔴 待底座。

| 里程碑 | 角色 | 产出物 | 客观验收闸门 | 现状 |
|--------|------|--------|------------|------|
| **M0 · 认知流水线 + 环境** | 任何人 | 看懂"Raw Skill→编译→graph+sdui→容器验证→注册"；本地起后端 | `curl /agent/skills` 看到样板 | 🟢 |
| **M1 · 写业务逻辑（Raw Skill）** | 业务专家（前门） | `SKILL.md`(§22 十五节) + `assumptions.json`(已确认假设清单) | **过 HARD-GATE**(§21 完整性+一致性) + **作者终审**(S9) | 🟡 前门程序未上线，当前由开发者按《编写规范》手写 |
| **〔交接〕Session 0 契约复核** | 编译侧入口 | — | Raw Skill + assumptions.json 合规、可进编译 | 🟡 手工复核 |
| **M2 · 业务逻辑 → graph.py**（执行支线） | 开发者 + agent | `skill_ir.json` + `graph.py`(或 GraphSpec) + 行为/契约测试 | `lint_skill_contract`·`lint_runtime_contract`·`lint_tools`·`lint_no_naked_llm`·`lint_no_naked_send` 全绿 | 🟡 编译会话手工跑 |
| **M3 · 页面设计 → SDUI**（呈现支线 · 与 M2 并行） | 开发者 + agent + 金涛 | `sdui.py` 投影器；（缺组件时）**组件需求提示词 → 金涛** | `lint_sdui_contract` 全绿（只用现有组件、props 合法）；缺口已转金涛 | 🟡 投影手工产，缺口走金涛人工 |
| **M4 · 真实容器 + 数据中心验证** | 开发者 + agent | `execution_evidence` + 三类验证报告 | **Final Gate** = behavior ∧ contract ∧ runtime 全 passed；run 到 done，输入/产物走数据中心 files API | 🔴 测试底座 / 数据中心测试租户在需求阶段，暂走手工容器 + Mock |
| **M5 · 注册交付** | 开发者 / CI | skill 随镜像 · 新工具回流 toolbox · 金涛补的组件合入并更新清单 · 记录已验证 digest | 注册后 `curl /agent/skills` 看到新 skill；digest 标记 | 🔴 镜像 digest 钉死流程待建 |

### 各里程碑 · 喂 agent 的最小料 + 精简提示词要点

**M1 ·【业务专家】写 Raw Skill** — 料：`可编译业务Skill编写规范 §22 模板 + §21 检查清单`（各节按需深读）。
> 提示词：照 §22 十五节模板写 `<业务名>` 的 Raw Skill（业务语言、不写代码）；每处"模糊→确定"的判断进 `assumptions.json`（字段：`id/section/kind/question/options/resolved_value/evidence/confirmed_by`）；写完自检 §21 清单，缺项标 warning 不假装完整。

**M2 ·【开发者+agent】业务逻辑→graph** — 料：`AIDA-RUNTIME-CONTRACT`（graph 真身契约）+ `工作流执行指南 §6/§8/§9`（Session A/C/D）。
> 提示词：把 Raw Skill 抽成 `skill_ir.json`（工具字段只写能力需求 + 候选，`allowed_tools` 从 9 个 DEFAULT_TOOLS 里选或声明需新增）；据 SkillIR 生成 `graph.py`，**必须对齐运行时契约**：node 返回 state diff、`steps/logs` 走 reducer 累加、HITL 是软中断（写 `state["hitl"]`→END→resume，不是 `interrupt()`）、工具失败返回 `Error:` 字符串不抛、provider 无原生 `output_schema`（结构化输出在适配器层 prompt 注入 + `json.loads`）。

**M3 ·【开发者+agent】页面设计→SDUI** ★（吸收你的答案）— 料：`README §7` + `SDUI组件库需求`（可用组件清单 + props 契约）+ `agent/skills/zhgk/sdui.py`（投影器样例）。
> 提示词：输入＝我的界面设计素材（html / 截图 / 代码）+ Raw Skill §输出/§状态/§风险 的呈现规划。结合**现有 SDUI 组件库清单**，把它投影成本业务场景的 `project(state)→dict`（整体排布 + 呈现）；**只能用现有组件**（通用段复用 `projector_base`，业务段从输出/风险/状态字段派生）。**若现有组件无法表达某处呈现 → 不要自造**，生成一份"组件需求提示词"（要什么组件、props、用在哪、为何现有组件不够）发给 SDUI 组件维护者**金涛**统一添加；本处先用最接近的现有组件占位。产出过 `lint_sdui_contract`。

**M4 ·【开发者+agent】容器+数据中心验证** — 料：`工作流执行指南 §10–§17` + `数据中心API §4`（标准数据流配方）。
> 提示词：在真实 AIDA 容器跑 run；输入从数据中心 files API 读（`GET /files`→`download`）、产物写回（`POST /files/upload` 到输出目录）、定位走 `GET /projects/{id}/tree`；收 execution_evidence，过三类验证（行为∧契约∧运行稳定性），出 Final Gate 结论（AI 说"完成"不算，只有证据决定）。

**M5 ·【开发者/CI】注册交付** — 料：`README §6 工具回流` + `测试底座对齐方案`（digest 钉死）。
> 提示词：注册 skill（`registry.register` 一行 + SKILL.md 两处部署）；通过验证的新工具回流 toolbox（幂等/去重/版本/provenance）；记录"已验证 digest"。

---

## 5. 触发式深读总映射（"考虑 agent 上下文"的核心机制）

把长文档从"无条件整篇喂"改成"问题驱动按需取那一节"。下表是门户应内置的索引（放进对应里程碑的提示词或 note）：

| 当 agent 撞到这个问题 | 才读这一节 | 行量级 |
|----------------------|-----------|-------|
| Raw Skill 某节不会写（输入/输出/规则/HITL/LLM 点…） | `可编译业务Skill编写规范 §7–§17` 对应节 | 各 ~15–30 |
| Raw Skill 合不合格 | `可编译业务Skill编写规范 §21` 清单 | ~20 |
| graph 不符合 AIDA 运行时（state/HITL/工具/provider） | `AIDA-RUNTIME-CONTRACT §0` 速查 + 对应 §1–§5 | ~30–50 |
| SkillIR / Graph 各会话边界与产出 | `工作流执行指南 §6 / §8 / §9` | 各 ~30 |
| SDUI 投影器怎么写 / metrics 契约 | `SDUI.md §3.2`–`§3.3` | ~40 |
| 有哪些 SDUI 组件可用 / 缺了怎么报金涛 | `SDUI组件库需求`（组件清单 + 缺口通道 R3） | 按需 |
| 读上游输出 / 写解析 / 产出血缘 | `数据中心API §4.1 / §4.2 / §4.3` | 各 ~10 |
| 产物落哪一层 / 命名 / 自检 | `业务数据规范 §3.3 / §7.1 / §11` | 各 ~15 |
| 三类验证 / Final Gate 判定 | `工作流执行指南 §11 / §17` | ~30 |

> 对比：原第⑥步一次性 `@` 2189 行 → 新设计里，每处深读 ≈ 10–50 行。

---

## 6. 上下文预算对比

| 阶段 | 改造前（每步整篇 `@`） | 改造后（每里程碑峰值阅读） |
|------|----------------------|--------------------------|
| 认知 | ①111 + ②278 + ③154（read 列表 1282） | M0：README §1–3 ≈ **60** |
| 写 Raw Skill | —（旧门户无此步） | M1：§22 模板 + §21 清单 ≈ **120** |
| 编译 graph | ⑦SKILL-DEV 308 + SDUI 280 = 588 | M2：RUNTIME-CONTRACT §0 速查 ~30 +按需 |
| 编译 SDUI | （同上） | M3：组件清单 + zhgk/sdui.py 样例 ~按需 |
| 数据/执行 | ⑥**2189** | M4：执行指南 §10–17 + 数据中心API §4（撞到才读，各 ~10–30） |
| **峰值单步阅读量** | **2189 行** | **~120 行**（+ 按需小节，每项行量级见 §5） |

---

## 7. portal.json 落地改法（生成器零改）

现有 schema 已足够表达本方案，**不必动 `gen_team_portal.py`**：

- `doors[id=developer].steps[]`：从 8 个对象 **重组为 6 个里程碑**（M0–M5），内容照 §4。
- **角色标识**：用 `step.title` 前缀表达（如 `"M1 ·【业务专家】写业务逻辑"`、`"M3 ·【开发者+agent】页面设计→SDUI"`），无需新字段。Session 0 交接闸门可作为 M1 的 `next` 或 M2 的 `note`。
- **现状标注（🟢🟡🔴）**：放进每步 `goal` 末尾或 `note`（如 `"⚠ 现状：测试底座在需求阶段，本步暂走手工容器 + Mock 数据中心"`）。
- **金涛缺口通道**：写进 M3 的 `note`（"缺组件→生成需求提示词→发金涛，本处先用现有组件占位"）。
- **触发式深读映射**：放进每步 `prompt[]` 文本尾部或 `note`（§5 子集）。
- **read[] 区分"底本"与"按需"**：用 `label` 文案表达（`"📖 施工底本：…"` vs `"🔍 撞到 X 才读：…§Y"`），零字段改动。

**可选增强（需小改生成器，非必须）**：给 step 加 `role` / `status` 字段，`build_step` 渲染成角色色条 + 🟢🟡🔴 状态点。**建议先用文案表达，零风险落地**，UI 增强作为后续。

**落地命令**：
```bash
python agent/scripts/gen_team_portal.py     # 重生成 docs/site/portal.html
python agent/scripts/lint_team_portal.py    # 守门：HTML ≡ json 源
```

---

## 8. 已定方向（本轮三问已拍板）+ 仍待确认

**已定**：
1. **页面设计落地** = 混合形态：开发者交付设计素材（html/截图/代码）+ 呈现规划 → coding agent 结合现有组件库投影 SDUI → 缺组件生成需求提示词发金涛。（M3）
2. **基调** = 目标全自动形态为主线，现状 gap 仅 🟢🟡🔴 极简标注。
3. **角色** = 业务专家 + 开发者接力，M1→M2 之间 Session 0 交接闸门。

**仍待你确认**：
1. **「新人」门 / 「架构师」门**是否本轮同步轻量化，还是只动「模块开发者」门？
2. **金涛缺口通道是否要做成显式制品**——比如门户给一个"组件需求提示词模板"（agent 一键产出、可直接发金涛），还是仅在 M3 note 里说明？
3. **M0 认知步**保留独立里程碑，还是并入 M1 前的一段 intro（门户 `door.intro`）以进一步减步？
4. **是否要给长文档补"分层深读锚点"**（在 `可编译业务Skill编写规范.md` 等加显式小节锚点），让 §5 映射可直接深链——属"加重档"，默认不做。

---

*— 方案 v2 完 · 审定后照 §7 落地，本文件可删 —*
