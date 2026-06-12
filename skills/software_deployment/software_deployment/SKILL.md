---
name: software_deployment
description: >
  软件部署与调测全流程编排：作业管理二级任务接收(Step1) → 验收用例与场景拆三级计划(Step2)
  → LLD 下发设备底表(Step3) → CloudOps 初配(Step4) → 手工补充(Step5) → 完整配置与导入前材料检查(Step6)
  → 配置调测设备(Step7) → 导入 Toolkit(Step8) → 部署测试(Step9～11)。
  支持冷启、断点续做、单步重跑、一键重算、演示重置。关键词：部署调测 / 拆分计划 / 下发计划 /
  CloudOps / 接收任务 / 二级任务 / LLD / 完工清单 / 设备底表 / 调测计划
---

# 软件部署与调测 · 全流程编排

本文件是本 Skill 体系的**唯一主入口**，负责流程编排、意图路由与状态恢复。
所有路径均相对于 skill 根目录（`software_deployment/`，含 `runtime/`、`ProjectData/`）。

---

## A. 流程总览

| Step | 名称 | 触发关键词 | 运行时子 Skill | Host action（start → invoke） | 关键输入 → 输出 | 前置依赖 |
|------|------|------------|----------------|------------------------------|-----------------|----------|
| 1 | 接收二级任务 | 接收任务 / 接收二级 / 开始部署 | `plan-receive` | `plan_receive` → `plan_receive_invoke` | 二级 Excel/JSON → `plan/Input/second_level_tasks.json` | `input/plan_receive` 有任务文件 |
| 2 | 拆分调测计划 | 拆分计划 / 拆三级 / 调测计划 | `plan_split` | `plan_split` → `plan_split_invoke` | 用例 Word 存在性检查 + 场景 + 可选 Pod 映射 → `third_level_tasks.json` | `step1_plan_receive_at` 非空 |
| 3 | 下发设备底表 | 下发计划 / 设备底表 / LLD 下发 | `plan_dispatch` | `plan_dispatch` → `plan_dispatch_invoke` | LLD xlsx → `device_base_table.json`、完工清单宽表 | `step2_plan_split_at` 非空，存在三级计划 |
| 4 | CloudOps 初配 | CloudOps 初配 / 生成初配 | `cloudops_init` | `cloudops_init_start` → `cloudops_init_invoke` | LLD → `plan/Output/CloudOps*.xlsx` | `step3_plan_dispatch_at` 非空 |
| 5 | CloudOps 补充 | 补充配置 / 手工表 | `cloudops_supplement` | `cloudops_supplement_start` → `cloudops_supplement_upload_done` | 手工补充表登记 | 步骤 4 已完成（`deploy_chain.step4_*`） |
| 6 | CloudOps 完整配置 + 材料检查 | 完整配置 / 完工清单 / ZTP / 测试参数 | `cloudops_full` | `cloudops_full_start` → `cloudops_full_invoke`；`cloudops_material_check` / `cloudops_ztp_upload_done` / `cloudops_params_upload_done` | 完工清单 + 手工表 → 完整 CloudOps xlsx；ZTP/测试参数只登记提醒 | 步骤 5 已登记 |
| 7 | 配置调测设备 | 调测设备 / 执行机 / SK | `toolkit_executor` | `toolkit_executor_configure` → `toolkit_executor_configured` | 调测 IP/SK → `toolkit_executor.json` | 步骤 6 已生成完整配置 |
| 8 | 导入 Toolkit 配置 | 导入 / Toolkit / 执行机 | `toolkit_import` | `toolkit_import_start` → `toolkit_import_invoke` | 完整 CloudOps xlsx → Toolkit | 步骤 6 + 步骤 7 |

**材料巡检（任意步）**：`upstream_check` → 子 Skill `upstream-check`（只列本步 manifest 槽位，不执行写盘）。

---

## B. 智能路由

| 用户意图关键词 | 路由目标 |
|----------------|----------|
| 开始 / 进入 / 续做 / 冷启 | → **入口** `sd_start`（按 `deploy_chain.json` 推荐下一步） |
| 接收 / 二级任务 / 作业管理 | → **Step 1** |
| 拆分 / 三级 / 验收用例 / 调测计划 | → **Step 2** |
| 下发 / LLD / 设备底表 | → **Step 3** |
| 重算 / 重新拆分 / 同材料重算 | → **`plan_regenerate`**（可选 `include_dispatch`） |
| CloudOps 初配 / 步骤 4 | → **Step 4** |
| 补充 / 手工表 / 步骤 5 | → **Step 5** |
| 完整配置 / 完工清单 / 步骤 6 | → **Step 6** |
| ZTP / 灵衢配置 / 测试参数 | → **Step 6 材料检查** |
| 检查材料 / 本步说明 / 缺什么文件 | → **`upstream_check`** |
| 下载测试底表 / 下载完工清单 / 设备底表 | → **`download_checklist`** |
| 生成调测报告 / 导出报告汇总 | → **`report_aggregate`** |
| 重置 / 演示清空 | → **`sd_reset`** |
| 无法判断 | → **询问用户**，展示上表 |

