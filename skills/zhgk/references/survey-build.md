# Step 2 · 勘测数据汇总

> AIDA Agent 后端节点：`survey_build`
> 原 nanobot 脚本：`zhgk/survey-build/scripts/generate_survey_table.py`（首次）或 `merge_and_rebuild.py`（增量）

## 输入

| 文件 |
|---|
| `RunTime/勘测问题底表_过滤.xlsx`（Step 1 产出） |
| `Images/`（现场照片，可选） |
| `Input/勘测数据.xlsx`（如有） |

## 处理

1. 读取过滤后底表的所有勘测项
2. 把已有的勘测数据 / 照片识别结果填入对应项
3. 生成 3 类待办清单：
   - 待客户确认勘测项
   - 待拍摄图片项
   - 待补充勘测项

注：本 step 当前**主要走数据透视**，照片识别走单独脚本 `write_image_results.py`（可选 LLM）。

## 模式

| 模式 | 触发 |
|---|---|
| 首次生成 | `generate_survey_table.py` |
| 增量更新（用户补完后再跑） | `merge_and_rebuild.py` |
| 全量重建（推翻重来） | `generate_survey_table.py --fresh` |

## 输出

| 文件 |
|---|
| `Output/全量勘测结果表.xlsx` |
| `Output/待客户确认勘测项.xlsx` |
| `Output/待拍摄图片项.xlsx` |
| `Output/待补充勘测项.xlsx` |
| `RunTime/project_info.json` |

## 完成后引导

「Step 2 完成。已生成全量勘测表（X 项已填 / Y 项待办）。是否继续生成工勘报告？」
