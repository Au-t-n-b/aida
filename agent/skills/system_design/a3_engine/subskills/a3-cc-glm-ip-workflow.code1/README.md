# a3-cc-glm-ip-workflow

离线 A3「**存储管理面**」地址规划，严格对齐：

- **L2**：`src/manage_agent/sub_agents/LLD_IP/a3_l2_cc_glm_ip_address.py`
- **L3**：`src/manage_agent/sub_agents/LLD_IP/a3_cc_glm_ip_address.py`

输入：`存储管理面端口互联` + `项目信息收集表` → 输出：`output/run_*/A3存储管理面地址规划.xlsx`（确定性，无 LLM）。

## 目录结构

```
a3-cc-glm-ip-workflow.code1/
├── SKILL.md
├── README.md
├── requirements.txt
└── scripts/
    ├── offline_cc_glm_pipeline.py   # 主入口
    ├── validate_inputs.py
    ├── cc_glm_io.py
    ├── cc_glm_segment_rules.py
    ├── cc_glm_ip_allocate.py
    └── dw_manage_segment_rules.py
```

## 安装

```bash
cd skill_staging/a3-cc-glm-ip-workflow.code1
python -m pip install -r requirements.txt
```

将 **端口互联表** 与 **项目信息收集表** 放在运行时的 cwd 下（或通过参数指定）。

## 运行

**一条命令**，按资源表 `网关位置*` 自动选 L2 或 L3：

```bash
python scripts/offline_cc_glm_pipeline.py
```

- `网关位置* = LEAF` → L3 → `a3_cc_glm_ip_address.py`
- `网关位置* = SPINE`（或其它非 LEAF）→ L2 → `a3_l2_cc_glm_ip_address.py`

常用参数：

```bash
python scripts/offline_cc_glm_pipeline.py \
  --connect ./建模仿真输出文档007-端口连线表.xlsx \
  --resource ./项目信息收集表.xlsx \
  --sheet-connect auto \
  --out-dir output \
  --skip-prompt-check
```

调试时可强制层级：`--force-layer L2` 或 `--force-layer L3`（与资源表不一致时会 WARN）。

## 输出示例

```
output/run_20260515_143000/
├── A3存储管理面网段规划.xlsx      # 0-6 网段规划（L3: Leaf / L2: Spine + Leaf网段）
├── A3存储管理面IP地址规划.xlsx    # 0-7/0-8 IP 地址规划
├── A3存储管理面地址规划.xlsx      # 与线上一致，供 EDM/归档（sheet 名「地址规划」）
├── layer_detection.txt
└── run_meta.csv
```

## 输入校验

```bash
python scripts/validate_inputs.py --connect ./存储管理面端口互联.xlsx --resource ./项目信息收集表.xlsx
```

## 与在线 Agent 的差异

本 skill 覆盖两个脚本的 **拓扑解析、网段规划、IP 分配、Excel 产出** 核心路径；以下依赖在线环境，离线不执行：

- `a3_switch_loopback_ip_generate` / `a3_cc_ybm_ywm_switch_loopback_ip_generate`
- `_get_switch_mlag_data` → 网络设备接入规划
- `_update_dw_gatewayinfo`（L2）/ `_update_gateway_info`（L3）
- `upload_to_edm`、`display_message`、`display_file`
