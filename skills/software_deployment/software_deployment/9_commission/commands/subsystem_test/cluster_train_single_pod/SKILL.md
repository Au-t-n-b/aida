> 命令 · **集群训练测试-单 POD**（clusterTrainingTask）。执行由 `shared/task_runner` 统一负责。

# 集群训练测试-单 POD cluster_train_single_pod

对应 CloudOps **子系统测试 → 集群系统集成测试（单 Pod 训练）**；Agent `cluster_model_test_handler`。

## 前置

步骤 7/8 完成；**训练场景**才可执行（`scene.json` 为 `infer` 时 SKILL 提示无法下发）。

## 特有参数

- 设备字段：`nodeList`
- `trainConfigParam` / `storageConfigParam` / `groupElementSize`：引擎从 **集群模型** 页签填充（镜像路径、分组大小等）
- 参数页签：**集群模型**（`runtime/params_template_sheets.json`）
- 轮询：`poll_mode=cluster_train`（`resultData.processingNum==0` 或 `reportEnd`）
- `report_wait_s=120`

## 产出

- `ProjectData/results/cluster_train_single_pod/<task_name>/{report.zip, extracted/, receipt.json}`

## 模板

- `config/execute.json`、`config/query.json`（`stepName=cluster-model-test`）
