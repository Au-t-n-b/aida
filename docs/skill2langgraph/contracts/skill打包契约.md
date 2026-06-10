# Skill 打包契约（编译产物形态 · 草案 v0.3）

> 状态：Draft v0.3（2026-06-09）· **未冻结**
> v0.3（walking skeleton 实跑回填）：①强调 `SKILL.md`+`module.json` 为**强制注入前闸门产物**（会话 C 实跑漏产 → lint_skill_contract 跑不了，见 R-C-18）；②§4 映射补 `state.binding`——SkillIR 自定义跨步态须落 `ProjectData/RunTime/*.json`、SDUI 数据走 `metrics` channel（SkillState 内置 channel 固定，自定义键会被 LangGraph 丢弃）。
> 定位：会话 C 编译产出的"skill 模块"必须满足的形态，使其同时**可被 AIDA 加载、可在测试底座运行、可注册发布**。
> 关联：AIDA `../../../AGENTS.md`「新作业模块·碰这些文件」事实表 + 钩子全集；运行时契约 `../../../agent/docs/AIDA-RUNTIME-CONTRACT.md`（Tool/SkillState/HITL/建图）；`SkillIR-schema.md`（映射来源）；测试底座 `../requirements/测试底座/01_AIDA-Agent模块需求.md`（注入/lint/registry）。
> 来源权威：AIDA `agent/skills/_template/` 脚手架——本契约是它的"生成视角"规格化。

---

## 1. 产物文件清单

| 文件 | 内容 | 必/可选 | 归属 |
|---|---|---|---|
| `agent/skills/<name>/skill.py` | `<Name>Skill(BaseSkill)`：`name` + `steps=[…]` + 工厂 `get_<name>_skill()` + 钩子 | 必 | **镜像（代码）** |
| `agent/skills/<name>/steps/*.py` | 每 step 一文件：`key`/`name` + `check_inputs()`(HITL 软中断) + `run(ctx,state,emit)` | 必 | 镜像 |
| `agent/skills/<name>/sdui.py` | `project(state)→dict`，复用 `projector_base`，**只用现有组件** | 必 | 镜像 |
| `agent/skills/__init__.py` | `registry.register("<name>", get_<name>_skill)` 一行 | 必 | 镜像 |
| `skills/<name>/SKILL.md` | frontmatter + 触发词 + 端点表 + **后端节点表**（节点 ↔ step.key 契约） | 必 | 镜像 + 数据中心 Skill 中心 |
| `<name>/module.json` | 模块元数据（flow / HITL / task 列表） | 必 | 数据中心 Skill 中心 |
| `<name>/state.json` schema | 读契约（含 `schemaVersion`），对齐 SkillIR.state | 必 | 运行态在容器，schema 进契约 |
| `agent/tools/<tool>.py` | `tool_needs.resolution=self_impl` 的新工具，满足 Tool 基类契约 | 视情况 | 镜像（通过后注册回 toolbox） |
| `frontend MODULE_TO_SKILL` 一行 | 要界面时 | 可选 | 前端部署 |

> 存储分工（总设计 §2.1）：**代码→镜像；注册/元数据→数据中心 Skill 中心（draft→published）；run 态→容器内 SqliteSaver；项目文件→数据中心 files API**。

## 2. 必守约束

| # | 约束 | 出处 |
|---|---|---|
| C1 | LLM 走 `ctx.invoke_llm(messages, step_key=…)`，**禁裸 LLM**（过 `lint_no_naked_llm`） | AGENTS.md |
| C2 | 外发走统一出口（mailer/notifier/send_welink），**禁裸外发**（`lint_no_naked_send`） | AGENTS.md |
| C3 | 跨 step 数据走 `SkillState`（`files`/`metrics`/自定义键），node 返回 **diff**（`steps`/`logs` reducer 累加） | 契约 §3 |
| C4 | HITL = 软中断：`check_inputs` 失败 → 写 `state["hitl"]` → END → resume（**非** `interrupt()`） | 契约 §4 |
| C5 | `work_root` **不写死**——由注入决定（指向容器内一次性目录） | AIDA 04 §6 |
| C6 | 工具失败**不抛异常**，返回 `"Error:"` 字符串 / `{ok:false}`；新工具 `execute` **同步** | 契约 §2.2/§2.3 |
| C7 | SDUI 只用现有组件、过 `lint_sdui_contract`（三方一致） | SDUI 需求 |
| C8 | SKILL.md 后端节点 ↔ step.key 一一对应（`lint_skill_contract`） | AGENTS.md |

## 3. 注入前验收闸门（守门 lint，全绿才注入测试容器）

`lint_skill_contract` · `lint_runtime_contract` · `lint_sdui_contract` · `lint_tools` · `lint_no_naked_llm` · `lint_no_naked_send`（测试底座 01 §R4 固化其稳定接口/退出码）。

## 4. SkillIR → 打包 映射（会话 C 怎么生成）

| SkillIR 元素 | 落到 |
|---|---|
| `steps[]` | `steps/*.py`（key=step.id；`depends_on`→建图边；`guard`→`check_inputs`） |
| `steps[].kind=llm` + `llm_points` | step.run 内 `ctx.invoke_llm` + 适配器层按 `output_schema` 解析 |
| `hitl[]` | `check_inputs` 返回 `{ok:false, missing}` → `state["hitl"]` |
| `tool_needs` | `allowed_tools`（reuse）/ 新工具文件（self_impl）/ 缺口工单（gap） |
| `state`（binding=channel） | 直接写 SkillState 内置 channel（files/metrics/hitl/error…） |
| `state`（binding=runtime_file，v0.3） | 落 `ProjectData/RunTime/<name>.json`，下游读回（自定义跨步态必走此，否则运行时丢） |
| `state`（binding=read_model，v0.3） | 发布到 `metrics` channel 供 `sdui.project(state)` 读 |
| `sdui` | `sdui.py::project`（通用段复用 projector_base，业务段按 hints） |
| `success_criteria` + `test_scenarios` | 喂会话 B/D 生成行为/契约测试（不在本模块内） |
| `meta`/`scope` | `skill.py` 元信息 + `SKILL.md` frontmatter + `module.json` |

## 5. 建图契约（运行时，由 `BaseSkill.build_graph` 保证）

`StateGraph(SkillState)`；每 step→一 node；`add_conditional_edges(router)`：`error`/`hitl.step` 非空→END，否则→下一 step。生成的 skill 只要遵循 step 结构即自动获得此建图（契约 §5）。

## 6. 待冻结项

- `_template` 脚手架字段与本清单逐项对账（确保"生成即可注册"）。
- 新工具的 `Tool` 契约草案（name/params/execute 描述）随 `tool_needs.self_impl` 内联，还是单独文件。
- `module.json` 字段集（与数据中心 Skill 中心 `bindsModuleCode`/`status` 对齐）。
- `state.json` `schemaVersion` 与 SkillIR.state 的同构校验。