**材料上传通则（步骤 1～6）**：各步 `*_start` 会扫描对应 `ProjectData/input/` 目录；**已有文件**时展示「已检测到」并给出 **[用目录里的材料，继续]** 与 **[重新上传]**，不强制弹上传卡。

---

## C. 各步骤执行模板

### Step 1：接收二级任务

**前置检查**：

- `ProjectData/input/plan_receive/` 存在 `second_level_tasks.json` 或匹配 `*部署调测任务列表*.xlsx` / `*交付计划*.xlsx`（见 `upstream_manifest` → `second_level_tasks`）
- **目录已有材料**：引导卡展示文件名，用户选「用目录里的材料，继续接收」或「重新上传」
- **目录无材料**：弹出 HITL 上传（purpose `sd-plan-receive-tasks`）

**执行**：Read `software_deployment/plan-receive/SKILL.md`，严格按其中指令；Host 触发 `plan_receive`，用户确认后 `plan_receive_invoke`。

**完成标志**：

- `ProjectData/plan/Input/second_level_tasks.json`
- `deploy_chain.step1_plan_receive_at` 非空

**完成后**：引导用户进入 Step 2：「二级任务已接收，是否拆分调测计划？」

---

### Step 2：拆分调测计划

**前置检查**：

- `deploy_chain.step1_plan_receive_at` 非空（否则先 Step 1）
- `input/plan_split/` 有验收用例 `*.docx`（槽位 `testcase`，必填；本阶段只检查文件存在并记录路径）
- `ProjectData/plan/RunTime/scene.json` 含 `cooling`、`product_specification`、`train_infer_scene`（拆分前由 registry 同步；缺失则提示设定场景）
- 多 Pod 时：`input/plan_split/` 有机房-Pod 映射 xlsx（槽位 `pod_map`）

**执行**：Read `software_deployment/plan_split/SKILL.md`；`plan_split` → `plan_split_invoke`。实现脚本位于 `software_deployment/plan_split/scripts/plan_split.py`（`SECOND_TO_THIRD` + 场景叠加，验收用例 Word **不解析、不逐条入库**）。

**完成标志**：

- `ProjectData/plan/Output/third_level_tasks.json`
- `deploy_chain.step2_plan_split_at` 非空
- `deploy_chain.step2_testcase_path` 记录验收用例 Word 路径

**完成后**：引导 Step 3：「三级计划已生成，是否下发设备底表？」

---

### Step 3：下发设备底表

**前置检查**：

- `deploy_chain.step2_plan_split_at` 非空
- `ProjectData/plan/Output/third_level_tasks.json` 存在
- `input/plan_dispatch/` 有 LLD（文件名含 `LLD设计` 或匹配 manifest `lld_design`）

**执行**：Read `software_deployment/plan_dispatch/SKILL.md`；`plan_dispatch` → `plan_dispatch_invoke`。实现脚本位于 `software_deployment/plan_dispatch/scripts/dispatch_plan.py`。

**完成标志**：

- `ProjectData/plan/Output/device_base_table.json`
- `ProjectData/plan/Output/dispatch_record.json`
- `全量设备完工清单列表_{项目}.xlsx`（及 `_latest.xlsx`）
- `deploy_chain.step3_plan_dispatch_at` 非空

**完成后**：引导 Step 4：「设备底表已下发，是否生成 CloudOps 初配？」

---

### Step 4：CloudOps 初配

**前置检查**：

- `deploy_chain.step3_plan_dispatch_at` 非空
- LLD 仍可解析（与 Step 3 同源或 `input/plan_dispatch`）

**执行**：Read `software_deployment/cloudops_init/SKILL.md`；`cloudops_init_start` → `cloudops_init_invoke`。

**完成标志**：

- `deploy_chain.json` → `step4_cloudops_init_at` 非空
- `plan/Output/` 下 CloudOps 初配 xlsx（路径记入 `step4_cloudops_output_path`）

**完成后**：引导 Step 5。

---

### Step 5：CloudOps 补充

**前置检查**：

- Step 4 已完成
- `input/cloudops/` 有 `CloudOps*手工*.xlsx` 或通过 HITL 上传（purpose `sd-cloudops-manual`）

**执行**：Read `software_deployment/cloudops_supplement/SKILL.md`；`cloudops_supplement_start` → 放入文件后 `cloudops_supplement_upload_done`。

**完成标志**：

- `deploy_chain.json` → `step5_cloudops_supplement_at` 非空

**完成后**：引导 Step 6。

---

### Step 6：CloudOps 完整配置

**前置检查**：

- Step 5 已登记
- `input/cloudops/` 有 `*完工清单*.xlsx`（槽位 `check_list`）
- 手工补充表已就绪（槽位 `cloudops_manual`）

**执行**：Read `software_deployment/cloudops_full/SKILL.md`；`cloudops_full_start` → `cloudops_full_invoke`。

**完成标志**：

- `deploy_chain.json` → `step6_cloudops_full_at` 非空
- `plan/Output/` 完整 CloudOps 配置 xlsx（`step6_cloudops_full_path`）

