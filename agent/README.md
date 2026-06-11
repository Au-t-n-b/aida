# AIDA Agent · SKILL + Langfuse 实现现状

> **范围**：智慧工勘（zhgk）作为 A+B 标准 SKILL pilot，已端到端跑通；所有 LLM 调用统一经 LangChain 抽象层，被 Langfuse 全量捕获。
> 后续业务场景 Skill（规划设计 / 设备安装 / 部署调测）按本模板复制。

---

## 一、SKILL 实现 · A+B 双层架构

### 1.1 设计理念


| 层                           | 位置                         | 职责                                                                                          | source of truth   |
| --------------------------- | -------------------------- | ------------------------------------------------------------------------------------------- | ----------------- |
| **A 层 · Claude Code Skill** | `~/.claude/skills/<name>/` | 给 Claude Code / LLM 路由用的「门面」：SKILL.md frontmatter（name + description + 触发词）+ references/ 文档 | ✅ **唯一真相**        |
| **B 层 · LangGraph 原生**      | `agent/skills/<name>/`     | 真正的执行代码：BaseSkill + BaseStep + run() 业务逻辑                                                   | 只放代码，不重复 metadata |
| **接缝**                      | `agent/skills/_loader.py`  | BaseSkill 启动时解析 A 层 SKILL.md frontmatter，注入 self.metadata.description                       | 同步靠代码、不靠人         |


### 1.2 核心文件布局

```
~/.claude/skills/zhgk/                          ← A 层
├── SKILL.md                                    （frontmatter: name/description/触发词）
└── references/                                 （流程参考文档）
    ├── scene-filter.md
    ├── survey-build.md
    ├── report-gen.md
    └── report-distribute.md

agent/skills/                                   ← B 层
├── __init__.py                                 SkillRegistry 启动注册
├── base.py                                     BaseSkill / BaseStep / SkillContext / SkillState
├── _loader.py                                  SKILL.md frontmatter 轻量 YAML 解析
├── _registry.py                                SkillRegistry · 渐进式暴露门面
└── zhgk/
    ├── skill.py                                ZhgkSkill 定义
    ├── prompts/__init__.py                     ASSESSMENT/RISK SYSTEM+USER 模板
    └── steps/                                  全部原生 Python（Phase 2 已去 subprocess）
        ├── preflight.py                        环境预检 + LLM 摘要
        ├── scene_filter.py                     BOQ 制冷匹配 + 底表过滤
        ├── survey_build.py                     多源勘测合并 + 待办表
        ├── report_gen.py                       LLM 评估 + 风险 + docx
        └── report_distribute.py                审批包 + 收件人筛选（邮件默认关）
```

### 1.3 关键抽象 · `BaseSkill` / `BaseStep`

[skills/base.py](skills/base.py)

- `**BaseSkill.__init__**`：自动读 A 层 SKILL.md frontmatter → `self.metadata`；description 覆盖类属性，保持单向同步
- `**BaseSkill.build_graph()**`：按 `steps: list[BaseStep]` 顺序自动生成 LangGraph，串行边 + 条件路由（HITL / error 出口）
- `**BaseSkill.execute_step()**`：统一 step 执行模板 —— 前置检查 → run → 收产物 → 返回 state diff
- `**BaseStep.run(ctx, state, emit)**`：业务子类必须实现
- `**SkillContext**`：注入路径 + LLM + run_id + project，避免每个 step 重复读 env

### 1.4 LLM 调用规范（强制）

只有 **3 个合法入口**：

```python
# 入口 1：单次调用 + 自动元数据（推荐 · 99% 场景）
ctx.invoke_llm(messages, step_key=self.key, run_name=..., kind="assessment")

# 入口 2：拿原生 ChatOpenAI（需要 stream / 特殊 config 时）
llm = ctx.llm; llm.invoke(...)

# 入口 3：脱离 SkillContext 时（FastAPI handler 等）
from agent.llm import chat_once, chat_stream
```

**任何其他方式都会被 lint 拦截**：

[scripts/lint_no_naked_llm.py](scripts/lint_no_naked_llm.py) 扫禁用模式：

