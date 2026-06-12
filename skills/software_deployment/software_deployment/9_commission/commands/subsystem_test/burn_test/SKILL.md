> 命令 · **计算硬件压测**（burnTest）。执行由 `shared/task_runner` 统一负责。

# 计算硬件压测 burn_test

对应 CloudOps 执行机 **服务器测试 → 计算硬件压测**（SP 压测）；Agent `sp_test` / `ThirdActivity.SP_TEST`。

## 前置

- 步骤 7/8 完成；`gateway.json` 有效。
- 通常依赖 init_install（OS / 昇腾安装）已完成。

## 特有参数

- 设备字段：`nodeList`
- 参数页签：**硬件压测**（`runtime/params_template_sheets.json`）
- `burnTestTaskMeta.burnTestTaskConfig.operationType`：Skill 首期固定 `"2"`（下发 + 完整轮询）；`"1"` 时 Agent 仅下发不轮询
- `powerMode`、`operations` 等保持 Agent 默认常量；空值/默认可能导致下发失败（待步骤 8 参数模板运行时解析 Spec 补齐）
- query：仅 `taskId` + 分页，无 `stepName`

## 产出

- `ProjectData/results/burn_test/<task_name>/{report.zip, extracted/, receipt.json}`

## 模板

- `config/execute.json`、`config/query.json`（真值来源 Agent `params/sp_test/`）
