> 本文件是 software_deployment 主 Skill 的子指令（Step 5/6），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ⑤ — CloudOps 补充配置

## 概述

登记或上传 **CloudOps 手工补充表**，更新 `deploy_chain` 中的补充路径，为步骤 ⑥ 合并完工清单做准备。本步**不**生成最终完整配置。

## 触发条件

- 用户说「补充配置」「手工表」「步骤 5」
- Host `action` = `cloudops_supplement_start` → `cloudops_supplement_upload_done`
- `deploy_chain.step4_cloudops_init_at` 已设置

## 前置要求

| 检查项 | 说明 |
|--------|------|
| Step 4 已完成 | `step4_cloudops_init_at` 非空 |
| 手工表（执行时） | `input/cloudops/CloudOps*手工*.xlsx` 或 `CloudOps*补充*.xlsx` |
| 初配产物 | `step4_cloudops_output_path` 指向有效 xlsx |

未完成 Step 4 时子流程提供按钮回到 `cloudops_init_start`。

## 执行

```text
cloudops_supplement_start        → 展示 probe 结果、可选 HITL（sd-cloudops-manual）
cloudops_supplement_upload_done  → process_manual_supplement_upload(...)
```

实现：`runtime/subskills/cloudops/runtime/driver.py` → `_run_supplement`  
核心：`software_deployment/cloudops_supplement/scripts/supplement.py`。

用户也可**不经过上传卡**，直接将 xlsx 放入 `input/cloudops` 后点「登记步骤 5」。

## 输出

| 字段 | 说明 |
|------|------|
| `deploy_chain.step5_cloudops_supplement_at` | 登记时间 |
| `deploy_chain.step5_cloudops_manual_path` | 手工表路径 |
| `deploy_chain.step5_checklist_detected` | 是否已探测到完工清单（可为 false，Step 6 再补） |

## 依赖

- `openpyxl`

## 完成后

引导 Step 6：「补充已登记。请上传 **完工清单** 并说 **完整配置**。」

---

本步骤执行完毕，返回 `software_deployment/SKILL.md` 继续 Step 6。
