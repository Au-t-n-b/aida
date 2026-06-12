> 命令 · **集群模型测试（全集群版）**。✅ 已接入。

# 集群模型测试 cluster_model_test

对应思维导图 **11. 集群系统测试** · 跨 Pod / 全集群训练集成验证。

## 与单 Pod 版差异

| 项 | 全集群 `cluster_model_test` | 单 Pod `cluster_train_single_pod` |
|----|----------------------------|-----------------------------------|
| 模块 | `cluster_test` | `subsystem_test` |
| 默认范围 | `scope=all` | `scope=pod` |
| `work_stage` | `clusterTrainingTask` | 同左 |
| `poll_mode` | `cluster_train` | 同左 |
| query `stepName` | `cluster-model-test` | 同左 |

模板来源：Agent `config/params/cluster_model_test/{execute,query}.json`；运行时由 `subsystem_params_builder` enrich 训练参数。

## 前置

- 步骤 7/8 完成；训练镜像与模型路径已在参数模板或 execute 模板中配置。
- 全集群训练耗时长（默认 `hours=12`），联调可用 `scope=pod` 缩小范围。

## 设备范围

- `device_kind=server`，`device_field=nodeList`。

## 产出

- `ProjectData/results/cluster_model_test/<taskName>/report.zip`
- 进度：`deploy_chain.step11_cluster_test_at`
