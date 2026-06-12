# oob-interconnect

计算带外管理面 LEAF–SPINE 互联规划离线工具：以《建模仿真输出文档007-端口连线表.xlsx》+《项目信息收集表.xlsx》为输入，生成二层（VLAN+ETH-Trunk）或三层（/30 互连地址）互联规划表。

- 纯 Python，不连接任何外部服务、数据库或鉴权。
- 默认平面配置贴近项目内 `LEAF_SPINE_CONFIG`；平面集合仍可由配置驱动（JSON 文件或 Python 字典）扩展或裁剪。
- CLI 默认输出文件名为 `A3网络互联规划.xlsx`，也可通过 `--out` 覆盖路径。
- 默认输出整表覆盖写入；使用 `--merge-existing` 时按项目脚本口径读取旧输出，删除本次网络平面后追加新结果。

## 安装

```bash
pip install -r requirements.txt
# 或：pip install -e .
```

## 输入约定

### 1）建模仿真输出文档007-端口连线表.xlsx

默认 sheet 为 `计算带外管理面端口互联`，含「设备命名」单元格的行作为表头；其下为数据。列结构按位置取：

- **二层** 取：第 1 列 = leaf 设备，第 2 列 = 本端端口，第 3 列 = 本端带宽，倒数 4 = 对端带宽，倒数 3 = 对端接口类型，倒数 2 = 对端端口，最后 1 列 = spine 设备。
- **三层** 取：第 1、2、倒数 2、3、最后 1 列（同上，不含带宽）。

筛选条件：`leaf 列 ~ keyword`（大小写不敏感）且 `spine 列 ~ "spine"`。

### 2）项目信息收集表.xlsx

优先读取 sheet `资源表`；若不存在或不含 `网络平面` 列，则自动扫描首个包含 `网络平面` 列的 sheet。资源 sheet 需含列：

| 列 | 含义 |
|----|------|
| `网络平面` | 与平面配置 `network_type` 完全一致 |
| `VLAN` | 二层用；可以是 `VLAN*` 等以 `VLAN` 开头的列名 |
| `互连地址段` / `内部网络设备互连地址段` | 三层用；格式 `起始IP-结束IP`。若无这些列，会自动使用资源行中首个 IPv4 起止地址段（如 `地址池*`） |
| `网关位置` | 三层用；可以是 `网关位置*` 等以 `网关位置` 开头的列名，值为 `LEAF` 或 `SPINE` |

可在 `oob_interconnect/constants.py` 修改 `RESOURCE_SHEET / RESOURCE_PLANE_COLUMN / RESOURCE_VLAN_COLUMN / RESOURCE_IP_POOL_COLUMN` 以匹配你的表头。

### 3）平面配置（可选 JSON）

```json
{
  "<sheet_name>": { "keyword": "<leaf 列匹配关键字>", "network_type": "<项目信息收集表「网络平面」取值>" }
}
```

- key：《建模仿真输出文档007-端口连线表.xlsx》中的 sheet 名（默认 `计算带外管理面端口互联`）。
- `keyword`：对 leaf 列做包含匹配（大小写不敏感）。
- `network_type`：在《项目信息收集表.xlsx》「网络平面」列定位的取值，也是输出表「网络平面」列值。

默认及示例文件 `plane_config.example.json`：

```json
{
  "计算带外管理面端口互联": {
    "keyword": "DWGL-LEAF",
    "network_type": "计算带外管理面"
  }
}
```

> 适用范围：本工具覆盖**所有「LEAF → SPINE」互联规划**类场景。同一套算法适用于任意网络平面，只需把对应 sheet 名 / 关键字 / 网络平面名填进配置。  
> 不适用：**接入规划**（服务器或接入交换机的接入端口规划，单端口而非 LEAF↔SPINE 互联）不属于本工具范畴。

**不提供则使用内置默认配置**（见 `constants.py`），即计算带外管理面。

## 命令行

