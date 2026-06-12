# a3-cpm-lq-ip-workflow

离线 A3「超平面（灵衢 L1/L2 平面）」LoopBack 与 BGP AS 规划：`007 + 网络资源需求表` → `output/run_*/超平面网络规划.xlsx`（确定性计算，不依赖 LLM）。

> 业务来源：`a3_cpm_lq_ip_address.py`
> 提示词：`a3_cpm_L1_ip_prompt.py` / `a3_cpm_L2_ip_prompt.py`

## 分配规则速览

- **L1**：每台 7 个连续 LoopBack；BGP AS 范围 `start-end`，每台递增；`灵衢L1/L2平面 = 1`
- **L2**：每台 2 个连续 LoopBack；所有 L2 共享 1 个 BGP AS；`灵衢L1/L2平面 = 2`
- IP 按 `IPv4Address` 整数加法递增，与原 python 实现一致（**不跳过 `.0` / `.255`**）
- 单超节点 L1 上限 = 48，超过抛错
- 各 sp 的 L1/L2 设备按 sp 内 0..N-1 序号映射到模板槽位（IP/AS 在 sp 之间复用）

## 目录结构

- `SKILL.md`：skill 说明与输入/输出契约
- `scripts/offline_cpm_lq_ip_pipeline.py`：主入口（生成最终 Excel）
- `scripts/validate_inputs.py`：输入校验（可选）
- `scripts/cpm_lq_loopback_rules.py`：模板/解析/映射规则
- `scripts/cpm_lq_segment_rules.py`：**已废弃**（i2/i3 路线遗留物，部署前请删除）
- `output/`：运行输出目录（自动生成）

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 运行（生成结果）

```bash
python scripts/offline_cpm_lq_ip_pipeline.py
```

常用参数：

- `--007 PATH`：007 端口连线表（必须在 cwd 树下；省略则自动探测）
- `--resource PATH`：项目信息收集表/网络资源需求表（必须在 cwd 树下；省略则自动探测）
- `--out-dir output`：输出目录（默认 `output`）
- `--sheet007 SHEET`：007 sheet（默认 `"0"`，解析失败时自动扫描所有 sheet）
- `--sheet-resource NAME`：资源表 sheet 名（默认 `网络资源需求表`）
- `--net-plane-l1 NAME`：L1 网络平面行名（默认 `L1交换机LoopBack地址`）
- `--net-plane-l2 NAME`：L2 网络平面行名（默认 `L2交换机LoopBack地址`）
- `--skip-prompt-check`：跳过可选 prompt 文本一致性检查

输出示例：

- `output/run_YYYYMMDD_HHMMSS/超平面网络规划.xlsx`
- sheet：`超平面网络规划`
- 列：`设备名称 / LoopBack起始IP / LoopBack结束IP / BGP AS号 / 灵衢L1/L2平面 / 超节点ID / 超节点规模 / 设备ESN / 交换机ID`

## 可选：运行前校验输入

```bash
python scripts/validate_inputs.py
```

可用 `--sheet007` / `--sheet-resource` 指定读取的 sheet。
