> 本文件是 software_deployment 主 Skill 的子指令（Step 4/6），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ④ — CloudOps 初配

## 概述

由 **LLD** 生成 CloudOps **初始配置** xlsx，写入 `plan/Output/`，作为步骤 ⑤⑥ 的基线文件。

## 触发条件

- 用户说「CloudOps 初配」「生成初配」「步骤 4」
- Host `action` = `cloudops_init_start` → `cloudops_init_invoke`
- 进度为 `dispatched`（deploy_chain.step3_plan_dispatch_at 已设置）

## 前置要求

| 检查项 | 说明 |
|--------|------|
| 计划已下发 | `sync_step3_from_state()` 为真（见 `runtime/deploy_chain.py`） |
| LLD 可解析 | 与 Step 3 同源：`resolve_lld_path` / `input/plan_dispatch` |
| CloudOps 模板 | `4_cloudops_init/templates/cloud_ops_config_template.xlsx`（相对 `software_deployment/`；可用 `SD_CLOUDOPS_TEMPLATE_PATH` 覆盖） |

若 Step 3 未完成，子流程引导 `plan_dispatch`。

## 执行

```text
cloudops_init_start   → 列 LLD、hitl.confirm_request
cloudops_init_invoke  → run_cloudops_init_for_project(...)
```

实现：`runtime/subskills/cloudops/runtime/driver.py` → `_run_init`  
核心：`software_deployment/cloudops_init/scripts/cloudops_runner.py`、`lld_to_cloudops.py`。

## 输出

| 字段 / 文件 | 说明 |
|-------------|------|
| `deploy_chain.step4_cloudops_init_at` | ISO 时间戳 |
| `deploy_chain.step4_cloudops_output_path` | 初配 xlsx 相对或绝对路径 |
| `deploy_chain.step4_cloudops_lld_source` | 所用 LLD 路径 |
| `plan/Output/CloudOps*.xlsx` | 初配工作簿 |

## 依赖

- `openpyxl`
- 与部署调测 Agent `lld_file_handler` 行为对齐的本地转换逻辑

## 完成后

引导 Step 5：「初配已生成。请放入 **手工补充表** 并说 **补充配置**。」

---

本步骤执行完毕，返回 `software_deployment/SKILL.md` 继续 Step 5。
