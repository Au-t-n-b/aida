---
name: proposal_gen
description: 早期介入·交付预案生成（early.proposal.table_gen）。读取合同 BOQ 解析结果，解析技术建议书与测试用例，组装设备信息表等各章并落盘。当用户提到交付预案生成、设备信息表、验收策略、测试用例提取时触发。
---

# proposal_gen · 交付预案生成

## LangGraph 步骤

| Step | 名称 | 输入 IPO | 输出 IPO |
|------|------|----------|----------|
| preflight | 环境预检 | — | — |
| ingest_contract | 接入合同解析 | `合同/解析结果/BOQ设备解析原始结果/` | state.files（只读） |
| parse_tech_proposal | 验收策略 | `交付预案/输入文件/技术建议书/*.docx` | `交付预案/解析结果/服务建议书解析结果/` |
| parse_testcases | 测试用例 | `交付预案/输入文件/测试用例/*` | `交付预案/解析结果/测试用例解析结果/` |
| assemble_device_table | 设备信息表 | 合同 normalized.json | `交付预案/解析结果/预案草稿/2.设备配置信息.json` |
| assemble_service_maint | 服务维保 | `合同/解析结果/服务BOQ解析结果/` | 草稿第8章（待落盘） |
| table_gen_release | 落盘发布 | 各章草稿 | `交付预案/输出结果/*` + HITL |

## 前置依赖

须先完成 `contract_boq` Skill，或手工将 `*.normalized.json` 落至合同解析目录。
