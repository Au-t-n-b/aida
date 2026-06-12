# a3-net-dw-manage-ip-workflow

离线 A3「**网络带外管理**」地址规划：`007 + 项目信息收集表` → `output/run_*/A3网络带外管理地址规划.xlsx`（确定性，无 LLM）。

> 业务来源：
> - L2（`网关位置*=SPINE`）：`a3_net_dw_manage_ip_address.py`
> - L3（`网关位置*=LEAF`）：`a3_l3_net_dw_manage_ip_address.py`

## 自动选层

在 **项目信息收集表 → 网络资源需求表** 中：

1. 第一列 `网络平面` 精确找到 **`网络带外管理面`** 行。
2. 读取 `网关位置*`：
   - **SPINE** → L2（网关在 Spine，Leaf 网段可合并，最终网关信息转移到 Spine）
   - **LEAF** → L3（每 Leaf 独立网段，特殊 LEAF 带外地址=网关）

## 目录结构

- `SKILL.md`：skill 契约与完整业务规则
- `scripts/offline_net_dw_manage_pipeline.py`：主入口
- `scripts/net_dw_manage_rules.py`：确定性规则实现
- `scripts/validate_inputs.py`：输入校验
- `requirements.txt`：依赖
- `output/run_*/`：运行输出（自动生成；勿使用 `output_retest`）

## 安装

```bash
cd _skill_staging/a3-net-dw-manage-ip-workflow.code1
python -m pip install -r requirements.txt
```

将 `007` 与 `项目信息收集表` 放在当前工作目录（或子目录）下。

## 运行

```bash
python scripts/offline_net_dw_manage_pipeline.py
```

常用参数：

```bash
python scripts/offline_net_dw_manage_pipeline.py \
  --mode auto \
  --007 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 网络带外管理面端口互联 \
  --resource-sheet 网络资源需求表 \
  --out-dir output
```

## 输出示例

- `output/run_YYYYMMDD_HHMMSS/A3网络带外管理地址规划.xlsx`
  - sheet：`网络带外管理地址`
  - 不额外输出网关中间 Excel

## 校验输入（可选）

```bash
python scripts/validate_inputs.py \
  --007 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 网络带外管理面端口互联
```

## 与线上脚本差异说明

| 能力 | 线上 | 本 skill |
|------|------|----------|
| 网段规划 | LLM + `split_ip_range` 工具 | 确定性 `split_ip_range_subnets` + i2/i3 规则 |
| 结果展示 / EDM / DB | 有 | **无**（仅 Excel） |
| 业务逻辑 | 两脚本 | **严格对齐** |
