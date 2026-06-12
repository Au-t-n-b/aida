> 命令 · **灵衢连线检查**（lqConnectionCheck）。执行由 `shared/task_runner` 统一负责。

# 灵衢连线检查 lq_connection

校验灵衢交换机连线。`device_kind=switch`，设备来自 CloudOps 完整配置《交换机信息》表。

## 前置

步骤 7/8 完成；完整配置含《交换机信息》；`gateway.json` 有效。

## 特有参数

- 设备字段：`switchesDeviceIds`。
- `checkType=hccsSwitch`（模板内置）。

## 产出

- `ProjectData/results/lq_connection/<task_name>/{report.zip, extracted/, receipt.json}`
- `deploy_chain.step9_init_install_at`

## 模板

- `config/execute.json`、`config/query.json`（stepName=connectionCheckCollection, deviceType=2）。
