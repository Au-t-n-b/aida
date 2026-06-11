---
name: guihua
description: 规划设计（建模仿真，jmfz）—— 数据中心机房建模仿真全流程编排（规划设计前半段）。当用户说 "开始规划设计 / 建模仿真 / 跑 jmfz / 设备适配 / 适配信息表 / 创建超节点 / 机柜落位 / 移交设备安装 / 建模仿真资料包"，或描述含「BOQ / 设备信息表 / 超节点 / 灵衢 / 机柜 / 适配 / nVisual / 仿真软件 / batchCreateCombo / batchMoveNodes」等术语时调用本 skill。本 skill 通过 AIDA Agent 后端（LangGraph）顺序执行 5 个 step：① 设备适配（解析设备信息表 + 调仿真 API 匹配型号/板卡 → 适配信息表）② 数据确认（HITL）③ 创建超节点（batchCreateCombo×5）④ 机柜落位（刷新 nVisual 后 batchMoveNodes×162，HITL 门）⑤ 移交设备安装（HITL 边界 + 结题）。支持从任意步骤切入、HITL 文件/确认补齐、增量重跑、断点续跑、全流程一键执行。
---

# 规划设计 / 建模仿真（guihua）· AIDA Agent Skill

> A 层门面：何时调用 + 触发词 + HTTP 约定。真正执行由 `agent/skills/guihua/` 的 LangGraph 后端完成。
> 线下移植自 `Desktop/skill/jmfz`（api_adapt + auto_dragd）。仿真 API 默认 dry-run（离线复用 fixture 兜底），置 `SIM_API_LIVE=1` 接内网真跑；右侧「仿真软件」页签 iframe 接 nVisual Web UI。
> **范围边界**：本 skill = 规划设计**前半段**（建模仿真）。「生成参数面设备」及之后由独立的**设备安装**模块承接；后半段「系统设计」另行实现。

## 何时使用本 skill

- **触发关键词**：开始规划设计 / 建模仿真 / 设备适配 / 适配信息表 / 创建超节点 / 机柜落位 / 移交设备安装
- **业务场景描述**：用户进入建模仿真模块，要把设备信息表适配成仿真型号、创建超节点、逐机柜落位
- **不要调用**：纯讨论建模仿真但无执行需求；仅查看历史产物；设备安装 / 系统设计模块的工作

---

## A. 流程总览（5 个 step）

| Step | 名称 | 关键输入 → 输出 | 后端节点 |
|---|---|---|---|
| 1 | 设备适配 | 设备信息表.md → 调仿真 API 匹配 → 设备适配信息表（compat_table.md） | `adapt_build` |
| 2 | 数据确认 | 适配信息表 → 用户确认「数据准确，创建超节点」（HITL ChoiceCard） | `data_confirm` |
| 3 | 创建超节点 | 适配表 + 机柜几何 → batchCreateCombo×5（requests.json / combo_created.json） | `combo_create` |
| 4 | 机柜落位 | 刷新 nVisual（HITL 门）→ batchMoveNodes×162 逐机柜（move_progress.json） | `cabinet_move` |
| 5 | 移交设备安装 | 用户确认生成参数面（HITL 边界）→ 移交载荷 + 结题报告.md | `handoff` |

> ⚠️「后端节点」列与 `agent/skills/guihua/steps` 的 `step.key` **逐一一致**（`lint_skill_contract` 校验）。

---

## B. 调用 AIDA Agent 后端（HTTP / SSE）

本 skill **不直接执行 Python**。所有调用走 `http://127.0.0.1:7401`：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/agent/guihua/start` | 启动 run（body 可空 `{}`），返回 `run_id` |
| GET  | `/agent/guihua/stream/{run_id}` | SSE 实时事件流（含 `sdui` 树） |
| POST | `/agent/guihua/resume` | HITL 续跑：文件补齐 或 确认（body `{run_id, payload:{choice:"confirm"|"redo"}}`） |
| POST | `/agent/guihua/upload/batch` | 上传资料包（多文件，按文件名落 Input/） |
| GET  | `/agent/guihua/artifact?path=...` | 下载产物 |
| GET  | `/agent/guihua/ui/{run_id}` | 拉当前 SDUI 树（首屏/断线重连） |

> ✅ 这些端点在注册 skill 后**自动可用**（`main.py` 已泛化为 `/agent/{skill}/*`，`graph.py` 按 `skill_id` 构图）—— 无需改后端 HTTP 层。

---

## C. HITL 形态（三道确认门 + 可选文件型）

- **文件型**（可选）：未上传设备信息表时不阻断，自动复用内置 fixture 离线生成；要用真实数据则上传 `设备信息表.md`（及 `机房机柜信息表.xlsx`）走 `/agent/guihua/upload/batch` → `/resume`。
- **确认型**（step 2/4/5）：`hitl.need_inputs` → 前端 ChoiceCard → `/resume` 带 `payload:{choice:"confirm"}`。
  - `data_confirm`：「数据准确，创建超节点」；redo=「重新生成适配表」（连带重置下游创建/落位）。
  - `cabinet_move`：「已刷新 nVisual，开始落位」（收敛原 CLI 的手动刷新暂停）；redo=「暂不落位」。
  - `handoff`：「生成参数面，移交设备安装」（模块边界）；redo=「暂不移交」。

---

## D. 产物清单与验收

| Step | 完成标志（文件应在 `ProjectData/RunTime/` 或 `Output/`） |
|---|---|
| 1 | `RunTime/compat_table.md`（设备适配信息表） |
| 3 | `RunTime/requests.json` + `RunTime/combo_created.json`（创建请求 + 哨兵） |
| 4 | `RunTime/move_progress.json`（逐机柜落位进度 / 断点） |
| 5 | `RunTime/handoff.json`（移交设备安装载荷）+ `Output/modeling_simulation_workbench_report.md`（结题报告） |

> 所有仿真 API 调用（含 dry-run）留痕于 `RunTime/sim_api_calls.jsonl`，payload/响应可回溯。

---

## E. 与 Desktop/skill/jmfz 的关系

- 业务逻辑逐字移植：`api_adapt/build_compat_table.py` → `services/compat_table.py`；`auto_dragd/run_place_api.py` → `services/place_api.py`；HTTP 收敛到统一出口 `services/sim_api.py`。
- 差异：jmfz 是脚本 + CLI `input()` 暂停，本 skill 是 AIDA A+B/LangGraph 实现，刷新暂停收敛成 `cabinet_move` 的 HITL 门；副作用走唯一出口（铁律④）默认 dry-run + 留痕。
- 离线骨架：`services/fixtures/`（设备信息表 / 适配表 / requests / cabinets）保证无内网时端到端可跑；置 `SIM_API_LIVE=1` 接内网真跑。
- 工作区：`GUIHUA_ROOT` 环境变量，默认复用 jmfz 工作区 `~/.nanobot/workspace/skills/jmfz`。
