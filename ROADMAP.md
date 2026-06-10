# AIDA 工作路线图（智慧工勘作业流程上线）

> **创建**：2026-06-07  
> **负责人**：团队  
> **当前分支**：`feat/merge-delivery-frontend`  
> **参考 UI**：`C:/Users/j00954996/Desktop/smart_survey/smart_survey/ui/gongkan_workbench.html`

---

## 路线图总览

```
Step 1：本地完整测试 + 调优         ← 当前焦点（另一个会话完成 SDUI 改动后启动）
  ↓ 通过 smoke test + SDUI 视觉验收
Step 2：数据中心接口集成              ← 等同事调试好 DC API 后并行启动
  ↓ 文件上传/下载走 DC
Step 3：服务侧部署 + 测试             ← Step 1+2 完成后
  ↓ 生产环境验收
Step 4：文档完善 + 开发者地图         ← Step 3 完成后最终落地
```

---

## Step 1 · 本地完整测试与调优

### 前置条件

| 条件 | 状态 | 说明 |
|------|------|------|
| 另一个会话完成 SDUI 改动 | ⏳ 等待 | 见该会话 HANDOFF.md Phase 7 清单 |
| 3 个模板文件放置到位 | ❌ **缺失阻断** | 详见下方 §1.1 |
| `zhgk_files.py` v4 迁移 | ❌ **Bug 阻断** | 详见下方 §1.2（当前代码是 v3 遗留） |

### 1.1 三个模板文件（必须人工放置）

```
D:/srv/zhgk/ProjectData/Template/
  ├─ 入场评估标准表.xlsx       ← filter_build 读底表
  ├─ 工勘常见高风险库.xlsx     ← report_gen_run 风险识别
  └─ 新版项目工勘报告模板.docx  ← report_gen_run 9 表填充（需含 ≥9 个表格）
```

来源：`C:/Users/j00954996/Desktop/smart_survey/smart_survey/ProjectData/Template/`

### 1.2 阻断级 Bug：zhgk_files.py 完全是 v3 遗留

**问题**：`agent/zhgk_files.py`（file_handler）与 v4 `path_config.py` 路径完全不一致，任何文件型 HITL 上传都会出错。

| 当前 v3 代码（错误） | v4 实际路径（正确） |
|---------------------|-------------------|
| `ProjectData/Start/勘测问题底表.xlsx` | 已废弃，不存在 |
| `ProjectData/Start/评估项底表.xlsx` | 已废弃，不存在 |
| `ProjectData/Start/工勘常见高风险库.xlsx` | `ProjectData/Template/工勘常见高风险库.xlsx` |
| `ProjectData/Input/勘测信息预置集.docx` | 已废弃，不存在 |
| BOQ glob：`*BOQ*.xlsx` | 正确，保留 |

**需要改动**：
```python
# agent/zhgk_files.py 需要重写 FIXED_ITEMS 和 infer_upload_kind：
FIXED_ITEMS = [
    {"id": "base_table", "label": "入场评估标准表",
     "path": "ProjectData/Template/入场评估标准表.xlsx"},
    {"id": "risk_lib", "label": "工勘常见高风险库",
     "path": "ProjectData/Template/工勘常见高风险库.xlsx"},
    {"id": "report_tpl", "label": "工勘报告模板（可选）",
     "path": "ProjectData/Template/新版项目工勘报告模板.docx", "optional": True},
]
# infer_upload_kind 加入 "template" kind 并更新文件名识别逻辑
```

### 1.3 测试矩阵（4 意图 × 核心路径）

#### intent: `scene_suggest`（最短路径，约 5 步）
```
preflight → intent_select(scene_suggest) → determine_gen → filter_build
→ data_append(可选) → confirm_table → END
```
验收要点：
- [ ] Stepper 只显示 5 步，不显示全部 15 步
- [ ] filter_build 完成后 SDUI 展示条目数 NumberCards + 细分场景 Table
- [ ] 产物：`Output/xxx_全量勘测结果表.xlsx`（空 AI 评估列，仅结构）

#### intent: `survey_work`（主流程，约 12 步）
```
preflight → intent_select(survey_work) → determine_gen → filter_build
→ method_split → data_append(HITL/跳过) → confirm_table(HITL)
→ wait_survey(HITL 上传) → assess → issue_list → resurvey_gate(HITL)
  → 选"复勘"：回到 wait_survey（第 2 轮）→ assess → issue_list → resurvey_gate
  → 选"结束"：END
```
验收要点：
- [ ] HITL ChoiceCard/FilePicker 出现在页面**顶部**（置顶而非底部）
- [ ] assess 完成后 SDUI 展示五值评估看板（NumberCard × 5）
- [ ] issue_list 完成后 SDUI 展示问题清单 Table（前 10 条 + 总数）
- [ ] 多轮复勘：第 2 轮 wait_survey 显示「第 2 轮勘测」提示
- [ ] method_split：有客户反馈条目时 Alert(tone="info") 提示

