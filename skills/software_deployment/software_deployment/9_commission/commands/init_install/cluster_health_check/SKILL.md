> 命令 · **集群健康检查**（clusterHealthCheck）。执行由 `shared/task_runner` 统一负责。

# 集群健康检查 cluster_health_check

对服务器集群执行健康检查（集群侧）。`device_kind=server`，设备来自底表已初始化设备。

参数模板页签：**集群健康检查**（`CloudOps_task_params_template_*.xlsx`），默认检查项模板 `全量检测-A3服务器`。

## 前置

步骤 7/8 完成；`gateway.json` 有效。

## 特有参数

- 设备字段：`serviceDeviceIds`。
- `scenario`：由 `scene.json` 推导，引擎自动填。
- `serverTemplateId` / `switchTemplateId`：与 Agent `cluster_health_check` 一致（openlab 模板为 A3 全量检测）。
- query：**无** `stepName`，`deviceType=1`。
- 导出：先 `ReportQuery`（`checkType=server`）取 `createTime`，再 `ReportExport` 带 `reportList`。

## 产出

- `ProjectData/results/cluster_health_check/<task_name>/{report.zip, extracted/, receipt.json}`

## 模板

- `config/execute.json`、`config/query.json`
