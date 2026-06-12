---
name: a3-input-components-workflow
description: Offline A3 查询输入件流程。Use when deterministically reproducing a3_input_components.py behavior: query the three simulation input tags Device_Info, Location_Information, and Interconnection_Relationship, then render a Markdown table of found standard filenames without validating Excel content.
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_input_components_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线复现 A3 `查询输入件` 流程，业务逻辑严格对齐 `src/manage_agent/sub_agents/LLD_IP/a3_input_components.py`。

该流程只判断固定输入件 tag 是否存在，并展示已找到输入件的标准文件名；不读取 Excel 内容，不校验 sheet/字段/空值，不因缺失输入件终止流程。

## Agent Trigger

线上 agent 中触发指令为 `查询输入件`，对应函数：

`a3_input_components.a3_check_if_it_is_appropriate(user_id, project_id, files_path, net_resource_path, dialogue_id)`

## Entrypoint

`python scripts/offline_input_components_pipeline.py [--scan-dir DIR] [--manifest PATH] [--tag TAG ...] [--out-dir output]`

推荐：将标准输入 Excel 放在 skill 根目录后，在根目录执行（无额外参数即扫描 cwd）：

`python scripts/offline_input_components_pipeline.py --out-dir output`

## Dependencies

`pip install -r requirements.txt`

## Inputs

离线流程用以下方式表示 `get_project_latest_file_by_tag(project_id, "design_agent", tag)` 的查询结果：

- **目录自动扫描（推荐）**：未提供 `--manifest` / `--tag` 时，扫描 cwd；或通过 `--scan-dir DIR` 指定目录。目录内可放置任意数量 Excel；仅当存在 `Fixed File Config` 中的标准 `filename` 时，对应 tag 视为有返回值，其余 Excel 忽略。
- `--tag Device_Info`：显式标记 `Device_Info` 有返回值。
- `--manifest PATH`：JSON 或 CSV，提供 tag 到路径的映射；tag 存在且路径非空即视为有返回值。

## Fixed File Config

严格只查询以下 3 个输入件：

| 业务名称 | tag | 展示文件名 |
|---|---|---|
| `设备信息概览` | `Device_Info` | `建模仿真输出文档001-设备信息表.xlsx` |
| `设备位置信息` | `Location_Information` | `建模仿真输出文档004-设备位置表.xlsx` |
| `端口互联关系` | `Interconnection_Relationship` | `建模仿真输出文档007-端口连线表.xlsx` |

## Deterministic Rules

1. 按固定顺序遍历 `设备信息概览`、`设备位置信息`、`端口互联关系`。
2. 对每项执行一次 tag 查询，等价于线上 `get_project_latest_file_by_tag(project_id, "design_agent", v["tag"])`。
3. 若查询结果为空：只记录 `未找到{k}文件，将使用默认文件` 语义，不加入展示内容。
4. 若查询结果非空：向 `content` 追加该项配置中的标准 `filename`，不是追加实际路径。
5. 将 `content` 转成单列 DataFrame，列名固定为 `文件名称`。
6. 使用 `DataFrame.to_markdown(index=False)` 生成 Markdown 表格。
7. 输出标题固定为 `查询输入件`，展示编码语义对齐线上 `display_message("0-8", "查询输入件", ...)`。

## Outputs

目录：`output/run_YYYYMMDD_HHMMSS/`

- `查询输入件.md`：唯一输出文件；单列 Markdown 表格，列名 `文件名称`（对齐线上 `display_message`）。

## Non-goals

- 不检查输入件是否妥当。
- 不打开或解析 Excel 文件。
- 不校验表头、sheet、字段、网络平面或数据完整性。
- 不调用 LLM、EDM、数据库或前端展示 API。

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
