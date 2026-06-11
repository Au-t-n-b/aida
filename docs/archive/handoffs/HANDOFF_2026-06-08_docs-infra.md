# 交接 · 文档基础设施会话（2026-06-08）

> 给**下一个 agent** 冷启接手用。本会话围绕「**文档可信化**」：建派生+守门的 HTML 资产、补/对齐接入规范、产出文档健康诊断、启动 P0① 整改。**所有改动已提交**（分支 `feat/merge-delivery-frontend`）。
> 上一任务（zhgk v4 迁移）的交接是 [`HANDOFF.md`](HANDOFF.md)，与本文无关但可参考。

---

## 0. 一句话现状
派生+守门已从「契约层」延伸到「HTML 资产层」与「文档站」；接入规范已对齐当前实现；产出了 `docs/architecture/03_doc_health_diagnosis.md`（**这是路线图，先读它 §6**）；P0① 第一刀已落（去手抄枚举）。**下一步信噪比最高 = 刷新 `样板盘点` 的陈旧 5-step 叙事（实为 15-step）**。

---

## 1. 冷启必读 · 环境与坐标
- **仓库**：`D:\aida`　**分支**：`feat/merge-delivery-frontend`
- **后端 venv**：`agent/.venv/Scripts/python.exe`（Python **3.10.9**；CI 用 3.11——纯 stdlib 生成器不受影响）
- **核心哲学**：单一真相 + lint 守门（「派生而非手抄，改了不同步即 CI 红」）。任何"枚举代码事实"的文档都要么指向源、要么被 lint 守。
- ⚠️ **有外部进程在异步提交**（疑似 Stop 钩子或并行会话）：commit 会带合理中文消息凭空出现（本会话 `44c0c76`/`1986cd8`/`660a6ed` 都是它提的）。**别和它打架**——动手前后都 `git log`/`status` 核一遍。
- ⚠️ **别误纳垃圾**：工作树常驻 `0605-linux*`、`*.json`（`openapi_resume*`/`run_status`/`sdui_output`/`sdui_report_gen`）是 pre-existing，**不是你的**。一律**显式路径** `git add`，绝不 `git add -A/.`。

---

## 2. 本会话已交付（全部已提交）

| Commit | 内容 |
|--------|------|
| `e6d6e03` | feat(sdui)：`gen_sdui_gallery.py` 内省 builder.py → 派生 `agent/docs/sdui-gallery.html`（26 节点契约目录）+ `lint_sdui_gallery.py` 新鲜度守门 + `.gitattributes` 锁 LF；SDUI.md 删手抄节点表→指向画廊 |
| `1168c8a` | feat(docs)：`gen_docs_site.py` 扫 docs/+agent/docs/ MD → 派生**单文件文档站** `docs/site/index.html`（markdown-it+mermaid，双击即开）+ `lint_docs_site.py`；mermaid.min.js(3.3MB) gitignore |
| `562385f` | docs：补 `agent/docs/接入/` 两份接入规范 + `docs/数据中心对外接口设计.md`；**两份接入规范对齐当前实现**（见 §5） |
| `660a6ed` | docs：`AGENT_QUICKSTART §6` 去陈旧 lint 表→指向 AGENTS.md；新增 `docs/architecture/03_doc_health_diagnosis.md`（文档健康诊断） |
| `3f36e6c` | docs：P0① 收尾——README/诊断的「6/8 个 lint」去数字化 |

> CI（`.github/workflows/ci.yml`）已接两个新守门 step（sdui-gallery / docs-site 新鲜度）。AGENTS.md 守门清单与命令速查已同步。

---

## 3. 新基础设施 · 怎么用（**黄金规则**）

```bash
# 改了 builder.py（SDUI 契约）→ 必须重生成画廊，否则 lint_sdui_gallery 红
agent/.venv/Scripts/python.exe agent/scripts/gen_sdui_gallery.py
# 改了任何 docs/ 或 agent/docs/ 的 .md（含新增文档）→ 必须重生成文档站，否则 lint_docs_site 红
agent/.venv/Scripts/python.exe agent/scripts/gen_docs_site.py
# 提交前守门（完整清单见 AGENTS.md，须在 venv 下跑否则契约 lint 显 SKIP）
agent/.venv/Scripts/python.exe agent/scripts/lint_sdui_gallery.py
agent/.venv/Scripts/python.exe agent/scripts/lint_docs_site.py
```

- **生成器都是纯 stdlib + 确定性输出**（同源→同字节，供 lint diff）；改它们后注意保持确定性（无时间戳、归一行尾）。
- **mermaid 图**：`docs/site/assets/mermaid.min.js`(3.3MB) 默认 gitignore，缺则降级为源码块。本地要看图跑 `.gitignore` 里那行 `curl`（从 jsdelivr 拉）。
- **`⏳目标态` 约定**（本会话引入）：文档里非现状内容必须标 `⏳目标态/占位/废弃`，**未标=承诺现状**。下一个 agent 写文档请遵守。

---

## 4. 关键文档落点
- **路线图**：[`docs/architecture/03_doc_health_diagnosis.md`](docs/architecture/03_doc_health_diagnosis.md) —— 文档健康诊断，**§6 是 6 项整改清单（P0–P2）**，§7 是 4 条团队约定。**接手先读这篇。**（它是**时点快照**，证据会过期，判断/建议是耐用部分。）
- **接入规范**：[`agent/docs/接入/`](agent/docs/接入/) —— 执行面（Skill/LangGraph）+ 界面面（SDUI）两份。已对齐当前实现，`⏳目标态` 标出同事写的、尚未实装的系统设计相设计。
- **数据中心 API**：[`docs/数据中心对外接口设计.md`](docs/数据中心对外接口设计.md) —— 原样落仓，**待后续**：SKILL 执行要调它、还需定义数据规范（用户明确说"后面再调整"）。

