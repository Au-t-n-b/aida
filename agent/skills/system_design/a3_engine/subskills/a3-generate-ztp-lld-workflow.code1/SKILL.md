---
name: a3-generate-ztp-lld-workflow
description: Offline A3 生成ZTP设计文件。Use when deterministically reproducing generate_ztp_lld.generate_ztp_lld_file — merge 超平面网络规划、灵衢带外管理地址规划、设备位置信息 into ZTP_LLD.xlsx sheet 网络IP规划 without LLM/EDM/DB.
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_generate_ztp_lld_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线复现 agent 指令 **`生成ZTP设计文件`**，业务逻辑严格对齐 `src/manage_agent/sub_agents/LLD_IP/generate_ztp_lld.py` 中的 `generate_ztp_lld_file`。

> **不包含**：`ztp_cfg_generate`（见 `a3-generate-ztp-cfg-workflow`）、`generated_ztp_api.py`（生成灵衢开局文件）。

## Agent Trigger

`GENERATE_ZTP_FILE_KEYWORD = "生成ZTP设计文件"`

## Entrypoint

`python scripts/offline_generate_ztp_lld_pipeline.py [--scan-dir DIR] [--out-dir output]`

推荐：将输入 Excel 放在 skill 根目录后执行：

`python scripts/offline_generate_ztp_lld_pipeline.py --out-dir output`

## Dependencies

`pip install -r requirements.txt`

## Inputs

| 输入 | 说明 | 自动扫描关键字 |
|------|------|----------------|
| 超平面网络规划 | Loopback 起止 IP、设备名称等 | 文件名含 `超平面`、`规划`，不含 `网关` |
| 灵衢带外管理地址规划 | 带外管理地址/网关/掩码/VLAN | 含 `灵衢`、`带外`、`地址`、`规划`，不含 `网关` |
| 设备位置信息 | sheet 默认 `设备位置信息` | 含 `004`、`设备位置` |

目录可放多个 Excel；仅匹配上述三类，其余忽略。

### 缺失规划表时自动运行前置 skill（默认开启）

若当前目录**没有**超平面 / 灵衢带外管理规划表，脚本会：

1. 在 `_skill_staging` 下检索 `SKILL.md` 描述匹配的前置 skill；
2. **静默**运行（不打印前置 skill 控制台输出）；
3. 使用生成结果作为本 skill 输入。

| 缺失文件 | 前置 skill（默认） | 前置 skill 还需 |
|---------|-------------------|----------------|
| 超平面网络规划 | `a3-cpm-lq-ip-workflow.code1` | `007` + `项目信息收集表`（放本目录即可） |
| 灵衢带外管理地址规划 | `a3-lq-dw-manage-ip-workflow.code1` | 同上 |

前置 skill 产出写入**系统临时目录**，合并完成后自动删除，**不**在 skill 目录下生成 `_prereq_output`。

前置 skill 执行失败时，回退使用 `_skill_staging` 内同名文件的最新已有产出。

禁用自动前置：`--no-auto-prereq`

显式指定：

`--cpm PATH --manage PATH --location PATH [--location-sheet 设备位置信息]`

## Deterministic Rules

1. 校验位置表列：`设备名称`、`所属机房`、`所属机柜`、`安装起始U位`。
2. `merge(带外管理, 超平面, on=设备名称, how=left)`。
3. 按设备名回填 `机房名称`、`机柜编号`、`柜内位置`（U 位后缀 `U`）。
4. 删除列（若存在）：`用户名`、`密码`、`设备SN`。
5. 校验 `LoopBack起始IP`、`LoopBack结束IP`；按起止 IP 展开 `loopBack0..N`（至少 7 列）。
6. `网关` = `{带外管理网关}/{带外管理掩码}`。
7. 列重命名并固定输出列顺序（与线上一致）。
8. 写出 sheet **`网络IP规划`**。

## Outputs

`output/run_YYYYMMDD_HHMMSS/ZTP_LLD.xlsx`（唯一输出文件）

## Non-goals

- 不上传 EDM、不写数据库、不推送前端消息。
- 不生成 cfg / zip。

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
