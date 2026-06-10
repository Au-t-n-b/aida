# SKILL 开发规范（工程手册）

> 对应团队范式（[03](../../20_架构与范式/03_团队Agent开发范式.md)）：**§2 能力资产化**、**§4 HITL**、**§5 契约先行**、**§7 初始化清单**。  
> 铁律与 lint 见 [AGENTS.md](../../../AGENTS.md)；指标见 [evals/METRICS.md](../../40_评测/METRICS.md)。

---

## 1. 双层架构（A + B）

| 层 | 职责 | 位置 | 谁执行 |
|----|------|------|--------|
| **A** | 何时调用、触发词、业务 SOP、HTTP 约定 | `~/.claude/skills/<name>/SKILL.md` | Claude/Cursor Agent、文档 |
| **B** | 步骤实现、文件检查、LLM、落盘、LangGraph | `agent/skills/<name>/` | FastAPI + `uvicorn` |

**原则**：SKILL.md **不**直接跑 Python 脚本；执行走 `http://127.0.0.1:7401` 的 `/agent/<skill>/…`（工勘为 `/agent/zhgk/…`）。

---

## 2. 新建一个 Skill（检查清单）

```
□ A 层  ~/.claude/skills/<name>/SKILL.md（frontmatter: name, description + 触发词 + 端点表）
□ B 层  agent/skills/<name>/skill.py  → class XxxSkill(BaseSkill)
□ Steps agent/skills/<name>/steps/*.py → 每个 BaseStep 子类
□ 注册  agent/skills/__init__.py → registry.register("<name>", get_<name>_skill)
□ 图    ✅ 自动：graph.py 按 skill_id 经 registry 构图；端点 /agent/{skill}/* 已泛化（注册即得）
□ 钩子  按需在 XxxSkill 设 sdui_projector / step_retry_keys / file_handler / initial_project
□ 契约  CONTRACT.md + 前端 types（有读模型时）
□ 界面  agent/skills/<name>/sdui.py（投影器 project(state)→UI 树）→ 见 SDUI.md
□ 守门  lint_skill_contract.py（SKILL.md「后端节点」列 ↔ steps[].key）
□ 评测  evals/fixtures/<name>-golden.json + eval_<name>.py
□ ADR   非显然决策进 decisions/
```

---

<a id="skill-basestep"></a>

## 3. BaseStep 必实现

```python
class MyStep(BaseStep):
    key = "my_step"           # LangGraph 节点 ID，小写下划线
    name = "中文显示名"
    artifacts_pattern = [     # 相对 work_root 的产物路径（可选）
        "ProjectData/Output/xxx.xlsx",
    ]
    internal = False          # True = 基础设施步（如 preflight），豁免部分契约 lint

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        # 返回 ok / missing / found / note
        # missing 项进入 hitl.need_files

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        # emit("日志") → state.logs → SSE
        # LLM: ctx.invoke_llm(messages, step_key=self.key)  禁止裸 openai；自动带 skill/step tag 进 trace
        # 文件: ctx.start_dir / input_dir / runtime_dir / output_dir
```

**执行模板**（勿绕过）：所有节点由 `BaseSkill.execute_step()` 统一调用：

1. `check_inputs` → 失败则返回 `hitl` + `steps` 记录 `status=hitl` → 图路由 **END**
2. 成功则 `run()` → 成功时 **`hitl: {}` 清空**

---

## 4. 文件工作区（ZHGK_ROOT）

- 环境变量：`agent/.env` 中 `ZHGK_ROOT=<工作区根>`（如桌面 `zhgk-desktop`）。
- 子目录：`ProjectData/{Start, Input, RunTime, Output, Images}`。
- 初始化：`python agent/scripts/init_zhgk_workspace.py --dest ... --copy-start-full --copy-tools`。

**跨 step 衔接靠磁盘产物**，不是把大文件塞进 `SkillState`。

---

<a id="skill-hitl"></a>

## 5. HITL（人在回路）

### 5.1 中断机制（软中断）· 两种形态

