# 新作业模块开发清单（NEW_SKILL_CHECKLIST）

> 目标：照 zhgk 这个样，**首次 ~30 分钟搭起一个能端到端 run 的新作业模块骨架**。
> 配套：起手 [START_HERE.md](START_HERE.md) · 细则 [SKILL-DEVELOPMENT.md](../30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md) / [TOOL-DEVELOPMENT.md](../30_skill开发/31_手写规范/TOOL-DEVELOPMENT.md) · 规范 [03 团队范式 §7](../20_架构与范式/03_团队Agent开发范式.md)
>
> 图例：☐ 动作 · ⚠️ 卡点（最容易错）· ✓ 验证 · 📋 复制模板 · ✏️ 必改
> 全程把 `<name>` 换成你的模块 id（如 `modeling` / `install` / `deploy`），小写下划线。

---

## 阶段 0 · 起手认知（~5 min）

- ☐ 读 [START_HERE.md](START_HERE.md) 第 0–1 节，看懂架构图 + zhgk 模块图
- ☐ Cursor / CC 打开本仓库，确认 [.cursorrules](../../.cursorrules) / [AGENTS.md](../../AGENTS.md) 已加载
- ☐ 选业务：先挑 **2–3 个 step** 的最简流程（验证范式，不求业务完整）
- ☐ 画出 step 链：`preflight → <step1> → <step2> → END`（**顺序即 DAG**）

## 阶段 1 · 搭骨架（~10 min）