#### intent: `report_gen`（依赖已有 survey_work 产物）
```
preflight → intent_select(report_gen) → determine_gen(从 project_info 缓存读)
→ [skip filter_build~resurvey_gate] → assess(复评) → issue_list
→ report_gen_run → report_distribute(HITL)
```
验收要点：
- [ ] assert 能从 Output/ glob 找到上一轮 survey_work 生成的全量勘测结果表
- [ ] report_gen_run 生成工勘报告.docx（含 9 个 Table）
- [ ] SDUI 展示四件套 ArtifactGrid（4 个文件，状态 ready）
- [ ] report_distribute HITL 显示发送选项

#### intent: `supplement`（依赖已有 survey_work 产物 + 追加条目）
```
preflight → intent_select(supplement) → determine_gen
→ [skip filter_build/method_split] → data_append(HITL 必选追加)
→ confirm_table → wait_survey → assess → issue_list → resurvey_gate
```
验收要点：
- [ ] supplement_run 正确追加新条目到已有全量勘测结果表

#### 边界情况测试
- [ ] BOQ 不存在：determine_gen 触发 HITL ChoiceCard 手动选择代际制冷
- [ ] 模板文件缺失：preflight 报告缺失，metric 中 `template_ok=False`
- [ ] 多次 resume 后 project 状态保持正确（intent 不被清空）
- [ ] confirm_table 选 redo 后 table_confirmed 清除，data_append_choice 清除，generation_cooling 保留

### 1.4 SDUI 视觉验收清单（对照 gongkan_workbench.html 参考设计）

HTML 参考设计的信息布局（将用 SDUI 组件对应实现）：

| HTML 元素 | SDUI 对应实现 | 当前状态 |
|-----------|-------------|---------|
| 顶部 Steps bar（横向） | Stepper（vertical 改 horizontal？） | ⚠️ 当前 vertical |
| Metric cards grid（5个KPI） | NumberCard × 5（Row 布局） | ❌ 未实现 |
| 满足度评估分布 Pie chart | DonutChart（满足/不满足/不涉及） | ⚠️ 已有 BarChart，补 DonutChart |
| 不满足项按分类统计 Bar chart | BarChart（按 category 统计） | ❌ 未按 category 分 |
| Artifact section（2×2 Grid） | ArtifactGrid × 4 | ❌ 未实现为四件套 |
| Alert bar（warning/error） | Alert nodes | ✅ 已实现 |
| Exec log（可折叠） | SduiMarkdownNode（code block） | ⚠️ 用 summary_card 降级 |
| 右侧数据面板 · 填写率 Donut | DonutChart（等待/已填写） | ❌ 未实现 |
| 右侧 · Distribution bars | BarChart（按 step 分布） | ❌ 未实现 |
| 右侧 · Timeline 事件流 | Timeline node | ❌ 未实现 |

**Note**：SDUI 是单列 Stack，不是双栏布局。右侧面板内容需要折叠进「数据面板」Card 或放在主栏底部。可以用 Row 节点实现左右双栏（DonutChart flex=1 + BarChart flex=2）。

### 1.5 survey-agent.tsx SKILL_META 更新

```typescript
// 当前（v3，错误）:
steps: [
  { key: 'scene_filter',  name: '场景筛选', sub: '制冷·底表' },   // v3，已删
  { key: 'survey_build',  name: '勘测汇总', sub: '填写率' },        // v3，已删
  { key: 'report_gen',    name: '评估报告', sub: '风险·评估' },     // v3，已删
  { key: 'report_distribute', name: '审批分发', sub: '邮件·包' },
],

// 应改为（v4，4 个意图入口）:
steps: [
  { key: 'scene_suggest', name: '场景建议',  sub: '快速生成勘测清单' },
  { key: 'survey_work',   name: '勘测作业',  sub: '完整流程（主入口）' },
  { key: 'supplement',    name: '补充勘测',  sub: '追加条目或复勘' },
  { key: 'report_gen',    name: '生成报告',  sub: '输出正式工勘报告' },
],
files: [
  { name: '入场评估标准表.xlsx',       ext: 'xlsx' },
  { name: 'BOQ.xlsx',                  ext: 'xlsx' },
  { name: '新版项目工勘报告模板.docx', ext: 'docx', optional: true },
],
```

