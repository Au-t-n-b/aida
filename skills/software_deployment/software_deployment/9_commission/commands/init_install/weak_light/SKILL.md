> 命令 · **服务器弱光检查**（weakLightCheck）。执行由 `shared/task_runner` 统一负责。

# 服务器弱光检查 weak_light

校验服务器光模块弱光、闪断、温度等。`device_kind=server`，设备来自底表已初始化设备。

## 前置

步骤 7/8 完成；`gateway.json` 有效；底表 `taskStatus=INIT_DONE`。

## 特有参数

- 设备字段：`serverDeviceIds`（注意：不是 `serviceDeviceIds`）。
- `configs[]`：弱光/闪断/温度阈值（模板内置，与 Agent 一致）。
- `collectAllServer` / `collectAllSwitch`：默认 `false`，由 `serverDeviceIds` 指定范围。
- `scenario`：由 `scene.json` 推导，引擎自动填。

## 产出

- `ProjectData/results/weak_light/<task_name>/{report.zip, extracted/, receipt.json}`
- `deploy_chain.step9_init_install_at`

## 模板

- `config/execute.json`、`config/query.json`（stepName=collectInfo, deviceType=1）。