- **不是** LangGraph 原生 `interrupt()`。`check_inputs` 返回 `ok=False` → `execute_step` 写 `hitl` → 条件边 → **END**；前端补齐后 `/resume` 续跑。
- 详见 ADR [0001-resume-soft-interrupt-rerun](../../90_决策ADR/0001-resume-soft-interrupt-rerun.md)。

| 形态 | check_inputs 返回 | 投影成 | 用户操作 | 续跑通道 | 样板 |
|------|-------------------|--------|---------|---------|------|
| **文件型** | `missing=[...]`（非空） | `FilePicker` | 上传文件 | `/upload/batch` → `/resume` | zhgk `scene_filter` |
| **确认型** | `missing=[]` + `need_inputs=[...]` | `ChoiceCard` | 选一项 | `/resume`（payload `{"choice": value}`） | guihua `device_confirm` |

**确认型 HITL（`need_inputs`）契约**（类型见 [base.py](../../../agent/skills/base.py) `NeedInput` / `NeedInputOption`）：

```python
# step.check_inputs：未确认时返回确认门（missing 必须为空，否则被当文件型）
def check_inputs(self, ctx):
    if (ctx.project.get("confirmations") or {}).get("device"):
        return {"ok": True, "missing": [], "found": ["confirmations.device"]}
    return {"ok": False, "missing": [], "note": "请核对设备清单后继续",
            "need_inputs": [{
                "id": "device", "label": "确认设备清单",
                "options": [                       # ⚠️ 选项必须是 dict（含 value），不要用裸 str
                    {"label": "确认无误", "value": "confirm"},
                    {"label": "重新提取", "value": "redo"},
                ]}]}
```

- 投影器（`sdui.py`）**统一用** `agent.sdui.builder.choice_options(options)` 构造 ChoiceCard，别自己拼 `SduiChoiceOption`（历史上 zhgk 按 str、guihua 按 dict 读，撞过 value 漂移 bug；`lint_sdui_contract` 不查这层，靠本约定 + `choice_options` 兜底）。
- 用户选择经 `/resume` 以 `{"choice": value}` 回传，由 `XxxSkill.apply_resume_payload(project, payload, hitl_step)` 写进 `project`（如 `project["confirmations"]["device"]=True`）。因 `full_restart` 重跑保留 `project`，确认状态跨重跑存活，下次 `check_inputs` 据此放行。参考 `GuihuaSkill.apply_resume_payload`。
- ⚠️ 确认型 HITL 必须走 `full_restart`（默认）。**不要**把确认门 step 放进 `step_retry_keys`——`step_retry` 路径不调 `apply_resume_payload`，确认会丢。