### 1.6 Step 1 验收标准

- [ ] 4 个意图全部跑通 happy path
- [ ] 多轮复勘循环正确（at least 2 rounds）
- [ ] SDUI 视觉：五值看板、问题清单 Table、四件套 ArtifactGrid 全部渲染
- [ ] HITL 置顶（用户无需滚动就能看到操作区）
- [ ] 所有 6 个 lint 守门全绿
- [ ] `npm run build` 前端构建无 ts error

---

## Step 2 · 数据中心接口集成

### 2.1 与同事对齐的问题清单（接口调试完成前需确认）

在同事完成 DC API 调试之前，需要明确以下内容：

| 问题 | 说明 |
|------|------|
| **认证方式** | Token 还是 API Key？是否需要 session？ |
| **文件上传** | 上传后返回什么？file_id? URL? |
| **文件下载** | 按 file_id 下载？还是按路径？ |
| **模板文件** | DC 上有统一模板库？还是每个项目独立？ |
| **项目元数据** | 能否通过 activity_id 查询项目信息（项目名/机房名/人员）？ |
| **勘测结果存储** | 结果表需要推送到 DC？还是只本地保存？ |
| **权限范围** | 哪些操作需要鉴权，哪些是公开的？ |

### 2.2 集成架构设计（推荐混合方案）

不替换本地 IO 层，而是在其上增加 DC 同步层：

```
当前架构（本地）：
  步骤 → path_config → 本地文件

目标架构（混合）：
  步骤 → path_config → 本地文件
                     ↕ 同步
               DC API Client
                     ↕
              数据中心文件存储
```

具体同步点：

```
preflight 预检：
  → 若本地 Template/ 无底表，从 DC 拉取（活动 ID → 模板版本）
  → 若本地 Input/ 无 BOQ，从 DC 拉取（活动 ID → 项目 BOQ）

filter_build / report_gen_run（产物生成后）：
  → 自动将产物推送到 DC（关联 activity_id）

wait_survey（上传勘测结果）：
  → 支持：① 前端直接上传文件（现有）② 从 DC 下载已有结果（新增）

远近一体化人员信息：
  → 通过 DC API 按 activity_id 查询，不再需要本地文件
```

### 2.3 需要新增/修改的文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `agent/skills/zhgk/services/dc_client.py` | **新增** | DC API 封装（auth + upload + download + metadata query） |
| `agent/skills/zhgk/steps/preflight.py` | **修改** | 预检时尝试从 DC 拉取模板文件 |
| `agent/skills/zhgk/steps/wait_survey.py` | **修改** | 支持从 DC 加载已有勘测结果 |
| `agent/skills/zhgk/steps/filter_build.py` | **修改** | 产物生成后推送 DC |
| `agent/skills/zhgk/steps/report_gen_run.py` | **修改** | 四件套产物推送 DC |
| `agent/zhgk_files.py` | **重写** | v4 路径 + DC 上传/下载路由 |
| `agent/.env` | **配置** | 加入 DC_API_BASE_URL / DC_API_TOKEN 等 |

### 2.4 dc_client.py 接口设计草案

```python
# agent/skills/zhgk/services/dc_client.py
class DCClient:
    """数据中心 API 封装（具体实现等同事接口文档确认后填充）"""

    def __init__(self, base_url: str, token: str): ...

    # 文件操作
    async def upload_file(self, activity_id: str, file_path: Path, category: str) -> str:
        """上传文件，返回 file_id"""

    async def download_file(self, file_id: str, dest_path: Path) -> None:
        """按 file_id 下载到本地"""

    # 模板/预置
    async def get_template(self, template_name: str, dest_path: Path) -> bool:
        """从 DC 拉取模板文件，返回是否成功（不存在时 False 而非抛异常）"""

    # 项目元数据
    async def get_project_meta(self, activity_id: str) -> dict:
        """按活动 ID 查项目信息（项目名/机房名/工程师/联系人等）"""

    async def get_personnel(self, activity_id: str) -> dict:
        """获取远近一体化人员信息（替代本地 Excel 文件）"""
```

### 2.5 集成原则

