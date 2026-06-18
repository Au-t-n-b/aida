# Step 1 · 场景筛选与底表过滤

> AIDA Agent 后端节点：`scene_filter`
> 原 nanobot 脚本：`zhgk/scene-filter/scripts/scene_filter.py`

## 输入

| 文件 | 说明 |
|---|---|
| `Start/勘测问题底表.xlsx` | 固定资产 · 全量勘测项清单 |
| `Start/评估项底表.xlsx` | 固定资产 · 全量评估项清单 |
| `Start/工勘常见高风险库.xlsx` | 固定资产 · 风险库 |
| `Input/*BOQ*.xlsx` | 用户上传 · 文件名需含 "BOQ" |
| `Input/勘测信息预置集.docx` | 用户上传 · 固定文件名 |

## 处理

1. 从 BOQ 读取设备清单，识别项目场景（推理 / 训练 / 训推 / 大EP）
2. 从勘测信息预置集读取机房元信息（机房数 / 制冷方式 / 客户等）
3. 按场景过滤 3 张底表 → 只保留与本项目相关的行
4. 生成定制工勘表（前两步合并）

注：本 step 当前**纯规则过滤**，不调 LLM。

## 输出

| 文件 |
|---|
| `RunTime/定制工勘表.xlsx` |
| `RunTime/勘测问题底表_过滤.xlsx` |
| `RunTime/评估项底表_过滤.xlsx` |
| `RunTime/工勘常见高风险库_过滤.xlsx` |

## 完成后引导

「Step 1 完成。下一步：上传现场勘测照片，或说『开始汇总勘测数据』」
