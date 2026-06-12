---
name: device_install
description: 设备安装（Skill-First · 新范式单流水线）—— 数据中心工程安装全流程编排。主建设流程：接收上游实施计划→计划下发→SN扫码表生成→ESN填写；辅助流：进展反馈/进展查询/计划查询/计划调整/设备总览。当用户说「设备安装 / 任务下发 / SN扫码表 / ESN / 进展反馈 / 进展查询 / 计划调整 / 设备总览 / 完工清单」等时调用。
idle_screen:
  icon_key: device_install
  title: 设备安装
  subtitle: 计划下发 · SN扫码 · ESN填写
  files_hint: 启动前确认文件 · ProjectData\Input
  steps:
    - key: plan_receive
      name: 接收实施计划
      sub: 上游双 Sheet
    - key: task_dispatch
      name: 计划下发
      sub: 勾选·下发
    - key: sn_generate
      name: SN扫码表
      sub: 按单元生成
    - key: esn_fill
      name: ESN填写
      sub: 完工清单
  files:
    - name: 设备安装实施计划.xlsx
      ext: xlsx
  chat_intro:
    title: 设备安装 · 流程说明
    once: true
    body: |
      **主建设流程（点击「启动设备安装」启动）：**

      1. **接收实施计划** — 从上游读取自包含《设备安装实施计划》（含 SN Sheet）
      2. **计划下发** — 勾选《实施计划》条目后下发
      3. **SN扫码表生成** — 按勾选管理单元过滤，按机房+设备大类生成 SN 扫码表
      4. **ESN信息填写** — 大盘内逐台填写 ESN，生成完工清单/报告

      **辅助流（command 路由）：** 进展反馈 / 进展查询 / 计划查询 / 计划调整 / 设备总览。
---

# 设备安装（device_install）· AIDA Agent Skill

## 何时使用本 skill

| 用户说 | 调用场景（command） |
|--------|---------|
| 开始设备安装 / 任务下发 / SN扫码 / ESN | build（主建设流水线） |
| 进展反馈 / 上报进展 | progress_report |
| 进展查询 / 查看进度 | progress_query |
| 计划查询 / 查看计划 | plan_query |
| 计划调整 / 修改时间 | plan_adjust |
| 设备总览 / 设备状态 | device_overview |

---

## A. 业务流程（单流水线 · command 路由）

| 步骤 | 名称 | 输入 → 输出 | command | 后端节点 |
|------|------|------------|---------|---------|
| 1 | 接收实施计划 | 上游《设备安装实施计划.xlsx》→ tasks_state + sn_pool | build | `plan_receive` |
| 2 | 计划下发 | 勾选实施计划 → 更新实施计划 + 已选任务标记已下发 | build | `task_dispatch` |
| 3 | SN扫码表生成 | 按勾选管理单元过滤 sn_pool → SN扫码表.xlsx | build | `sn_generate` |
| 4 | ESN信息填写 | 在线填写 ESN → 完工清单/完工报告 | build | `esn_fill` |
| 5 | 进展反馈·选任务 | 已下发任务 → 选定任务（HITL） | progress_report | `progress_select` |
| 6 | 进展反馈·更新 | 选定任务 → 更新状态 | progress_report | `progress_apply` |
| 7 | 进展查询 | 任务状态 → 整体完成率 + 按管理单元 | progress_query | `progress_query` |
| 8 | 计划查询 | 任务 → 任务明细表 | plan_query | `plan_query` |
| 9 | 设备总览 | 任务 → 按机房分组总览 | device_overview | `device_overview` |
| 10 | 计划调整 | 引导上游重新交付实施计划 | plan_adjust | `plan_adjust` |

> **preflight（环境预检）** 为内部基础设施步骤（`internal=True`），豁免契约约束，先于所有业务步骤执行。
> 命令路由不经 intent_select HITL：`command` 由 `/start` 启动载荷给定，每步 `_command_guard.should_skip` 决定是否跳过。

---

## B. 端点速查

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/agent/device_install/start`            | 启动 run（body: `{command, project_code, project_name}`） |
| GET  | `/agent/device_install/stream/{run_id}`  | SSE 实时事件流 |
| POST | `/agent/device_install/resume`           | HITL 续跑（body: `{run_id, payload: {choice\|rows}}`） |
| POST | `/agent/device_install/run-patch`        | 运行时补丁（body: `{run_id, payload: {action, rows}}` · 任务进展改百分比，不重跑流水线） |
| POST | `/agent/device_install/upload`           | 上传文件到 Input/ |
| GET  | `/agent/device_install/ui/{run_id}`      | SDUI 快照 |
| GET  | `/agent/device_install/artifact?path=...`| 下载产物 |

---

## C. 数据目录结构

```
# 源文件目录（DEVICE_INSTALL_SOURCE_ROOT）：须含上游交付的
#   设备安装实施计划.xlsx（双 Sheet：实施计划 + SN扫码表）
#   未配置时默认 = <work_root>/ProjectData/Input/

# 作业产物输出目录（DEVICE_INSTALL_OUTPUT_ROOT）：
#   下发后实施计划 / 全量任务 / 责任人表 / SN扫码表 / 完工清单·报告
#   未配置时默认 = <work_root>/ProjectData/Output/
#   指向 ProjectData/Output 之外（如数据中心 .../交付作业/设备安装/输出结果）时，
#   文件按指定目录落盘，但网页端 /artifact 在线下载/预览失效（数据中心直接读盘）。

# 工作区（DEVICE_INSTALL_ROOT）：运行态与产物
ProjectData/
  Input/    ← plan_receive 同步上游实施计划副本
  Output/   ← 作业产物（DEVICE_INSTALL_OUTPUT_ROOT 未配置时的默认落点）
  RunTime/  ← tasks_state.json / sn_pool.json（全量 SN）/ sn_tables.json（勾选后）
  Images/   ← 现场照片（可选）
```

---

## D. HITL 交互设计

| 步骤 | HITL 类型 | 触发条件 | 用户操作 |
|------|-----------|---------|---------|
| plan_receive | — | 无（从 DEVICE_INSTALL_SOURCE_ROOT 直接读取） | — |
| task_dispatch | EditableTable（勾选） | 实施计划已接收 | 勾选待下发条目 → 确认下发 |
| esn_fill | EditableTable | 未提交或 ESN 校验未通过 | 大盘内逐台填写 ESN → 提交 |
| progress_select / progress_apply | ChoiceCard | 进展反馈 | 选任务 + 选状态 |

---

## E. 产物清单

| 产物 | 生成步骤 |
|------|---------|
| 设备安装实施计划.xlsx（Input 副本 / Output 下发快照） | plan_receive / task_dispatch |
| SN扫码表_{机房}_{设备大类}.xlsx | sn_generate |
| 完工清单_{机房}_{设备大类}.xlsx + 设备安装完工报告.xlsx | esn_fill |
