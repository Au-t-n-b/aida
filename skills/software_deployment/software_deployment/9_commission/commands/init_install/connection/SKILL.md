> 命令 · **服务器连线检查**（connectionCheck）。执行由 `shared/task_runner` 统一负责。

# 服务器连线检查 connection

校验服务器（BMC/带内）连线。`device_kind=server`，设备来自底表已初始化设备。

## 前置

步骤 7/8 完成；`gateway.json` 有效。

## 特有参数

- `scenario`：由 `scene.json` 推导（训练 trainingServer / 推理 inferenceServer），引擎自动填。
- 设备字段：`serviceDeviceIds`。

## 产出

- `ProjectData/results/connection/<task_name>/{report.zip, extracted/, receipt.json}`
- `deploy_chain.step9_init_install_at`

## 模板

- `config/execute.json`、`config/query.json`（stepName=connectionCheckCollection, deviceType=1）。
