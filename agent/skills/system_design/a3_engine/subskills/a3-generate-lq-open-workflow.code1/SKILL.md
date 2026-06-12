---
name: a3-generate-lq-open-workflow
description: Offline A3 生成灵衢开局文件。Use when deterministically reproducing generated_ztp_api.ztp_cfg_generate_by_api — build CloudOps ztp-build/export JSON from 项目信息收集表 ZTP配置 sheet plus ZTP_LLD 网络IP规划, optionally call API for zip. No LLM/EDM/DB.
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_generate_lq_open_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线复现 agent 指令 **`生成灵衢开局文件`**，业务逻辑严格对齐 `src/manage_agent/sub_agents/LLD_IP/generated_ztp_api.py`。

与 **`生成ZTP配置文件`**（`generate_ztp_lld.ztp_cfg_generate` 本地模板）不同，本流程通过 **CloudOps API** 导出开局 zip。

## Agent Trigger

`GENERATE_LQ_OPEN_KEYWORD = "生成灵衢开局文件"`

对应函数：`generated_ztp_api.ztp_cfg_generate_by_api`

## Entrypoint

`python scripts/offline_generate_lq_open_pipeline.py [--scan-dir DIR] [--call-api] [--out-dir output]`

推荐：

`python scripts/offline_generate_lq_open_pipeline.py --out-dir output`

## Dependencies

`pip install -r requirements.txt`

## Inputs

| 输入 | sheet | 自动扫描 |
|------|-------|----------|
| 项目信息收集表 | `ZTP配置`（列 `CloudOps变量`、`规划值`） | 文件名含 `项目信息收集` |
| ZTP LLD | `网络IP规划` | 文件名含 `ZTP_LLD` 或 `ZTP`+`LLD` |

### 缺失输入时自动补齐（默认开启）

| 缺失 | 处理 |
|------|------|
| `ZTP_LLD.xlsx` | 静默运行 `a3-generate-ztp-lld-workflow`（可链式生成）；失败则回退 `_skill_staging` 最新同名文件 |
| `项目信息收集表.xlsx` | 在 `_skill_staging` 检索最新副本（无自动生成 skill） |

链式生成 ZTP_LLD 时，目录需含 `007`、`004`、`项目信息收集表` 等（见 ztp-lld skill）。

前置产出使用**系统临时目录**，不创建 `_prereq_output`。

禁用：`--no-auto-prereq`

## Deterministic Rules（对齐 ZTPConfigConverter）

1. 读 `ZTP配置` → `project_config`（`CloudOps变量` → `规划值`）。
2. 读 `网络IP规划` → `device_configs` 列表。
3. `map_variables`：`是/否` → bool；`isTypical`：`typical` → true；`portDesDefineRules` → JSON/字面量列表。
4. 填充 `ztpInputConfig` 各 Agent 字段与 `roomParas`。
5. 每台设备生成 `ztpConfigList` 一项（`get_device_model` 按交换机名称匹配型号）。
6. Loopback：`LoopBack起始IP` 或 `loopBack0`；结束 IP 优先 `LoopBack结束IP` / `loopBack6` / `loopBack1`。
7. 写出 `api_request.json`。
8. `--call-api` 时 POST CloudOps `ztp-build/export`，保存 zip。

## CloudOps 调用（可选）

环境变量：

- `CLOUDOPS_AUTHORIZATION`（或 `CPCIA_AUTHORIZATION`）
- `CLOUDOPS_X_HW_ID`（或 `CPCIA_APP_ID`）
- `CLOUDOPS_EXPORT_URL`（可选覆盖）
- `--test-env` → beta 网关

## Outputs

`output/run_YYYYMMDD_HHMMSS/`

| 模式 | 文件 |
|------|------|
| 默认（仅映射） | `api_request.json` |
| `--call-api` | `api_request.json` + `{project_name}_灵衢开局文件_*.zip` |

## Non-goals

- 不使用 LLM、EDM、数据库、前端消息推送。
- 不实现本地 cfg 模板生成（见 `a3-generate-ztp-cfg-workflow`）。

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
