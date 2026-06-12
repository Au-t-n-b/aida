> 模块 · **集群系统测试**（用户步骤 ⑪ / deploy_chain ⑪）。

# cluster_test — 集群系统测试

全集群 HCCL 与集群模型训练类命令。命令骨架与子系统测试相同，差异在设备范围（默认全集群）与模板参数。

## 命令清单

| 命令 | task_type | device_kind | 状态 |
|------|-----------|-------------|------|
| 集合通信测试 | hccl_test | server | ✅ |
| 集群模型测试 | cluster_model_test | server | ✅ |

## 相近单 Pod 命令（subsystem_test）

| 用户意图 | 应用命令 |
|----------|----------|
| 集群通信配置测试-单 POD | `hccl_test_single_pod` |
| 集群训练测试-单 POD | `cluster_train_single_pod` |

## 共性前置

- 步骤 7/8 完成；`gateway.json` 有效。
- 设备范围统一见 `shared/device_scope/SKILL.md`。

进度：完成任一命令写 `deploy_chain.step11_cluster_test_at`。
