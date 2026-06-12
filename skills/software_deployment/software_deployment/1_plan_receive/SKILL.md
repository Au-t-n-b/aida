> 本文件是 software_deployment 主 Skill 的子指令（Step 1/6），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ① — 接收二级任务

## 概述

将作业管理下发的**部署调测二级活动**（Excel 或 JSON）规范化写入 `plan/Input/`，作为后续拆分三级的唯一任务源。

## 触发条件

- 用户说「接收任务」「接收二级任务」「开始部署调测」
- Host `action` = `plan_receive`（材料确认后 `plan_receive_invoke`）
- 冷启后进度为 `idle`（deploy_chain 无 step1_*）

## 前置要求

| 检查项 | 路径 / 规则 |
|--------|-------------|
| 二级任务文件 | `ProjectData/input/plan_receive/` 下存在下列之一：`second_level_tasks.json`、`*部署调测任务列表*.xlsx`、`*交付计划*.xlsx` |
| 目录可写 | `ProjectData/plan/Input/`、`ProjectData/plan/RunTime/` 可创建 |

缺失时 Host 发出 HITL 上传卡：`purpose` = `sd-plan-receive-tasks`，落盘至 `input/plan_receive`，resume = `plan_receive_invoke`。

## 执行

```bash
# 在 skill 根目录执行（与 zhgk scene-filter 一致）
python software_deployment/1_plan_receive/scripts/receive_tasks.py
```

平台内由 `plan_receive` → `plan_receive_invoke` 触发；进度写入 `deploy_chain.step1_*`，**不要**手工改进度文件。

1. `plan_receive`：列出 manifest 槽位 `second_level_tasks`，`hitl.confirm_request`
2. `plan_receive_invoke`：调用本目录脚本逻辑（`receive_tasks.run_receive` / `persist_received_tasks`）

编排入口：`runtime/subskills/plan/runtime/driver.py`（仅 HITL 与事件，业务在 `scripts/receive_tasks.py`）。

重新上传：`plan_receive_reupload`（同上传 purpose `sd-plan-receive-tasks`）。

## 输出

| 文件 | 位置 | 说明 |
|------|------|------|
| `second_level_tasks.json` | `ProjectData/plan/Input/` | 规范化二级任务列表 |
| `deploy_chain.json` | `ProjectData/plan/RunTime/` | `step1_plan_receive_at`、`step1_second_tasks_path`、`step1_task_count` |

## 依赖

- Python：`openpyxl`（读 xlsx）
- 规则：槽位定义见 `data/upstream_manifest.json` → `second_level_tasks`

## 完成后

返回主编排；引导话术：「二级任务已接收（N 条）。请上传验收用例并说 **拆分计划**。」

---

本步骤执行完毕，返回 `software_deployment/SKILL.md` 继续 Step 2。
