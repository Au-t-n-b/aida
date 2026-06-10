# AIDA zhgk v4 迁移交接文档

> **生成时间**：2026-06-07  
> **当前工作分支**：`feat/merge-delivery-frontend`  
> **最新 commit**：`0f78318`（v3 死代码清理）  
> **远端**：`aida_github` (D:\aida_github) · `gitea` (http://10.143.2.109:3010/jintao/aida.git) · `origin` (GitHub)  
> **业务逻辑参考源**：`C:/Users/j00954996/Desktop/smart_survey/smart_survey/`

---

## 一、本轮已完成工作（Phase 0–5 + 清理，全部落地）

### 已提交的 5 个 commit（本轮工作）

| Commit | 内容 |
|--------|------|
| `575dc4d` | Phase 0+1 — 16 个 services 迁移 + 15-step 意图驱动骨架 + SKILL.md v4 |
| `38f6e76` | Phase 2 — preflight v4、determine_gen（BOQ解析+HITL）、filter_build（底表→建表）、SDUI v4 |
| `952f2fb` | Phase 3 — 7 步 survey_work 核心实现（method_split→resurvey_gate） |
| `0c44896` | Phase 4+5 — scene_suggest_run、supplement_run、report_gen_run（风险识别+9表Word） |
| `0f78318` | chore — 删除 v3 死代码（report_gen.py, scene_filter.py, survey_build.py） |

### 15 步流水线状态（全实现）

| # | 步骤 key | 文件 | 意图范围 | 状态 |
|---|---------|------|---------|------|
| 1 | `preflight` | preflight.py | 所有 | ✅ 环境预检+LLM摘要（internal） |
| 2 | `intent_select` | intent_select.py | 所有 | ✅ HITL ChoiceCard 4选1 |
| 3 | `scene_suggest_run` | scene_suggest_run.py | scene_suggest | ✅ 场景+LLM推荐摘要 |
| 4 | `determine_gen` | determine_gen.py | survey/supplement/report_gen | ✅ BOQ解析+缓存+HITL三路 |
| 5 | `filter_build` | filter_build.py | survey_work | ✅ 底表过滤→build_survey_table |
| 6 | `method_split` | method_split.py | survey_work | ✅ 按勘测方法分组统计 |
| 7 | `data_append` | data_append.py | survey_work | ✅ HITL→append_data_items |
| 8 | `confirm_table` | confirm_table.py | survey_work | ✅ HITL confirm/redo（含摘要） |
| 9 | `wait_survey` | wait_survey.py | survey_work/supplement | ✅ FilePicker+多轮复勘支持 |
| 10 | `assess` | assess.py | survey_work/report_gen | ✅ evaluate_all+五值统计 |
| 11 | `issue_list` | issue_list.py | survey_work/report_gen | ✅ build_issue_list（LLM逐条） |
| 12 | `resurvey_gate` | resurvey_gate.py | survey_work | ✅ HITL 复勘/跳过门控 |
| 13 | `supplement_run` | supplement_run.py | supplement | ✅ HITL→append_data_items |
| 14 | `report_gen_run` | report_gen_run.py | report_gen | ✅ 风险识别+9表Word报告 |
| 15 | `report_distribute` | report_distribute.py | report_gen | ✅ 邮件/WeLink分发 |

### Services 层（16 个文件，来自 smart_survey/services/，已适配 aida LLM）

```
agent/skills/zhgk/services/
  _llm_adapter.py       ← 把 ctx.invoke_llm 包装成 LLMCallable = Callable[[str,str],str]
  types.py              ← 数据类型定义
  boq_parser.py         ← BOQ.xlsx 解析，抽取代际-制冷
  table_filter.py       ← 底表过滤（代际/制冷/场景匹配）
  survey_table_builder.py ← 建全量勘测结果表
  assessment_engine.py  ← LLM 五值评估（满足/不满足/不涉及/未勘测/无法识别）
  issue_list_builder.py ← LLM 逐条生成问题清单
  risk_engine.py        ← LLM 风险识别
  resurvey_manager.py   ← 复勘轮次管理（write_survey_results）
  report_builder.py     ← 9 表 Word 报告填充
  project_meta.py       ← 项目元数据（活动ID/项目名/机房等）
  session_memory.py     ← 跨步骤共享 KV
  issue_manager.py      ← 问题状态管理
  error_codes.py        ← 错误码定义
  logger.py             ← 日志封装（适配了 path_config 相对导入）
  __init__.py
```

---

## 二、尚未完成的工作（下一个 agent 继续）

### 2.1 必须完成（端到端可用前提）

#### ① 放置 3 个模板文件（**阻断测试，人工操作**）

```
D:/srv/zhgk/ProjectData/Template/
  ├─ 入场评估标准表.xlsx      ← 阻断 filter_build
  ├─ 工勘常见高风险库.xlsx    ← 阻断 report_gen_run (identify_risks)
  └─ 新版项目工勘报告模板.docx ← 阻断 report_gen_run (fill_report, 需含 ≥9 个表格)
```

来源：`C:/Users/j00954996/Desktop/smart_survey/smart_survey/ProjectData/Template/`（如存在）

#### ② SDUI 完整重设计（Phase 7 — **主要剩余代码工作**）

**背景**：`agent/skills/zhgk/sdui.py` 当前实现已有基础 KPI、风险表等，但缺少以下关键面板，需参照 `smart_survey` 的 UI 设计用 aida SDUI 组件补全：

**需要新增的 SDUI 面板（按步骤顺序）：**

**a. filter_build 完成后 — 条目预览面板**
```
┌ NumberCards ──────────────────────────────┐
│  [76 条]       [3 场景]       [A3-液冷]   │
│  勘测条目      细分场景        代际-制冷    │
└───────────────────────────────────────────┘
┌ Table "勘测条目预览（前 10 条）" ──────────┐
│  细分场景 │ 勘测要素 │ 项目 │ 勘测方法      │
└───────────────────────────────────────────┘
```
实现位置：`sdui.py` → 新函数 `_build_filter_preview(state)`  
数据来源：`state['metrics']['sub_scenes']` / `state['metrics']['filtered_count']`

**b. assess 完成后 — 五值评估看板（最重要）**
```
┌ StatisticRow（5个）─────────────────────────────────────────┐
│  [45 ✅] 满足  [8 ❌] 不满足  [12 ◯] 不涉及                  │
│  [10 🟡] 未勘测  [6 ❓] 无法识别                            │
└─────────────────────────────────────────────────────────────┘
若 不满足 > 0 → Alert(tone="danger"):
  "❗ 存在 8 项不满足，已生成问题清单"
若 不满足 == 0 → Alert(tone="success"):
  "✅ 全部条目满足或不涉及，可直接生成报告"
```
数据来源：`state['metrics']['assessment_count_满足']` 等五值计数键

**c. issue_list 完成后 — 问题清单 Table**
```
┌ Table "问题清单（N 项）" ────────────────────────────────────┐
│  # │ 问题描述              │ 整改建议        │ 状态           │
└─────────────────────────────────────────────────────────────┘
```
数据来源：`state['metrics']['issue_rows']`（需在 issue_list step 的 metrics 里记录前 N 行）

**d. report_gen_run 完成后 — 产物四件套卡片**
```
┌ ArtifactGrid "四件套产物" ────────────────────────────────────┐
│  📊 全量勘测结果表.xlsx    📋 问题清单表.xlsx                   │
│     [预览] [下载]              [预览] [下载]                   │
│  🔍 风险识别结果表.xlsx   📄 工勘报告.docx                     │
│     [预览] [下载]              [下载]                          │
└──────────────────────────────────────────────────────────────┘
```
当前 `build_artifacts()` 从 `state['artifacts']` 读取，需确认 report_gen_run step 正确写入了 4 个 artifact 条目。

**实现指南**：
- 所有新函数加入 `sdui.py` 的 `project()` 函数的 `for node in (...)` 块
- 用 `m = collect_metrics(state)` 取指标，缺失则返回 `None`（不渲染）
- 遵守 `lint_sdui_contract.py`（`project()` 返回 dict，含 root/meta 键）

#### ③ 前端模块注册（一行代码）

文件：`frontend/src/routes/module.tsx`  
找到 `MODULE_TO_SKILL` 字典，加一行：
```typescript
zhgk: 'zhgk',
```
然后在前端模块列表加入 zhgk 入口（参考同文件其他模块的写法）。

### 2.2 可选优化（不阻断主流程）

- [ ] `agent/evals/eval_zhgk.py` 补 fixture（`agent/evals/fixtures/zhgk-golden.json`）并跑通
- [ ] `assess` step：metrics 中补充 5 个单值 key（`assessment_count_满足` 等），SDUI 五值看板依赖此数据
- [ ] `issue_list` step：metrics 中补充 `issue_rows`（列表，含问题描述/整改建议/状态）
- [ ] `wait_survey`：FilePicker 前端体验优化（自动提示下载路径、说明当前是第几轮复勘）
- [ ] `scene_suggest_run`：加底表条目 NumberCards（需 state['metrics']['sub_scenes'] 可用）

---

## 三、关键设计（接手必读）

### 3.1 意图路由 — 单流水线 + 内部跳过

```python
# agent/skills/zhgk/steps/_intent_guard.py
STEP_INTENTS: dict[str, frozenset[str]] = {
    "scene_suggest_run": frozenset({"scene_suggest"}),
    "filter_build":      frozenset({"survey_work"}),
    "assess":            frozenset({"survey_work", "report_gen"}),
    # ... 全部 14 步映射见文件
}

def should_skip(step_key: str, project: dict) -> bool:
    intent = project.get("intent", "")
    allowed = STEP_INTENTS.get(step_key)
    return intent not in allowed if (intent and allowed) else False
```

每个有意图路由的 step 在 `run()` 开头：
```python
from ._intent_guard import should_skip
if should_skip(self.key, ctx.project):
    return StepResult(status="skipped", ...)
```

### 3.2 跨步骤状态持久化 — project_info.json

`StepResult` 没有 `project` 字段，非 HITL 数据通过文件持久化：

```
D:/srv/zhgk/ProjectData/RunTime/project_info.json
{
  "generation_cooling": "A3-液冷",
  "survey_table_path": ".../Output/xxx_全量勘测结果表.xlsx",
  "method_groups": {"现场勘测": 45, "客户反馈": 12},
  "total_items": 57
}
```

辅助函数（各 step 共用）：
- `_get_generation_cooling(ctx)` → 优先 ctx.project → 读 project_info.json → glob
- `_get_survey_table(ctx)` → 同上

### 3.3 HITL 门 — apply_resume_payload（skill.py）

resume 时 `apply_resume_payload(project, payload, hitl_step)` 更新 project，
然后 `full_restart`（preflight 重跑，已满足的步骤 check_inputs 直接放行）。

| hitl_step | resume 写入 project 的 key | 说明 |
|-----------|--------------------------|------|
| `intent_select` | `intent` | 四选一 |
| `determine_gen` | `generation_cooling` | 手动指定时 |
| `data_append` | `data_append_choice` | "append_all" / "skip" |
| `confirm_table` | `table_confirmed=True`；redo→清此key | redo 不清 generation_cooling |
| `wait_survey` | （文件型）复勘时清 `resurvey_decision` | — |
| `resurvey_gate` | `resurvey_decision` | "resurvey"/"skip_resurvey" |
| `supplement_run` | `supplement_choice` | "append_all" / "skip" |

### 3.4 多轮复勘联动（wait_survey ↔ resurvey_gate）

```
resurvey_gate HITL → "resurvey"
→ apply_resume_payload: project["resurvey_decision"] = "resurvey"
→ full_restart
→ wait_survey.check_inputs(): resurvey_pending=True → FilePicker（忽略「已有结果」检测）
→ 用户上传新表（Input/已填写_全量勘测结果表.xlsx）
→ wait_survey resume → apply_resume_payload("wait_survey"): 清 resurvey_decision
→ full_restart → wait_survey.run(): write_survey_results(round=2)
→ assess 再次运行（第2轮结果覆盖 AI评估结果 列）
```

### 3.5 LLM 调用规范（严格禁裸调用）

```python
# Step 内直接调用
resp = ctx.invoke_llm(messages, step_key=self.key)

# 传给 services 层（接收 LLMCallable = Callable[[str,str],str]）
from ..services._llm_adapter import make_llm_adapter
llm = make_llm_adapter(ctx, step_key=self.key)
results = evaluate_all(survey_table, llm)   # assessment_engine
risks = identify_risks(risk_items, rows, llm)  # risk_engine
```

---

## 四、守门命令（提交前必跑，全绿才 commit）

```bash
cd D:/aida
agent\.venv\Scripts\activate

python agent/scripts/lint_no_naked_llm.py      # 禁裸 LLM
python agent/scripts/lint_no_naked_send.py     # 禁裸外发
python agent/scripts/lint_skill_contract.py   # SKILL.md ↔ step.key 契约
python agent/scripts/lint_tools.py            # 工具契约
python agent/scripts/lint_sdui_contract.py    # SDUI 三方一致
python agent/scripts/lint_runtime_contract.py # 运行时契约
```

**当前所有守门均通过 ✅**（截至 commit `0f78318`）

---

## 五、端到端冒烟测试（模板文件就位后执行）

```bash
# 后端
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload

# 前端
cd frontend && npm run dev  # → http://localhost:5173

# 验证 skill 已注册
curl http://127.0.0.1:7401/agent/skills/zhgk

# 发起 survey_work 流程（BOQ.xlsx 需在 D:/srv/zhgk/ProjectData/Input/）
curl -X POST http://127.0.0.1:7401/agent/zhgk/start \
  -H "Content-Type: application/json" \
  -d '{"intent":"survey_work","project_name":"测试项目","room_name":"A机房","activity_id":"T001"}'

# 流式事件
curl http://127.0.0.1:7401/agent/zhgk/stream/{run_id}

# HITL resume（示例：intent_select 选择 survey_work）
curl -X POST http://127.0.0.1:7401/agent/zhgk/resume \
  -H "Content-Type: application/json" \
  -d '{"run_id":"{run_id}","from_step":"intent_select","payload":{"choice":"survey_work"}}'
```

---

## 六、目录/文件速查

| 需要改什么 | 找哪个文件 |
|-----------|-----------|
| 意图路由规则 | `agent/skills/zhgk/steps/_intent_guard.py` |
| HITL 用户选择写入 project | `agent/skills/zhgk/skill.py` → `apply_resume_payload()` |
| 路径配置（Template/Input/Output） | `agent/skills/zhgk/path_config.py` |
| SDUI 步骤显示名 / KPI 指标 / 面板 | `agent/skills/zhgk/sdui.py` |
| Skill 触发词 / 端点文档 | `skills/zhgk/SKILL.md`（同步到 `~/.claude/skills/zhgk/SKILL.md`） |
| 业务服务（评估/风险/报告等） | `agent/skills/zhgk/services/*.py` |
| smart_survey 源码参考 | `C:/Users/j00954996/Desktop/smart_survey/smart_survey/` |
| 前端模块注册 | `frontend/src/routes/module.tsx` → `MODULE_TO_SKILL` |

---

## 七、建议启动顺序（给下一个 agent）

1. **立即可开始**：`sdui.py` 补全（Phase 7）— 不依赖模板文件，纯代码工作
2. **立即可开始**：`frontend/src/routes/module.tsx` 加 `zhgk` 注册（一行）
3. **需人工放置文件后**：端到端 smoke test → filter_build → assess → report_gen_run
4. **可选**：eval fixture (`agent/evals/eval_zhgk.py --fixture`)

---

*本文档由 Claude Sonnet 4.6 生成，2026-06-07，对应最新 commit `0f78318`*
