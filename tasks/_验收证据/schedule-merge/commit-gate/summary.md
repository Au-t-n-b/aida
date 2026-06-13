# Schedule Merge Commit Gate

## Scope

- 本文件只记录合入计划每个逻辑提交的快检结果。
- 未执行合入后完整 E2E after replay。
- 当前合入提交：
  - `05e1097 合并：schedule 后端隔离落 agent/schedule`
  - `0c2e7d8 合并：schedule 前端功能隔离落 features/schedule`
  - `be5f3e0 调整：计划导航收敛到排期与风险报告`

## Environment Fixes

```powershell
python -m pip install --index-url https://pypi.org/simple --no-cache-dir --no-deps python-multipart
python -m pip install --index-url https://pypi.org/simple --no-cache-dir --no-deps sse-starlette
```

- 结果：通过。
- 说明：仅补当前 Python 环境依赖，未修改仓库文件。

## Backend Gate

```powershell
python -X utf8 -m agent.schedule.contracts.generate_ts --check
```

- 结果：通过。
- 输出关键行：`[契约新鲜度] ✅ 生成物与模型一致`。
- 说明：普通 `python -m ...` 在当前 PowerShell GBK 输出环境打印 `✅` 会触发编码错误，后续固定使用 `python -X utf8`。

```powershell
python -c "from agent.schedule.router import router; from agent.schedule.importer import load_input_bundle; b=load_input_bundle(); print({'router_routes': len(router.routes), 'rooms': len(b.rooms), 'pods': len(b.pods), 'batches': len(b.batches), 'teams': len(b.teams), 'activities': len(b.activities), 'dependencies': len(b.dependencies)})"
```

- 结果：通过。
- 输出关键值：`router_routes=7, rooms=3, pods=9, batches=3, teams=2, activities=70, dependencies=119`。

```powershell
python -m pytest agent/schedule/tests
```

- 结果：通过。
- 输出关键值：`71 passed, 9 warnings`。

```powershell
python -c "from agent.main import app; print(app.title); print(any(getattr(route, 'path', '') == '/api/v1/schedule/project-data' for route in app.routes))"
```

- 结果：通过。
- 输出关键值：`AIDA Agent · zhgk pilot`、`True`。

## Export Smoke

- 已在后端提交快检中执行 `project-data -> generate -> adjust -> commit -> export-plan`。
- 导出路径：`agent/schedule/project-data/12_输出文件/交付计划表.xlsx`。
- 输出关键值：HTTP 状态码均为 `200`，导出文件约 `58990` bytes，工作表 `397` 行、`32` 列。
- 说明：导出接口默认覆盖 `12_输出文件/交付计划表.xlsx`，符合已确认合入计划。

## Frontend Gate

```powershell
npm run typecheck
```

- 结果：通过。

```powershell
npm run lint:no-ts-nocheck
```

- 结果：通过。
- 输出关键值：`@ts-nocheck 数维持在 36（baseline 36）`。

```powershell
npm run build
```

- 结果：通过。
- 说明：Vite 仅输出既有资源解析、chunk size、plugin timing 警告。

## Route And Nav Gate

- `/plan`：无 `view` 或带 `stage=init|adjust` 时进入 schedule 排期页面。
- `/plan?view=plan|task|risk|assumption|issue|change`：仍进入 aida 原旧计划页面。
- `/plan-init`：兼容跳转到 `/plan?stage=init`。
- `/plan-adjust`：兼容跳转到 `/plan?stage=adjust`。
- `/plan-risk-report`：挂载 schedule 风险报告页面。
- 主导航计划分组只保留：`基本信息 / 计划排期 / 风险报告`。

## Result

- Commit gate 结论：通过。
- 未执行 after replay，等待用户单独指令。