```bash
# 计算带外管理面 — 二层
python scripts/run_oob_interconnect.py --layer l2 \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 计算带外管理面端口互联

# 计算带外管理面 — 三层
python scripts/run_oob_interconnect.py --layer l3 \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 计算带外管理面端口互联

# 使用自定义平面配置
python scripts/run_oob_interconnect.py --layer l2 \
  --plane-config plane_config.example.json \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 计算带外管理面端口互联 \
  --out runs/A3网络互联规划.xlsx

# L2 可选：接入规划 + 历史互联（用作 Trunk 参考）
python scripts/run_oob_interconnect.py --layer l2 \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 计算带外管理面端口互联 \
  --out runs/A3网络互联规划.xlsx \
  --access-plan out/access_plan.xlsx --trunk-history backup/old_interconnect.xlsx

# 项目兼容输出：按网络平面替换旧输出中的同平面行后追加新结果
python scripts/run_oob_interconnect.py --layer l2 \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --plan 计算带外管理互联规划 \
  --out runs/A3网络互联规划.xlsx \
  --merge-existing
```

## Python API

```python
from oob_interconnect import run_l2, run_l3, run_l2_multi, run_l3_multi
from oob_interconnect.plane_config import load_plane_config

cfg = load_plane_config("plane_config.example.json")  # 或 None 用默认计算带外管理面

run_l2("建模仿真输出文档007-端口连线表.xlsx", "计算带外管理面端口互联",
       "项目信息收集表.xlsx", "runs/A3网络互联规划.xlsx",
       plane_config=cfg)
run_l3("建模仿真输出文档007-端口连线表.xlsx", "计算带外管理面端口互联",
       "项目信息收集表.xlsx", "runs/A3网络互联规划.xlsx", plane_config=cfg)

run_l2_multi("建模仿真输出文档007-端口连线表.xlsx", "项目信息收集表.xlsx",
             "runs/A3网络互联规划.xlsx", plane_config=cfg)
run_l3_multi("建模仿真输出文档007-端口连线表.xlsx", "项目信息收集表.xlsx",
             "runs/A3网络互联规划.xlsx", plane_config=cfg)
```

## 输出列

输出工作簿 sheet 名固定为 `网络互联规划`。

`网络平面`, `本端设备`, `本端接口`, `本端接口IP地址`, `本端接口掩码`, `本端ETH-TRUNK`, `本端VLAN`, `对端设备`, `对端接口`, `对端接口IP地址`, `对端接口掩码`, `对端ETH-TRUNK`, `对端VLAN`, `PVID`, `端口类型`, `标签`

- 二层：填 VLAN、ETH-Trunk、`端口类型=trunk`、`标签=INTER_LINK`。
- 三层：按 `/30` 点对点地址推进；若资源表配置 `网关位置=LEAF/SPINE`，只在对应侧填 IP 和掩码，另一侧留空；未配置时保留两端都填的旧行为。

## 行为说明

- **单平面**：默认 `--out` 仅含本次生成的平面行，整表覆盖；加 `--merge-existing` 后保留旧输出中其他网络平面。
- **多平面**：内存中顺序生成所选平面；L2 共享 Trunk 占用避免跨平面冲突；默认 `pd.concat` 后一次覆盖写入，加 `--merge-existing` 后按本次生成的网络平面集合替换旧输出。
- **L2 Trunk 起始编号**：默认 2，可改 `constants.DEFAULT_TRUNK_START`。
- **L3 /30 起始 IP**：自动向上对齐到 4 的倍数；若可容纳子网数不足 → 抛错不生成。

## 目录

```
.
├── README.md
├── SKILL.md
├── pyproject.toml
├── requirements.txt
├── plane_config.example.json
├── scripts/
│   └── run_oob_interconnect.py
└── oob_interconnect/
    ├── __init__.py
    ├── cli.py
    ├── constants.py
    ├── load_007.py
    ├── l2_engine.py
    ├── l3_engine.py
    ├── merge_output.py
    ├── pipeline.py
    ├── plane_config.py
    ├── resource.py
    └── trunk_assign.py
```
