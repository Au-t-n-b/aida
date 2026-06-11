# Step 4 · 专家审批与干系人分发

> AIDA Agent 后端节点：`report_distribute`
> 原 nanobot 脚本：`zhgk/report-distribute/scripts/{distribute_report.py, distribute_report_4b.py}`

## 输入

| 文件 |
|---|
| `Output/工勘报告.docx`（Step 3 产出） |
| `Output/全量勘测结果表.xlsx`（Step 2 产出） |
| `Output/机房满足度评估表.xlsx`（Step 3 产出） |
| `Output/风险识别结果表.xlsx`（Step 3 产出） |
| `Start/远近一体化人员信息.xlsx`（固定资产） |
| `RunTime/project_info.json`（Step 2 产出） |

## 子步骤

### 4-A. 专家审批

运行 `distribute_report.py`：发邮件给 PD / TD / DC L1 工勘专家
- 收件人：从 `远近一体化人员信息.xlsx` 按角色过滤
- 邮件正文：项目概况 + 评估摘要 + 风险摘要
- 附件：4 份产物

**等待**：用户告知专家回复结果。

### 4-B. 干系人分发

用户确认「审批通过」后运行 `distribute_report_4b.py`：发邮件给**所有干系人**（不限角色）。

### 4-C. 数据补全（用户说「数据不足/需补充」）

引导回 Step 2 增量模式。

## 平台限制

| 平台 | 邮件能力 |
|---|---|
| Windows + Outlook | ✅ 通过 pywin32 |
| 其他 | ❌ 跳过此 step，提示用户手工发送 |

## 完成标志

邮件发送成功，无 SMTP / pywin32 错误。

## 完成后

「本次工勘流程已完成闭环。」
