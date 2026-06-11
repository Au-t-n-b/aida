# AIDA 运行时契约 · 供 Skill→LangGraph 流水线对齐

> **用途**：给 Skill2LangGraph 流水线（SkillIR → Graph → AIDA-compatible Harness）提供 **AIDA 真实的 provider 与工具运行时契约**。
> 设计文档里的 `ProvidedLLM` / `call_tool 链路` / `AidaCompatibleState` 多为「推荐/假设接口」；**本文给真身 + 标注需校正的差异**，Harness、契约测试、Graph 生成都应以本文为准。
> **权威源码**：`agent/llm.py`（provider）、`agent/tools/`（工具运行时）、`agent/skills/base.py`（SkillContext / SkillState / build_graph）。

---

<a id="runtime-cheatsheet"></a>

## 0. 一页速查 · 设计文档需校正的 5 点

| # | 设计文档 | AIDA 真身 | 校正动作 |
|---|---------|----------|---------|
| 1 | `ProvidedLLM.invoke(..., output_schema) -> dict` | 无 `output_schema`、无原生结构化输出；返回 LangChain `AIMessage`（取 `.content`） | 结构化输出在**适配器层**实现（prompt 注入 schema + `json.loads`），不要假设 provider 原生支持 |
| 2 | `invoke(skill_id, step_key, run_id)` 三参 | `skill_id`/`run_id` 由 `SkillContext` **构造时绑定**，`invoke_llm` 只传 `step_key` | ProvidedLLM 适配器持有 `skill_id`/`run_id`，对外只暴露 `step_key` |
| 3 | 工具失败 = 抛异常 | 工具失败**不抛**，返回 `"Error: ..."` 字符串 + 自纠提示；`execute` **同步** | 稳定性验证「工具成功」= 结果**不以 `Error` 开头** |
| 4 | HITL ≈ `interrupt()` | **软中断**：`check_inputs` 失败→`hitl` diff→router→`END`；resume 另起 run | 契约「human gate→HITL」按软中断 + END + resume 建模，**不是** `interrupt()` |
| 5 | allowed tools 开放 | `DEFAULT_TOOLS` 现 **7 个**内置工具 | SkillIR `allowed_tools` 从 7 个里选，或要求同事新增 `Tool` 子类 |

---

## 1. Provider 契约（LLM）

### 1.1 真身（`agent/llm.py`）
- 底层：`langchain_openai.ChatOpenAI`，接智谱 BigModel（OpenAI 兼容协议）。
- 配置（`agent/.env`）：`ZHIPU_API_KEY` / `ZHIPU_BASE_URL`(默认 `https://open.bigmodel.cn/api/coding/paas/v4`) / `ZHIPU_MODEL`(默认 `glm-4.5`，实测常用 `glm-4-flash`)。
- 单例：`get_llm(temperature=0.2)` 复用同一 `ChatOpenAI`（`timeout=60`, `max_retries=2`, `callbacks=Langfuse`）。
  - ⚠️ **单例副作用**：temperature 在首次创建后固定；不同 node 想要不同 temperature，当前单例**不支持**——Harness 若需 per-node temperature，要绕开 `get_llm` 单例。
- 三个合法入口：
  ```python
  ctx.invoke_llm(messages, *, step_key="", run_name=None, extra_metadata=None, extra_tags=None)  # 推荐
  ctx.llm.invoke(messages, config=...)        # 需 stream / 自定义 config
  from agent.llm import chat_once, chat_stream # 脱离 ctx 时（FastAPI handler）
  ```

### 1.2 `SkillContext.invoke_llm` 真实语义（Graph node 调模型的标准姿势）
```python
# skill_id / run_id 来自 ctx（构造时绑定）；invoke 只关心 step_key + 可选元数据
resp = ctx.invoke_llm(
    messages,                 # LangChain 格式：[("system", "..."), ("human", "...")] 或 BaseMessage[]
    step_key="report_gen",    # 进 Langfuse 的 step 标签
    extra_metadata={...},     # 可选
    extra_tags=[...],         # 可选
)
text = resp.content           # ★ 返回 AIMessage，不是 dict；文本在 .content
```
内部自动构造 `config = {metadata:{skill,step,run_id,...}, tags:["skill:x","step:y"], run_name:"x.y"}` → Langfuse 据此聚合（按 skill 看成本 / 按 step 看延迟 / 按 run_id 反查链路）。

