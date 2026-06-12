> 命令 · **集群推理测试-单 POD**（clusterInferTask）。执行由 `shared/task_runner` 统一负责。

# 集群推理测试-单 POD cluster_infer_single_pod

对应 CloudOps **子系统测试 → 集群系统集成测试（单 Pod 推理）**；Agent `infer_handler` / `ClusterInferHandler`。

## 前置

步骤 7/8 完成；**推理场景**才可执行（`scene.json` 为 `train` 时无法下发）。

## 特有参数

- 设备字段：`nodeList`
- `groupElementSize`、`storageConfigParam`、`trainConfigParam`：引擎从 **集群推理** 页签 + `shared/subsystem_params/config/cluster_infer/{imageType}.json` 合并（对齐 Agent `parse_cluster_infer_params`）
- 参数页签：**集群推理**（`runtime/params_template_sheets.json`）
- 轮询：`poll_mode=cluster_train`（与训练共用完成判定）
- 导出：Agent 侧为 xlsx；引擎标准 `report.zip`

## 产出

- `ProjectData/results/cluster_infer_single_pod/<task_name>/{report.zip, extracted/, receipt.json}`

## 模板

- `config/execute.json`、`config/query.json`（真值来源 Agent `params/cluster_infer/`）
