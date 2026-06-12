# a3-dw-manage-ip-workflow

离线 A3「计算带外管理面」地址规划：`007 + 项目信息收集表` → `output/run_*/计算带外管理地址.xlsx`（确定性计算，不依赖 LLM）。

## 目录结构

- `SKILL.md`：skill 说明与输入/输出契约
- `scripts/offline_dw_manage_pipeline.py`：主入口（生成最终 Excel）
- `scripts/validate_inputs.py`：输入校验（可选）
- `scripts/dw_manage_segment_rules.py`：规划与分配规则
- `output/`：运行输出目录（自动生成）

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 运行（生成结果）

```bash
python scripts/offline_dw_manage_pipeline.py
```

常用参数：

- `--007 PATH`：007 端口连线表（必须在 cwd 树下；省略则自动探测）
- `--resource PATH`：项目信息收集表/资源表（必须在 cwd 树下；省略则自动探测）
- `--out-dir output`：输出目录（默认 `output`）
- `--skip-prompt-check`：跳过可选 prompt 文本一致性检查

输出示例：

- `output/run_YYYYMMDD_HHMMSS/计算带外管理地址.xlsx`

## 可选：运行前校验输入

```bash
python scripts/validate_inputs.py
```

可用 `--sheet007` / `--sheet-res-index` 指定读取的 sheet。

