> 命令 · **单机模型测试**（singleTrainingTask）。执行由 `shared/task_runner` 统一负责。

# 单机模型测试 single_model_test

对应 CloudOps 执行机 **服务器测试 → 单机模型测试**；Agent `single_model_test_handler` / `ThirdActivity.SINGLE_MODEL_TEST`。

## 前置

- 步骤 7/8 完成；`gateway.json` 有效。
- **训练场景**才可执行（`scene.json` 中 `train_infer_scene=train`）；推理场景无法下发，Skill 应提示用户切换场景或选用其他命令。

## 特有参数

- 设备字段：`nodeList`
- 参数页签：**单机模型测试**（`runtime/params_template_sheets.json`）
- 镜像类型、上传途径、本地路径等保持 Agent 默认常量；空值/默认可能导致下发失败
- query：仅 `taskId` + 分页 + `keyWord`，无 `stepName`

## 产出

- `ProjectData/results/single_model_test/<task_name>/{report.zip, extracted/, receipt.json}`

## 模板

- `config/execute.json`、`config/query.json`（真值来源 Agent `params/single_model_test/`）