- `from openai import` / `from anthropic import` / `import litellm`
- `from langchain_openai import`（除 `agent/llm.py` 白名单）
- `requests/httpx + chat/completions` URL
- `open.bigmodel.cn` 直打

挂在 `npm run prebuild` → 违规即 build 阻断。

### 1.5 渐进式暴露 · 路由层准备

[skills/_registry.py](skills/_registry.py)

```python
registry.register("zhgk", get_zhgk_skill)   # 启动只挂工厂引用
registry.list_metadata()                     # 只返回 name+description，不加载 step
registry.get("zhgk")                         # 真正实例化（含 SKILL.md 解析）
```

对外暴露：

- `GET /agent/skills` → 所有 skill 元数据（路由层 / 前端 picker 拿这份）
- `GET /agent/skills/{name}` → 单个 skill 详情（frontmatter + 正文摘要 + step 列表）

### 1.6 FastAPI 入口（[main.py](main.py)）

```
GET  /healthz                              健康检查 + LLM + Langfuse 状态
GET  /agent/skills                         渐进式暴露门面
GET  /agent/skills/{name}                  单 skill 详情
POST /agent/zhgk/start                     启动一次 run
GET  /agent/zhgk/stream/{run_id}           SSE 流式订阅
POST /agent/zhgk/resume                    HITL 续跑
POST /agent/zhgk/upload                    文件上传 (BOQ/presets/image)
GET  /agent/zhgk/status/{run_id}           当前状态快照
GET  /agent/zhgk/artifact?path=...         产物下载
GET  /agent/zhgk/runs                      run 列表
```

---

## 二、Langfuse 监控实现

### 2.1 接入点 · 极简

[llm.py](llm.py) 一个文件搞定：

```python
def _init_langfuse_once() -> list:
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sk = os.environ.get("LANGFUSE_SECRET_KEY")
    if not (pk and sk):
        return []                                 # 未配置 → 退化为无 trace（不阻断）
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    Langfuse(public_key=pk, secret_key=sk, host=...)
    return [CallbackHandler()]

def get_llm(temperature=0.2) -> ChatOpenAI:
    return ChatOpenAI(..., callbacks=_init_langfuse_once())   # 一次性挂上
```

**0 改动 skill 代码** —— 所有走 `ctx.llm.invoke()` / `ctx.invoke_llm()` 的调用都自动被捕获。

### 2.2 元数据流转 · 两级注入

**① Graph 顶层**（[main.py](main.py) `_run_graph_streaming`）

```python
config = {
    "configurable": {"thread_id": run_id},
    "callbacks": get_langfuse_callbacks(),       # 整个 run 共享一个 trace tree
    "metadata": {"skill", "run_id", "project_code", "project_name", "scenario"},
    "tags": [f"skill:{skill_id}", f"run:{run_id}"],
    "run_name": f"{skill_id}.run.{run_id}",      # 顶层 trace 名
}
async for chunk in graph.astream(init_state, config=config): ...
```

→ 整个 run 变成**一棵 trace 树**，LangGraph 自动把每个节点变成 child `CHAIN` span。

**② LLM 调用级**（[skills/base.py](skills/base.py) `SkillContext.invoke_llm`）

```python
def invoke_llm(self, messages, *, step_key, run_name=None, extra_metadata=None, extra_tags=None):
    config = {
        "metadata": {"skill", "step", "run_id", "kind", **extra_metadata},
        "tags": [f"skill:zhgk", f"step:report_gen", f"kind:{kind}"],
        "run_name": run_name or f"{skill_id}.{step_key}",
    }
    return self.llm.invoke(messages, config=config)
```

→ 每个 LLM 调用变成嵌套 `GENERATION` span，带 step/kind 标签。

### 2.3 定价配置

[scripts/langfuse_models.json](scripts/langfuse_models.json) · 当前 11 个模型：


