---
name: device_install
version: 1.0.0
enabled: true
ui:
  label: 设备安装
  group: ops
  order: 30
  icon: install
  route_key: install
runtime: {}
description: 设备安装（Skill-First · 新范式单流水线）—— 数据中心工程安装全流程编排。主建设流程：解析交付计划表→指派责任人→确认实施计划→计划下发→SN扫码表生成→ESN填写；辅助流：进展反馈/进展查询/计划查询/计划调整/设备总览。当用户说「设备安装 / 责任人信息表 / 实施计划 / 任务下发 / SN扫码表 / ESN / 进展反馈 / 进展查询 / 计划调整 / 设备总览 / 完工清单」等时调用。
idle_screen:
  icon_key: device_install
  title: 设备安装
  subtitle: 计划下发 · SN扫码 · ESN填写
  files_hint: 启动前确认上游三份文件 · 见各业务目录（无需上传 Input）
  steps:
    - key: preflight
      name: 环境预检
      sub: 校验输入文件
    - key: principal_fill
      name: 指派责任人
      sub: 在线编辑信息
    - key: tasks_generate
      name: 确认实施计划
      sub: 在线编辑计划
    - key: task_dispatch
      name: 计划下发
      sub: 勾选计划下发
    - key: sn_generate
      name: SN扫码表
      sub: 按单元生成
    - key: esn_fill
      name: ESN填写
      sub: 完工清单
  files:
    - name: 交付计划表.xlsx
      ext: xlsx
    - name: '{批次}_{机房}_{设备型号}到货表_{日期}.xlsx'
      ext: xlsx
    - name: 建模仿真输出文档004-设备位置表.xlsx
      ext: xlsx
  chat_intro:
    title: 设备安装 · 流程说明
    once: true
    body: |
      **主建设流程（点击「启动设备安装」启动）：**

      1. **指派责任人** — 解析《交付计划表》，按活动生成责任矩阵（责任人自动带出，在线复核/补齐责任主体）
      2. **确认实施计划** — 结合《设备位置表》《到货信息表》生成自包含《实施计划》（含 SN Sheet），在线复核/编辑计划日期
      3. **计划下发** — 勾选《实施计划》条目后下发
      4. **SN扫码表生成** — 按勾选管理单元过滤，按机房+设备大类生成 SN 扫码表
      5. **ESN信息填写** — 大盘内逐台填写 ESN，生成完工清单/报告

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
| 1 | 指派责任人 | 《交付计划表》→ 按活动去重的责任矩阵（在线复核责任人/责任主体） | build | `principal_fill` |
| 2 | 确认实施计划 | 全量任务 +《设备位置表》/《到货信息表》→ 自包含《设备安装实施计划》（在线编辑计划日期）+ sn_pool | build | `tasks_generate` |
| 3 | 计划下发 | 勾选实施计划 → 更新实施计划 + 已选任务标记已下发 | build | `task_dispatch` |
| 4 | SN扫码表生成 | 按勾选管理单元过滤 sn_pool → SN扫码表.xlsx | build | `sn_generate` |
| 5 | ESN信息填写 | 在线填写 ESN → 完工清单/完工报告 | build | `esn_fill` |
| 6 | 进展反馈·选任务 | 已下发任务 → 选定任务（HITL） | progress_report | `progress_select` |
| 7 | 进展反馈·更新 | 选定任务 → 更新状态 | progress_report | `progress_apply` |
| 8 | 进展查询 | 任务状态 → 整体完成率 + 按管理单元 | progress_query | `progress_query` |
| 9 | 计划查询 | 任务 → 任务明细表 | plan_query | `plan_query` |
| 10 | 设备总览 | 任务 → 按机房分组总览 | device_overview | `device_overview` |
| 11 | 计划调整 | 引导上游重新交付计划表 | plan_adjust | `plan_adjust` |

> **preflight（环境预检）** 为内部基础设施步骤（`internal=True`），豁免契约约束，先于所有业务步骤执行。
> 命令路由不经 intent_select HITL：`command` 由 `/start` 启动载荷给定，每步 `_command_guard.should_skip` 决定是否跳过。

---

