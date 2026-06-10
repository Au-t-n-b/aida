# 工具（Tool）开发规范（工程手册）

> 对应团队范式（[03](../../20_架构与范式/03_团队Agent开发范式.md)）：**§3 工具规范**、**§6 评测（工具维）**。  
> 铁律见 [AGENTS.md](../../../AGENTS.md)；指标见 [evals/METRICS.md](../../40_评测/METRICS.md) §4。

---

## 1. 原则

- 每个能力 = 一个 **`Tool` 子类**，进 **`ToolRegistry`**，会话与 Step 共用。
- 参数必须 **JSON Schema**；调用必须 **`execute_traced`**（进 Langfuse）。
- **description 质量 = 召回质量**；差描述 → 高 **自纠率**（评测核心信号）。

---

## 2. 最小实现

```python
from agent.tools.base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"  # 全局唯一，小写下划线

    @property
    def description(self) -> str:
        return "给模型看的：何时调用、输入/output 语义、边界。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "..."},
            },
            "required": ["path"],
        }

    def execute(self, path: str, **kwargs) -> dict:
        # 返回 JSON 可序列化结构；错误用 {"ok": False, "error": "..."}
        ...
```

基类还提供：`cast_params`、`validate_params`（失败返回模型可自纠的文案）、`to_schema()`。

### 2.1 返回与成败契约（统一）

execute() 返回两种合法形态，**失败必须可被 `is_tool_error` 识别**（registry 受控执行、trace 可观测、评测成功率都靠它判定，不再猜字符串前缀）：

| 返回形态 | 成功 | 失败 |
|---------|------|------|
| **字符串工具**（read_file / doc_*） | 正文文本 | `ToolError("原因")` —— 自动补 `Error:` 前缀，继承 `str` 向后兼容 |
| **结构化工具**（run_survey / send_*） | `{"ok": True, ...}` | `{"ok": False, "error": "原因"}` |

```python
from agent.tools.base import Tool, ToolError

def execute(self, path: str, **kw) -> str:
    if not Path(path).is_file():
        return ToolError(f"文件不存在：{path}")   # ✅ 显式失败 → trace 记 ok=False
    return Path(path).read_text("utf-8")          # 成功正文
```

> ⚠️ **dict 工具失败务必置 `ok=False` 或 `error`**：否则 `is_tool_error` 视其为成功，把失败计入成功率、漏掉自纠信号（历史 bug：`run_survey` 返回 `{ok:False}` 却被 trace 记成功）。
> 裸 `return "Error: ..."` 字符串仍兼容，但**新工具用 `ToolError`**（类型显式，未来可加 lint）。

---

## 3. 注册与白名单

| 类型 | 注册位置 | 暴露范围 |
|------|----------|----------|
| **会话通用工具** | `tools/__init__.py` → `DEFAULT_TOOLS` | 所有 ReAct 聊天 |
| **业务专用工具** | Skill 内局部 `allowed=[...]` | 仅该子任务 |

**受控 ReAct**：`get_definitions(allowed)` 只暴露白名单，避免工具污染召回。

**命名建议**（[03 范式](../../20_架构与范式/03_团队Agent开发范式.md) §3）：能力域前缀 `fs_` / `doc_` / `mail_` / `survey_` …，降低重名。

---

## 4. 调用链与 trace

```
chat_engine / BaseStep
    → execute_traced(tool, args, trace_meta={...})
        → Tool.execute(...)
```

**metadata 约定**（评测按此过滤）：

| 字段 | 含义 |
|------|------|
| `kind` | `"tool"` |
| `scope` | `"chat"` / `"step"` |
| `conv_id` | 会话多轮对齐 |
| `run_id` | 工勘 run 对齐 |

无 Langfuse 时：`session_tool_log` 写 `evals/results/session_logs/{conv_id}.jsonl`。

---

## 5. skill-as-tool（高阶工具）

用于「聊着把 Skill 跑起来」，**不**在 execute 里跑图。

| 工具 | action | 后续 |
|------|--------|------|
| `run_survey` | `launch_zhgk` | 前端 `skill_launch` → `/agent/zhgk/start` + SSE |

模板：`agent/tools/run_survey.py`

新增 Skill 唤起工具：

1. `execute` 返回 `ok`, `action`, `skill`, `steps`, 项目参数。
2. 在 `chat_engine` 识别 `action` 并 yield 对应事件。
3. 前端增加进度卡与 API 订阅。

---

## 6. 副作用

- **邮件 / 外发**：走 `mailer.py` / `notifier`，默认 dry-run。
- **写文件**：Skill Step 写 `ZHGK_ROOT`；通用读文件用 `read_file` 等工具，勿裸 SMTP。

**🚪守门**：`lint_no_naked_send.py` ✅；`lint_no_naked_llm.py` 覆盖工具内 LLM。

**🚪守门（已补）**：`lint_tools.py`（name/desc/schema 契约 + 孤儿检测，挂 prebuild）✅。

---

## 7. 工具评测（已落地）

| 指标 | 含义 | 优化信号 |
|------|------|----------|
| **自纠率** ⭐ | validate 失败 → 模型重试 | 高 → 改 description/schema |
| 成功率 | execute 未失败（`is_tool_error` 判定） | 低 → 实现不稳 |
| p50/p95 | 耗时 | 高 → 优化实现 |
| 调用热度 | 次数 | 指导优先改哪个工具 |

- 脚本：`agent/evals/eval_tools.py`
- 基线：`BASELINE`（自纠率 ≤ 0.30、成功率 ≥ 0.70 等）
- 界面：`/evals` 工具 tab，`?mode=latest|overview`
- 导出：`export_deviations.py` → `cursor-tools-*.md`

---

## 8. 新增工具检查清单

```
□ 继承 Tool，name 全局唯一
□ description 写清「何时用 / 不用」
□ parameters 完整 JSON Schema（required 准确）
□ 注册 DEFAULT_TOOLS 或文档说明仅局部 allowed
□ execute 失败可被 is_tool_error 识别（str 工具用 ToolError，dict 工具置 ok=False/error）
□ 经 execute_traced 调用（会话侧已统一）
□ 手测 + 看 /evals 工具 tab 自纠率
□ 若影响 golden：更新 fixtures/tools-golden.json
```

---

## 9. 当前默认工具（pilot）

见 `agent/tools/__init__.py`：`read_file`, `send_mail`, `send_welink`, `present_choices`, `run_survey`, `doc_read_xlsx`, `doc_write_docx`（共 7 个）。

---

## 10. 参考

- 基类：`agent/tools/base.py`
- 注册：`agent/tools/registry.py`
- Trace：`agent/tools/trace.py`
- 评测：`agent/evals/eval_tools.py`、`agent/evals/README.md`
