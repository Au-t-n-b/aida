> 命令 · **灵衢配置检查**（lqConfigCheck）。执行由 `shared/task_runner` 统一负责。

# 灵衢配置检查 lq_config_check

校验灵衢交换机配置与 ZTP 开局文件一致性。`device_kind=switch`，设备字段 **`deviceIds`**。

## 前置

步骤 **6** 已登记 ZTP zip → 步骤 7/8 完成；完整配置含《灵衢交换机信息》；`gateway.json` 有效。A3 场景必须上传 ZTP。

## 特有参数

- 下发：**multipart**，`file`=ZTP zip（步骤 6 登记路径），`configCheckReq`=execute.json 填完后的 JSON。
- 轮询完成：`totalNums>0` 且 processing/waiting 均为 0（非 reportEnd）。
- 导出：**xlsx**，Sheet「配置检查结果」。

## 设备范围

**本命令不单独实现 POD**；一期请用 `include` / `all` / `exclude` / `param_file` / `prev_*`（设备池走公共 `device_resolver`，`scope=pod` 现网不可用）。

## 产出

- `ProjectData/results/lq_config_check/<task_name>/{report.xlsx, result.json, receipt.json}`
- `deploy_chain.step9_init_install_at`
- 回执含配置检查聚合统计与设备级 Pass/Fail

详细设计：`docs/灵衢配置检查-skill设计文档.md`
