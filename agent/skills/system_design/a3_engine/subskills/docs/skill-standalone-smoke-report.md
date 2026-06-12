# Subskills 独立冒烟报告

**日期**: 2026-06-02  
**环境**: 仅 `subskills/` 目录 + `pip install -r`（`_runtime_shared` + 各包 `requirements.txt`）  
**PYTHONPATH**: `subskills` 根目录（与 `run_smoke_matrix.py` 一致）  
**命令**: `python _runtime_shared/run_smoke_matrix.py`

---

## 1. 汇总

| 类别 | 通过 | 失败 | 跳过 | 说明 |
|------|------|------|------|------|
| pip install（有 requirements.txt） | 26 | 0 | — | 见 §2 |
| 共享模块 import | 2 | 0 | — | `_runtime_shared.sheet007_resolver` / `network_access_plan` |
| CLI `--help` / `list` | **29** | **0** | 0 | 见 §3 |
| **运行时** `from sheet007_resolver import`（子进程复现） | 0 | **5** | — | 见 §4（P0）；CLI help 不触发该路径 |
| 无 requirements.txt 的包 | — | — | 3 | ywm / ybm / gcm（依赖环境已装 pandas） |

**结论**: 各包 **CLI 入口可启动**（`--help` 不触发 007 读取）；**真正跑规划时会因 `sheet007_resolver` 顶层导入失败**（除非已修复为 `_runtime_shared.sheet007_resolver`）。

---

## 2. pip install

全部 **ok**（26 个 requirements 文件）：

- `_runtime_shared/requirements.txt`
- 各 `*.code1/requirements.txt`（含 `a3_LLD_generate_code1`）
- **未单独安装**（无 requirements.txt，本次仍能通过 `--help`）：`a3-ywm-ip-workflow.code1`、`a3-ybm-ip-workflow.code1`、`a3-gcm-ip-workflow.code1`、`dme-planning.code1`（dme 无 txt 但 help 通过，说明全局已有依赖）

---

## 3. CLI `--help` 冒烟（29/29 通过）

| 包 | 入口 | 结果 |
|----|------|------|
| a3-cc-glm-ip-workflow.code1 | offline_cc_glm_pipeline.py --help | pass |
| a3-cc-ybm-ip-workflow.code1 | offline_cc_ybm_pipeline.py --help | pass |
| a3-cc-ywm-ip-workflow.code1 | offline_cc_ywm_pipeline.py --help | pass |
| a3-compute-net-interconnect-l2-l3-workflow.code1 | offline_net_interconnect_pipeline.py --help | pass |
| a3-cpm-lq-ip-workflow.code1 | offline_cpm_lq_ip_pipeline.py --help | pass |
| a3-csm-ip-workflow.code1 | offline_csm_pipeline.py --help | pass |
| a3-device-naming-workflow.code1 | offline_device_naming_pipeline.py --help | pass |
| a3-dw-manage-ip-workflow.code1 | offline_dw_manage_pipeline.py --help | pass |
| a3-gcm-ip-workflow.code1 | offline_gcm_pipeline.py --help | pass |
| a3-generate-lq-open-workflow.code1 | offline_generate_lq_open_pipeline.py --help | pass |
| a3-generate-ztp-cfg-workflow.code1 | offline_generate_ztp_cfg_pipeline.py --help | pass |
| a3-generate-ztp-lld-workflow.code1 | offline_generate_ztp_lld_pipeline.py --help | pass |
| a3-input-components-workflow.code1 | offline_input_components_pipeline.py --help | pass |
| a3-l2-l3-ip-workflow.code1 | offline_l2_l3_ip_pipeline.py --help | pass |
| a3-lq-dw-manage-ip-workflow.code1 | offline_lq_dw_manage_pipeline.py --help | pass |
| a3-net-dw-manage-ip-workflow.code1 | offline_net_dw_manage_pipeline.py --help | pass |
| a3-net-interconnection-workflow.code1 | offline_ni_pipeline.py --help | pass |
| a3-storage-dw-manage-ip-workflow.code1 | offline_storage_dw_manage_pipeline.py --help | pass |
| a3-switch-asn-workflow.code1 | offline_switch_asn_pipeline.py --help | pass |
| a3-ybm-ip-workflow.code1 | ybm_offline_pipeline.py --help | pass |
| a3-ywm-ip-workflow.code1 | offline_ywm_pipeline.py --help | pass |
| a3_LLD_generate_code1 | offline_lld_generate_pipeline.py --help | pass |
| ccae-planner.code1 | run_ccae_planner.py --help | pass |
| dme-planning.code1 | generate_dme_plan.py --help | pass |
| lld-dispatch-orchestrator.code1 | offline_dispatch_pipeline.py list | pass |
| nce-planner.code1 | run_nce_planner.py --help | pass |
| net-dw-access-ip-workflow.code1 | run_net_dw_access_ip.py --help | pass |
| oob-interconnect-workflow.code1 | run_oob_interconnect.py --help | pass |
| switch-mlag-planning-workflow.code1 | run_switch_mlag.py --help | pass |

### 未纳入 CLI 表（无 Python 入口）

| 目录 | 说明 |
|------|------|
| lld-intent-recognition.code1 | 仅 Markdown 意图表，无 `scripts/*.py` 入口 |

### 建议补测（未跑）

- `net-dw-access-ip-workflow.code1` → `run_network_access_plan.py --help`
- 各包 `validate_inputs.py --help`（若存在）

---

## 4. 运行时导入（P0 失败）

模块实际路径：`_runtime_shared/sheet007_resolver.py`  
以下脚本使用 **`from sheet007_resolver import ...`**（在 `PYTHONPATH=subskills` 时 **不存在** 顶层模块）：

| 包 | 脚本 |
|----|------|
| a3-ywm-ip-workflow.code1 | ywm_io_utils.py |
| a3-ybm-ip-workflow.code1 | ybm_excel_io.py |
| a3-gcm-ip-workflow.code1 | gcm_io_utils.py |
| a3-l2-l3-ip-workflow.code1 | a3_l2_l3_ip_rules.py, offline_l2_l3_ip_pipeline.py |
| a3-dw-manage-ip-workflow.code1 | offline_dw_manage_pipeline.py |

**复现**（ywm + reference 007）:

```text
ModuleNotFoundError: No module named 'sheet007_resolver'
```

**修复方向**（仅 skill）：统一为 `from _runtime_shared.sheet007_resolver import ...`，并在 SKILL 中写明 `PYTHONPATH` 含 `subskills` 根目录。

---

## 5. 独立能力分级（结合冒烟）

| 级别 | 包 |
|------|-----|
| **CLI 可独立**（help） | 上表 29 个 |
| **规划可独立**（修导入后 + Excel） | dw/storage/net/lq、l2-l3、ywm/ybm/gcm、cc-*、csm、cpm、oob、ni、compute-net-interconnect、… |
| **需 subskills 树** | 凡用 `_runtime_shared` 的包 |
| **链式前置** | `*接入规划`（需 `A3网络设备接入规划.xlsx`）、融合 LLD、dispatch 批次 |
| **外部依赖** | a3-generate-lq-open（CloudOps HTTP） |

---

## 6. 复现命令

```powershell
cd d:\code_neiyuan\CPCIA_AGENT\src\manage_agent\sub_agents\LLD_IP\subskills
python _runtime_shared\run_smoke_matrix.py
```
