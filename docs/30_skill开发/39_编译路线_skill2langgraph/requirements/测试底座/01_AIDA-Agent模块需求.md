# AIDA Agent 模块配合需求 · 测试底座

> 状态：Draft v1（2026-06-08）
> 提出方：skill2langgraph 流水线
> 面向：AIDA Agent 后端开发（Claw LangGraph 执行引擎，`aida/agent/`）
> 总设计：`docs/skill2langgraph/测试底座对齐方案.md`
> 权威契约：`docs/30_skill开发/31_手写规范/AIDA-RUNTIME-CONTRACT.md`（本文凡引用运行时行为均以它为准）

## 0. 你为什么会收到这份需求

我们要用 **AIDA 本体**（而非复刻 Harness）作为生成 Graph 的测试底座。这要求 `aida/agent` 暴露若干**稳定接缝**：能注入生成的 skill、能把 LLM 换成回放、能读出执行证据、能稳定地驱动 HITL/resume。下列需求都是"让真身可被测试驱动安全地操控"。

## 1. 需求清单

### R1 · agent 代码收敛为单一真相 ★头号阻塞
**现状**：`04_容器化部署与运行时架构.md` §5.2 明确——`aida/agent`、`aida-vite/agent`、`claw-delivery-ui/agent` 存在多份副本且内容有别，"改 A 跑 B"已踩坑。
**要求**：确定唯一权威 `agent` 源，其余副本由它生成或软链；测试镜像与生产镜像都从这唯一源构建。
**验收**：① 文档明示唯一真相路径；② CI 校验无第二份可执行 `agent` 副本被打进镜像。
**不解决的后果**：测试用的 AIDA 与用户跑的不是同一个，整个"用本体测试即天然对齐"的前提失效。

### R2 · Provider 可注入回放（确定性）
**现状**：`aida/agent/llm.py` 的 `get_llm()` 从 env 读 `ZHIPU_BASE_URL`（:31），但是**单例**——首次创建后 temperature 等固定（契约 §1.1 ⚠️）。
**要求**：
- 提供**官方支持的 provider 重定向方式**：通过 env（`ZHIPU_BASE_URL` 指向 OpenAI 兼容回放端点）即可让全部 LLM 调用走回放，无需改 skill 代码。
- 解决单例副作用：要么允许 per-node temperature，要么明确文档化"测试回放下 temperature 无关"。
- 定义**录制模式**：一次 live 跑把"messages→响应"录成 fixture（与 `eval_*.py --fixture` 体系一致），供回放复用。
**验收**：① 设 `ZHIPU_BASE_URL=<回放端点>` 后，一次 run 的所有 model call 命中回放、零真实 token 消耗；② 同一 fixture 重放结果稳定；③ 录制产物格式文档化。
**出处**：契约 §1.1/§1.3；`AGENTS.md`（`eval_zhgk.py --fixture` 先例）。

### R3 · Skill 动态注入 / 加载契约
**现状**：skill 现在靠 `agent/skills/__init__.py` 里 `registry.register("<name>", get_<name>_skill)` **手工一行**注册（见该文件）；定义层在 `aida-datacenter/skills/<skill>/`，执行层在 `agent/skills/<skill>/`。
**要求**：提供**不改动 `__init__.py` 源码**即可装入一个新 skill 的机制，三选一并文档化：
- (a) 启动期**目录扫描自动注册**（约定目录即被加载）；或
- (b) 运行期**注册 API**（`POST` 一个 skill 包后可 `/agent/<skill>/start`）；或
- (c) **镜像构建期注入**（CI 把生成的 skill 包烤进测试镜像）。
**要求附**：明确一个"skill 包"的最小文件契约（`skill.py` BaseSkill+steps、`sdui.py`、`SKILL.md` 节点↔step.key、`module.json`、`state.json` schema、`work_root` 不写死）。
**验收**：给定一个符合契约的 skill 包，按文档方式装入后，`GET /agent/skills` 能列出它、`POST /agent/<skill>/start` 能跑起。
**出处**：`AGENTS.md`「新业务场景 Skill·碰这些文件」；`04` §6 五步。