### 1.3 给同事的 `ProvidedLLM` 适配指引
你的 `ProvidedLLM` 应是 `ctx.invoke_llm` 的**镜像**，差异处理：
- **结构化输出**：AIDA 无原生 `output_schema`。两种落地：
  1. （推荐，与 AIDA 现状一致）适配器在 prompt 里注入「请只输出符合此 JSON Schema 的 JSON」+ 调用后 `json.loads` 解析 + 失败重试；
  2. 或用 LangChain `llm.with_structured_output(schema)`（AIDA 当前**未用**，引入需评估）。
  → 契约测试「provided LLM 输出符合 schema」校验的是**适配器解析后**的结果，不是 provider 原生。
- **返回类型**：AIDA 返回 `AIMessage`。若你的 `invoke` 要 `-> dict`，适配器自己包：`{"content": resp.content, "raw": resp}`。
- **元数据绑定**：`skill_id`/`run_id` 在适配器构造时持有；`invoke` 对外只收 `step_key`（对齐 ctx 语义）。
- **trace**：复用 `get_langfuse_callbacks()`，把 callbacks 挂到 ChatOpenAI，model call evidence 自动进 Langfuse。

---

## 2. 工具运行时契约

### 2.1 调用链路（设计文档此处**正确**，补真实签名）
```
ctx.call_tool(name, params, *, step_key, emit)        # SkillContext 方法；scope = skill_id
  → execute_traced(DEFAULT_TOOLS, name, params, *, scope, step, run_id, conv_id, emit)
      → ToolRegistry.execute(name, params)
          → tool.cast_params → tool.validate_params → tool.execute(**params)
      → 尽力创建 Langfuse span(tool/params/result/latency) + 写 session_tool_log
```

### 2.2 `ToolRegistry.execute` 语义（**最关键**：错误不抛）
```python
def execute(name, params) -> Any:
    # 工具不存在 → 返回 "Error: 工具 'x' 不存在。可用：..."
    # 参数不合法 → 返回 "Error: ... 参数不合法：... [换一种方式重试]"
    # 执行抛异常 → 捕获，返回 "Error executing x: ..."
    # 成功 → 返回 tool.execute 的结果（字符串或结构化）
```
→ **工具永不向上抛异常**；失败回流：str 工具用 `ToolError` / `"Error..."` 文本，dict 工具用 `{ok:False, error}`（均供模型自纠）。
→ 稳定性验证判定：`ok = not is_tool_error(result)`（`tools/base.py` 统一契约，registry / trace / 评测共用；dict 工具看 `ok`/`error`，str 工具看 `Error` 前缀）。

### 2.3 `Tool` 基类契约（同事新增工具 / Graph 生成 tool node 时遵循）
```python
class Tool(ABC):
    name: str            # function-call 工具名（小写下划线，全局唯一）
    description: str     # 给模型看，决定召回
    parameters: dict     # JSON Schema（type/enum/min(max)imum/min(max)Length/required/嵌套/nullable）
    def execute(**kwargs) -> Any   # ★ 同步
    # 框架提供：cast_params(参数安全转换 "5"→5) / validate_params(→错误列表) / to_schema(→OpenAI function)
```
支持的 JSON Schema 类型：`string/integer/number/boolean/array/object` + nullable（`["string","null"]`）。

### 2.4 `DEFAULT_TOOLS` 真实清单（9 个）
| name | 用途 | 备注 |
|------|------|------|
| `read_file` | 读文件 | 参数 `path` + `max_bytes` |
| `send_mail` | 邮件 | 走 `mailer.py`，默认 **dry-run** + 留痕 |
| `send_welink` | IM 消息 | 走 `notifier.py`，默认 dry-run |
| `present_choices` | 发信/发IM前向用户确认 | chat_engine 拦截，**不真执行**（HITL 选择点） |
| `run_survey` | skill-as-tool：会话唤起 zhgk | 把 Skill 当高阶工具 |
| `doc_read_xlsx` | 读 Excel 工作表 | 返回 CSV / JSON；错误回 `Error:` 前缀，依赖缺失优雅降级 |
| `doc_write_docx` | 写 Word 文档 | Markdown → docx |
| `web_fetch` | 抓取 URL 正文 | httpx 代理感知，regex 去 HTML，截 8 KB；`Error:` 前缀失败 |
| `web_search` | DuckDuckGo Lite 搜索 | 无 API key，解析结果列表；`Error:` 前缀失败 |
> 未进 DEFAULT_TOOLS：`zhgk_bridge`（zhgk 专用）、`run_xxx.template`（skill-as-tool 模板）。
> **白名单**：`registry.get_definitions(allowed=[...])` 给受控子任务限定工具集——对应 SkillIR 的 `allowed_tools`。

