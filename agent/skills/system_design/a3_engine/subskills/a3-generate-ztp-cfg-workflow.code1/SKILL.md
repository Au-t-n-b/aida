---
name: a3-generate-ztp-cfg-workflow
description: Offline A3 生成ZTP配置文件。Use when deterministically reproducing generate_ztp_lld.ztp_cfg_generate — read ZTP LLD 网络IP规划 and 项目信息收集表 ZTP配置 sheet, render L1/L2 cfg templates and zip without LLM/EDM/DB.
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_generate_ztp_cfg_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线复现 agent 指令 **`生成ZTP配置文件`**，业务逻辑严格对齐 `generate_ztp_lld.ztp_cfg_generate`（`ztp_cfg_processor` 模板替换逻辑）。

> **不包含**：`generate_ztp_lld_file`（见 `a3-generate-ztp-lld-workflow`）、`generated_ztp_api.ztp_cfg_generate_by_api`（生成灵衢开局文件）。

## Agent Trigger

`GENERATE_ZTP_CFG_KEYWORD = "生成ZTP配置文件"`

## Entrypoint

`python scripts/offline_generate_ztp_cfg_pipeline.py [--scan-dir DIR] [--project-name NAME] [--out-dir output]`

## Dependencies

`pip install -r requirements.txt`

内置 `conf/config.ini`、`template/Ztp_L1_optical_template.cfg`、`template/Ztp_L2_optical_template.cfg`（与线上一致）。

## Inputs

| 输入 | sheet | 自动扫描 |
|------|-------|----------|
| ZTP LLD | `网络IP规划` | 文件名含 `ZTP_LLD` 或同时含 `ZTP`+`LLD` |
| 项目信息收集表 | `ZTP配置` | 文件名含 `项目信息收集` |

`--ztp-lld PATH --resource PATH` 可显式指定。

### 缺失输入时自动检查并补齐（默认开启）

执行前**先检查**每项输入是否存在于当前目录；若不存在则按下列规则处理（前置过程**静默**，不打印中间 skill 输出）：

| 缺失输入 | 处理方式 |
|---------|----------|
| `ZTP_LLD.xlsx` | 运行 `a3-generate-ztp-lld-workflow`（其内部可继续链式运行超平面/带外管理等前置 skill）；失败时回退 `_skill_staging` 内最新同名文件 |
| `项目信息收集表.xlsx` | 在 `_skill_staging` 内检索最新同名文件（**无自动生成 skill**，需人工提供） |

本 skill 目录建议至少具备：`007`、`项目信息收集表`、`004 设备位置表`（供链式生成 ZTP_LLD 使用）。

前置 skill 产出写入**系统临时目录**，读取完成后自动删除，**不**在 skill 目录下生成 `_prereq_output`。

禁用：`--no-auto-prereq`

## Deterministic Rules

1. 读取 LLD `网络IP规划`：表头映射见 `conf/config.ini` `[confElements]`。
2. 每行生成 `CfgData`；`L1/L2平面` 决定 L1 或 L2 模板；`网关` 拆分为 IP/掩码。
3. 从 `ZTP配置` sheet 第 2 行起：E 列变量名、C 列值 → `common_dict`（`是/否` 控制模板块注释）。
4. 模板占位符替换，输出 `L1/*.cfg`、`L2/*.cfg`、`ztp.ini`。
5. 打包为 `{project_name}_ZTP配置文件_{timestamp}.zip`。

## Outputs

`output/run_YYYYMMDD_HHMMSS/{project_name}_ZTP配置文件_*.zip`（**唯一**交付物；zip 内含 L1/L2 cfg 与 ztp.ini，不在 output 下保留 `cfg_bundle` 目录）

## Non-goals

- 不检查超平面/网关规划 xlsx 是否存在（线上仅打日志）。
- 不上传 EDM、不写数据库、不推送前端。

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