- 📋 `agent/skills/_template/` → 复制为 `agent/skills/<name>/`
- 📋 `~/.claude/skills/_template/SKILL.md` → 复制为 `~/.claude/skills/<name>/SKILL.md`
- ✏️ **A 层 SKILL.md**：改 frontmatter `name` / `description`（关键词换你的业务，**决定召回**）+ 触发词 + 端点表（前缀 `/agent/<name>/`）+ **「后端节点」表**（逐行列出每个 `step.key`）
- ✏️ **B 层 skill.py**：`class <Name>Skill(BaseSkill)` → `name="<name>"` + `steps=[...]`；工厂 `get_<name>_skill()`
- ✏️ **B 层 steps/**：每个 step 一个文件，`class XxxStep(BaseStep)`：`key`（小写下划线）+ `name`（中文）+ `artifacts_pattern`
- ⚠️ **SKILL.md 节点表的 key 必须和 `step.key` 逐一对应**——否则 `lint_skill_contract` 阻断（双向校验）
- ⚠️ preflight 这类基础设施步设 `internal=True`，豁免契约 lint

## 阶段 2 · 填业务逻辑（按 step 数）

对每个 step：

- ☐ `check_inputs(ctx)` → 返回 `{ok, missing, found, note}`；`missing` 非空即触发 HITL
- ☐ `run(ctx, state, emit)` → 业务逻辑；`emit("日志")` 推 SSE；返回 `StepResult`（可带 `metrics`）
- ☐ LLM：`ctx.invoke_llm(messages, step_key=self.key)`（自动进 trace）—— **禁裸 import**
- ☐ 工具：`ctx.call_tool(name, params)` —— **禁绕过 registry**
- ☐ 跨 step 数据：写磁盘产物（`ctx.runtime_dir` / `ctx.output_dir`）+ 小字段进 `state` / `metrics`
- ⚠️ **`check_inputs` 的必填路径 = `run` 真正读的路径**，否则 HITL 清单漂移（[SKILL-DEVELOPMENT.md](../30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md) §9）
- ⚠️ 跨 step 别把大文件塞 `SkillState`，靠磁盘产物衔接
- ⚠️ HITL 是**软中断**：补料后默认 `full_restart`（新 `thread_id` 全流程重跑），别假设断点续跑

## 阶段 3 · 接入运行时（~5 min）

- ✏️ 注册：`agent/skills/__init__.py` → `registry.register("<name>", get_<name>_skill)`
- ✅ **FastAPI 端点 / graph 已泛化**（6.04）：`graph.py` 按 `skill_id` 经 registry 自动构图；`main.py` 端点为 `/agent/{skill}/*`。**注册后立即拥有** `/agent/<name>/start|stream|resume|status|ui|artifact|runs`，**无需改 main.py / graph.py**。
- ✏️ 按需在 `<Name>Skill` 上设运行时钩子（都可选，默认有合理行为）：
  - `step_retry_keys = [...]` — 哪些 step 支持仅重试（否则 HITL 一律 full_restart）
  - `file_handler = <module>` — 有文件补齐 HITL 时挂（提供 `infer_upload_kind`/`save_upload`/`check_need_files`/`check_project_files`）；不挂则 `/upload`·`/files/check` 返回 501
  - `initial_project(payload)` — start 请求体填默认值（可选）
- 📋 skill-as-tool（会话唤起）：`agent/tools/run_xxx.template.py` → 复制为 `run_<name>.py`，`execute` **只返回** `{action:"launch_<name>", ...}`，不在 execute 里跑图
- ✏️ `chat_engine` 识别 `action == "launch_<name>"` → yield 事件；前端进度卡复用 `SkillProgressCard`
- ✓ `curl http://127.0.0.1:7401/agent/skills` 能看到 `<name>` 元数据；`curl -X POST .../agent/<name>/start` 能起 run

### 阶段 3.5 · 界面（SDUI · 可选但推荐）

- 📋 `agent/skills/_template/sdui.py` → 复制改造（或照 [`zhgk/sdui.py`](../../agent/skills/zhgk/sdui.py)）：`project(state) -> dict`（七段式投影）
- ✏️ `skill.py` 里 `sdui_projector = staticmethod(project)`（**SSE 自动路由，无需改 main.py**）
- ⚠️ **投影器只能读 step 真写进 `metrics`/`state` 的键**——要展示的业务数据，step 必须写进去（别只落磁盘）→ 见 [SDUI §3.3 契约](../30_skill开发/31_手写规范/SDUI.md)
- ⚠️ HITL 上传走 `/upload/batch`，**不要** `/upload` + `kind=<purpose>`（会 500）
- ✓ `python -c "from agent.skills.<name>.sdui import project; print(project({}))"` 产出合法树；前端 `/module/<name>` 自动渲染

## 阶段 4 · 观测 + 评测（~5 min）

- ☐ 图执行配 `callbacks=get_langfuse_callbacks()` + `metadata` 带 `run_id`（走 `base.py` `build_graph` 默认即有）
- 📋 `agent/evals/eval_skill.template.py` → 复制为 `eval_<name>.py`；`fixtures/<name>-golden.json` 写 2–3 条断言
- ✏️ 断言用**阈值不用精确等值**（如 `completion_rate ≥ 0.5`），容忍波动、只抓塌方
- ✏️ `/evals` 前端 skill selector 加 `<name>` 选项
- ✓ `GET /agent/evals/report?skill=<name>&mode=latest` 有数据

## 阶段 5 · 验收（守门必须全绿）

- ✓ `python agent/scripts/lint_no_naked_llm.py`
- ✓ `python agent/scripts/lint_no_naked_send.py`
- ✓ `python agent/scripts/lint_skill_contract.py`（需 venv）
- ✓ `npm run eval`（四维评测回归闸）
- ✓ 端到端：`POST /agent/<name>/start` → 订阅 stream → 跑到 `done`，产物落 `ProjectData/Output/`
- ☐ 落库：非显然决策写 `decisions/` ADR；回填「定制清单」（改了底座什么、为什么）

---

## 一页速记：哪些复制、哪些必改

| 文件 | 操作 |
|------|------|
| `agent/skills/_template/` | 📋 复制 → ✏️ name / steps / 业务 |
| `~/.claude/skills/_template/SKILL.md` | 📋 复制 → ✏️ frontmatter + 节点表 |
| `agent/tools/run_xxx.template.py` | 📋 复制 → ✏️ action 名 |
| `agent/evals/eval_skill.template.py` | 📋 复制 → ✏️ 断言 |
| `agent/skills/__init__.py` | ✏️ 注册一行 |
| `agent/main.py` / `agent/graph.py` | ⚠️ 确认 / 泛化路由（pilot 对 zhgk 写死） |
| `chat_engine` / 前端 `/evals` selector | ✏️ 加 action / 选项 |
