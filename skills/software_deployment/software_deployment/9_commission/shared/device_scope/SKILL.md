> 公共能力 · **设备范围理解**（三模块所有命令共用）。
> LLM 把「命令 + 范围描述」解析为结构化参数；实现见 `scripts/device_resolver.py`。

# 设备范围理解（8 种文法）

用户在命令名后追加范围描述。**范围语言全族唯一**，不在每个命令里重写；规则变化只改这里。

| # | 用户说法（XXXX = 任意命令名） | 解析参数 |
|---|------------------------------|----------|
| 1 | `XXXX检查` | `scope=all`（**已初始化设备全量**：server=底表∩完工清单已初始化；switch=完整配置交换机表） |
| 2 | `XXXX检查 PODxx` | `scope=pod, pod_ids=[xx]` |
| 3 | `XXXX检查 排除 设备[,设备…]`（多POD带 POD） | `scope=exclude, devices=[…], pod_ids=[…?]` |
| 4 | `XXXX检查 执行 设备[,设备…]` | `scope=include, devices=[…]` |
| 5 | `XXXX检查 执行参数文件指定设备` | `scope=param_file` |
| 6 | `XXXX检查（任务号）未通过的设备` | `scope=prev_failed, task_no=…` |
| 7 | `XXXX检查（任务号）已通过的设备` | `scope=prev_passed, task_no=…` |
| 8 | `XXXX检查（任务号）` | `scope=prev_same, task_no=…` |

## 参数 schema（传给 commission_run）

| 参数 | 类型 | 说明 |
|------|------|------|
| `scope` | str | 上表之一；缺省 `all` |
| `pod_ids` | int[] | POD 编号（superpodId） |
| `devices` | str[] | 设备 IP 或设备名（exclude/include） |
| `task_no` | str | 上次任务号（prev_*；空=最近一次） |
| `only_installed` | bool | 与「已初始化(已装)」取交集，默认 `true` |

## 设备来源（按命令 device_kind 自动选）

| device_kind | 来源 | 已装/可测判定 |
|-------------|------|----------|
| server | `plan/Output/device_base_table.json` **∩ 完整配置《服务器信息》** | `taskStatus != 未初始化`（完工清单刷过 INIT）**且** IP 在完整配置内（已导入 ops） |
| switch | CloudOps 完整配置《交换机信息》表 | 有账号密码 |

> **server 双重门禁**（对齐 Agent `query_all_devices` + `compare_with_cloudops_config`）：
> ① `taskStatus != 未初始化`（完工清单刷过 INIT）；② IP ∈ 完整配置《服务器信息》《交换机信息》第 0 列（确保已导入 ops）。
> 两者皆满足才可下发。读不到完整配置文件时跳过 ② 不误杀。switch 类的设备本就取自完整配置，无需 ②。

> **口径说明（重要）**：ops 实际能测的 server 仅限**完工清单已对应上的设备**（一批批上传刷 INIT），
> 而非全量底表 576 台。完整配置《服务器信息》表是给 ops 导入配置用，**不**作为 server 测试范围闸门；
> 闸门是完工清单 → 底表 `taskStatus != 未初始化`。交换机类则直接以完整配置《交换机信息》为准。

## 解析要点

- 无范围描述 → `all`；只带 POD → `pod`。
- 「排除/去掉/除了 X」→ `exclude`；句中含 POD 一并带 `pod_ids`。
- 「执行/只测/仅 X」→ `include`。
- 「执行参数文件指定设备/按参数文件」→ `param_file`。
- 含括号任务号 +「未通过/失败」→ `prev_failed`；+「已通过/成功」→ `prev_passed`；仅任务号 → `prev_same`。
