# a3-net-interconnection-workflow

离线 A3 **LEAF ↔ SPINE 网络互连规划**，严格对齐：

- **L2**：`src/manage_agent/sub_agents/LLD_IP/a3_l2_net_interconnection.py`
- **L3**：`src/manage_agent/sub_agents/LLD_IP/a3_ni_ip_address.py`

参考风格：`skill_staging/a3-csm-ip-workflow.code1`、`a3-cc-ywm-ip-workflow.code1`（统一指令 + 自动识别 + 确定性流水线）。

## 目录结构

```
a3-net-interconnection-workflow.code1/
├── SKILL.md
├── README.md
├── requirements.txt
└── scripts/
    ├── offline_ni_pipeline.py
    ├── validate_inputs.py
    ├── ni_io.py
    ├── ni_l2_allocate.py
    └── ni_l3_allocate.py
```

## 安装

```bash
cd skill_staging/a3-net-interconnection-workflow.code1
python -m pip install -r requirements.txt
```

## 运行

**一条命令**（按资源表 `网关位置*` 自动 L2/L3）：

```bash
python scripts/offline_ni_pipeline.py --intent "计算业务面互联规划"
```

```bash
python scripts/offline_ni_pipeline.py \
  --intent "存储管理面互联规划" \
  --connect ./建模仿真输出文档007-端口连线表.xlsx \
  --resource ./项目信息收集表.xlsx \
  --out-dir output
```

列出支持的互联规划指令：

```bash
python scripts/offline_ni_pipeline.py --list-intents
```

## 自动识别规则

| `网关位置*` | 层级 | 脚本 |
|-------------|------|------|
| LEAF | L3 | `/30` 互连 IP（`内部网络设备互连地址段`） |
| SPINE 等 | L2 | VLAN + ETH-TRUNK（`VLAN*`） |

与线上 `main_flow.py`：`third_intent += '_L3' if gateway == 'LEAF' else '_L2'` 一致。

## 校验

```bash
python scripts/validate_inputs.py \
  --intent "计算业务面互联规划" \
  --connect ./建模仿真输出文档007-端口连线表.xlsx \
  --resource ./项目信息收集表.xlsx
```

## 输出

`output/run_*/A3网络互连规划.xlsx`、`layer_detection.txt`、`run_meta.csv`
