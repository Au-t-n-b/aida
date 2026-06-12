# a3-device-naming-workflow

离线 A3 设备命名：对齐线上五条二级指令（生成设备清单、替换设备名称、ZTP名称替换×3）。

## 安装

```bash
python -m pip install -r requirements.txt
```

## 子命令

```bash
python scripts/offline_device_naming_pipeline.py list

# LLD 链路
python scripts/offline_device_naming_pipeline.py generate-list [--location PATH] [--sheet 设备位置信息]
# 填写 output/run_*/设备清单表.xlsx 中「客户定义设备名称」
python scripts/offline_device_naming_pipeline.py replace-lld [--device-list PATH] [--lld PATH] [--dry-run]

# ZTP 链路（三条独立指令，仅 plane 不同）
python scripts/offline_device_naming_pipeline.py replace-ztp [--ztp-lld PATH] [--mapping PATH] [--dry-run]
python scripts/offline_device_naming_pipeline.py replace-ztp-l1 [--ztp-lld PATH] [--mapping PATH] [--dry-run]
python scripts/offline_device_naming_pipeline.py replace-ztp-l2 [--ztp-lld PATH] [--mapping PATH] [--dry-run]
```

## 校验

```bash
python scripts/validate_inputs.py --mode generate-list
python scripts/validate_inputs.py --mode replace-lld
python scripts/validate_inputs.py --mode replace-ztp-l1
```

## 目录

- `SKILL.md` — skill 契约
- `scripts/` — 实现与入口
- `samples/` — 契约样例 YAML
- `output/` — 运行产出（自动生成）

建议在 **本 skill 根目录** 执行 CLI，避免 autodetect 命中其它 skill 下的 xlsx。
