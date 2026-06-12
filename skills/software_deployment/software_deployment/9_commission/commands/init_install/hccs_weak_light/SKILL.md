> 命令 · **灵衢光链路检查**（lqWeakLightCheck）。执行由 `shared/task_runner` 统一负责。

# 灵衢光链路检查 hccs_weak_light

灵衢交换机光模块与光链路健康检查。`device_kind=switch`。

## 前置

步骤 7/8 完成；完整配置含《灵衢交换机信息》且账号密码可用；`gateway.json` 有效。

## 特有参数

- 设备字段：`switchesDeviceIds`。
- 下发体 `configs[]`：光模块阈值，默认见 `config/execute.json`。
- 查询 `stepName=collectInfo`，`optResult=["3"]`。

## 设备范围

**本命令不单独实现 POD**；范围语义与一期限制见 **`docs/灵衢光链路检查-skill设计文档.md` §5.3**。一期请用 `include` / `all` / `exclude` / `param_file` / `prev_*`（设备池走公共 `device_resolver`，`scope=pod` 现网不可用）。

## 产出

- `ProjectData/results/hccs_weak_light/<task_name>/{report.zip, extracted/, result.json, receipt.json}`
- `deploy_chain.step9_init_install_at`（模块级，与同模块其他命令共用）
- 双段回执：采集统计 + 光链路报告摘要

详细设计：`docs/灵衢光链路检查-skill设计文档.md`
