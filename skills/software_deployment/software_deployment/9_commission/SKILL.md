> 本文件是 **步骤 ⑨⑩⑪ — 下发调测（9_commission）** 的总索引（Host `software_deployment` 编排调用）。
> 职责：**语义识别 + 路由下发**。本层不写执行细节；执行由 `shared/task_runner` 统一负责。

# 下发调测 · 9_commission（步骤 9+10+11 集合体）

「下发任务进行调测」的集合体，向下分三模块，命令骨架统一（下发→轮询→导出→存储）。

| 模块 | 目录 | 用户步骤 | deploy_chain |
|------|------|----------|--------------|
| 初始化与软件安装 | `commands/init_install/` | ⑨ | `step9_init_install_at` |
| 子系统测试 | `commands/subsystem_test/` | ⑩ | `step10_subsystem_test_at` |
| 集群系统测试 | `commands/cluster_test/` | ⑪ | `step11_cluster_test_at` |

## 框架（三层）

```
9_commission/
├── SKILL.md
├── shared/
│   ├── device_scope/       ← 设备范围（8 种文法）
│   ├── task_catalog/       ← 命令注册表
│   ├── task_runner/        ← 通用引擎 + hooks + parsers + params_loader
│   ├── subsystem_params/   ← 子系统/集群参数填充
│   └── traffic_config/     ← 打流测试 configs 生成
└── commands/<module>/<cmd>/ ← config/{execute,query}.json + 薄 SKILL.md
```

## 语义识别

把用户**一句命令**解析为结构化参数，调用 Host action **`commission_run`**：

| 参数 | 说明 |
|------|------|
| `command` | 命令名或别名（见 `shared/task_catalog`） |
| `scope` / `pod_ids` / `devices` / `task_no` / `only_installed` | 设备范围（见 `shared/device_scope/SKILL.md`） |

路由：`task_catalog.resolve_task(command)` → `task_runner.run_command(...)`。

> **范围口径（重要，详见 `shared/device_scope/SKILL.md`）**：`scope=all` ≠ 底表全量。
> server 类经 `only_installed=True`（默认）自动收敛为「底表 ∩ 完工清单已初始化」设备；
> switch 类范围为完整配置《交换机信息》表。ops 实际能测的只是**完工清单/完整配置里对应上的设备**，
> 非全量底表。需精确指定时优先 `scope=pod`（POD 号）或 `scope=include`（IP 列表）。

### 语义识别示例（init_install）

| 用户说法 | commission_run 参数 |
|----------|---------------------|
| 服务器弱光检查 | `command=weak_light`, `scope=all` |
| 集群健康检查（全部已初始化设备） | `command=cluster_health_check`, `scope=all` |
| 服务器 OS 安装 | `command=os_install`, `scope=all` |
| 昇腾软件安装 | `command=ascend_install`, `scope=all` |

### 语义识别示例（subsystem_test）

| 用户说法 | commission_run 参数 |
|----------|---------------------|
| 单机综合检测 | `command=single_comprehensive`, `scope=all` |
| 灵衢 PRBS 测试 | `command=lq_prbs_test`, `scope=all` |
| 计算硬件压测 | `command=burn_test`, `scope=all` |
| 打流测试 | `command=traffic_test`, `scope=all` |
| 集群通信配置测试-单 POD | `command=hccl_test_single_pod`, `scope=pod`, `pod_ids=[1]` |

### 语义识别示例（cluster_test）

| 用户说法 | commission_run 参数 |
|----------|---------------------|
| 集合通信测试（全部已初始化设备） | `command=hccl_test`, `scope=all` |
| 集群模型测试（全部已初始化设备） | `command=cluster_model_test`, `scope=all` |

## 命令清单

**init_install（10 条）：** connection✅、lq_connection✅、lq_config_check✅、lq_health_check✅、hccs_weak_light✅、weak_light✅、cluster_health_check✅、os_install✅、ascend_install✅、server_health_check**留位**

**subsystem_test（10 条）：** single_comprehensive✅、lq_prbs_test✅、burn_test✅、single_model_test✅、traffic_test✅、hccl_test_single_pod✅、cluster_train_single_pod✅、cluster_infer_single_pod✅、storage/network_subsystem_test**留位**

**cluster_test（2 条）：** hccl_test✅、cluster_model_test✅

完整登记见 `shared/task_catalog/scripts/task_catalog.py`。

## 前置（本步共性）

- 步骤 ⑦：`toolkit_executor.json`（执行机 IP / SK）
- 步骤 ⑧：`deploy_chain.step8_toolkit_import_at` 已设置
- `ProjectData/plan/RunTime/gateway.json`（APIGW）
- 灵衢配置检查另需步骤 ⑥ ZTP；灵衢健康检查另需步骤 ⑥ 测试参数 xlsx

## 结果与进度

- 统一结果：`ProjectData/results/<task_type>/<task_name>/{report.zip|xlsx, extracted/, result.json, receipt.json}`，索引 `results/index.json`
- 进度：每模块最近一次完成 → `deploy_chain.step9/10/11_*`

## 结果与下载（Host action = `toolkit`）

| 用户说法 | sub_action | 产物 |
|----------|------------|------|
| 下载测试底表 / 下载完工清单 | `download_checklist` | `plan/Output/全量设备完工清单列表_latest.xlsx` |
| 生成调测报告 / 报告汇总 | `report_aggregate` | `results/调测报告汇总_latest.xlsx` |

调测命令走 **`commission_run`**；下载类命令走上表，由 Host `driver.py` 发 guidance 卡 + `skill_web_download` 按钮。

## 加新命令

1. `shared/task_catalog` 加 TaskSpec（含 `poll_mode` / `report_parser` 等扩展字段）
2. `commands/<module>/<cmd>/config/{execute,query}.json`
3. `commands/<module>/<cmd>/SKILL.md`
4. 置 `implemented=True`；引擎与 driver 不改
