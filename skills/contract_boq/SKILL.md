---
name: contract_boq
description: 早期介入·合同 BOQ 解析（early.contract.boq_parse）。将 BOQ xlsx 经 uniEx clone-boq 解析为 normalized.json 与建模仿真设备信息表。当用户提到 BOQ 解析、合同清单、建模仿真设备信息表、normalized.json 时触发。
---

# contract_boq · 合同 BOQ 解析

## LangGraph 步骤

| Step | 名称 | 输入 IPO | 输出 IPO |
|------|------|----------|----------|
| preflight | 环境预检 | — | — |
| boq_input_check | BOQ 输入检查 | `合同/输入文件/BOQ/*.xlsx` | — |
| stage1_parse | Stage1 解析 | BOQ xlsx | `合同/解析结果/BOQ设备解析原始结果/*.normalized.json` |
| stage2_device_table | 建模仿真设备表 | normalized.json | `合同/输出结果/建模仿真/建模仿真设备信息表.md` |
| publish_outputs | 登记产物 | — | state.files |

## 环境变量

- `UNIEX_BENCH_ROOT`：uniEx-bench 仓库根目录
- `AIDA_BUSINESS_ROOT`：项目数据根（`projects/{id}/早期介入/...`）
