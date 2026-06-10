---
name: guihua
description: 规划设计（建模仿真，jmfz）—— 数据中心机房建模仿真全流程编排。当用户说 "开始规划设计 / 建模仿真 / 跑 jmfz / BOQ 提取 / 设备确认 / 创建设备 / 拓扑确认 / 拓扑连接 / 生成设备清单 / 建模仿真资料包"，或描述含「BOQ / 设备清单 / 拓扑 / 机柜 / 母线 / 网格 / 求解 / Nvisual / 建模仿真访问页」等术语时调用本 skill。本 skill 通过 AIDA Agent 后端（LangGraph + 智谱 GLM）顺序执行 5 个 step：① BOQ 提取（真 LLM 抽设备清单）② 设备确认（HITL）③ 创建设备 ④ 拓扑确认（HITL）⑤ 拓扑连接 + 结题。支持从任意步骤切入、HITL 文件/确认补齐、增量重跑、全流程一键执行。
---

# 规划设计 / 建模仿真（guihua）· AIDA Agent Skill

> A 层门面：何时调用 + 触发词 + HTTP 约定。真正执行由 `agent/skills/guihua/` 的 LangGraph 后端完成。
> 线下移植自 nanobot `jmfz`；黄金指标线下用真实抽取指标，内网环境可将 Nvisual 访问页接回 EmbeddedWeb 黄金指标位。

## 何时使用本 skill

- **触发关键词**：开始规划设计 / 建模仿真 / 跑 jmfz / BOQ 提取 / 设备确认 / 创建设备 / 拓扑确认 / 拓扑连接
- **业务场景描述**：用户上传建模仿真资料包（含 BOQ 表格），要抽设备清单、确认、建设备、确认拓扑、连接
- **不要调用**：纯讨论建模仿真但无执行需求；仅查看历史产物

---

## A. 流程总览（5 个 step）

| Step | 名称 | 关键输入 → 输出 | 后端节点 |
|---|---|---|---|
| 1 | BOQ 提取 | 资料包（BOQ .xlsx）→ 设备清单（device_list.json） | `boq_extract` |
| 2 | 设备确认 | 设备清单 → 用户确认（HITL ChoiceCard） | `device_confirm` |
| 3 | 创建设备 | 已确认清单 → 设备节点（devices_created.json） | `device_create` |
| 4 | 拓扑确认 | 设备节点 → 用户确认拓扑（HITL ChoiceCard） | `topo_confirm` |
| 5 | 拓扑连接 | 已确认拓扑 → 链路 + 结题报告.md | `topo_link` |

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

## C. HITL 两种形态

- **文件型**（step 1 缺资料包）：`hitl.need_files` → 上传走 `/agent/guihua/upload/batch` → `/resume`。
- **确认型**（step 2/4 设备/拓扑确认）：`hitl.need_inputs` → 前端 ChoiceCard → `/resume` 带 `payload:{choice:"confirm"}`。
  - 选 `confirm` 放行；选 `redo` 回退（设备确认的 redo 会触发重新提取 BOQ）。

---

## D. 产物清单与验收

| Step | 完成标志（文件应在 `ProjectData/RunTime/` 或 `Output/`） |
|---|---|
| 1 | `RunTime/device_list.json`（设备清单） |
| 3 | `RunTime/devices_created.json`（设备节点） |
| 5 | `Output/modeling_simulation_workbench_report.md`（结题报告） |

---

## E. 与 nanobot jmfz 的关系

- 业务语义（五阶段、文案、报告文件名）与 `~/.nanobot/workspace/skills/jmfz` 对齐。
- 差异：jmfz 是 nanobot Skill-First（driver.py + stdout 事件），本 skill 是 AIDA A+B/LangGraph 实现；jmfz 的黄金指标是 Nvisual 内网访问页 iframe，本线下版改用真实抽取指标（设备数/创建数/链路数）。
- 工作区：`GUIHUA_ROOT` 环境变量，默认复用 jmfz 工作区 `~/.nanobot/workspace/skills/jmfz`。