- **降级策略**：DC 请求失败不阻断本地流程，记录警告即可（`emit("[warn] DC同步失败，使用本地文件")`）
- **缓存优先**：本地 Template/ 有文件则优先使用，不每次拉取
- **不破坏现有 HITL**：文件型 HITL 仍然支持本地上传，DC 只是额外来源
- **禁裸 HTTP**：DC 调用走 `dc_client.py` 统一入口，不在 step 里直接 `httpx.post`

### 2.6 Step 2 验收标准

- [ ] preflight 能从 DC 拉取底表（activity_id 对应有模板时）
- [ ] BOQ 能从 DC 加载（不需要本地手动放置）
- [ ] 四件套产物生成后自动推送到 DC
- [ ] DC 不可用时流程能 fallback 到本地（不报错阻断）
- [ ] 人员信息从 DC API 获取（不再依赖本地 xlsx）

---

## Step 3 · 服务侧部署与测试

### 3.1 部署环境清单

```
服务器需求：
  CPU：4 核+（LLM 调用密集）
  内存：8GB+（多并发 LangGraph 运行时）
  磁盘：50GB+（ProjectData 产物存储）
  Python：3.11+
  Node.js：18+（前端构建用，构建后可卸载）
  nginx：1.18+
```

### 3.2 后端部署步骤

```bash
# 1. 代码同步
git clone <repo> /app/aida
cd /app/aida
git checkout feat/merge-delivery-frontend   # 或 main（合并后）

# 2. Python 环境
cd /app/aida/agent
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. 环境变量（关键）
cat > /app/aida/agent/.env << 'EOF'
ZHIPU_API_KEY=<生产 key>
ZHGK_ROOT=/data/zhgk-workspace
LANGFUSE_PUBLIC_KEY=<可选>
LANGFUSE_SECRET_KEY=<可选>
DC_API_BASE_URL=<数据中心接口地址>   # Step 2 完成后加
DC_API_TOKEN=<认证 token>            # Step 2 完成后加
EOF

# 4. 工作区初始化
mkdir -p /data/zhgk-workspace/ProjectData/{Template,Input,Output,RunTime,Images}
# 将三个模板文件放入 Template/

# 5. 启动（注意：SSE 要求 workers=1，不能 --workers 4）
.venv/bin/uvicorn agent.main:app \
  --host 127.0.0.1 \
  --port 7401 \
  --workers 1 \
  --log-level info
```

### 3.3 前端构建与部署

```bash
cd /app/aida/frontend
npm ci
npm run build
# dist/ 目录由 nginx 托管
```

### 3.4 nginx 配置（关键：SSE 必须正确配置）

```nginx
# /etc/nginx/sites-available/aida
server {
    listen 443 ssl;
    server_name aida.your-domain.com;

    # 前端静态资源
    root /app/aida/frontend/dist;
    index index.html;
    try_files $uri $uri/ /index.html;

    # 后端 API 代理
    location /agent/ {
        proxy_pass http://127.0.0.1:7401;

        # ⚠️ SSE 关键配置：必须禁用 buffering + 长超时
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;

        # ⚠️ SSE 必须 HTTP/1.1（HTTP/2 有分块传输差异）
        proxy_http_version 1.1;
        proxy_set_header Connection '';

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 文件上传大小限制
    client_max_body_size 100m;
}
```

**最常见的 SSE 部署问题**：

| 现象 | 原因 | 解决 |
|------|------|------|
| 流没有实时到达，一次性收到所有事件 | `proxy_buffering on`（默认值） | 加 `proxy_buffering off` |
| 连接超时（约 60s 断开） | `proxy_read_timeout` 太短 | 改为 300s |
| HTTP/2 环境下流不工作 | 协议差异 | `proxy_http_version 1.1` |
| 文件上传 413 | nginx 限制 | `client_max_body_size 100m` |

### 3.5 服务侧测试清单

**基础联通性**：
- [ ] `GET /agent/skills` → 返回 zhgk/guihua/xtsj 三个 skill 元数据
- [ ] `POST /agent/zhgk/start` → 返回 `run_id`
- [ ] `GET /agent/zhgk/stream/{run_id}` → SSE 事件实时到达（不是一次性批量）

**SDUI 渲染**：
- [ ] 前端 `/module/survey` → 显示 IdleScreen（v4 意图入口）
- [ ] 点击启动 → Stepper 更新，进度实时刷新

**HITL 交互**：
- [ ] FilePicker 上传 → `/upload/batch` → `/resume` → 流程继续
- [ ] ChoiceCard 选择 → `/resume` → 流程继续

