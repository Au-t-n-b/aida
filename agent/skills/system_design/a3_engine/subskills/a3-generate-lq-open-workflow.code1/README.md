# a3-generate-lq-open-workflow

离线 A3「**生成灵衢开局文件**」：`项目信息收集表(ZTP配置)` + `ZTP_LLD.xlsx` → CloudOps API 请求 →（可选）灵衢开局 zip。

> 业务来源：`generated_ztp_api.py` → `ztp_cfg_generate_by_api`

## 与「生成ZTP配置文件」区别

| 指令 | 实现 | 输出方式 |
|------|------|----------|
| 生成ZTP配置文件 | `generate_ztp_lld.ztp_cfg_generate` | 本地模板 |
| **生成灵衢开局文件** | `generated_ztp_api.ztp_cfg_generate_by_api` | **CloudOps API** |

## 安装

```bash
cd _skill_staging/a3-generate-lq-open-workflow.code1
python -m pip install -r requirements.txt
```

## 运行

将 `项目信息收集表.xlsx` 放入 skill 目录；缺 `ZTP_LLD` 时会自动链式生成：

```bash
# 确定性：仅生成 API 请求 JSON
python scripts/offline_generate_lq_open_pipeline.py --out-dir output

# 调用 CloudOps 导出 zip（需 token）
python scripts/offline_generate_lq_open_pipeline.py --out-dir output --call-api --project-name MyProject
```

环境变量（`--call-api` 时）：

```bash
set CLOUDOPS_AUTHORIZATION=Bearer ...
set CLOUDOPS_X_HW_ID=...
```

## 输出

- `output/run_*/api_request.json`（始终生成）
- `output/run_*/*_灵衢开局文件_*.zip`（仅 `--call-api` 成功时）

## 前置依赖

- `ZTP_LLD.xlsx`：可自动运行 `a3-generate-ztp-lld-workflow`
- `项目信息收集表.xlsx`：需自备或在 `_skill_staging` 内检索
