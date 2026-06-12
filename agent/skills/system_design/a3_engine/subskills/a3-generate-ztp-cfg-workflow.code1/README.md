# a3-generate-ztp-cfg-workflow

离线 A3「**生成ZTP配置文件**」：`ZTP_LLD.xlsx` + `项目信息收集表(ZTP配置)` → cfg zip。

> 业务来源：`generate_ztp_lld.ztp_cfg_generate`

## 前置依赖

最终需要：

1. `ZTP_LLD.xlsx`（sheet `网络IP规划`）— 缺失时**自动运行** `a3-generate-ztp-lld-workflow`
2. `项目信息收集表.xlsx`（sheet `ZTP配置`）— 缺失时在 `_skill_staging` 内检索最新副本

链式生成 ZTP_LLD 时，当前目录建议另有：`007`、`004 设备位置表`（与 ztp-lld skill 相同）。

## 安装

```bash
cd _skill_staging/a3-generate-ztp-cfg-workflow.code1
python -m pip install -r requirements.txt
```

## 运行

将 `007`、`项目信息收集表` 等放入 skill 根目录后一键执行（缺 `ZTP_LLD` 会自动链式生成）：

```bash
python scripts/offline_generate_ztp_cfg_pipeline.py --out-dir output --project-name MyProject
```

禁用自动前置：`--no-auto-prereq`

显式指定：

```bash
python scripts/offline_generate_ztp_cfg_pipeline.py \
  --ztp-lld ZTP_LLD.xlsx \
  --resource 项目信息收集表.xlsx \
  --project-name MyProject \
  --out-dir output
```

## 输出

仅生成 zip（不保留 `cfg_bundle` 中间目录）：

- `output/run_*/{project_name}_ZTP配置文件_*.zip`
  - 解压后含 `L1/`、`L2/` 下以管理 IP 命名的 `.cfg`，以及 `ztp.ini`

## 与 API 开局区别

| 指令 | 脚本 | 本 skill |
|------|------|----------|
| 生成ZTP配置文件 | `generate_ztp_lld.ztp_cfg_generate` | ✅ |
| 生成灵衢开局文件 | `generated_ztp_api.py` | ❌ |
