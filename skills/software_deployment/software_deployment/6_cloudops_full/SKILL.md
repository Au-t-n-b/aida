> 本文件是 software_deployment 主 Skill 的子指令（Step 6），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ⑥ — CloudOps 完整配置

## 概述

合并 **初配表 + 手工补充表 + 设备安装完工清单**，生成可导入的 **CloudOps 完整配置** xlsx；随后检查 ZTP 与 CloudOps 测试参数是否已上传。

## 触发条件

- 用户说「完整配置」「完工清单配置」「步骤 6」
- Host `action` = `cloudops_full_start` → `cloudops_full_invoke`
- 材料检查 / 上传回调：`cloudops_material_check`、`cloudops_ztp_upload_done`、`cloudops_params_upload_done`
- `deploy_chain.step5_cloudops_supplement_at` 已设置

## 前置要求

| 检查项 | manifest 槽位 |
|--------|----------------|
| 完工清单 | `check_list`：`*完工清单*.xlsx` in `input/cloudops/` |
| 手工补充 | `cloudops_manual`：`CloudOps*手工*.xlsx` |
| 初配基线 | `step4_cloudops_output_path` 有效 |
| Step 5 已登记 | `step5_cloudops_supplement_at` 非空 |

`preflight_step6`（`software_deployment/cloudops_full/scripts/prerequisites.py`）汇总缺失项；缺清单时弹出 HITL：`sd-cloudops-checklist`。

可选（后续测试阶段）：`cloudops_params`、`ztp_bundle`（见 manifest）。它们只提醒和登记，不阻塞 Step 7/8。

## 执行

```text
cloudops_full_start   → preflight，缺材料则 HITL + 重试按钮
cloudops_full_invoke  → run_full_config_for_project(...) → 展示 ZTP/测试参数材料面板
cloudops_material_check → 刷新 ZTP/测试参数状态
```

实现：`runtime/subskills/cloudops/runtime/driver.py` → `_run_full`  
核心：`software_deployment/6_cloudops_full/scripts/checklist_to_full.py`、`checklist_to_cloudops.py`；  
步骤 6b 材料检查：`software_deployment/6_cloudops_full/scripts/material_check.py`（ZTP zip + 测试参数 xlsx）。

## 输出

| 字段 / 文件 | 说明 |
|-------------|------|
| `deploy_chain.step6_cloudops_full_at` | 完成时间 |
| `deploy_chain.step6_cloudops_full_path` | 完整配置 xlsx |
| `deploy_chain.step6_materials_checked_at` | ZTP/测试参数检查时间 |
| `deploy_chain.step6_ztp_at` / `step6_params_at` | 可选材料登记时间 |
| `plan/Output/` | 最终 CloudOps 工作簿（名称依项目规则） |

## 当前限制

- Toolkit 流水线执行、测试报告生成属后续步骤；需另行配置执行机 / APIGW。
- 参数模板 `CloudOps_task_params*.xlsx` 和 ZTP zip 用于后续具体 Toolkit API 任务，本地 Skill 仅提示/登记，不强制 Step 6 或导入成功条件。

## 依赖

- `openpyxl`

## 完成后

可在工作台预览 `plan/Output` 产物；即使 ZTP/测试参数未齐，也可继续 Step 7「配置调测设备」与 Step 8「导入 CloudOps 配置」。

---

本步骤执行完毕，返回 `software_deployment/SKILL.md`。
