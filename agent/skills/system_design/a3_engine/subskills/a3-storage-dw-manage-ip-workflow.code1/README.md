# a3-storage-dw-manage-ip-workflow

离线 A3「存储带外管理地址规划」：`007 + 项目信息收集表` → `output/run_*/A3存储带外管理地址规划.xlsx`。

业务来源：

- L2：`a3_storage_dw_manage_ip_address.py`
- L3：`a3_l3_storage_dw_manage_ip_address.py`

## 自动选层

读取项目信息收集表 `网络资源需求表` 中 `网络平面 == 存储带外管理面` 的行：

- `网关位置* = SPINE` → L2
- `网关位置* = LEAF` → L3

## 安装

```bash
python -m pip install -r requirements.txt
```

## 运行

```bash
python scripts/offline_storage_dw_manage_pipeline.py
```

常用参数：

```bash
python scripts/offline_storage_dw_manage_pipeline.py \
  --mode auto \
  --007 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 存储带外管理面端口互联 \
  --resource-sheet 网络资源需求表 \
  --net-plane 存储带外管理面 \
  --out-dir output
```

## 输出

- `output/run_YYYYMMDD_HHMMSS/A3存储带外管理地址规划.xlsx`
- sheet：`存储带外管理地址`
- 列：`设备名称 / 带外管理地址 / 带外管理掩码 / 带外管理网关 / 带外管理VLAN / 接口名称`

## 校验

```bash
python scripts/validate_inputs.py \
  --007 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx
```