---

## 5. 当前实现的关键事实（**别再手抄，要用就指向源**）
- **SDUI 节点 = 26 类**（`agent/sdui/builder.py::SduiNode` union；看 `sdui-gallery.html`）。**无 `Tabs`/`Collapsible`**（曾被误列）。仓内历史错值：22/24/25。
- **技能 = 3 个**（`agent/skills/__init__.py` registry）：`zhgk`(线性 DAG·**15 step**·意图驱动) / `guihua`(线性·5 step) / `xtsj`(**dispatch_mode PoC**·2 命令 `input_check`/`address_plan`)。
- xtsj **没有**：page 分派 / `/agent/{skill}/page` 端点 / `project.page` / `dump_node_json` / LLM `intent.py`（这些在接入规范里都标了 `⏳目标态`）。xtsj 命令归一化用 `skill.py` 的简单 dict `SD_TO_COMMAND`。
- **lint 脚本 = 9 个**（`agent/scripts/lint_*.py`）；提交守门清单以 AGENTS.md / ci.yml 为准。
- **SSE 事件**：snapshot / sdui(主数据源) / node_update / done / error / close / heartbeat。
- base.py 钩子：`dispatch_mode`/`default_command`/`sdui_projector`/`step_retry_keys`/`file_handler`/`initial_project`/`apply_resume_payload`/`build_graph`。

---

## 6. 待办（按信噪比/优先级）

1. **【最高·内容漂移】刷新 `docs/样板盘点_智慧工勘zhgk.md`**：它描述 zhgk **已废弃的 5-step 老流水线**（preflight→scene_filter→survey_build→report_gen→report_distribute），**实为 15-step**（见 `skills/zhgk/skill.py`，`HANDOFF.md` 亦证实 v4=15 step）。这是整篇叙事陈旧（非单个枚举），需内容重写为 15-step 或改指向 `skills/zhgk/SKILL.md`。该文在开发者地图标"**复制新模块前必读·基线**"，陈旧基线危害高。
2. **【P0②】可信度标注 lint**（诊断 §6 #2）：新增 `agent/scripts/lint_doc_status.py`，扫"声称现状但锚点代码不存在"（如规范里的 `dump_node_json`/`/page`）。配合 `⏳目标态` 约定。
3. **【P1】消灭双源 SKILL.md**（#4）：仓库 `skills/` **4 份** vs 运行时 `~/.claude/skills/` **3 份**（已失同步）。部署缺的那份，或落实 `skill_md_path` 统一指向仓库内 + CI diff 守门。
4. **【P1】状态自动化**（#3）：`gen_status.py` 从 registry+git 派生状态看板，替掉手打的"状态速览/完成度/日期"（开发者地图 §7 等）。
5. **【P2】文档站补强**（#5）：① 文档间 MD 链接改写为 `#doc-N` hash 路由（现在 SPA 里点不动）；② 排除 `docs/ux/品牌与草图/归档/` 碎屑；③ 每篇显示 git 最后修改时间（新鲜度红绿灯）；④ 首页放 #4 状态看板。
6. **【P2】占位治理**（#6）：~20/47 文档带占位标记，移入 `docs/_wip/` 或加 badge。
7. **【更早的线头·可选】**：`design-preview/index.html`（手写 SDUI 设计系统，含 24/26 陈旧枚举）重定位为纯视觉提案；layer-2 真 React `/sdui-gallery` 路由（渲染真 `SduiNodeView`）；**会话最初被打断的 guihua↔xtsj 端到端打通分析**（一直没回去做）。

---

## 7. 工具/环境踩坑（省下一个 agent 的时间）
- **autocrlf=true**：守门 lint 都归一行尾（`\r\n`→`\n`）；`.gitattributes` 把生成的 HTML 锁 LF。改生成器/lint 时保持这点。
- **Kroki 被墙**：`kroki.io` 在本环境不可达（试过把 mermaid 预渲染 SVG，走不通）；`jsdelivr` 可达（vendoring 用它）。
- **Edit 工具对 `\uXXXX` 转义会卡**（它会同时尝试字面量和真字符，都不中）：遇到含 `\u` 的 old_string 改用 **Write 整文件重写**。
- **Bash cwd 跨调用持久**：一个 `cd` 会留到下次调用——**统一用绝对路径**（`/d/aida/...`），别依赖相对路径。
- **预览截图工具在本机 DPI 上不稳**（过放大/过缩小/超时）：核渲染改用 `preview_eval` 读 DOM（数 mermaid SVG / 表格 / 控制台错误），比截图可靠。
- **控制台 GBK 乱码**：`python -c` 打印中文在 Windows 控制台乱码，**数据本身没问题**，是显示问题。

---

## 8. 用户记忆（已持久化，跨会话可用）
- `aida_html_assets.md`：HTML 落仓决策框架（稳定叙述可手写 deck；活契约必须派生+守门；记录了 gen_sdui_gallery/gen_docs_site 与 design-preview 的关系）。

---

## 9. 给下一个 agent 的第一步建议
读 `docs/architecture/03_doc_health_diagnosis.md` → 然后做 §6 #1（刷新样板盘点 5→15 step）。这是当前最高信噪比、且能立刻验证（对 `skills/zhgk/skill.py` 核 step 列表，重生成文档站，`lint_docs_site` 绿）。
