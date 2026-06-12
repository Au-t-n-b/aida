> 命令 · **灵衢健康检查**（lqClusterHealthCheck）。执行由 `shared/task_runner` 统一负责。

# 灵衢健康检查 lq_health_check

灵衢交换机集群健康检查（按 CloudOps 检查项模板采集统计）。`device_kind=switch`，设备字段 **`deviceIds`**。

## 前置

步骤 7/8 完成；**CloudOps 测试参数**（`ProjectData/input/cloudops`）含 Sheet「灵衢健康检查」；完整配置含《灵衢交换机信息》；`gateway.json` 有效。

## 特有参数

- 下发体含 **`templateId`**（默认见 `config/execute.json`，由测试参数「检查项模板」覆盖）。
- 轮询完成：**仅 `reportEnd`**；`failNum == totalNums` 视为执行失败（不导出）。
- 轮询建议：`poll_max=250`，`poll_interval_s=30`（对齐 Agent）。
- 导出：**zip**，解析路径 `healthCheck/statistics_reports/*.xlsx`，Sheet「灵衢交换机健康检查统计」。

## 设备范围

**本命令不单独实现 POD**；范围语义与一期限制见 **`docs/灵衢健康检查-skill设计文档.md` §4.5**。一期请用 `include` / `all` / `exclude` / `param_file` / `prev_*`（设备池走公共 `device_resolver`，`scope=pod` 现网不可用）。

## 产出

- `ProjectData/results/lq_health_check/<task_name>/{report.zip, extracted/, result.json, receipt.json}`
- `deploy_chain.step9_init_install_at`
- 回执含 Markdown 统计表摘要

详细设计：`docs/灵衢健康检查-skill设计文档.md`
