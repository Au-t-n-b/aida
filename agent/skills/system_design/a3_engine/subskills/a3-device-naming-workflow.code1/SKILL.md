---
name: a3-device-naming-workflow
description: Offline A3 设备命名五条二级指令（生成设备清单、替换设备名称、ZTP名称替换×3），确定性 Excel I/O，无 LLM。
metadata:
  entrypoint: scripts/offline_device_naming_pipeline.py
  disable-model-invocation: true
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线实现线上五条命名相关二级指令，纯本地 Excel 读写，不依赖 EDM/LLM。

| 线上标准命令 | CLI 子命令 |
|--------------|------------|
| 生成设备清单 | `generate-list` |
| 替换设备名称 | `replace-lld` |
| ZTP名称替换 | `replace-ztp` |
| ZTP名称替换_L1 | `replace-ztp-l1` |
| ZTP名称替换_L2 | `replace-ztp-l2` |

## Entrypoint

```bash
pip install -r requirements.txt
python scripts/offline_device_naming_pipeline.py list
python scripts/offline_device_naming_pipeline.py generate-list [opts]
python scripts/offline_device_naming_pipeline.py replace-lld [opts]
python scripts/offline_device_naming_pipeline.py replace-ztp [opts]
python scripts/offline_device_naming_pipeline.py replace-ztp-l1 [opts]
python scripts/offline_device_naming_pipeline.py replace-ztp-l2 [opts]
```

## Dependencies

`pandas`, `openpyxl`

## Path Rules (CWD Contract)

- 输入/输出路径须在 cwd 树下；省略时在 cwd 自动探测：
  - 设备位置：含 `设备位置` 或 `004`
  - 设备清单：含 `设备清单`
  - LLD：含 `LLD` 且非 ZTP
  - ZTP_LLD：含 `ZTP` 且含 `LLD`
  - 映射表：含 `devicename-mapping` / `映射` / `mapping`

## Typical Flows

**LLD 链路**：`generate-list` → 填写 `客户定义设备名称` → `replace-lld`

**ZTP 链路**（与设备清单无强制关联）：准备 `source`/`target` 映射表 + `ZTP_LLD.xlsx` → `replace-ztp` / `replace-ztp-l1` / `replace-ztp-l2`

## Inputs / Outputs

| 子命令 | 主要输入 | 输出 |
|--------|----------|------|
| generate-list | 设备位置信息表 | `output/run_*/设备清单表.xlsx`（sheet `设备信息`） |
| replace-lld | 设备清单 + LLD 设计 | `output/run_*/*_replaced.xlsx` |
| replace-ztp* | ZTP_LLD + source/target 映射 | `output/run_*/*_ztp[_l1|_l2].xlsx` |

## Validation

`python scripts/validate_inputs.py --mode <generate-list|replace-lld|replace-ztp|replace-ztp-l1|replace-ztp-l2>`

## Dispatch integration

已注册至 [lld-dispatch-orchestrator](../lld-dispatch-orchestrator.code1)：`l3_skill_index.yaml` 五条 + `skill_registry.yaml` direct/L1 命名替换。调度示例：

```bash
python ../lld-dispatch-orchestrator.code1/scripts/offline_dispatch_pipeline.py plan --intent 命名替换
python ../lld-dispatch-orchestrator.code1/scripts/offline_dispatch_pipeline.py plan --intent 替换设备名称
```

## Implementation

- `scripts/device_list_generator.py` — 生成设备清单
- `scripts/lld_device_name_replacer.py` — 全 LLD 单元格完全匹配替换
- `scripts/ztp_device_name_replacer.py` — `网络IP规划` / `交换机名称` + 可选 `L1/L2平面` 过滤
- `scripts/naming_path_utils.py` — cwd 契约与 autodetect
- `scripts/offline_device_naming_pipeline.py` — 五子命令入口

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
