# 网络带外管理地址规划 Skill

这是 `a3_net_dw_manage_ip_address.py` 的离线重构版本，只依赖本目录代码、`pandas`、`openpyxl` 和 `tabulate`，不依赖 CPCIA_AGENT 项目的数据库、EDM、LLM、日志或上传服务。

本目录也包含 `a3_network_access_plan.py` 的离线查询版本：它读取已经生成的 `A3网络设备接入规划.xlsx` 第一个 sheet，按项目配置解析出的 `网络平面` 过滤结果。

## 快速运行

```bash
python scripts/run_net_dw_access_ip.py \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --out runs/A3网络带外管理地址规划.xlsx \
  --intermediate runs/A3带外管理网关地址规划.xlsx
```

常用参数：

| 参数 | 默认值 | 说明 |
|------|------|------|
| `--sheet` | `网络带外管理面端口互联` | 007 端口连线表页签 |
| `--plane` | `网络带外管理面` | 资源表第一个 sheet 中的 `网络平面` 值 |
| `--leaf-scope` | `global` | 有下挂网络设备的网段才追加 LEAF；`global` 复刻源文件全局追加 LEAF 行为，`segment` 仅追加本网段 LEAF |
| `--no-intermediate` | 无 | 不生成网关中间文件 |

## Python 调用

```python
from net_dw_access_ip import run_from_files

result = run_from_files(
    topology_file="建模仿真输出文档007-端口连线表.xlsx",
    resource_file="项目信息收集表.xlsx",
    output_file="runs/A3网络带外管理地址规划.xlsx",
    intermediate_file="runs/A3带外管理网关地址规划.xlsx",
)

print(result.address_df)
print(result.gateway_df)
```

## 接入规划查询

项目里的 `a3_network_access_plan.network_access_plan` 不重新计算端口接入关系，而是读取 `A3网络设备接入规划.xlsx` 第一个 sheet 并按 `网络平面` 过滤。本 skill 的 `network_access_plan(access_plan_file, sheet_name)` 使用同样的核心输入输出：本地传入接入规划文件路径，返回过滤后的 DataFrame。

```bash
python scripts/run_network_access_plan.py \
  --access-plan A3网络设备接入规划.xlsx \
  --plan 计算业务面接入规划 \
  --out runs/计算业务面接入规划.xlsx
```

也可以直接按 sheet 或网络平面查询：

```bash
python scripts/run_network_access_plan.py --access-plan A3网络设备接入规划.xlsx --sheet 计算业务面端口互联
python scripts/run_network_access_plan.py --access-plan A3网络设备接入规划.xlsx --plane 计算业务面
```

Python 项目对齐入口：

```python
from net_dw_access_ip import network_access_plan

df = network_access_plan(
    access_plan_file="A3网络设备接入规划.xlsx",
    sheet_name="计算业务面端口互联",
)
```

`query_access_plan()` 和 CLI 的 `--plan`、`--plane`、`--out` 是离线辅助能力；默认过滤、`vlan/pvid` 转换、空值展示文案与项目函数保持一致。

支持的 `--plan`：

| 规划名称 | 过滤网络平面 |
|------|------|
| `计算带外管理接入规划` / `计算带外管理面接入规划` | `计算带外管理面` |
| `存储带外管理接入规划` / `存储带外管理面接入规划` | `存储带外管理面` |
| `网络带外管理接入规划` / `网络带外管理面接入规划` | `网络带外管理面` |
| `灵衢带外管理接入规划` / `灵衢带外管理面接入规划` | `灵衢带外管理面` |
| `带外管理面接入规划` | `存储管理面` |
| `计算管理面接入规划` | `计算管理面` |
| `计算业务面接入规划` | `计算业务面` |
| `计算样本面接入规划` | `计算样本面` |
| `计算参数面接入规划` | `计算参数面` |
| `计算管存面接入规划` | `计算管存面` |
| `存储管理面接入规划` | `存储管理面` |
| `存储业务面接入规划` | `存储业务面` |
| `存储样本面接入规划` | `存储样本面` |

## 输出

- `A3网络带外管理地址规划.xlsx`
  - sheet：`网络带外管理地址`
  - 列：`设备名称, 带外管理地址, 带外管理掩码, 带外管理网关, 带外管理VLAN, 接口名称`
- `A3带外管理网关地址规划.xlsx`
  - 列：`name, network_segment, gateway, vlan, mask`
  - 文件已存在时按项目逻辑追加记录

## 依赖

```bash
pip install pandas openpyxl tabulate
```