### R4 · 生成物验收闸门（lint 稳定接口）
**现状**：`AGENTS.md` 列出守门 lint：`lint_skill_contract` / `lint_runtime_contract` / `lint_sdui_contract` / `lint_tools` / `lint_no_naked_llm` / `lint_no_naked_send`，且 `lint_runtime_contract` **已声明覆盖 "skill2langgraph 工厂对齐"**。
**要求**：把这套 lint 固化为**生成物注入前的验收闸门**：稳定的调用方式（脚本路径/参数）、稳定的**退出码语义**（0=过、非0=具体哪条破裂）、机器可解析的输出。流水线生成的 skill 必须过这套 lint 才允许注入测试容器。
**验收**：① lint 调用方式与退出码文档化、向后兼容；② 故意造一个违规 skill 能被对应 lint 精确拦截并给出可定位信息。
**出处**：`AGENTS.md`「提交前守门」。

### R5 · state.json 读契约稳定 + schemaVersion
**现状**：`state.json` 是"该 run 唯一真相"，前端 `render(state.json)`，产物清单以 `state.outputs` 为准（`04` §2.3/§7）；但 §5.1 指出更新机制（state.json 增量 vs SDUI patch）尚未完全收敛。
**要求**：
- 冻结 `state.json` 顶层形状并带 `schemaVersion`：至少含 `steps[] / logs[] / files / outputs / metrics / hitl / error / current_step / overall_progress`（对齐契约 §3 `SkillState`）。
- 明确 reducer 语义在落盘后的呈现（`steps/logs` 为累加结果，非覆盖）。
**验收**：给定一次 run，能仅凭 `state.json` + `schemaVersion` 提取出三类验证所需全部状态证据，无需读内部代码。
**出处**：契约 §3；`04` §2.3/§5.1。

### R6 · Checkpoint 可读出（node 轨迹 / resume 证据）
**现状**：run 态用 `AsyncSqliteSaver`（FastAPI），CLI/测试可 `MemorySaver`（契约 §5；`AGENTS.md`「别引 PostgresCheckpointer」）。
**要求**：文档化容器内 checkpoint 的**存储位置与可读取方式**（sqlite 路径 / 或一个只读导出接口），使测试驱动能取得 node 执行轨迹、state diff 序列、resume 前后状态，用于运行稳定性验证。
**验收**：跑完一次 run 后，能从 checkpoint 读出 node trace 与至少一次 state diff。
**出处**：契约 §5；`04` §4。

### R7 · HITL / resume 契约稳定
**现状**：HITL 是软中断——`check_inputs` 失败→写 `state["hitl"]={step,reason,need_files,need_inputs}`→router 到 `END`→另起 run resume；默认 `full_restart`，个别 step `step_retry`（契约 §4）。`/agent/<skill>/resume` 端点存在（`main.py:390`）。
**要求**：稳定化 `/start` 与 `/resume` 的请求/响应契约（含如何携带补料、如何指定 `full_restart` vs `step_retry`、resume 如何关联前一 run）；文档化 `apply_resume_payload`（确认型 HITL 跨 `full_restart` 存活）的对接方式。
**验收**：测试驱动能脚本化复现"触发 HITL→补料→resume→跑完"全链路，行为与契约 §4 一致。
**出处**：契约 §4；`AGENTS.md`（钩子全集 `apply_resume_payload`）。

### R8 · 就绪探针
**要求**：`/healthz`（`main.py:102` 已有）需明确**就绪语义**：测试驱动据此判断容器"可接受 `/start`"，避免竞态。若 healthcheck 不实发 LLM（`llm.py:127` 现状如此），需另给"依赖就绪"信号或文档化最小等待。
**验收**：驱动轮询 `/healthz` 转就绪后首个 `/start` 不因未初始化失败。

