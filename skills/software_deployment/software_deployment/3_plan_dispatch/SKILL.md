> 本文件是 software_deployment 主 Skill 的子指令（Step 3/6），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ③ — 下发设备底表

## 概述

读取 **LLD 设计** xlsx，按三级活动与设备类型规则展开**设备底表 JSON**，并导出 Agent 同款**全量设备完工清单**宽表，供 CloudOps 与现场使用。

## 触发条件

- 用户说「下发计划」「下发设备底表」「LLD 下发」
- Host `action` = `plan_dispatch` → `plan_dispatch_invoke`
- 进度为 `split`（deploy_chain.step2_plan_split_at 已设置）

## 前置要求

| 检查项 | 说明 |
|--------|------|
| 三级计划 | `ProjectData/plan/Output/third_level_tasks.json` 存在 |
| LLD | `input/plan_dispatch/` 下文件名含 **LLD设计** 或匹配 manifest `lld_design`（可放在 `lld/` 子目录） |
| 状态 | 未完成 Step 2 时提示先 `plan_split` |

缺失 LLD 时 HITL：`purpose` = `sd-plan_dispatch-lld`，resume = `plan_dispatch_invoke`。

## 执行

```text
plan_dispatch          → 确认 LLD 与三级计划
plan_dispatch_invoke   → dispatch_device_base(...) + checklist_export
```

实现：

- `runtime/subskills/plan/runtime/driver.py` → `_run_plan_dispatch`
- `software_deployment/plan_dispatch/scripts/dispatch_plan.py`
- `runtime/checklist_export.py`（宽表 xlsx + `_latest` 副本）

LLD 解析规则与 CPCIA `DispatchTask.load_lld_data` 对齐。

## 输出

| 文件 | 位置 | 说明 |
|------|------|------|
| `device_base_table.json` | `plan/Output/` | 设备底表（结构化） |
| `dispatch_record.json` | `plan/Output/` | 下发元数据 |
| `全量设备完工清单列表_{项目}.xlsx` | `plan/Output/` | 宽表 |
| `全量设备完工清单列表_latest.xlsx` | `plan/Output/` | 工作台默认打开副本 |
| `deploy_chain.json` | `plan/RunTime/` | `step3_plan_dispatch_at`、`step3_lld_path`、`step3_device_base_path`、`step3_checklist_path` |

## 依赖

- `openpyxl`
- 设备类型规则：`data/rules/third_activity_device_type.json`

## 完成后

引导 Step 4：「设备底表已生成。是否 **CloudOps 初配**？」

---

本步骤执行完毕，返回 `software_deployment/SKILL.md` 继续 Step 4。