| Model         | input ¥/1M | output ¥/1M | 备注                |
| ------------- | ---------- | ----------- | ----------------- |
| glm-4-flash   | 0.000      | 0.000       | 免费档               |
| glm-4-flashx  | 0.100      | 0.100       |                   |
| glm-4-air     | 0.500      | 0.500       |                   |
| glm-4-airx    | 10.000     | 10.000      |                   |
| glm-4-long    | 1.000      | 1.000       |                   |
| glm-4-plus    | 50.000     | 50.000      |                   |
| glm-4.5-air   | 0.800      | 2.000       | 推理                |
| glm-4.5       | 2.000      | 8.000       | 旗舰推理              |
| glm-5.1-flash | 0.000      | 0.000       | **占位**            |
| glm-5.1-air   | 1.000      | 3.000       | **占位**            |
| glm-5.1       | 4.000      | 12.000      | **占位**（reasoning） |


灌入命令：

```bash
python agent/scripts/langfuse_load_prices.py            # 跳过已存在
python agent/scripts/langfuse_load_prices.py --force    # 强制覆盖（改价时用）
```

### 2.4 已捕获的可观测维度

每次 `ctx.invoke_llm()` 后 Langfuse 自动持有：


| 维度          | 字段                                                             |
| ----------- | -------------------------------------------------------------- |
| Prompt 原文   | `input.messages[]`（system + human 全文）                          |
| Response 原文 | `output.content`（含 reasoning_tokens）                           |
| Model       | `model: glm-5.1`                                               |
| Token       | `usage.input / output / total`                                 |
| 成本          | `calculated_input_cost / output_cost / total_cost`（CNY）        |
| 延迟          | `latency`（秒）                                                   |
| 元数据         | `skill / step / kind / run_id / project_code / scenario`       |
| 标签          | `skill:zhgk / step:report_gen / run:run-xxx / kind:assessment` |
| 嵌套关系        | trace → CHAIN(step) → GENERATION(LLM)                          |


### 2.5 Dashboard 端能做的事


| 用法                | Langfuse 怎么做                                 |
| ----------------- | -------------------------------------------- |
| 看一次 run 完整链路      | tag 过滤 `run:run-xxx`                         |
| 按 step 拆延迟        | metadata filter `step = report_gen`          |
| 按 kind 拆成本        | tag filter `kind:risk`                       |
| 跨 run 看 skill 总成本 | metadata filter `skill = zhgk` + Aggregate   |
| 找慢调用              | sort by latency                              |
| 找解析失败的 prompt     | open trace → 看 response 原文                   |
| 模型切换前后对比          | filter by `model = glm-5.1` vs `glm-4-flash` |


### 2.6 关键代码改动总览


| 文件                                                                 | 角色                                                                                         |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| [llm.py](llm.py)                                                   | `_init_langfuse_once()` 单例 + `ChatOpenAI(callbacks=...)` + `get_langfuse_callbacks()` 对外导出 |
| [main.py](main.py)                                                 | `_run_graph_streaming` config 注入 graph 级 callbacks + metadata + tags                       |
| [skills/base.py](skills/base.py)                                   | `SkillContext.invoke_llm()` 助手 · LLM 级元数据                                                  |
| [skills/zhgk/steps/report_gen_run.py](skills/zhgk/steps/report_gen_run.py) | `_llm_json(kind=...)` 走助手；`kind="assessment"` / `"risk"`                                   |
| [skills/zhgk/steps/preflight.py](skills/zhgk/steps/preflight.py)   | 摘要调用走 `ctx.invoke_llm(kind="summary")`                                                     |
| [scripts/langfuse_models.json](scripts/langfuse_models.json)       | 11 个 GLM 模型定价                                                                              |
| [scripts/langfuse_load_prices.py](scripts/langfuse_load_prices.py) | 幂等灌价脚本（skip / `--force`）                                                                   |
| [.env](.env)                                                       | `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST`（gitignored）                |


### 2.7 实测数据 (run-0db8807e6d · glm-5.1)

```
顶层 trace      : zhgk.run.run-0db8807e6d
总成本          : ¥ 0.0249  (2.49 分)
总延迟          : 310.2 秒
CHAIN spans     : 11 (LangGraph 节点)
LLM 调用        : 11 次
Token 累计      : input=5559  output=8008
```