### R9 · 全局 dry-run / 测试模式开关
**现状**：`send_mail`/`send_welink` 默认 dry-run、`present_choices` 被拦截（契约 §2.4）。
**要求**：提供**全局强制 dry-run** 的 env/config 开关，保证测试模式下任何工具都不产生真实外发/外部副作用（即使将来新增工具默认非 dry-run）。
**验收**：开启后，构造会触发外发的场景，验证无真实投递、仅留痕。
**出处**：契约 §2.4；`AGENTS.md`「外发走统一出口」。

### R10 · 工具运行期确定性边界（外部调用回放 + 工具集断言）
**现状**：toolbox 的非确定源不止 LLM——外部网络类工具用 `urllib.request` 真发 HTTP（参见 `tools/mcp_adapter.py:86/90`），数据中心 API 类工具同理。本地文件工具（`read_file`/`doc_read_xlsx`/`doc_write_docx`）读写 `work_root`（`Path(path)`），种子化后确定。
> 说明：toolbox 模块尚未开发，工具暂放 `aida/agent/tools/`；`run_survey`/`zhgk_bridge` 等 skill-as-tool 是妥协产物，不纳入最终设计。本需求按**行为类别**约束，不绑定具体工具。toolbox 侧能力见 `docs/skill2langgraph/requirements/Toolbox模块需求.md`。
**要求**：
- **外部网络/数据中心 API 类工具可回放（定为：端点重定向）**：这类工具的外部端点（如 `base_url`）必须**可配置**，使其能像 `ZHIPU_BASE_URL` 一样**重定向到回放服务**。要求：① 凡发起外部调用的工具，其目标端点一律走 env/config 注入，**不得在工具内硬编码**；② 与 R2 的 LLM 录制/回放体系同构（录制档 vs 回放档）。
  > 决策：采**端点重定向**，**不采**"容器内注入 fake tool runtime"——后者等于引入第二套工具实现，与"用 AIDA 真身测试"的初衷冲突。端点重定向保持工具代码逐字节真身，只换它指向的外部地址。
- **本地文件工具保持真跑**：不桩，输入由 `input/` 种子 fixture 提供、输出写 `output/`（输入/产物经数据中心 §R2 files API + Manager §R2 桥接）。
- **工具集断言接口**：提供枚举"**该镜像/registry 当前可用工具集**"的方式（工具 name 列表），供注入前 fail-fast 校验。校验对象分两类（对应"复用 > 自实现"策略，见总设计 §5.3）：
  - **复用类工具**：skill 声明要复用的工具必须存在于该 digest 镜像/toolbox，缺失即拒绝注入；
  - **新工具**：随 skill 打包注入的新实现工具，必须可加载且通过 `lint_tools`（R4），方可起 run。
**验收**：① 设回放后，一次 run 内所有外部 HTTP 调用命中回放、不出容器；② 本地文件工具在种子 fixture 下结果确定；③ 声明复用了镜像中不存在工具的 skill，注入前被拦截并报出缺失工具名；④ 随包新工具不合规时被 `lint_tools` 拦截、不起 run。
**出处**：契约 §2.1/§2.4；总设计 §5.2/§5.3；`Toolbox模块需求.md`。

## 2. 落地状态参考（来自 AIDA 文档，便于排期）

| 能力 | 现状 | 出处 |
|---|---|---|
| LangGraph 执行引擎 | ✅ 单机跑通 | `04` §3 |
| provider env 可配 base_url | ✅ 已具备（单例待解） | `llm.py:31/83` |
| skill 手工注册 | ✅（动态注入待建） | `__init__.py` |
| 守门 lint 全套 | ✅ 已有（验收接口待固化） | `AGENTS.md` |
| state.json 真源 | ✅（schemaVersion/收敛待定） | `04` §2.3/§5.1 |
| agent 单一真相 | ❌ 多副本 | `04` §5.2 |