**完整作业流程**（survey_work 意图，使用真实底表）：
- [ ] 从启动到生成工勘报告.docx 全流程跑通
- [ ] 产物可从 ArtifactGrid 下载

**DC 集成（Step 2 完成后）**：
- [ ] 模板文件从 DC 自动拉取（不需要手动放置到服务器）
- [ ] 产物自动推送到 DC

### 3.6 进程管理（systemd）

```ini
# /etc/systemd/system/aida.service
[Unit]
Description=AIDA Agent Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/app/aida
ExecStart=/app/aida/agent/.venv/bin/uvicorn agent.main:app \
          --host 127.0.0.1 --port 7401 --workers 1 --log-level info
Restart=always
RestartSec=5
Environment=PYTHONPATH=/app/aida

[Install]
WantedBy=multi-user.target
```

---

## Step 4 · 文档完善与开发者地图

> 目标：下一个业务场景 Skill（不论是 guihua/xtsj 完善还是新模块）的开发者，
> 仅凭文档就能在 30 分钟内搭起骨架、理解架构决策、避开历史踩过的坑。

### 4.1 需要更新的现有文档

| 文档 | 问题 | 需要改什么 |
|------|------|---------|
| `agent/docs/START_HERE.md` | 架构图显示 v3 zhgk（4步线性）| 改为 v4 意图驱动模块图 |
| `agent/docs/SDUI.md §3.3` | metrics 表是 v3 step keys | 替换为 v4 全量 metrics 契约表（见 HANDOFF.md §三） |
| `agent/docs/SKILL-DEVELOPMENT.md` | 无 v4 意图驱动模式说明 | 新增 §11「多意图路由：线性 intent-guard vs dispatch_mode 选型指南」 |
| `agent/docs/AGENT_QUICKSTART.md` | 无 IdleScreen SKILL_META 说明 | 在「碰这些文件」表第 7 条后加：`survey-agent.tsx SKILL_META` + `file_handler` 接口契约 |
| `AGENTS.md` 碰文件表 | main.py 那条「⚠️ 确认/泛化」语义不清 | 改为「✅ 不需要改，注册后自动得到 8 个端点」 |

### 4.2 需要新增的文档

#### A. `agent/docs/DC-INTEGRATION.md`（Step 2 完成后）

```markdown
# 数据中心接口集成指南

## 集成架构（混合方案）
## dc_client.py API 参考
## 环境变量配置
## 降级策略（DC 不可用时的 fallback）
## 为其他模块接入 DC（复用 dc_client）
```

#### B. `agent/docs/DEPLOYMENT.md`（Step 3 完成后）

```markdown
# 服务侧部署手册

## 环境要求
## 后端部署（uvicorn + systemd）
## 前端构建与 nginx
## nginx SSE 关键配置（最常见的踩坑点）
## 工作区初始化
## 健康检查与监控
## 常见问题排查
```

#### C. `agent/docs/SDUI-COMPONENTS.md`（从 zhgk 实现提炼）

```markdown
# SDUI 组件使用手册（面向业务场景 Skill 开发者）

## 1. 意图感知 Stepper（intent-guard 配合 sdui.py 使用）
## 2. 五值评估看板（NumberCard × 5 的标准布局）
## 3. 问题清单 Table（带分页注记的标准写法）
## 4. 四件套 ArtifactGrid（关联 artifact 的 ArtifactGridNode）
## 5. 带上下文的 HITL 卡（confirm_table/resurvey_gate 模式）
## 6. Timeline（执行日志展示）
## 7. DonutChart + BarChart 组合（满足度分布）
## 所有组件的：数据来源（metrics key）+ 最小示例代码
```

#### D. SDUI.md §3.3 v4 完整 metrics 契约表

```markdown
## v4 各 step 写入 metrics 的键（投影器可读范围）

| step | metrics 键 | 写入时机 | 投影器用途 |
|------|-----------|---------|-----------|
| preflight | ai_summary, template_ok, boq_found, llm_ok | run 结束 | summary card |
| intent_select | intent（写 project，非 metrics） | resume 时 | stepper 过滤 |
| determine_gen | generation_cooling, gen_cooling_source | run 结束 | KPI 行 |
| filter_build | filtered_count, sub_scenes[], total_items | run 结束 | NumberCards, Table |
| method_split | method_groups{}, customer_feedback_count | run 结束 | Alert（客反提示）|
| data_append | data_append_choice, appended_count | run 结束 | KPI 补充 |
| assess | assessment_count_{满足,不满足,不涉及,未勘测,无法识别}, assessment_rows | run 结束 | 五值看板 |
| issue_list | issue_count, issue_rows[{描述,建议,状态}] | run 结束 | 问题清单 Table |
| risk_engine（in report_gen_run）| risk_hit, risks[{level,title,trigger}] | run 结束 | 风险告警表 |
| report_gen_run | report_path, triggered_risks | run 结束 | ArtifactGrid |
| report_distribute | recipients, email_sent | run 结束 | 分发摘要 |
```