## B. 端点速查

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/agent/device_install/start`            | 启动 run（body: `{command, project_id(UUID32), project_code, project_name}`） |
| GET  | `/agent/device_install/stream/{run_id}`  | SSE 实时事件流 |
| POST | `/agent/device_install/resume`           | HITL 续跑（body: `{run_id, payload: {choice\|rows}}`） |
| POST | `/agent/device_install/run-patch`        | 运行时补丁（body: `{run_id, payload: {action, rows}}` · 任务进展改百分比，不重跑流水线） |
| POST | `/agent/device_install/upload`           | 上传文件到 Input/ |
| GET  | `/agent/device_install/ui/{run_id}`      | SDUI 快照 |
| GET  | `/agent/device_install/artifact?path=...`| 下载产物 |

---

## C. 数据访问（数据中心 API 化）

业务数据一律走**数据中心 HTTP API**（语义寻址 `moduleCode`+`fileStage`+`projectId`，见 `dc_paths.py` / `dc_io.py`）。
DC 不可达时降级到挂载盘 `{AIDA_BUSINESS_ROOT}/project/<域>/<模块>/<阶段>/`；二者都失败才报缺料。
`projectId` **只认 UUID32**（数据中心语义寻址主键 · API 规范 §3.1/§5.2）。来源优先级：
`/start` 载荷 `project_id`(UUID32) → 容器 env `AIDA_PROJECT_ID`。生产由 Manager 经
`POST /api/v1/projects/runtime-context` 注入容器 env（`AIDA_PROJECT_ID`/`PROJ_ROOT`/`ORG_ROOT`），
一容器一项目；`project_code`（如 K1903）仅作业务展示，**不参与寻址**。`/files/check`、`/artifact`
为泛化端点，projectId 取自容器 env（不逐请求透传）。

```
# 上游读取（3 表 · 语义键）
#   《交付计划表》 → moduleCode=pm-plan     · fileStage=输出结果
#   《到货信息表》 → moduleCode=pm-plan     · fileStage=输入文件
#   《设备位置表》 → moduleCode=ops-design  · fileStage=输出结果 · folderSubPath=建模仿真

# 作业产物写出（本模块）
#   责任人信息表 / 设备安装实施计划 / SN扫码表 / 完工清单 / 完工报告
#     → moduleCode=ops-install · fileStage=输出结果
#   SDUI / /artifact 逻辑键： ops-install/输出结果/<文件名>

# 本地 scratch（业务树之外，不进数据中心）：
#   {AIDA_SCRATCH_DIR | agent/runtime/scratch}/device_install/<run_id>/
#     inbox/  ← 上游下载缓冲     out/    ← 产物生成缓冲（生成后 publish_output 上传 DC）
#     state/  ← tasks_state.json / sn_pool.json / sn_tables.json（运行态）
#     images/ ← 现场照片
#   _uploads/  ← HITL /upload 落点（run 内 fetch 一并扫描）
```

环境：`DATA_CENTER_BASE_URL`（必填，本地 mock：`python agent/.local/mock_datacenter.py`）+ `AIDA_PROJECT_ID`（UUID32 · 本地单项目；生产经 runtime-context 注入）；
可选 `AIDA_BUSINESS_ROOT`（挂载盘降级根）、`AIDA_SCRATCH_DIR`（scratch 根）、`DATA_CENTER_TOKEN`（§1.5 机机内网可空）。

---

## D. HITL 交互设计

| 步骤 | HITL 类型 | 触发条件 | 用户操作 |
|------|-----------|---------|---------|
| principal_fill | EditableTable | 未提交责任人信息 | 按活动复核/补齐「责任人·责任主体」→ 保存并继续 |
| tasks_generate | EditableTable | 未确认实施计划 | 复核/在线编辑「计划开始·计划完成·责任人」→ 确认并生成 |
| task_dispatch | EditableTable（勾选） | 实施计划已生成 | 勾选待下发条目 → 确认下发 |
| esn_fill | EditableTable | 未提交或 ESN 校验未通过 | 大盘内逐台填写 ESN → 提交 |
| progress_select / progress_apply | ChoiceCard | 进展反馈 | 选任务 + 选状态 |

---

## E. 产物清单

| 产物 | 生成步骤 |
|------|---------|
| 责任人信息表.xlsx（按活动） | principal_fill |
| 设备安装实施计划.xlsx（自包含双 Sheet：实施计划 + SN扫码表） | tasks_generate |
| SN扫码表_{机房}_{设备大类}.xlsx | sn_generate |
| 完工清单_{机房}_{设备大类}.xlsx + 设备安装完工报告.xlsx | esn_fill |
