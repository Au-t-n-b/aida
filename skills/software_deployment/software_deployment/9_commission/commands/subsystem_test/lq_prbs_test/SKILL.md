> 命令 · **灵衢 PRBS 压测**（prbsStressTest）。执行由 `shared/task_runner` 统一负责。

# 灵衢 PRBS 测试 lq_prbs_test

对应 CloudOps **灵衢 PRBS 压测**；Agent `lq_prbs_stress_test` / `ThirdActivity.PRBS_TEST`。

## 前置

- 步骤 7/8 完成；灵衢交换机已初始化（init_install）。
- 参数页签：**灵衢PRBS压测**（误码率阈值、压测时长）。

## 特有参数

- 设备字段：`deviceIds`（`device_kind=switch`，来源《交换机信息》）
- `work_stage`：`prbsStressTest`
- 三步轮询：`selectNodes` → `prbsStressTest` → `recoverDevice`（间隔 60s）
- `stressTestConfig` 默认与 Agent `execute.json` 一致

## 产出

- `ProjectData/results/lq_prbs_test/<task_name>/{report.zip, extracted/, receipt.json}`
- 完成后光模块恢复约 **1.5 小时**（现场需等待）

## 模板

- `config/execute.json`、`query_select_nodes.json`、`query_prbs_stress.json`、`query_recover.json`