### 4.3 更新 AGENTS.md 「碰这些文件」表

在现有 8 行基础上，补充当前遗漏的两项：

| # | 文件 | 改什么 | 必/可选 |
|---|------|--------|---------|
| 7b | `frontend/src/components/screens/survey-agent.tsx` | `SKILL_META` 加新模块图标+步骤预览+文件列表 | 可选（不加则 IdleScreen 用通用样式） |
| 7c | `agent/<name>_files.py` 或 `agent/skills/<name>/files.py` | 文件型 HITL handler：实现 `infer_upload_kind / save_upload / check_need_files / check_project_files`；在 skill.py 设 `file_handler=<module>` | 必（有文件上传时） |

### 4.4 Step 4 验收标准

- [ ] 一个没有参与本轮开发的同事，按新文档能在 30 分钟内搭起新模块骨架
- [ ] SDUI.md §3.3 与 v4 代码实际 metrics 100% 对应（无过时条目）
- [ ] START_HERE.md 模块图反映 v4 架构
- [ ] DC 集成指南覆盖「DC 不可用降级」场景
- [ ] 部署手册覆盖 SSE nginx 配置（含踩坑记录）

---

## 附录 A · 各步骤依赖关系图

```
Step 1 本地调优
    │
    ├── 前置①：另一个会话完成 SDUI 改动（Phase 7+8）
    ├── 前置②：三个模板文件放置
    └── 前置③：zhgk_files.py v4 迁移（阻断级 bug 修复）

Step 2 DC 集成
    │
    ├── 前置①：Step 1 完成（本地流程稳定后再对接外部系统）
    ├── 前置②：同事完成 DC API 调试 + 提供接口文档
    └── 可与 Step 1 调试阶段后期并行（dc_client.py 设计可提前）

Step 3 服务部署
    │
    ├── 前置①：Step 1 完成
    └── 前置②：Step 2 完成（DC 集成后部署更有意义）

Step 4 文档
    ├── 部分可在 Step 1 完成后立即开始（SDUI 组件手册、metrics 表更新）
    └── DC 集成指南、部署手册等待对应步骤完成后补充
```

---

## 附录 B · 已知 Blockers 追踪

| Blocker | 严重度 | 等待方 | 解除条件 |
|---------|--------|--------|---------|
| `zhgk_files.py` v3 路径 | 🔴 阻断 | 本团队 | Step 1 开始前修复 |
| 三个模板文件缺失 | 🔴 阻断 | 人工操作 | 手动放置到 Template/ |
| 另一个会话 SDUI 改动 | 🟡 待完成 | 另一会话 | Phase 7+8 完成 |
| DC API 接口文档 | 🟡 等待 | 数据中心同事 | 调试完成后提供 |
| 服务器环境准备 | 🟡 待确认 | 运维/团队 | Step 3 启动前确认 |

---

## 文档治理 backlog（与 zhgk 上线正交 · 单独推进）

> 真相源 = `AGENTS.md` + `docs/` 框架；以下为派生制品 / 历史文档待按真相源对齐项。

| 待办 | 说明 | 状态 |
|------|------|------|
| portal 按 START_HERE/AGENTS 对齐（蓝本 [`PORTAL_REDESIGN_PROPOSAL.md`](PORTAL_REDESIGN_PROPOSAL.md)） | `docs/onboarding/portal.json`：① 模块开发者门升级到 START_HERE §4 编译流水线 5 步模型（业务逻辑→编译执行支线‖呈现支线→跑通→注册 + 角色 + 运行时真身 + 🟡🔴 现状 + 组件管家通道）；② step② 措辞改为 §2 抽象口径（实例→抽象骨架）；③ 全门路径/术语适配到新结构（参考内网迭代版 `aida迭代/aida/docs/skill2langgraph` 及其 portal.json，但套我们的新路径/术语）；改后跑 `gen_team_portal.py` 重生成 | ⏳ 待办 |

---

*本文档由 Claude Sonnet 4.6 生成，2026-06-07*  
*更新责任人：完成每个 Step 后，在对应小节补充实际情况和遗留问题*
