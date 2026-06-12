> 本文件是 software_deployment 主 Skill 的子指令（步骤 ⑧），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ⑧ — 导入 Toolkit 配置 & 刷新底表初始化

## 概述

在与执行机连通后，将步骤⑥生成的 **CloudOps完整配置文件.xlsx** 导入地端 Toolkit（APIGW `UploadFile` / `lldImport`）。
随后执行 **9c 底表刷新**：用「设备安装完工清单」中的 **设备名称 + ESN** 对齐 `device_base_table.json`，把默认“未初始化”更新为“完成初始化”，并重新导出「全量设备完工清单列表」宽表。

## 触发条件

- 用户说「导入 Toolkit」「步骤 8」「导入配置到执行机」
- Host `action` = `toolkit_import_start` → `toolkit_import_invoke`
- `deploy_chain.step7_executor_config_at` 已设置

## 前置要求

| 检查项 | 说明 |
|--------|------|
| Step 6 已完成 | `deploy_chain.step6_cloudops_full_at` 非空，存在 `plan/Output/CloudOps完整配置文件.xlsx` |
| Step 7 已完成 | `ProjectData/plan/RunTime/toolkit_executor.json` 有 `base_url_ip` 与 `secret_key` |
| 网关凭证 | `ProjectData/plan/RunTime/gateway.json`（`apigw_url` / `gateway_key` / `hw_app_id`）；可选环境变量 `CLOUDOPS_*` 覆盖 |
| 完工清单（用于 9c） | `ProjectData/input/cloudops/` 下 `*完工清单*.xlsx`（含列：设备名称、ESN/SN） |

## 执行

```text
toolkit_import_start  → 门禁检查 + 引导确认
toolkit_import_invoke → UploadFile(lldImport) + 底表初始化刷新 + 导出宽表
```

实现：`runtime/driver.py`（toolkit action 分支）  
核心：`software_deployment/8_toolkit_import/scripts/toolkit_import.py`

## 输出

| 字段 / 文件 | 说明 |
|-------------|------|
| `deploy_chain.step8_toolkit_import_at` | 导入与刷新完成时间 |
| `plan/Output/全量设备完工清单列表_*.xlsx` | 覆盖/新增宽表导出（含 latest 别名） |
| `plan/Output/device_base_table.json` | 写回初始化后的任务状态 |

---

本步骤执行完毕，返回 `software_deployment/SKILL.md`。
