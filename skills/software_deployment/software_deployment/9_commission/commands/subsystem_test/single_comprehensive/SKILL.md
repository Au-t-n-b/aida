> 命令 · **单机综合检测**（singleComprehensiveDetection）。执行由 `shared/task_runner` 统一负责。

# 单机综合检测 single_comprehensive

对应 CloudOps 执行机 **单机测试 → 单机综合检测**；Agent `single_comprehensive_check` / `ThirdActivity.SINGLE_COMPREHENSIVE_TEST`。

与 **集群健康检查**（`cluster_health_check`）、**服务器健康检查**（CloudOps 图1，Agent 无 handler）不同。

## 前置

步骤 7/8 完成；`gateway.json` 有效。

## 特有参数

- 设备字段：`deviceIds`
- `templateId`：参数模板 xlsx **单机综合检测** 页签（openlab 默认 `全量检测-A3服务器` → `f2a3059ee6af4915ab59081848eec03f`）
- `scenario`：由 `scene.json` 推导，引擎自动填
- query：`stepName=collectInfo`，`deviceType=1`

## 产出

- `ProjectData/results/single_comprehensive/<task_name>/{report.zip, extracted/, receipt.json}`

## 模板

- `config/execute.json`、`config/query.json`（真值来源 Agent `params/single_comprehensive_check/`）
