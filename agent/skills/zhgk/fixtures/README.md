# zhgk 演示工勘报告（随项目 demo 数据）

`report_gen_run` 在本地联调时使用 `ProjectData/Input/本地工勘报告.pdf` 作为演示撰写源文件。

## 资产归属

| 文件 | 归属 | 是否随项目 push Gitea |
|------|------|----------------------|
| `本地工勘报告.pdf` | **项目演示资产** | ✅ 是 |
| `入场评估标准表.xlsx` | 组织资产 / 用户上传 | ❌ 否（filter_build HITL 自行上传） |
| `工勘常见高风险库.xlsx` | 组织资产 / 用户上传 | ❌ 否（filter_build HITL 自行上传） |

## 真相源（项目级）

| 项 | 路径 |
|---|---|
| 源 PDF（人工维护） | `D:\.cursor_workplace\aida\工勘报告.pdf` |
| **项目演示资产（canonical）** | `{AIDA_BUSINESS_ROOT}/projects/70e5ca737ae5433e9f0f3134d216acf7/交付作业/智慧工勘/输入文件/本地工勘报告.pdf`（本地默认 `{仓库}/data/projects/...`） |
| 追踪清单 | 同目录 `manifest.json` |
| 运行时落点 | `{ZHGK_ROOT}/ProjectData/Input/本地工勘报告.pdf`（init/reset 从项目资产复制） |
| 旧版兜底 | `agent/skills/zhgk/fixtures/本地工勘报告.pdf`（遗留，非 canonical） |

## 同步命令

在仓库根目录执行：

```bash
python agent/scripts/sync_zhgk_mock_report.py --dest-workspace
```

- 默认将源 PDF 中的项目名称 `字节跳动` 替换为 `京东3期`
- 写入项目演示路径并更新 `manifest.json`
- `--dest-workspace` 会同时复制到当前 `ZHGK_ROOT` 工作区

`init_zhgk_workspace.py`、`reset_zhgk_workspace.py` 与 `scripts/reset_local_dev.ps1` 会从项目演示资产自动 seed 到 `Input/`。

## 重置工勘流程

```bash
# 清 Output/RunTime/Images，保留 Template（底表+风险库）
python agent/scripts/reset_zhgk_workspace.py
```

`--clear-template` 才会删除风险库；换底表后只想重建勘测项时用默认命令即可。
