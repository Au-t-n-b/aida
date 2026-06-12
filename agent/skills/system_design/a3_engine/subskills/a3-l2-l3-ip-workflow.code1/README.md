# a3-l2-l3-ip-workflow

离线 A3 **计算管理面**网关地址规划：`007 + 网络资源需求表` -> `output/run_*/A3计算管理面L2/L3地址规划.xlsx`。

> 业务来源：L2 对齐 `a3_l2_ip_address.py`；L3 参考 `a3_ywm_ip_address.py` 整体流程，并替换为计算管理面口径。

## 分配规则速览

- 先读取项目信息收集表第一列 `网络平面 == 计算管理面` 的行。
- 再读取该行 `网关位置*`：`SPINE` 自动执行 L2，`LEAF` 自动执行 L3。
- **L2**：服务器共享一个统一网段；按地址池内可用 IP 顺序分配；网关按 `网段起始位` / `网段结束位` / 具体 IP 计算；网段规划展示到 Spine。
- **L3**：按 Leaf 连续划分网段；每台 Leaf 一个网段；服务器在所在 Leaf 网段内顺序取 IP；网关为该 Leaf 的 VLANIF 地址；输出字段使用计算管理面。
- 可用 IP 均排除网关，并限制在资源表 `地址池*` 范围内。
- 服务器识别关键字与原脚本 `SERVER_NAME_KEYWORD` 一致。

## 目录结构

- `SKILL.md`：skill 说明与输入/输出契约
- `scripts/offline_l2_l3_ip_pipeline.py`：主入口
- `scripts/a3_l2_l3_ip_rules.py`：确定性业务规则
- `scripts/validate_inputs.py`：输入校验
- `requirements.txt`：离线依赖
- `output/`：运行输出目录

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 运行

自动按 `计算管理面` 的 `网关位置*` 选择 L2 或 L3：

```bash
python scripts/offline_l2_l3_ip_pipeline.py --007 建模仿真输出文档007-端口连线表.xlsx --resource 项目信息收集表.xlsx
```

强制生成 L2 二层接入规划：

```bash
python scripts/offline_l2_l3_ip_pipeline.py --mode l2 --007 建模仿真输出文档007-端口连线表.xlsx --resource 项目信息收集表.xlsx
```

强制生成 L3 三层接入规划：

```bash
python scripts/offline_l2_l3_ip_pipeline.py --mode l3 --007 建模仿真输出文档007-端口连线表.xlsx --resource 项目信息收集表.xlsx
```

常用参数：

- `--mode auto|l2|l3`：默认 `auto`，按计算管理面 `网关位置*` 自动选择。
- `--007 PATH`：007 端口连线表；省略时自动探测。
- `--resource PATH`：项目信息收集表/网络资源需求表；省略时自动探测。
- `--sheet NAME`：端口互联 sheet，默认 `计算管理面端口互联`。
- `--resource-sheet SHEET`：资源表 sheet，默认 `0`。
- `--out-dir output`：输出目录。

输出示例：

- `output/run_YYYYMMDD_HHMMSS/A3计算管理面L2地址规划.xlsx`
- `output/run_YYYYMMDD_HHMMSS/A3计算管理面L3地址规划.xlsx`

每个结果 Excel 包含：

- `{网络平面}网段规划`
- `{网络平面}地址规划`
- `网络设备接入规划`

## 可选：运行前校验输入

```bash
python scripts/validate_inputs.py --007 建模仿真输出文档007-端口连线表.xlsx --resource 项目信息收集表.xlsx
```
