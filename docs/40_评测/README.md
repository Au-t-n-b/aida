# Agent 评测台 · 操作手册

> 团队范式 §6「可观测 → 评测 → 呈现 → AI 优化」在本项目的落地路径。  
> **指标定义（权威）**：[METRICS.md](METRICS.md) · **SKILL/工具开发**：[../docs/README.md](../30_skill开发/31_手写规范/README.md)

## 一、启动服务（界面必读）

需要 **两个进程**：Agent API（7401）+ 前端（`frontend/`）。

### 1. Agent 后端

```powershell
cd D:\code\aida
agent\.venv\Scripts\python.exe -m uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

确认：`curl http://127.0.0.1:7401/healthz`

### 2. 前端（AI 评测中心）

```powershell
cd D:\code\aida\frontend
npm run dev
```

浏览器打开 Vite 地址（通常 `http://127.0.0.1:5173`），侧栏进入 **AI 评测**（`/evals`）。

界面数据源：`http://127.0.0.1:7401/agent/evals/*`（见 `frontend/src/components/screens/evals/shared.tsx` 的 `API_BASE`）。

**初次使用**：评测中心页内可展开 **「指标说明」**（各 KPI 卡片下方亦有计算公式摘要）；文案与 [METRICS.md](METRICS.md) 同步，源码在 `frontend/src/components/screens/evals/metric-glossary.ts`。

---

## 二、测 SKILL（智慧工勘 zhgk）

### 2.1 跑一遍真实 Skill（产生产物 + Langfuse trace）

```powershell
# 启动工勘（返回 run_id，记下它）
curl -X POST http://127.0.0.1:7401/agent/zhgk/start `
  -H "Content-Type: application/json" `
  -d '{"project_code":"K1903","scenario_run":"训推一体"}'

# 浏览器或 curl 订阅 SSE 看推进
# curl http://127.0.0.1:7401/agent/zhgk/stream/<run_id>
```

跑完至少 `scene_filter` + `survey_build` 后，`skill_result.json` 会出现在 zhgk 工作区，且**自带 run_id**（用于评测精确对齐 trace）。

工作区默认：`%USERPROFILE%\.nanobot\workspace\skills\zhgk`（可用环境变量 `ZHGK_ROOT` 覆盖）。

### 2.2 跑 SKILL 评测脚本

```powershell
cd D:\code\aida

# 推荐：用产物里的 run_id 精确对齐 Langfuse（产物有 run_id 时可省略 --run-id）
agent\.venv\Scripts\python.exe agent\evals\eval_zhgk.py

# 或指定某次 run
agent\.venv\Scripts\python.exe agent\evals\eval_zhgk.py --run-id run-xxxxxxxxxx

# CI / 离线回归（golden fixture，不依赖真实 run）
agent\.venv\Scripts\python.exe agent\evals\eval_zhgk.py --fixture
```

结果写入：`agent/evals/results/zhgk-{时间戳}.json`，并尽力写回 Langfuse score（`eval.quality` / `eval.success`）。

### 2.3 界面查看

1. 打开 `/evals` → **SKILL 测评** tab  
2. 点 **刷新**（或页面加载时自动拉取）  
3. 角标应显示 **● 实时数据**（非「○ 演示数据」）

也可一键刷新（调 API 跑评测）：

```powershell
curl -X POST "http://127.0.0.1:7401/agent/evals/refresh?live=1"
```

---

## 三、测工具

### 3.1 产生工具调用 trace

工具 span 来自 **会话 ReAct** 或 **step 内 ctx.call_tool**。任选其一：

**A. 会话里调工具（推荐，快）**

在交付助手会话里说：「读一下 README 前 200 字节」→ 触发 `read_file`；或「帮我跑 K1903 工勘」→ 触发 `run_survey`。

**B. 本地 smoke（不经过 LLM）**

```powershell
agent\.venv\Scripts\python.exe agent\scripts\tool_smoke.py
```

注意：smoke **不一定**进 Langfuse（取决于 Langfuse 是否 init）；要算真实自纠率，优先用会话多轮故意传错参数让模型重试。

### 3.2 跑工具评测

```powershell
agent\.venv\Scripts\python.exe agent\evals\eval_tools.py          # 拉 Langfuse 最近 7 天
agent\.venv\Scripts\python.exe agent\evals\eval_tools.py --days 14
agent\.venv\Scripts\python.exe agent\evals\eval_tools.py --fixture  # CI 离线
```

结果：`agent/evals/results/tools-{时间戳}.json`

### 3.3 界面查看

`/evals` → **工具测评** tab → **刷新**。数据源：`GET /agent/evals/tools/report`。

---

## 四、AI 分析（偏离导出 → Cursor）

```powershell
# 先确保上面 zhgk + tools 评测各至少跑过一次
agent\.venv\Scripts\python.exe agent\evals\export_deviations.py

# 或 npm
cd D:\code\aida
npm run eval:export
```

生成：

| 文件 | 用途 |
|------|------|
| `results/deviations-{ts}.json` | 完整偏离包 |
| `results/cursor-skill-{ts}.md` | 粘贴给 Cursor：优化 Skill/step/prompt |
| `results/cursor-tools-{ts}.md` | 粘贴给 Cursor：优化工具 description/schema |

界面里也可点 **导出 SKILL 偏离 →** / **导出待优化工具 →**（前端从 live 数据即时拼 JSON，与 export 脚本逻辑一致）。

API：

- `GET /agent/evals/deviations/skill?skill=zhgk`
- `GET /agent/evals/deviations/tools?threshold=0.15`

---

## 五、一键命令速查

```powershell
# 回归闸（fixture，进 prebuild）
npm run eval

# 真实环境评测 + 导出偏离
npm run eval:live      # eval_zhgk + eval_tools（live）
npm run eval:export    # 偏离 JSON + Cursor markdown

# 工具框架自检
agent\.venv\Scripts\python.exe agent\scripts\tool_smoke.py
```

---

## 六、常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 界面「○ 演示数据」 | Agent 未启动或 `/agent/evals/report` 无 results | 起 uvicorn；跑 eval_zhgk |
| 成本一直 ¥0 | Langfuse 未配 glm 价表 | `python agent/scripts/langfuse_load_prices.py` |
| 工具 tab 仍 mock | 无 `tools-*.json` | 跑 `eval_tools.py` 后点刷新 |
| run_id 对齐告警 approx | 旧产物无 run_id | 重跑 zhgk 或 `--run-id` |
| Langfuse 超时 | 网络/云慢 | 重试；质量维不依赖 Langfuse |
