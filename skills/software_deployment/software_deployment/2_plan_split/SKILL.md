> 本文件是 software_deployment 主 Skill 的子指令（Step 2/6），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ② — 拆分调测计划

## 概述

在二级任务基础上，结合**项目场景**（液冷/训推/A2A3/多 Pod）完成拆分，并检查验收用例 Word 是否已接收：

1. **基于场景选择软件部署活动**：静态表 `SECOND_TO_THIRD` + 场景叠加 → `third_level_tasks.json`
2. **验收用例检查**：验收用例 Word（.docx）只做存在性检查并记录路径，不做测试活动抽取。

三级列表**不是**把 Word 逐条当作三级来源；测试活动抽取需求未明确前，Word 不解析、不写结构化测试活动。

## 触发条件

- 用户说「拆分计划」「拆三级」「生成调测计划」
- Host `action` = `plan_split` → `plan_split_invoke`
- 进度为 `received`（deploy_chain.step1_plan_receive_at 已设置）

## 前置要求

| 检查项 | 说明 |
|--------|------|
| Step 1 已完成 | `deploy_chain.step1_plan_receive_at` 非空；存在 `plan/Input/second_level_tasks.json` |
| 验收用例 | `input/plan_split/*.docx`（manifest `testcase`，**必填**；系统设计输出或手工上传） |
| 场景 | `plan/RunTime/scene.json` 含 `cooling`、`product_specification`、`train_infer_scene`（拆分前 `sync_scene_from_projects`） |
| 多 Pod | `input/plan_split/` 含 `*机柜*架构*.xlsx` 或 `*Pod*.xlsx`（manifest `pod_map`） |

可选：`input/plan_split/*场景*.xlsx`、`*人员*.xlsx`。

## 业务规则（Agent 须遵守）

1. **Word 用途**：只检查 `*.docx` 已上传并写入 `deploy_chain.step2_testcase_path`；**不**作为三级行来源。
2. **三级来源**：`data/rules/second_to_third.json` + `software_deployment/plan_split/scripts/constants.py` 场景叠加（对齐 CPCIA `generate_task_map()`）。
3. **拆分前**自动同步 `scene.json`（请求带 `project_id` 或 `NANOBOT_PROJECTS_JSON`）。

## 执行

```text
plan_split          → 列材料、缺则 HITL（sd-plan_split-testcase / sd-plan_split-pod-map）
plan_split_invoke   → 调用 `software_deployment/plan_split/scripts/plan_split.split_plan(...)`
```

实现：`runtime/subskills/plan/runtime/driver.py` → `_run_plan_split`。

## 输出

| 文件 | 位置 | 说明 |
|------|------|------|
| `third_level_tasks.json` | `ProjectData/plan/Output/` | 三级活动列表（场景+二级映射） |
| `deploy_chain.json` | `ProjectData/plan/RunTime/` | `step2_plan_split_at`、`step2_testcase_path`、三级任务数量等 |

## 依赖

- `openpyxl`、`python-docx`
- 规则文件：`data/rules/second_to_third.json`

## 完成后

引导 Step 3：「已生成 N 条三级活动。请准备 LLD 并说 **下发计划**。」

---

本步骤执行完毕，返回 `software_deployment/SKILL.md` 继续 Step 3。
