> 命令 · **服务器 OS 安装**（osInstall）。执行由 `shared/task_runner` 统一负责。

# 服务器 OS 安装 os_install

对服务器下发 OS 安装任务（挂载 ISO 等）。`device_kind=server`，设备来自底表已初始化设备。

## 前置

步骤 7/8 完成；`gateway.json` 有效。
ISO/驱动路径默认取自 UAT 参数模板 xlsx「OS安装」页签占位值（`E:\data\openlab\...`、`pcBmcIp=141.4.154.167`），仅用于联调 CreateTask；现场请改为真实路径。

## 特有参数

- 设备字段：`deviceIds`（不是 `serviceDeviceIds`）。
- **不传** `taskName`（与连线检查不同）。
- `scenario`：由 `scene.json` 推导，引擎自动填。
- query：`stepName=batchMountIso`。

## 产出

- `ProjectData/results/os_install/<task_name>/{report.zip 或 xlsx, extracted/, receipt.json}`
- `deploy_chain.step9_init_install_at`

## 模板

- `config/execute.json`、`config/query.json`
