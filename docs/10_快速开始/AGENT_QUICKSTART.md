# AGENT_QUICKSTART · 加一个业务场景 Skill（coding agent 速查）

> **读者**：coding agent（上下文受限、检索式读取）。本页是 **self-contained 的最小操作集**——读这一页就能动手加一个 skill，不必先读完整条文链。
> **样板**：照 [`agent/skills/zhgk/`](../../agent/skills/zhgk/)（4 step · 文件型 HITL）或 [`agent/skills/guihua/`](../../agent/skills/guihua/)（5 step · 确认型 HITL）抄。脚手架在 [`agent/skills/_template/`](../../agent/skills/_template/)。
> **要细则再展开**：规范 [03 团队范式](../20_架构与范式/03_团队Agent开发范式.md) · [SKILL-DEVELOPMENT](../30_skill开发/31_手写规范/SKILL-DEVELOPMENT.md) · [SDUI](../30_skill开发/31_手写规范/SDUI.md) · [TOOL-DEVELOPMENT](../30_skill开发/31_手写规范/TOOL-DEVELOPMENT.md)。

---

## 0. 开工前 · 环境就绪（首次一次即可）

```powershell
cd D:\code\aida
python -m venv agent\.venv                  # 仓库不带 venv，自己建
agent\.venv\Scripts\Activate.ps1
pip install -r agent\requirements.txt       # langgraph / fastapi / langchain-openai 等
cd frontend; npm install; cd ..             # 前端依赖（要跑界面才需要）
```

- **LLM key**：真 LLM 步骤需在 `agent\.env` 写 `ZHIPU_API_KEY=<你的key>`（缺 key 仍可搭骨架 + 跑 `--fixture`，但真抽取/评估跑不了）。
- **coding agent**：用 Claude Code / Cursor **打开 `D:\code\aida` 根目录**——它会自动加载 `CLAUDE.md`(=`AGENTS.md`) 的「加 skill 事实表」，从源头进入范式。
- **工作区根**（可选）：skill 产物根用环境变量（如 `<NAME>_ROOT`）；不设走默认 `~/.nanobot/...`，模板已 `mkdir` 兜底、不会 raise。
- ⚠️ **没在 venv 下跑时**，`lint_skill_contract` / `lint_tools` / `lint_sdui_contract` 会显示 **SKIP（跳过）而非失败**——别误判「绿了」，三个契约 lint 必须在 `agent\.venv` 下跑才真校验。

---

## 1. 碰这些文件（`<name>` = 你的 skill id，小写下划线）

| # | 文件 | 改什么 | 必/可选 |
|---|------|--------|---------|
| 1 | `agent/skills/_template/` → `agent/skills/<name>/` | 复制脚手架（`skill.py`+`sdui.py`+`steps/`），全局替换 `xxx`→`<name>`、`Xxx`→类名前缀 | 必 |
| 2 | `…/<name>/skill.py` | `<Name>Skill(BaseSkill)`：`name="<name>"` + `steps=[…]`（顺序即 DAG）+ 工厂 `get_<name>_skill()`；`_get_<name>_root()` 用 `mkdir` 兜底**别 raise** | 必 |
| 3 | `…/<name>/steps/*.py` | 每 step 一文件，见 §4 骨架 | 必 |
| 4 | `…/<name>/sdui.py` | `project(state)→dict`，复用 [`agent/sdui/projector_base.py`](../../agent/sdui/projector_base.py)（只写 `_kpi_items` + 摘要） | 推荐 |
| 5 | `agent/skills/__init__.py` | `registry.register("<name>", get_<name>_skill)` —— **一行** | 必 |
| 6 | `skills/<name>/SKILL.md` **＋** `~/.claude/skills/<name>/SKILL.md` | frontmatter(`name` 须 == 代码 `name`) + 触发词 + 端点表 + **「后端节点」表**（逐行列 `step.key`）；**两处都要部署** | 必 |
| 7 | `frontend/src/routes/module.tsx` | `MODULE_TO_SKILL` 加 `<moduleKey>: '<name>'` —— **一行** | 必（要界面） |
| 7b | `frontend/src/components/screens/survey-agent.tsx` · `SKILL_META` | 加 `<skillId>: { icon: '…', steps: [{key, name, sub}], files: [{name, ext}] }` — 不加也能跑，但 IdleScreen 显示通用占位样式（无步骤预览/无文件提示） | 推荐（强烈） |
| 8 | `agent/tools/run_<name>.py` + `chat_engine` | skill-as-tool（execute 只返 `{action:"launch_<name>"}`，不在 execute 跑图） | 可选 |
| 9 | `agent/evals/eval_<name>.py` + `fixtures/<name>-golden.json` | 评测回归（阈值断言，非精确等值） | 可选 |

## 2. 不用碰（1→N 泛化已覆盖，改了是反模式）

- `agent/main.py` / `agent/graph.py`：注册后**自动**得到 `/agent/<name>/{start,stream,resume,status,ui,artifact,runs}` 全套端点 + 按 skill_id 构图。
- 前端 `SkillAgentScreen`（survey-agent.tsx）/ `useSduiStream` / `SduiNodeView`：SDUI 通用递归渲染，新模块零前端逻辑。

