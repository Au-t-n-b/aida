# a3-cc-ybm-ip-workflow

离线 A3「**存储样本面**」地址规划，严格对齐：

- **`src/manage_agent/sub_agents/LLD_IP/a3_cc_ybm_ip_address.py`**（L3 主逻辑；含 `od1600t_ip_address_generate`）

**一条指令、自动识别 L2/L3 与设备场景**，无需在命令中区分层级或存储型号。输入：端口互联表 + 项目信息收集表 → 输出 Excel（确定性，无 LLM）。

> 说明：在线 `存储样本面地址规划_L2` 当前仍映射 `a3_ni_ip_generate`；本 skill 的 L2 按资源表 `网关位置*` 走 **I2 网段 + 与 L3 相同的 `a3_cc_ybm` 分配规则**，便于与 L3 离线验收一致。

## 目录结构

```
a3-cc-ybm-ip-workflow.code1/
├── SKILL.md
├── README.md
├── requirements.txt
└── scripts/
    ├── offline_cc_ybm_pipeline.py
    ├── validate_inputs.py
    ├── cc_ybm_io.py
    ├── cc_ybm_segment_rules.py
    ├── cc_ybm_ip_allocate.py
    └── dw_manage_segment_rules.py
```

## 安装

```bash
cd skill_staging/a3-cc-ybm-ip-workflow.code1
python -m pip install -r requirements.txt
```

## 运行

```bash
python scripts/offline_cc_ybm_pipeline.py
```

### L2/L3 自动识别

| 网关位置* | 层级 | 网段算法 |
|-----------|------|----------|
| **LEAF** | **L3** | I3 一 Leaf 一网段 |
| **SPINE** 等 | **L2** | I2 共用网段（设备数×8） |

### 设备场景自动分支

| 场景 | 条件 |
|------|------|
| `od1600t` | 含 OD1600T（优先） |
| `osa800_only` | 含 OSA800 |
| `osp_only` | OSP 存储（双接口+控制口） |

```bash
python scripts/offline_cc_ybm_pipeline.py \
  --connect ./建模仿真输出文档007-端口连线表.xlsx \
  --resource ./项目信息收集表.xlsx \
  --skip-prompt-check
```

## 输出

```
output/run_YYYYMMDD_HHMMSS/
├── A3存储样本面网段规划.xlsx      # OSP/OSA800
├── A3存储样本面IP地址规划.xlsx
├── A3存储样本面地址规划.xlsx
├── scenario_detection.txt
└── run_meta.csv
```

## 输入校验

```bash
python scripts/validate_inputs.py
```
