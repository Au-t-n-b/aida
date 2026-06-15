# 后端

> **当前路线（2026-06-10 拍板）**：后端先**基于 `02_项目数据`（真实表）+ `/contracts` 契约**开发，**不基于本体**。
> 本体（DORA）方案整体延后：等基于 `02_项目数据` 的系统开发完成后，再评估**部分接入**。
> 原《01 本体开发规范》已移至 `99_归档/04后端_本体开发规范/`，届时再取回参考。**开发 agent 无需阅读本体相关材料。**

## 现状

- 后端代码：已具备 `importer`、`engine`、`api`、`store` 四块；API 服务壳在 `app/main.py`，排期端点在 `app/api/`，SQLite 版本存储在 `app/store/`。
- 运行环境：`04 后端/.venv`（gitignore 不入库）；依赖清单 [requirements.txt](requirements.txt)；**内网安装走固定 prompt [环境安装.md](环境安装.md)**。
- 技术栈：**Python ≥3.10 + FastAPI + Pydantic v2 + SQLite**（2026-06-10 已钉死，权威在根 `AGENTS.md` §1）。
- 接口与数据形状：以仓根 [`/contracts/`](../contracts/README.md) 为唯一权威（v1 已冻结），输入字段对接 `02_项目数据/*/表头.md`；语义↔文件对齐分析见 [`20_数据地图_语义对齐.md`](../01_系统蓝图/01_算力交付排期/02_架构地图/20_数据地图_语义对齐.md)。
- 模型调用：见 [模型调用手册.md](模型调用手册.md)（排期侧默认 `qwen3.7-max`；真实密钥在 `04 后端/.env`，已 gitignore 不入库）。
- 风险报告 AI 总结：`/api/v1/schedule/report-summary` 从 `.env` 读取 `BAILIAN_API_KEY`，默认用百炼流式调用累积完整文本后再解析 JSON。可选 `BAILIAN_BASE_URL`、`BAILIAN_TIMEOUT_SECONDS`（默认 90 秒）、`BAILIAN_LIVENESS_TIMEOUT_SECONDS`（默认 10 秒）、`BAILIAN_MAX_RETRIES`（默认 2 次重试）、`BAILIAN_RETRY_BACKOFF_SECONDS`（默认 0.5 秒指数退避）；外网如需代理，在启动 shell 里设置 `HTTP_PROXY` / `HTTPS_PROXY=http://127.0.0.1:7897`，不要写进代码或入库配置。（收口实测旁注：本机直连 dashscope 即通；经 env-var 代理时 httpx 可能 SSL EOF，dashscope 直连不受 pip 那种指纹掐断影响。）
- 依赖安装（2026-06-10 实测）：**内网**直接用默认 pip 配置（华为镜像，本机 `~/pip/pip.ini` 已配）；**外网** pip 的 TLS 握手会被防火墙按指纹掐断（直连/经代理皆然），可行路径 = **curl 经本地代理下 wheel + 离线装**：
  `curl -x http://127.0.0.1:7897 -LO <pypi wheel地址>` → `pip install --no-index --find-links=<目录> <包>`。
  已用此法装好 pydantic 2.13.4（wheel 暂存 `~/wheels_tmp`，建虚拟环境时可复用）。

## API 服务启动

前提：`04 后端/.venv` 已按 [环境安装.md](环境安装.md) 建好；启动时 `PYTHONPATH` 必须包含仓根，这样 `app` 与 `/contracts` 都能被导入。**在工棚（worktree）里启动则设为工棚根**（如 `D:\project\wt-T-XXX`），否则找不到 contracts、7402 起不来。环境变量在**当前 shell** 设好再启动，别把 `$env:X=…` 拼进字符串传给新开的子 shell（T-005 踩坑：会被提前展开写坏，服务静默失败）。

地址一律写 **`127.0.0.1`、不写 `localhost`**（前端代理、curl、healthz 检查同理）：Windows 上 `localhost` 可能解析为 IPv6 `::1`，而 uvicorn 默认绑 IPv4，连接报 `ECONNREFUSED`。

PowerShell 逐条执行：

```powershell
cd "D:\project\交付项目-整体梳理\04 后端"
$env:PYTHONPATH="D:\project\交付项目-整体梳理"
.\.venv\Scripts\uvicorn.exe app.main:app --port 7402
```

若已激活虚拟环境，也可按工单约定执行：

```bash
cd "04 后端" && uvicorn app.main:app --port 7402
```

健康检查：`GET /healthz` 返回 `200 {"status":"ok"}`。排期接口前缀为 `/api/v1/schedule`，当前端点：

- `POST /api/v1/schedule/generate`：输入 `GenerateRequest`，调用引擎生成初排，并保存为计划版本。
- `POST /api/v1/schedule/adjust`：输入 `AdjustRequest`，按实体 `id` 覆盖合并基线输入；无诉求返回 A 稳定方案，提前诉求返回 A/B/C，延后诉求返回 buffer 方案。
- `POST /api/v1/schedule/commit`：输入 `CommitRequest`，按 `option_id` 写回正式计划并递增版本；T-016 起可选带 `duration_overrides`（活动实例 id → 工期天数），后端校验极限 SLA 后由引擎重算下游 FS 顺延再落新版，未带该字段时保持原方案快照写回；T-047 起下发时重算 beta 影子推荐并写入 SQLite 追踪日志，不改变响应契约。
- `GET /api/v1/schedule/change-template`：下载 T-013 固定变更表模板（`02_项目数据/10_变更表模板/变更表模板.xlsx`）。
- `POST /api/v1/schedule/parse-changes`：multipart 上传固定模板 Excel，返回 `ParseChangesResponse(changes, warnings)`；只解析机房 ready、PoD 到货、批次上电/上线目标，空单元格表示不改，模板结构不可用时返回 422 `IMPORT_ERROR`。
- `GET /api/v1/schedule/project-data`：经导入器只读加载 `02_项目数据` 并返回既有 `InputBundle`，供前端开场盘子接真数据；可选 query `total_card_count` 透传给导入器用于规模分档，不传则沿用导入器回退规则。导入失败返回 422 `ErrorResponse(IMPORT_ERROR)`。
- `POST /api/v1/schedule/report-summary`：输入 `ReportSummaryRequest`（风险报告抬头、统计、四清单条目快照），调用百炼 `qwen3.7-max` 生成解释层 `ReportSummaryResponse`；模型只写整体结论和行动建议，不参与排期计算。缺 key 返回 503 `LLM_CONFIG_MISSING`，超时返回 504 `LLM_TIMEOUT`，其它调用失败返回 502 `LLM_CALL_FAILED`。

SQLite 默认文件：`04 后端/.venv/schedule.sqlite3`（本地运行产物，不入库），保存正式计划版本、沙箱调整方案与 T-047 影子推荐校准日志。需要改位置时设置 `SCHEDULE_DB_PATH`。