## 3. 可选钩子（设在 `<Name>Skill` 上，全集见 [`base.py`](../../agent/skills/base.py)）

| 钩子 | 何时设 |
|------|--------|
| `sdui_projector = staticmethod(project)` | 要作业界面（几乎总要）。模板已绑好。 |
| `file_handler = <module>` | 有**文件型** HITL；模块需提供 4 个函数（见下表）。不设则 `/upload` 返 501。参考实现：[`agent/zhgk_files.py`](../../agent/zhgk_files.py) | 有文件上传必设 |
| `step_retry_keys = ["<step>"]` | 某步补料后只重试该步（不重跑前序 LLM）。**不可与确认型 HITL 同用。** |

**file_handler 模块必须实现的 4 个函数**（接口契约）：

```python
# agent/<name>_files.py
def infer_upload_kind(filename: str) -> str:
    """由文件名推断落盘位置标识（boq / template / image / input / ...）"""
    ...

def check_project_files(root: Path) -> dict[str, Any]:
    """扫描 root，返回 {ok, found_count, total, items[{id,label,path,found,matched,hint}]}"""
    ...

def check_need_files(root: Path, need_files: list[str]) -> dict[str, Any]:
    """按 HITL 的 need_files 列表逐项检查（支持 glob）"""
    ...

async def save_upload(root: Path, kind: str, file: UploadFile) -> dict[str, Any]:
    """单文件落盘，返回 {ok, kind, filename, path, size}"""
    ...
```

⚠️ **常见坑**：`check_project_files` 路径必须与 `path_config.py` 保持一致！参考 `zhgk_files.py` 的 `FIXED_ITEMS`（Template/ 底表）与 `BOQ_ITEM`（Input/ glob）拆分写法。
| `initial_project(payload)` | start 请求体填默认值（确认型 HITL 须 `setdefault("confirmations", {})`）。 |
| `apply_resume_payload(project, payload, hitl_step)` | **确认型** HITL：把 `payload["choice"]` 写进 `project["confirmations"][gate]`，靠 full_restart 保留 project 跨重跑存活。照 `GuihuaSkill`。 |

## 4. step 骨架（真实签名 · 来自 `base.py`）

```python
# agent/skills/<name>/steps/<step>.py
from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult

class XxxStep(BaseStep):
    key = "xxx"                                   # 必须 == SKILL.md「后端节点」表一项（lint_skill_contract 双向校验）
    name = "中文名"
    artifacts_pattern = ["ProjectData/Output/xxx.xlsx"]   # 可选 · 可下载产物
    # internal = True                             # 基础设施步（如 preflight），豁免契约 lint

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        miss = [p for p in ["ProjectData/Input/xxx.xlsx"] if not (ctx.work_root / p).exists()]
        return {"ok": not miss, "missing": miss, "found": [], "note": "补料提示"}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] {self.name}…")
        resp = ctx.invoke_llm([("system", "…"), ("human", "…")], step_key=self.key)  # 禁裸 import openai/anthropic
        out = ctx.call_tool("read_file", {"path": "…"}, step_key=self.key, emit=emit)  # 禁绕过 registry
        return {"metrics": {"<业务指标>": 1}}     # 写进 metrics 的键才能被 sdui 投影器读到（SDUI §3.3）
```

## 5. HITL 两形态（区别只在 `check_inputs` 返回）

- **文件型**：`{"ok": False, "missing": ["Input/x.xlsx"], …}` → FilePicker → `/upload/batch` + `/resume`。
- **确认型**：`missing=[]` 但 `need_inputs` 非空 → ChoiceCard：
  ```python
  return {"ok": False, "missing": [], "need_inputs": [{
      "id": "device", "label": "确认设备清单？",
      "options": [{"label": "确认", "value": "confirm"}, {"label": "重抽", "value": "redo"}],
  }]}
  ```
  选项**统一用 dict**（`{label, value}`，别用裸 str）；配 `apply_resume_payload` 落 `project["confirmations"]`。

## 6. 提交前守门（全绿才提交 · CI 同款）

完整守门清单 + 命令以 [`AGENTS.md` 命令速查](../../AGENTS.md)（与 CI [`ci.yml`](../../.github/workflows/ci.yml) 同款）为**唯一真相**——不在此重抄（漏一条即假绿）。两个 QUICKSTART 关键点：

- **必须在 `agent\.venv` 下跑**：否则 `lint_skill_contract` / `lint_tools` / `lint_sdui_contract` / `lint_sdui_gallery` / `lint_docs_site` 显 **SKIP** 而非校验，别把 SKIP 误判成「绿了」。
- 改了 `SKILL.md` / `builder.py` / `docs/` 后记得**重生成派生物**（`gen_sdui_gallery.py` / `gen_docs_site.py`），否则新鲜度 lint 红。

## 7. 端到端自检

```bash
curl http://127.0.0.1:7401/agent/skills            # 看到 <name> 元数据 = 注册成功
curl -X POST http://127.0.0.1:7401/agent/<name>/start -d '{}'   # 起 run
# 前端 /module/<moduleKey> 自动渲染 SDUI（IdleScreen → 启动 → SduiNodeView）
```