按 step.kind 拆：

```
preflight.summary           1 次  · 22.2s 平均  · ¥0.0023
report_gen.assessment       5 次  · 12.9s 平均  · ¥0.0045
report_gen.risk             5 次  · 42.5s 平均  · ¥0.0182   ← 最慢，prompt 含 1200 字现场数据
```

---

## 三、当前覆盖率 · 完整 vs 缺口


| 维度                       | 状态                                   |
| ------------------------ | ------------------------------------ |
| Skill 抽象（A+B）            | ✅ pilot 跑通（zhgk）                     |
| SKILL.md 单向同步            | ✅                                    |
| 渐进式暴露（registry）          | ✅                                    |
| 禁裸 LLM 调用 lint           | ✅                                    |
| LLM 调用 trace             | ✅ 全捕获                                |
| LangGraph 节点 span        | ✅ 自动嵌套                               |
| 元数据（skill/step/kind/run） | ✅                                    |
| 模型定价 + 成本                | ⚠️ glm-5.x 价是占位                      |
| **全 5 step 原生 + trace**  | ✅ scene_filter / survey_build / report_distribute 已去 subprocess，全部进 trace 树 |
| 持久化 checkpointer         | ✅ AsyncSqliteSaver（agent/runtime/checkpoints.db · 重启不丢） |
| 多 skill 路由 / Planner     | ❌（等第 2 个 skill 再说）                   |
| HITL trace               | ⚠️ 中断点本身有 span，但用户回复未关联              |
| 代发邮件                    | ⏸️ 默认关闭（ZHGK_SEND_EMAIL=1 才发；原 COM/VBScript 在本机失败，原生版待接 SMTP） |


**Phase 2 完成**：✅ AsyncSqliteSaver（run 重启不丢）；✅ scene_filter / survey_build / report_distribute 全部原生 Python 重写，去掉 subprocess —— 整条 pipeline 现在是一棵完整 LangGraph trace（11 CHAIN span 覆盖 5 个 step），无子进程黑盒。

> 邮件说明：原 subprocess 版用 Outlook COM / VBScript 自动发邮件，在本机因 ActiveX 不可用而失败。原生版默认**不发邮件**（代发邮件需显式授权），保留 `ZHGK_SEND_EMAIL=1` 开关，未来接 SMTP。

> ⚠️ **异步 checkpointer 注意**：FastAPI 用 `graph.astream()`（异步），必须走 `AsyncSqliteSaver`（[graph.py](graph.py) `get_graph_async()`）。
> 同步 `SqliteSaver` 不实现 `aget_tuple`/`aput`，在异步路径会 `NotImplementedError`，run 会卡在 init 不前进。

---

## 四、快速上手

### 4.1 启动

```bash
cd D:/code/aida
# 首次安装依赖
./agent/.venv/Scripts/pip.exe install -r agent/requirements.txt

# 启动 agent
./agent/.venv/Scripts/python.exe -m uvicorn agent.main:app --host 127.0.0.1 --port 7401
```

### 4.2 触发一次 run

```bash
curl -X POST http://127.0.0.1:7401/agent/zhgk/start \
  -H "Content-Type: application/json" \
  -d '{"project_id":"demo","project_name":"演示项目"}'

# 流式订阅
curl http://127.0.0.1:7401/agent/zhgk/stream/run-xxx

# 状态快照
curl http://127.0.0.1:7401/agent/zhgk/status/run-xxx
```

### 4.3 看 trace

打开 [https://cloud.langfuse.com](https://cloud.langfuse.com) → `traces` → 按 `run:run-xxx` 过滤。

### 4.4 改 LLM 模型

修改 `agent/.env`：

```
ZHIPU_MODEL=glm-5.1            # 或 glm-4-flash / glm-4.5 / ...
```

重启 agent 生效。

### 4.5 守门检查

```bash
python agent/scripts/lint_no_naked_llm.py     # 扫裸 LLM 调用
npm run prebuild                              # 包含上述检查 + ts-nocheck 守门
```

