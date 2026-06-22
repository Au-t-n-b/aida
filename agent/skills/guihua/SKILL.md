---
name: guihua
version: 1.0.0
enabled: true
ui:
  label: 规划设计
  group: ops
  order: 20
  icon: modeling
  route_key: modeling
runtime: {}
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
| 1 | 设备适配 | 载入设备适配信息表.md（jmfz/api_adapt 产物）→ compat_table.md + BOQ 概览 | `adapt_build` |
| 2 | 数据确认 | 「查看详细数据」核对适配表 →「数据准确？」（HITL ChoiceCard，右下「设备数据准确」按钮亦可触发） | `data_confirm` |
| 3 | 创建超节点 | 「是否创建超节点？」（HITL 门）→ subprocess run_place_api --only-create（batchCreateCombo×5） | `combo_create` |
| 4 | 机柜落位 | 刷新 nVisual + 「开始落位？」（HITL 门）→ subprocess run_place_api --only-move（batchMoveNodes×162） | `cabinet_move` |
| 5 | 生成参数面设备 | 「是否生成参数面…？」（HITL 门）→ subprocess csm-rack run_device_install（建 Leaf×54 → 上架×18 → batchCreateLink×2） | `handoff` |

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

## C. HITL 形态（四道确认门 + 可选文件型）

- **文件型**（可选）：未上传时复用 vendored 适配表离线渲染；要用真实数据则上传走 `/agent/guihua/upload/batch` → `/resume`。
- **确认型**（step 2/3/4/5）：`hitl.need_inputs` → 前端 ChoiceCard → `/resume` 带 `payload:{choice:"confirm"}`。
  - `data_confirm`：「数据准确？」（右下「设备数据准确」按钮 = 该门 confirm）；redo=「重新生成适配表」（连带重置下游创建/落位/生成）。
  - `combo_create`：「数据已确认，是否开始创建超节点？」；redo=「暂不创建」。
  - `cabinet_move`：「超节点已经创建完毕，是否开始机柜落位？」（含手动刷新 nVisual）；redo=「暂不落位」。
  - `handoff`：「超节点已经创建并且落位完毕，是否生成参数面设备，并且完成设备上架和拓扑生成？」；redo=「暂不生成」。

---

## D. 产物清单与验收

| Step | 完成标志（文件应在 `解析结果/` 或 `输出结果/建模仿真/`） |
|---|---|
| 1 | `解析结果/compat_table.md`（设备适配信息表） |
| 3 | `解析结果/combo_created.json`（创建哨兵） |
| 4 | `解析结果/move_progress.json`（逐机柜落位进度 / 断点） |
| 5 | `解析结果/csm_done.json`（参数面生成汇总）+ `输出结果/建模仿真/modeling_simulation_workbench_report.md`（结题报告）；csm-rack 明细见 `vendor/jmfz/csm-rack/output/execution-result.json` |

> 真跑交付：step 3/4/5 经 subprocess 调 vendored jmfz 脚本（`agent/skills/guihua/vendor/jmfz/`）真发仿真网关 `100.102.191.17:9091`（本次明确豁免 AGENTS「禁 subprocess 调 py」红线，技术债待移植成 services）。

---

## E. 与 Desktop/skill/jmfz 的关系

- 业务逻辑逐字移植：`api_adapt/build_compat_table.py` → `services/compat_table.py`；`auto_dragd/run_place_api.py` → `services/place_api.py`；HTTP 收敛到统一出口 `services/sim_api.py`。
- 差异：jmfz 是脚本 + CLI `input()` 暂停，本 skill 是 AIDA A+B/LangGraph 实现，刷新暂停收敛成 `cabinet_move` 的 HITL 门；副作用走唯一出口（铁律④）默认 dry-run + 留痕。
- 离线骨架：`services/fixtures/`（设备信息表 / 适配表 / requests / cabinets）保证无内网时端到端可跑；置 `SIM_API_LIVE=1` 接内网真跑。
- 工作区：`AIDA_BUSINESS_ROOT` 环境变量（平台统一注入）；路径模型见 `bridge.py` + `path_config.py`，默认 `/opt/aida/aida-data/business/project/交付作业/规划设计`。