**完成后**：展示步骤 6b「导入前材料检查」：

- ZTP 文件：A3 场景建议上传，供后续灵衢配置检查使用；可由系统设计模块输出，也可用户直接上传；文件名需带 `ZTP`。
- CloudOps 上传测试参数：供后续 Toolkit 具体 API 任务按需解析；可下载模板后填写并上传。

这两项 **不阻塞** 后续「配置调测设备 / 导入 CloudOps 配置文件」；缺失时只提醒，真正执行相关测试任务时再做强校验。

**材料登记动作**：

- `cloudops_material_check`：刷新 ZTP / 测试参数状态
- `cloudops_ztp_upload_done`：登记 `ZTP*.zip`
- `cloudops_params_upload_done`：登记 `CloudOps_task_params*.xlsx` 或文件名含「测试参数」的 xlsx

**完成标志**：

- `deploy_chain.json` → `step6_cloudops_full_at` 非空
- `plan/Output/` 完整 CloudOps 配置 xlsx（`step6_cloudops_full_path`）
- 可选材料：`step6_ztp_at`、`step6_params_at`

**完成后**：可继续 Step 7「配置调测设备」，或直接尝试 Step 8「导入 Toolkit」（若执行机未配置会提示回 Step 7）。

---

## D. 一键重算模式

当用户说「重算调测计划」「同材料重新拆分」：

1. 确认 `plan_receive` 或 `plan/Input/second_level_tasks.json` 可读
2. Host action：`plan_regenerate`（确认后 `plan_regenerate_invoke`）
3. 默认覆盖 `third_level_tasks.json`；`include_dispatch: true` 且存在 LLD 时同时覆盖 `device_base_table.json`
4. **不**自动清除 CloudOps 链；若需从 Step 4 重做，使用 `sd_reset` + `from_step: 4`

---

## E. 状态恢复（断点续跑）

每次执行前读取：

- `ProjectData/plan/RunTime/deploy_chain.json` → 用户可见 1～11 步进度（`stepN_*` 字段名与步骤号一致），`state.json` 已废弃
- 粗粒度 step 由 `paths.load_plan_runtime_step` 从 `step1_*~step3_*` 推导

| 场景 | 推荐行为 |
|------|----------|
| 无 `step1_plan_receive_at` | 从 Step 1 开始 |
| 有 step1、无 step2 | 从 Step 2 开始 |
| 有 step2、无 step3 | 从 Step 3 开始 |
| 有 step3 且 step4 空 | 从 Step 4 开始 |
| step4 有、step5 空 | 从 Step 5 开始 |
| step5 有、step6 空 | 从 Step 6 开始 |
| step6 有、调测设备未配置 | 从 Step 7 开始 |
| 已导入 Toolkit | 进入 Step 9 及后续测试任务 |

用户显式指定步骤时，以用户指令为准。`sd_start` 会根据上表给出推荐按钮。

---

## F. 环境预检

用户说「检查材料」或 `upstream_check`：

- 调用 `runtime/paths.check_prerequisites(for_actions=[...])`
- 仅展示**当前步骤**在 `upstream_manifest.json` 中 `requiredFor` 匹配的槽位
- 不写入 state / Output

拆分前额外建议：确认 `scene.json` 已由项目 registry 同步（`runtime/projects_registry.py`）。

---

## G. 路径与配置

| 用途 | 路径 / 模块 |
|------|-------------|
| 路径函数 | `runtime/paths.py` |
| 材料 manifest | `data/upstream_manifest.json` |
| CloudOps 模板（步骤 4） | `4_cloudops_init/templates/cloud_ops_config_template.xlsx` |
| 二级→三级规则 | `data/rules/second_to_third.json` |

禁止在文档或脚本中硬编码绝对路径；一律相对 skill 根目录。

---

## H. 演示重置（仅联调）

```json
{
  "action": "sd_reset",
  "from_step": 3,
  "reset_scope": "dispatch"
}
```

| from_step / reset_scope | 效果 |
|-------------------------|------|
| 1 / `all` | `state`→`idle`，清 plan Output + CloudOps 链 |
| 2 / `split` | `state`→`received`，清拆分及之后产物 |
| 3 / `dispatch` | `state`→`split`，清下发及 CloudOps |
| 4～6 / `cloudops` | 保持 `dispatched`，仅清 `deploy_chain` 与 CloudOps xlsx |

**默认保留** `ProjectData/input/*`。

---

## I. Agent 算法对照（变更时同步）

| 概念 | Agent 参考 |
|------|------------|
| 部署调测 Agent | `deployment_agent` |
| 拆分计划 | `third_level_tasks_handler.init_software_deployment` |
| 静态二级→三级 | `constant/tasks.py` → `SECOND_TO_THIRD` |
| 下发 | `dispatch_task.dispatch_tasks` |
| CloudOps | `lld_file_handler`、`checklist_file_handler` |
| 本地实现 | `software_deployment/*/scripts/`（各子 skill 就近实现） |

规则变更时：更新 `data/rules/second_to_third.json` 与 `software_deployment/plan_split/scripts/constants.py`，并修订对应子 `SKILL.md`。