### 5.2 补料 API（工勘 zhgk）

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/agent/zhgk/files/check?need=`（可多次） | 按 **当前 need_files** 逐项检查；无 need 时查 scene_filter 五件套 |
| POST | `/agent/zhgk/upload/batch` | 多文件 + 表单 `need`（与 HITL 清单一致） |
| POST | `/agent/zhgk/resume` | 补料后续跑 |

**upload kind**（`zhgk_files.infer_upload_kind`）：`boq` | `presets` | `personnel` | `image` | `start`  
- `personnel` → 固定 `Start/远近一体化人员信息.xlsx`（本地文件名可不同）。

### 5.3 续跑语义（resume）

| `resume.mode` | 何时 | 行为 |
|---------------|------|------|
| `full_restart` | 默认（scene_filter、report_gen、**确认型 HITL** 等） | 干净 `init_state` + 新 `thread_id`，**从预检重跑全流程**；重跑前调 `apply_resume_payload` 把用户回复并入 `project` |
| `step_retry` | `report_distribute` HITL | **仅重试该步**，不重跑 report_gen LLM；⚠️ 不调 `apply_resume_payload`，故不可与确认型 HITL 同用 |

请求体可带 `from_step: "report_distribute"`；响应含 `mode` / `message` 供前端展示。

### 5.4 前端契约（frontend/）

- 进度卡（会话内）：`ZhgkProgressCard` → `start` + SSE `stream/{run_id}`。
- 作业界面（全屏）：**SDUI 投影器**驱动，HITL 卡（FilePicker/ChoiceCard）由后端 `sdui.py` 产出，前端通用渲染。见 [SDUI.md](SDUI.md)。
- HITL 上传走 **`/upload/batch`**（按文件名推断 kind）；**禁止** `/upload` + `kind=<purpose>`（purpose 非合法 kind，会 500）。
- HITL 清单用 **`hitl.need_files`** 调 check/upload，**禁止**用五件套检查冒充 Step4 缺失项。
- 齐备后再 resume；resume 重跑会重新校验 `check_inputs`，是真正的门禁（不自动 resume，避免只传部分文件误推进）。

---

## 6. skill-as-tool（会话唤起）

长流程 **不得**在 `Tool.execute()` 里跑 LangGraph（会阻塞、无 SSE）。

**标准模式**（`run_survey`）：

1. 工具返回 `{ action: "launch_zhgk", steps: [...], project_code, ... }`。
2. `chat_engine` yield `skill_launch`。
3. 前端调 `/agent/zhgk/start` + 订阅 stream。

新增 Skill 时：复制该模式，改 `action` 名与前端事件处理。

---

## 7. 可观测

- LangGraph `astream` config：`callbacks=get_langfuse_callbacks()`，`metadata` 含 `run_id` / `project_code`。
- 节点 = CHAIN span；`ctx.llm` = GENERATION span。
- Step 内工具：`ctx.call_tool` → `execute_traced`（`metadata.kind=tool`）。

---

## 8. 守门命令

```bash
python agent/scripts/lint_no_naked_llm.py     # 禁裸 LLM 调用
python agent/scripts/lint_no_naked_send.py    # 禁裸外发
python agent/scripts/lint_skill_contract.py   # SKILL.md「后端节点」列 ↔ step.key（需 venv）
python agent/scripts/lint_tools.py            # 工具 name/desc/schema 契约（需 venv）
python agent/scripts/lint_sdui_contract.py    # SDUI 协议三方一致 builder↔sdui.ts↔NodeView（需 venv）
```

---

## 9. 反模式（不要做）

- ❌ subprocess 调旧 nanobot 脚本规避 LLM 规范（应 Python 化 Step）
- ❌ 在 Step 里写与 `check_inputs` 不一致的必填路径（导致 HITL 清单漂移）
- ❌ 假设 resume 从当前 step 断点续跑（除非已实现 `step_retry`）
- ❌ SKILL.md 写了后端节点但 Python 未注册同名 `step.key`（`lint_skill_contract` 会拦）

---

## 10. 参考实现

- Skill 组装：`agent/skills/zhgk/skill.py`
- Steps：`agent/skills/zhgk/steps/*.py`
- 编排：`agent/graph.py`、`agent/skills/base.py` `build_graph()`
- HTTP：`agent/main.py`
- 文件检查/上传：`agent/zhgk_files.py`

---

## 11. 多意图路由 · 两种模式选型指南

当同一个 Skill 需要支持多条可选业务流时，有两种范式。**选错范式会让代码难以维护**。

### 11.1 Intent-guard 单线 Pipeline（zhgk 模式）

**适用**：多条业务流之间有**共享步骤**（如「全流程」和「报告生成」都需要 assess + issue_list）。

**机制**：所有步骤统一注册在一条 15 步 Pipeline 里，每步开始时调 `should_skip()` 检查当前 intent 是否允许该步骤执行；不允许则直接 `return {}`（0 成本跳过）。

```
Pipeline: preflight → intent_select → [A] → [B] → [C] → [D] → ...
                                                            ↑
                      _intent_guard.STEP_INTENTS 决定每步对哪些 intent 开放
```

**文件布局**：
```
agent/skills/<name>/steps/
  _intent_guard.py       # STEP_INTENTS dict + should_skip()
  preflight.py
  intent_select.py       # HITL：让用户选 intent；写进 project["intent"]
  step_a.py              # 开头 if should_skip(self.key, ctx.project): return {}
  ...
```

**关键约定**：
- `intent_select` 是 HITL，选项写进 `project["intent"]`（经 `apply_resume_payload` 落 project）
- `project["intent"]` 跨 `full_restart` 存活（project 整体被保留）
- SDUI 投影器可据 intent 过滤 Stepper 步骤（`_build_intent_step_names()` 模式，见 zhgk sdui.py）

**何时换到 dispatch_mode**：若各意图的步骤**没有任何共享**，且每次只需跑几步，改用 §11.2。

---

### 11.2 Dispatch 模式（xtsj 模式）

**适用**：每次用户消息只触发**一条命令**（无状态、命令驱动），步骤集之间无共享。

**机制**：`dispatch_mode = True` 使图只跑 `project["command"]` 对应的一组步骤（`COMMAND_STEPS` 表），完成即 END，不保留跨命令状态。

```python
# agent/skills/<name>/skill.py
class XtsjSkill(BaseSkill):
    dispatch_mode = True   # 每次 run 只跑 project["command"] 对应的 steps
    ...

COMMAND_STEPS: dict[str, list[str]] = {
    "input_check":  ["input_check"],
    "address_plan": ["address_plan"],
    ...
}
```

**SDUI** 投影器按 `project["command"]` 切换视图（见 `agent/skills/xtsj/sdui.py`）。

---

### 11.3 决策矩阵

| 问题 | Intent-guard | Dispatch |
|------|-------------|---------|
| 各流程有共享步骤 | ✅ 天然复用 | ❌ 要重复注册 |
| 每次只跑一条命令 | 可以（跳过无关步骤） | ✅ 更简洁 |
| 需要「全流程」串联 | ✅ 15 步单流水线 | ❌ 要手动串 |
| Stepper 意图过滤 | ✅ `_build_intent_step_names()` | 无（per-command 视图） |
| HITL 多轮（补料→重跑→复勘） | ✅ `apply_resume_payload` 跨重跑存活 | 不适用（无状态） |

---

## 12. file_handler 钩子接口（文件型 HITL）

`BaseSkill.file_handler` 设为一个 Python 模块（`agent/skills/<name>/xxx_files.py`），该模块需实现 **4 个函数**。不设 `file_handler` 时 `/upload` 端点返回 501。

### 12.1 接口签名

```python
# agent/skills/<name>/<name>_files.py

def infer_upload_kind(filename: str) -> str:
    """从文件名推断 upload kind（用于 /upload/batch 多文件路由）。
    返回字符串，如 "boq" / "survey_result" / "report_template"。
    未匹配时返回 "other"（不要 raise）。"""
    ...


def save_upload(kind: str, src_path: str, work_root: str) -> str:
    """把已写入临时目录的文件 src_path，按 kind 移动到正确的工作区目录。
    返回目标绝对路径（写入 state.files[kind]）。
    同 kind 多次上传覆盖旧文件。"""
    ...


def check_need_files(need_list: list[str], work_root: str) -> tuple[list[str], list[str]]:
    """检查 HITL need_files 清单中哪些已上传、哪些仍缺失。
    返回 (found: list[str], missing: list[str])。"""
    ...


def check_project_files(work_root: str) -> tuple[list[str], list[str]]:
    """检查「全量启动文件」（不依赖 HITL need_files，供 /files/check 端点用）。
    返回 (found: list[str], missing: list[str])。"""
    ...
```

### 12.2 接入方式

```python
# agent/skills/<name>/skill.py
from . import <name>_files as _files

class XxxSkill(BaseSkill):
    file_handler = _files    # 挂钩子，main.py /upload/batch 自动路由到 _files.infer_upload_kind / save_upload
```

### 12.3 参考实现

- `agent/zhgk_files.py`（zhgk，含 infer_upload_kind / save_upload / check_need_files / check_project_files）
- HITL 上传必须走 `/upload/batch`，**不要**用 `/upload` + `kind=<purpose>`（purpose 非合法 kind → 500）。
