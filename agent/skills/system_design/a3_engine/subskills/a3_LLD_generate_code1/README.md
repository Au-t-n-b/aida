# a3_LLD_generate_code1

A3 LLD 离线总编排：plan 生成工作流；integrate **仅输出最终 LLD 表**（无 step_out / staging）。

## 安装

```bash
cd a3_LLD_generate_code1
python -m pip install -r requirements.txt
```

## 快速开始

### 1. 工作流计划（可选，仅元数据）

```bash
python scripts/offline_lld_generate_pipeline.py --mode plan \
  --topology ../files/A3_files/建模仿真输出文档007-端口连线表.xlsx \
  --resource ../files/A3_files/项目信息收集表.xlsx \
  --project-name 测试项目
```

产出：`output/run_*/workflow_plan.json`（**不含**各 step 中间目录）

### 2. 融合最终 LLD（主输出）

```bash
python scripts/offline_lld_generate_pipeline.py --mode integrate \
  --project-name 测试项目 \
  --scan-dir ../output
```

产出：**仅** `output/测试项目-LLD设计-YYYYMMDD_HHMM.xlsx`

### 3. collect（可选）

将子 skill 产出复制到扫描目录（非必须，若子 skill 已直接写入 `--scan-dir`）：

```bash
python scripts/offline_lld_generate_pipeline.py --mode collect \
  --source-dir /path/to/child/output \
  --scan-dir ../output
```

## 输出约定

| 类型 | 路径 |
|------|------|
| 最终 LLD | `{out-dir}/{项目名}-LLD设计-{时间戳}.xlsx` |
| plan 元数据 | `{out-dir}/run_*/workflow_plan.json`（可选） |
| ~~step_out / staging~~ | **不再创建** |

## 约束

- 不接入 EDM / DB / LLM
- integrate 按平面 `A3*` 取 mtime 最新文件
