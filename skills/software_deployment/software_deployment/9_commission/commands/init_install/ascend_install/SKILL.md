> 命令 · **服务器昇腾软件安装**（ascendInstall）。执行由 `shared/task_runner` 统一负责。

# 服务器昇腾软件安装 ascend_install

对服务器安装昇腾软件栈（多阶段：安装→重启→网络配置→HCCL 端口→信息采集）。`device_kind=server`。

## 前置

步骤 7/8 完成；`gateway.json` 有效；建议 OS 已安装且节点连通。
`localPath` / `ascendVersion` 默认取自 UAT 参数模板 xlsx「昇腾软件安装」页签（`7.1.RC1`、`E:\data\openlab\Ascend\...`）；现场请改为真实安装包路径。

## 特有参数

- 设备字段：`deviceIds`。
- **不传** `taskName`。
- `components`：默认与 Agent 一致（python、npu_firmware、npu_driver 等）。
- 轮询：`poll_mode=ascend_multi_step`，间隔 30s，需等 5 个 step 均完成。
- query：仅 `taskId`。

## 产出

- `ProjectData/results/ascend_install/<task_name>/{report.zip, extracted/, receipt.json}`
- `deploy_chain.step9_init_install_at`

## 模板

- `config/execute.json`、`config/query.json`