---

## 3. State 契约

### 3.1 `SkillState`（设计文档 `AidaCompatibleState` 与此**高度一致** ✓，补 reducer）
```python
class SkillState(TypedDict, total=False):
    run_id: str; skill_id: str; started_at: str; project: dict
    steps: Annotated[list[StepRecord], add]   # ★ reducer 累加（node 返回 diff 会被 append，不是覆盖）
    logs:  Annotated[list[str], add]          # ★ 同上
    current_step: str; overall_progress: int
    files: dict; hitl: HitlRequest; hitl_resume: dict
    metrics: dict; error: str
```
→ **Graph 生成关键**：node 返回的是 **state diff**；`steps`/`logs` 走 `operator.add` reducer 累加。契约测试「state schema 兼容」要校验 node 写入符合此结构 + reducer 语义。

### 3.2 `StepRecord` / `StepStatus`
```python
StepStatus = "pending" | "running" | "completed" | "failed" | "hitl"
StepRecord = {key, name, status, started_at, ended_at, progress, artifacts, log_tail, error, metrics}
```

---

## 4. HITL 契约（软中断，非 `interrupt()`）

```python
# 机制：step.check_inputs(ctx) 返回 {ok:False, missing:[...]} → BaseSkill.execute_step 产出：
state["hitl"] = {"step": "...", "reason": "...", "need_files": [...], "need_inputs": [...]}
# → router 见 hitl.step 非空 → 路由到 END（软中断，不是 LangGraph 原生 interrupt()）
```
- **resume**：默认 `full_restart`（新 `thread_id` 全流程重跑）；个别 step 支持 `step_retry`（仅重试该步）。见 ADR `0001-resume-soft-interrupt-rerun`。
- 契约测试「human gate → AIDA-compatible HITL」应验证：guard 失败时产出上述 `hitl` 结构 + 图终止于 END，**而非** interrupt 挂起。

---

<a id="runtime-graph"></a>

## 5. Graph 构建契约（`BaseSkill.build_graph`）

同事 Graph 生成 / GraphSpec 编译器要对齐的真实建图行为：
```
- StateGraph(SkillState)
- 每个 step → 一个 node；node 内每次 invoke 重建 SkillContext(run_id, project 来自 state)，调 execute_step(step, state, ctx)
- 边：START → steps[0]；每个 step 用 add_conditional_edges(router) 决定 → 下一 step / END
- router：state.error 非空 → END；state.hitl.step 非空 → END；否则 → next_step
- execute_step 模板：check_inputs → (失败→hitl diff) / run(ctx,state,emit) → 收 artifacts → completed/failed diff
- checkpointer：FastAPI 用 AsyncSqliteSaver（异步必须）；CLI/测试可 MemorySaver；默认同步 SqliteSaver
```
> **GraphSpec → 编译器**思路（设计文档会话 C 建议）与此**契合**：把 SkillIR 的 step/依赖/guard/gate 编译成「node + conditional_edges + check_inputs」即可，不必让 Codex 直接写 Python。

---

## 6. 给四个 Codex 会话的输入补充建议

| 会话 | 设计文档输入 | 建议补充（来自本契约） |
|------|------------|---------------------|
| A · SkillIR | schema + 抽取规则 | `allowed_tools` 取值域 = §2.4 的 9 个工具名（或显式声明"需新增 Tool"）；`provided LLM 节点要求`注明无 output_schema |
| C · Graph | Graph contract | 注入 §3.1 SkillState（含 reducer）+ §5 建图契约 + §4 软中断 HITL 表达 |
| D · 契约测试 | SkillIR | 校验项对齐：node 返回 diff（非覆盖）、工具成功=非 Error 字符串、HITL=软中断+END |
| Harness | — | provider 用 §1.3 适配器；工具走 §2.1 真实链路；稳定性判定用 §2.2 / §1.3 |

---

## 版本
| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-04 | 初版：从 llm.py + tools/ + skills/base.py 提取真实 provider/工具/state/HITL/建图契约，标注与 Skill2Graph 设计文档的 5 处差异校正 |
| v1.1 | 2026-06-05 | §2.4 工具清单 5→7（补 `doc_read_xlsx`/`doc_write_docx`）；§2.2 判定 = `is_tool_error`；新增 `lint_runtime_contract` 守门防漂（契约≡代码） |
| v1.2 | 2026-06-06 | §2.4 工具清单 7→9（补 `web_fetch`/`web_search`）；同步 §6 工具数量引用 |
