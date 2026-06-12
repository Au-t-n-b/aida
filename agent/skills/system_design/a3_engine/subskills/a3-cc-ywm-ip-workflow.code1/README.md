# a3-cc-ywm-ip-workflow

离线 A3「**存储业务面**」地址规划，严格对齐：

- **L2**：`src/manage_agent/sub_agents/LLD_IP/a3_l2_cc_ywm_ip_address.py`
- **L3**：`src/manage_agent/sub_agents/LLD_IP/a3_cc_ywm_ip_address.py`

**一条指令、自动识别 L2/L3**，无需在命令中区分层级。输入：端口互联表 + 项目信息收集表 → 输出 Excel（确定性，无 LLM）。

## 目录结构

```
a3-cc-ywm-ip-workflow.code1/
├── SKILL.md
├── README.md
├── requirements.txt
└── scripts/
    ├── offline_cc_ywm_pipeline.py   # 主入口
    ├── validate_inputs.py
    ├── cc_ywm_io.py
    ├── cc_ywm_segment_rules.py
    ├── cc_ywm_ip_allocate.py
    └── dw_manage_segment_rules.py
```

## 安装

```bash
cd skill_staging/a3-cc-ywm-ip-workflow.code1
python -m pip install -r requirements.txt
```

将 **端口互联表** 与 **项目信息收集表** 放在运行时的 cwd 下（或通过参数指定）。

## 运行

```bash
python scripts/offline_cc_ywm_pipeline.py
```

### L2/L3 自动识别

读资源表 `网络平面 == 存储业务面` 行的 **`网关位置*`**（与 `main_flow` / `a3-cc-glm-ip-workflow` 相同）：

| 网关位置* | 层级 | 对齐脚本 |
|-----------|------|----------|
| **LEAF** | **L3** | `a3_cc_ywm_ip_address.py` |
| **SPINE** 或其它 | **L2** | `a3_l2_cc_ywm_ip_address.py` |

### 设备场景自动分支

读端口互联表后按源码三分支：

| 场景 | 条件 | 行为摘要 |
|------|------|----------|
| `osp_only` | 仅有 OSP9950/OSP9550 | Leaf 网段 + 按节点顺序分配 OSP IP |
| `osa800_only` | 仅有 OSA800 | 网段规划 + OSA800（L2 按组网场景 bond/多IP） |
| `mixed` | 两者都有 | 先 OSP 占网段/VLAN，再 `find_available_ip_vlan_range` 为 OSA800 分配（固定 bond4） |

常用参数：

```bash
python scripts/offline_cc_ywm_pipeline.py \
  --connect ./建模仿真输出文档007-端口连线表.xlsx \
  --resource ./项目信息收集表.xlsx \
  --sheet-connect auto \
  --out-dir output \
  --skip-prompt-check
```

调试：`--force-layer L2` 或 `--force-layer L3`。

## 输出

```
output/run_YYYYMMDD_HHMMSS/
├── A3存储业务面网段规划.xlsx      # L3: Leaf；L2: Spine + Leaf网段
├── A3存储业务面IP地址规划.xlsx    # OSP / OSA800 分 sheet
├── A3存储业务面地址规划.xlsx
├── layer_detection.txt            # layer + device_scenario
└── run_meta.csv
```

## 输入校验

```bash
python scripts/validate_inputs.py --connect ./端口互联.xlsx --resource ./项目信息收集表.xlsx
```

## 与在线 Agent 的差异

离线覆盖：**拓扑解析、网段规划、OSP/OSA800 IP 分配、Excel 产出**。以下在线能力不执行：

- `a3_switch_loopback_ip_generate` / `a3_cc_ybm_ywm_switch_loopback_ip_generate`
- `_get_switch_mlag_data` → `A3网络设备接入规划.xlsx`
- `_update_dw_gatewayinfo`（L2）/ `_update_gateway_info`（L3）
- `upload_to_edm`、`display_message`、`invoke_llm_tools`
