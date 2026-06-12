> 命令 · **灵衢总线打流测试**（trafficTest）。执行由 `shared/task_runner` 统一负责。

# 打流测试 traffic_test

对应 CloudOps **灵衢总线打流测试**；Agent `traffic_test_handler`。

## 前置

- 步骤 7/8 完成；计算节点已初始化。
- 参数页签：**灵衢总线打流测试**（测试类型、芯片类型、是否跨节点）。

## 特有参数

- 设备字段：`deviceIds`
- **`trafficTestConfigs`**：引擎运行时按 POD 生成（见 `shared/traffic_config/traffic_config_builder.py`）
  - 参数默认值：`runtime/params_template_sheets.json` → **灵衢总线打流测试**
    - 场景：测试类型 / 芯片类型 / 是否跨节点
    - 流参数（对齐 Agent `TrafficTestParamsSet`）：**端口** / **数据大小** / **迭代次数** → `port` / `dataSize` / `cycleNum`
    - 缺省：`cycleNum=40`；HCCS 下 `dataSize` 留空（CloudOps 不接受 `256M` 类后缀，会 9003）
  - IP 映射：CloudOps《服务器信息》`设备ID` ↔ `管理网-IPV4地址`
  - 若模板里已有非空 `trafficTestConfigs` 则不再覆盖
- 轮询：`poll_mode=traffic_array`（`data` 为数组，全部 `optResult != "0"` 视为完成）
- 报告格式：xlsx（Toolkit 导出）

## 产出

- `ProjectData/results/traffic_test/<task_name>/`

## 模板

- `config/execute.json`、`config/query.json`
