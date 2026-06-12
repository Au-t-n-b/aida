# software_deployment 数据存储契约（MVP 本地 → 后续数据库）

MVP 阶段全部落本地；跑通后按本表接 CPCIA 同款 DB。业务只依赖 `deploy_chain`、`task_results`、
`file_registry` 及后续 `runtime/stores/*`，避免脚本散落读文件路径。

## 三类划分

| 类别 | 含义 | MVP | 上库后 |
|------|------|-----|--------|
| A 必须 DB | 多项目真值、与 EDM/活动/进度联动 | JSON 模拟 | MySQL |
| B 混合 | 元数据 DB + 大二进制文件/对象存储 | 均在 ProjectData | doc_id + 路径 |
| C 可永本地 | Skill 配置、编排 | 本地 | 一般不上库 |

## 按步骤对照

### ①～③ 计划（统一写入 deploy_chain）
| 数据域 | MVP 路径 | 类 | CPCIA 对标 |
|--------|----------|-----|------------|
| 步骤 ①～③ 时间戳/路径 | deploy_chain.step1_*～step3_* | A | 阶段进度（单一真值；`state.json` 已废弃） |
| 验收用例 Word | ProjectData/input/plan_split/*.docx + deploy_chain.step2_testcase_path | B | 项目验收用例文件；本阶段只做存在性检查 |
| 二/三级任务 | plan/Input\|Output/*_tasks.json | A | project_activity_info |
| 场景 | plan/RunTime/scene.json | A | project_info |
| 设备底表 | plan/Output/device_base_table.json | A | device_info_db_service |
| 下发记录 | plan/Output/dispatch_record.json | A | insert_device_tasks |
| 上传 xlsx | ProjectData/input/* | B | project_file_info |

### ④～⑦ CloudOps / ZTP
| 数据域 | MVP 路径 | 类 | CPCIA 对标 |
|--------|----------|-----|------------|
| 步骤时间戳 | deploy_chain.json | A | 阶段进度 |
| CloudOps/ZTP 文件 | plan/Output、input/cloudops | B | project_file_info |

### ⑧～⑨ Toolkit
| 数据域 | MVP 路径 | 类 | CPCIA 对标 |
|--------|----------|-----|------------|
| 执行机 | toolkit_executor.json | A | 项目执行机（SK 加密） |
| 网关 | gateway.json / 环境变量 | C→A | 租户配置 |
| 导入回执 | toolkit_import.json | B | history_task 片段 |

### ⑩+ Toolkit 任务
| 数据域 | MVP 路径 | 类 | CPCIA 对标 |
|--------|----------|-----|------------|
| 运行索引 | results/index.json | A | DeploymentTestHistoryTask |
| 回执/解析 | results/.../receipt.json, result.json | A | history_task + 设备结果行 |
| 报告 zip | results/.../report.zip | B | project_file_info |
| 步骤完成 | deploy_chain.step9_*～step11_* | A | deploy_progress |

不落库：CreateTask/轮询中间态（仅内存；完成写 receipt）。

## 文件标签机制（对齐 Agent）

所有「需要被后续检索」的文件都登记到**项目文件表**，靠 **标签** 而非文件名检索，避免改名遗漏。

- 标签常量：`runtime/file_tags.py`（`FileTagName` / `AgentTag` / `FILE_NAME_TAG_MAP`），字符串与 Agent 一致。
- 登记表（MVP 本地）：`runtime/file_registry.py` → `ProjectData/plan/RunTime/file_index.json`，
  字段对齐 Agent `project_file_info`（tag_name / agent_name / file_path / doc_id / parsed_status / status …）。
- 结果文件自动打标签：`task_results.save_task_result` 内部登记
  原始报告 `report.zip` → tag=`task_type`（如 `connection`），解析 `result.json` → tag=`REPORT_JSON`（与 Agent 一致）。
- 补登历史：`file_registry.scan_and_register_existing(skill_dir)` 按 `FILE_NAME_TAG_MAP` 扫 input/Output。

常用标签：`CloudOps_Config_Full` / `CloudOps_Config_Init` / `CloudOps_Config_Manual` /
`CloudOps_Params_Config` / `Device_Checklist` / `LLD_Design` / `ZTP_CFG` / `TestCase` / `REPORT_JSON`。

上库时：`register_file` / `query_by_tag` → `project_file_info_db.insert/query`，调用方不变。

## 上库时改这些模块
| CPCIA | nanobot 替换入口 |
|-------|------------------|
| device_info_db_service | DeviceStore（device_base_table + 报告回写） |
| project_file_info_db | file_registry（input/Output/results 标签登记） |
| HistoryTaskHandler | task_results → TaskRunStore |
| project_activity_info_db | ActivityStore（二/三级任务） |
| deploy 进度 | deploy_chain → DeployProgressStore |

## 不需要 DB
dashboard.json、guide_tasks.json、upstream_manifest.json、SKILL.md、driver 事件流。

## 敏感字段
secret_key、gateway_key：MVP 在 RunTime JSON；上库需加密或密钥服务。
