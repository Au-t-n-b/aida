> 本文件是 software_deployment 主 Skill 的子指令（步骤 ⑦），由 `software_deployment/SKILL.md` 编排调用。

# 步骤 ⑦ — 设置调测设备（执行机 IP / SK）

## 概述

登记 Toolkit 网关 **调测 IP** 与 **SK**，写入 `ProjectData/plan/RunTime/toolkit_executor.json`，供步骤 8～11 导入 CloudOps、下发调测任务时读取。

对齐 Agent：图 1「设置调测设备」对话框（调测 IP + SK）；端口固定 **28880**（不在界面展示）。

## 触发条件

- Host `action` = `toolkit_executor_configure` → 用户填写表单 → `toolkit_executor_configured`
- `deploy_chain.step6_cloudops_full_at` 已设置（步骤 6 已生成完整配置；ZTP/测试参数可后补）

## 执行

```text
toolkit_executor_configure   → hitl.form_request（调测IP + SK 两个输入框）
toolkit_executor_configured  → 解析表单 → 写入 toolkit_executor.json → 更新 deploy_chain
```

实现：`runtime/driver.py`（toolkit 子流程）+ `runtime/toolkit_executor.py`。

## 输出

| 字段 | 说明 |
|------|------|
| `deploy_chain.step7_executor_config_at` | 登记时间 |
| `plan/RunTime/toolkit_executor.json` | `base_url_ip`、`base_url_port`（28880）、`secret_key` |

## 完成后

可继续步骤 8「导入 CloudOps 配置文件」（Workbench / Toolkit 联调）。

---

本步骤执行完毕，返回 `software_deployment/SKILL.md`。
