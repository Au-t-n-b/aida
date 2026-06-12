> 命令 · **集群通信配置测试-单 POD**（hcclTestTask）。执行由 `shared/task_runner` 统一负责。

# 集群通信配置测试-单 POD hccl_test_single_pod

对应思维导图 **集群通信配置测试-单Pod**；Agent `hccl_test_handler`（单 Pod 场景）。

## 前置

- 步骤 7/8 完成；多 Pod 项目场景下出现在 task_map。
- 参数页签：**集合通信**（HCCL_SOCKET_IFNAME、测试方式、算子等）
- 引擎运行时从 `params_template_sheets.json` → **集合通信** 填充 `hcclBaseParam.hcclSocketIfname`、`groupElementSize` 等（见 `shared/subsystem_params/subsystem_params_builder.py`）

## 特有参数

- 设备字段：`nodeList`
- query：`stepName=hcclTask`
- `hcclThresholds`：默认嵌入 A3 单 Pod 阈值（`single_pod_threshold/hccl_threshold_A3.json`）
- 轮询：`poll_mode=hccl_count`

## 产出

- `ProjectData/results/hccl_test_single_pod/<task_name>/`

## 模板

- `config/execute.json`、`config/query.json`
