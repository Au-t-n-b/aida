# Step 3 · 评估与报告生成（含 LLM）· 详细规范

> 这是 zhgk skill 4 个 step 里**最值钱**的一步：所有 LLM 评估都在这里发生。
> 对应 AIDA Agent 后端节点：`report_gen`
> 对应原 nanobot 脚本：`zhgk/report-gen/scripts/{generate_assessment.py, generate_risk.py, generate_report.py}`

## A. 输入

| 文件 | 来源 |
|---|---|
| `RunTime/评估项底表_过滤.xlsx` | Step 1 产出 |
| `RunTime/工勘常见高风险库_过滤.xlsx` | Step 1 产出 |
| `Output/全量勘测结果表.xlsx` | Step 2 产出 |
| `RunTime/project_info.json` | Step 2 产出 |
| `Start/新版项目工勘报告模板.docx` | 项目固定模板 |
| `Start/机房满足度评估表_参考.xlsx`（可选） | 列头参考 |

## B. 子步骤

### B-1. 评估表生成（每行 1 次 LLM 调用）

读 `评估项底表_过滤.xlsx`，每行 5 列是「检查内容及要求」，调用 LLM：

```
System: 你是数据中心机房工勘评估专家。请按要求输出严格 JSON。

User:
请对以下"检查内容及要求"给出评估结论与缺陷记录。

检查内容及要求：{check}

输出 JSON：{"conclusion": "满足|不满足|无法识别|不涉及", "defect": "缺陷记录（若满足/不涉及可为空）"}
只输出 JSON，不要输出其它文本。
```

输出 → 写入 `Output/机房满足度评估表.xlsx`，6 列：
- 序号 / 严重性等级 / 分类 / 检查内容及要求 / 评估结论 / 缺陷记录

颜色规则：
- 满足 → 绿色 `92D050`
- 不满足 → 红色 `FF0000`（白字加粗）
- 无法识别 → 黄色 `FFFF00`（黑字加粗）
- 不涉及 → 灰色 `D9D9D9`

### B-2. 风险识别（每条风险 1 次 LLM 调用）

读 `工勘常见高风险库_过滤.xlsx`，遍历每条风险，结合「全量勘测结果表」判定是否触发：

```
System: 你是数据中心机房工勘风险评估专家。

User:
风险描述：{risk_desc}
触发条件：{trigger}
现场数据：{site_summary}

请判断该风险是否在本项目机房成立。输出 JSON：
{"hit": true|false, "level": "高|中|低", "evidence": "证据描述"}
```

输出 → 写入 `Output/风险识别结果表.xlsx`，含 hit=true 的条目。

### B-3. 工勘报告 docx 渲染（无 LLM，纯模板）

读模板 `Start/新版项目工勘报告模板.docx`，套用 jinja-docx 风格的占位符，渲染：
- 项目概况（来自 `project_info.json`）
- 全量勘测结果表
- 评估结果统计
- 风险清单
- 整改待办

输出 → `Output/工勘报告.docx` + `Output/整改待办.xlsx`

## C. 完成标志

| 文件 | 必须存在 |
|---|---|
| `Output/机房满足度评估表.xlsx` | ✅ |
| `Output/风险识别结果表.xlsx` | ✅ |
| `Output/工勘报告.docx` | ✅ |
| `Output/整改待办.xlsx` | ✅ |

## D. 完成后

1. 状态推送 `step=report_gen, status=completed, progress=100`
2. 展示统计摘要：
   - 满足/不满足/无法识别/不涉及 数量
   - 触发的风险条数
   - 整改待办数
3. 引导用户：「报告已生成，是否发送给专家审批？」（进入 Step 4）

## E. LLM 配置（调用方关注）

- 模型：`glm-4.5`（默认） · 可在 `.env` 改 `ZHIPU_MODEL`
- 温度：0.2（评估场景偏确定）
- 最大 token：512（评估行）/ 1024（风险行）
- 重试：2 次（langchain_openai 自动）

## F. Token 估算

按底表 ~100 行评估 + ~30 条风险计：
- 评估：100 × (150 input + 50 output) = ~20k token
- 风险：30 × (200 input + 80 output) = ~8.4k token
- 一次完整 Step 3 ≈ **28k token**（GLM-4.5 ≈ 0.07 元）

## G. 失败回退

- 单行 LLM 失败 → 该行 conclusion 写「无法识别」，defect 写「LLM 调用失败：{err}」
- 整 step 失败超过 50% → 标记 step.status=failed，由 graph 中止流程
- 提示用户：检查后端日志 + LLM 配额
