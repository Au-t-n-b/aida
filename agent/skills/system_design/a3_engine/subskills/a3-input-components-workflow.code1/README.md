# a3-input-components-workflow

离线 A3「查询输入件」流程：根据固定仿真输入件 tag，输出已找到输入件的标准文件名 Markdown 表格。

> 业务来源：`src/manage_agent/sub_agents/LLD_IP/a3_input_components.py`

## 目录结构

- `SKILL.md`：skill 契约与完整业务规则
- `scripts/offline_input_components_pipeline.py`：确定性入口脚本
- `requirements.txt`：依赖
- `output/`：运行输出（自动生成）

本 skill 根目录可放置仿真输入 Excel；脚本按**标准文件名**自动识别（不解析文件内容）。

## 安装

```bash
cd _skill_staging/a3-input-components-workflow.code1
python -m pip install -r requirements.txt
```

## 推荐：放置输入件后一键执行

将输入 Excel 放在 skill 根目录（与 `scripts/` 同级），然后在该目录执行：

```bash
cd _skill_staging/a3-input-components-workflow.code1
python scripts/offline_input_components_pipeline.py --out-dir output
```

未指定 `--manifest` / `--tag` / `--scan-dir` 时，脚本会**自动扫描当前工作目录**，若存在下列标准文件名，则视为对应 tag 已命中：

| 业务名称 | tag | 需放置的标准文件名 |
|---------|-----|-------------------|
| 设备信息概览 | `Device_Info` | `建模仿真输出文档001-设备信息表.xlsx` |
| 设备位置信息 | `Location_Information` | `建模仿真输出文档004-设备位置表.xlsx` |
| 端口互联关系 | `Interconnection_Relationship` | `建模仿真输出文档007-端口连线表.xlsx` |

指定其他目录扫描：

```bash
python scripts/offline_input_components_pipeline.py --scan-dir . --out-dir output
```

**说明**：目录中若有其它 Excel（如 `建模仿真输出文档006-设备落位图.xlsx`、`项目信息收集表.xlsx`），本流程**不会**纳入查询结果，与线上 `a3_input_components.py` 一致。

### 可以一次放入很多文件吗？

可以。你可以把整套仿真/项目 Excel 都放进 skill 目录，脚本只会按**标准文件名**精确匹配上面 3 个输入件：

- 匹配到 → 计入「查询输入件」展示表
- 未匹配 → 忽略（与线上脚本一致，不单独输出忽略列表文件）

例如目录里同时有 001、004、006、007、项目信息收集表共 5 个文件时，仍会正确识别 3 个所需文件并写入 `查询输入件.md`。

## 其它运行方式

直接用 tag 表示已存在输入件：

```bash
python scripts/offline_input_components_pipeline.py \
  --tag Device_Info \
  --tag Location_Information \
  --tag Interconnection_Relationship
```

或使用 manifest：

```bash
python scripts/offline_input_components_pipeline.py --manifest files.json
```

`files.json` 示例：

```json
{
  "Device_Info": "建模仿真输出文档001-设备信息表.xlsx",
  "Interconnection_Relationship": "建模仿真输出文档007-端口连线表.xlsx"
}
```

## 输出

仅生成一个文件（对齐线上 `display_message` 的 Markdown 展示）：

- `output/run_YYYYMMDD_HHMMSS/查询输入件.md`

Markdown 只包含已找到输入件的标准文件名，列名固定为 `文件名称`。

## 与线上脚本一致的边界

- 只查询 `Device_Info`、`Location_Information`、`Interconnection_Relationship`。
- 缺失输入件不进入展示表格，只记录“将使用默认文件”语义。
- 不检查 Excel 内容，不判断输入件是否妥当。
