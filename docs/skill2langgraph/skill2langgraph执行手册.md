# skill2langgraph 执行手册（agent 操作 skill）

> 状态：Draft v0.1（2026-06-09）· 基于 device_install_mini walking skeleton 实跑提炼
> 读者：**coding agent**（Claude Code / Codex / Cursor）。这是让"参考文档库，把这份 Raw Skill 按 skill2langgraph 编译成 AIDA skill"这句话**接得住**的操作手册。
> 一句话：本手册把流水线的**编排纪律**写死——尤其是"每个 session 起独立隔离 subagent + 盲化约束"，这是文档本身无法自动保证、却决定验证完整性的关键。

---

## 0. 触发与前置

**触发**：用户对你说"参考文档库，按 skill2langgraph 把 `<Raw Skill 路径>` 编译成 AIDA skill"（或类似）。

**前置检查（缺则先补，别硬跑）**：
- [ ] 输入：一份 Raw Skill（`SKILL.md` §22 模板）；理想还有 `assumptions.json`。手写来源也合规（见 `contracts/交付契约.md`）。
- [ ] 可执行件在手：① **校验规则集 lint**（跑 `contracts/校验规则集.md` 的规则）② **测试底座薄驱动**（注入真实 AIDA + 取证）。若仓库无现成实现，你需先按手册末「可执行件」一节临时实现一个最小版。
- [ ] 目标 AIDA：可运行的 `agent`（P0 单机进程即可；`ZHIPU_API_KEY` 已配则可 live LLM）。
- [ ] 契约：从文档库读 `contracts/`（SkillIR-schema / 校验规则集 / 打包 / assumptions / 交付）与 `../../agent/docs/AIDA-RUNTIME-CONTRACT.md`。

> 业务人员从零写 skill **不走本手册**——他们走**前门**（`引导编写流程-完整设计.md`），产出 Raw Skill 后才进这里。

---

## 1. ★铁律：每个 session 起独立隔离 subagent + 盲化

这是本手册存在的核心理由。**绝不要在一个上下文里把 SkillIR、Graph、测试都做了**——那等于自己批改自己，验证失去意义。

| session | 起独立 subagent | 只喂 | **绝不喂**（盲化） |
|---|---|---|---|
| A SkillIR | ✓ | Raw Skill + `contracts/SkillIR-schema.md` | 校验规则集、行为测试 |
| B 行为测试 | ✓ | Raw Skill | SkillIR、Graph、任何实现 |
| C skill 模块 | ✓ | SkillIR + AIDA 契约 + 打包契约 + 样板 | 行为/契约测试 |
| D 契约测试 | ✓ | SkillIR + 打包契约 | C 的实现代码、行为测试 |
| E/F/G 报告 | ✓ | 执行证据 + 对应产物 | — |

- **A⊥B**：都从 Raw Skill 独立派生（A 出 SkillIR，B 出黑盒行为测试）。B 看不到 SkillIR，测试才不会迁就实现。
- **C⊥D**：都从 SkillIR 派生（C 出 Graph，D 出契约测试）。D 看不到 Graph，才不是给实现背书。
- 用你宿主工具的**原生 subagent**（Claude Code Agent 工具 / `claude -p` / `codex exec` / `cursor-agent -p`），产物**落文件**交接，不靠共享上下文。

---

## 2. 流程（照做）

```
[0] 拿到 Raw Skill
     │
[1] Session 0：跑【校验规则集 lint】on Raw Skill（完整性能查的先查）   ── 不过→打回作者
     │ 过
[2] 起隔离 subagent ──┬─ 会话A：Raw Skill → SkillIR(JSON)
                      └─ 会话B：Raw Skill → 黑盒行为测试            （A⊥B，并行）
     │
[3] Session 0：跑【校验规则集 lint】on SkillIR（R-C 完整性 + R-K 一致性 + R-A 运行时） ── error>0→回[2]修
     │ 0 error
[4] 起隔离 subagent ──┬─ 会话C：SkillIR → AIDA skill 模块(skill.py+steps+sdui+SKILL.md+module.json+必要新工具)
                      └─ 会话D：SkillIR → 契约测试                  （C⊥D，并行）
     │
[5] 注入 + 守门 lint：把 C 产物放进 agent/skills/<name>/，注册一行；跑
        lint_skill_contract / lint_runtime_contract / lint_sdui_contract / lint_tools
        / lint_no_naked_llm / lint_no_naked_send                    ── 不过→回[4]修
     │ 全绿
[6] 测试底座执行【薄驱动】：构造测试 work_root（输入文件入 ProjectData/Input/），
        在真实 AIDA runtime invoke graph（happy + 缺输入等场景），读证据
        （state / steps / hitl / 产物文件 / 中间态 / Langfuse）
     │
[7] 三类验证（喂真实证据）：
        · 行为验证：B 的黑盒测试 vs 证据（是否保留 Raw Skill 语义）
        · 契约验证：D 的契约测试 vs Graph 元数据+证据（是否忠实实现 SkillIR）
        · 运行稳定性：跑完/进预期 HITL、工具非 Error、provider 输出可解析、HITL 软中断、无异常
     │
[8] Final Gate = 行为 ∧ 契约 ∧ 稳定性
        · 全绿 → 起 E/F/G 出交付包（Graph 文档 + 行为报告 + 契约报告），注册到数据中心 Skill 中心(draft→published)
        · 不绿 → 按"失败回环"定位，回对应 session 重做
```

