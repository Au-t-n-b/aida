> 命令 · **集合通信测试（全集群版）**。✅ 已接入。

# 集合通信测试 hccl_test

对应思维导图 **11. 集群系统测试** · 跨 Pod / 全集群 HCCL 集合通信测试。

## 与单 Pod 版差异

| 项 | 全集群 `hccl_test` | 单 Pod `hccl_test_single_pod` |
|----|-------------------|------------------------------|
| 模块 | `cluster_test` | `subsystem_test` |
| 默认范围 | `scope=all`（多 Pod 节点） | `scope=pod` |
| `hcclThresholds` | 模板为空 `[]`；Agent handler 按场景选阈值文件 | 模板含单 Pod 阈值数组 |
| `work_stage` | `hcclTestTask` | 同左 |
| `poll_mode` | `hccl_count` | 同左 |

模板来源：Agent `config/params/hccl_test/{execute,query}.json`。

## 前置

- 步骤 7/8 完成；集群节点已初始化且 OS/昇腾就绪。
- 全集群场景需多 Pod 节点在设备底表登记。

## 设备范围

- `device_kind=server`，`device_field=nodeList`。
- 联调推荐先 `scope=pod` 小范围验证，再 `scope=all`。

## 产出

- `ProjectData/results/hccl_test/<taskName>/report.zip`
- 进度：`deploy_chain.step11_cluster_test_at`