---

## 3. 失败回环（哪条红→回哪）

| 现象 | 多半根因 | 回到 |
|---|---|---|
| Session 0 R-K-01 报"输入不可达" | SkillIR 漏步骤/漏声明/state binding 错 | 会话 A |
| 守门 lint 不过（缺 SKILL.md/裸 LLM/SDUI 不一致） | C 产物不合打包契约 | 会话 C |
| 行为验证红 | Graph 没保留业务语义（如统计取了 LLM 文本，见 R-K-09） | 会话 C（必要时回 A 补规则） |
| 契约验证红 | Graph 偏离 SkillIR（步骤/工具/HITL/状态不符） | 会话 C |
| 稳定性红（工具 Error/异常/HITL 非软中断） | C 没对齐 AIDA 运行时契约 | 会话 C |
| 反复对不齐、根因在结构 | SkillIR 本身表达不了 | 会话 A（必要时回前门改 Raw Skill） |

> **绝不带病放行**：任一 error 未清不出交付包（照搬 HARD-GATE 纪律）。

---

## 4. 实跑得到的硬约束（务必照做）

来自 device_install_mini walking skeleton 的真实教训（已固化进 contracts v0.3）：

1. **自定义跨步状态必须落盘**（`binding=runtime_file` → `ProjectData/RunTime/*.json`）。`SkillState` 只认固定 channel（run_id/skill_id/project/steps/logs/current_step/overall_progress/files/hitl/hitl_resume/metrics/error），**自定义顶层键会被 LangGraph 静默丢弃**。SDUI 数据走 `metrics` channel。（R-A-06）
2. **统计量真源不能是 LLM 自由文本**。计数/数量必须由 rule 步骤派生，LLM 只可复述（实跑：LLM 写"40"实为 29）。（R-K-09）
3. **会话 C 必须产 `SKILL.md`（后端节点↔step.key）+ `module.json`**，否则 `lint_skill_contract` 跑不了、注入不完整。（R-C-18）
4. LLM 走 `ctx.invoke_llm(messages, step_key=...)`，结构化在适配器层（prompt 注入 schema + json 解析 + 重试）；工具走 `ctx.call_tool`，失败不抛异常、返回 `"Error:"` 字符串，判 `is_tool_error`；HITL = `check_inputs` 失败→写 `state["hitl"]`→END，**非** `interrupt()`。
5. `work_root` 不写死；输入从 `ctx.input_dir` 取、产物写 `ctx.output_dir`。

---

## 5. 降级（P0 现状，可接受）

- 进程态（非容器）：直接对 `aida/agent` 进程注入+跑，不等容器化。
- live LLM（无回放）：结果不确定、烧 token；"行为可重复"这次拿不到，手动 PoC 可接受。
- 接地占位：文档库能力清单未就绪时，工具接地用人工确认+占位+记假设，待清单就绪批量重校。
- 不注册回 toolbox / 无 digest 钉死：P2 基建到位后再开。

---

## 6. 可执行件（不在文档库，本手册指向它们）

| 件 | 作用 | 现状 |
|---|---|---|
| **校验规则集 lint** | 跑 `contracts/校验规则集.md` 的 R-C/R-K/R-A，输出结构化报告（Session 0 与 S8 同源调用） | 待固化为脚本；当前可由 agent 按规则逐条判，但**应实现为可执行 lint** |
| **测试底座薄驱动** | 注入 skill→真实 AIDA invoke graph→取证（参考实跑那 ~80 行：构造 work_root、`build_graph()`、`graph.invoke()`、dump state/产物/中间态） | 待固化；实跑已验证可行 |
| **隔离 subagent 编排** | 按 §1 铁律起 A–G、喂盲化输入、收文件产物 | 用宿主工具原生 subagent；可写成一段编排脚本 |

> 这三件是流水线的"可执行内核"。文档库给知识，这三件给执行。缺它们时，agent 可临时手动顶替（实跑就是这么做的），但生产应固化。

---

## 7. 一句话用法

> 对你的 coding agent 说："**参考文档库 `docs/skill2langgraph/`，按 `docs/skill2langgraph/skill2langgraph执行手册.md` 把 `<Raw Skill>` 编译成 AIDA skill**"——它就会照本手册起隔离 subagent、过 Session 0、注入真实 AIDA、三类验证、出交付包。**前提**：可执行件（lint/harness）在手、目标 AIDA 可跑。
