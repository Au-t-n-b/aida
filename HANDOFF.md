# 交接文档 · AIDA 前端 + 建模仿真（2026-06-11）

> 给接手 agent：本文件是本轮多会话工作的交接。先读 `AGENTS.md`（红线/铁律）+ 本文件，再动手。
> 用户偏好：**中文回复** · **先分析后执行**（动手前给影响面/风险/决策点，不可逆操作先确认）。

---

## 0 · 当前整体进度

| 模块 | 状态 |
|---|---|
| 建模仿真（guihua 后端，规划设计前半段） | ✅ 全量实现 + 离线验证通过；**内网真跑待用户验证** |
| 会话框 ClawRail（同事样式包整合） | ✅ 完成 + 注释乱码已修 |
| SDUI 组件样式优化（对齐 v4 设计稿） | 🟡 两轮已做（12+ 节点）；**第三块「zhgk/guihua 页面呈现」未开始** |
| 设备安装模块 | ⏸ 另一会话在做（不属于本线） |
| 系统设计（规划设计后半段，xtsj skill） | ⏸ 未开始 |

**用户最后的指令方向**：SDUI 优化做完两轮后，下一步是 **B｜zhgk/guihua 页面呈现优化**（布局层级/留白/KPI/HITL 卡片呈现），或继续 SDUI 剩余低频节点。**未定，需问用户。**

---

## 1 · 关键环境 / 约定（先记住，避免踩坑）

- **工作目录** `D:\code\aida`，**非 git 仓库**。Windows + PowerShell（Bash 工具也可用）。
- **后端 venv**：`agent/.venv/Scripts/python.exe`。
- **前端**：`cd frontend && npm run typecheck / build / lint:no-ts-nocheck / dev`(5173)。
- **Windows 控制台 GBK**：跑 lint 脚本前加 `PYTHONUTF8=1`，否则 ❌/中文报 UnicodeEncodeError（脚本逻辑没错，是 print 崩）。
- **守门（提交前必跑全绿）**：
  - 后端：`lint_no_naked_llm` · `lint_no_naked_send` · `lint_skill_contract` · `lint_sdui_contract` · `lint_sdui_gallery` · `lint_runtime_contract`（均在 `agent/scripts/`）
  - 前端：`npm run typecheck` · `npm run lint:no-ts-nocheck`（baseline 36，别新增 @ts-nocheck）
  - 改了 `agent/sdui/builder.py` → 必跑 `python agent/scripts/gen_sdui_gallery.py` 重生成 gallery，否则 lint_sdui_gallery 红。
- **SKILL.md 有两份**：`skills/<name>/SKILL.md`（repo）+ `~/.claude/skills/<name>/SKILL.md`（部署副本）。**BaseSkill 运行时和 lint 都优先读 `~/.claude` 副本**——改 SKILL.md 必须两份同步（`cp`）。
- **不要改** `agent/main.py` / `agent/graph.py`（已泛化，注册即得端点）。
- **副作用红线**：禁 subprocess 调脚本规避；外发走唯一出口 + dry-run + 留痕。

---

## 2 · 建模仿真 guihua（已完成，内网待验证）

**位置**：`agent/skills/guihua/`。从占位重构为真实 jmfz 逻辑（移植自 `C:\Users\华为\Desktop\skill\jmfz`）。

**5 个 step**（`steps/`，A 层 SKILL.md「后端节点」列已同步）：
`adapt_build`(设备适配·调仿真API匹配型号/板卡) → `data_confirm`(HITL) → `combo_create`(batchCreateCombo×5) → `cabinet_move`(HITL 刷新门 + batchMoveNodes×162) → `handoff`(HITL 边界·移交设备安装)。

**业务逻辑**：`services/sim_api.py`（仿真 API 统一出口，默认 dry-run + 留痕，已加入 lint_no_naked_send 白名单）· `compat_table.py`（型号/板卡匹配）· `place_api.py`（创建/落位编排）· `fixtures/`（离线样本：device_info.md / compat_table.md / requests_fixture.json / cabinets.json）。

**确认门机制**：3 道 HITL（gate=data/move/handoff），走 `skill.py` 的 `apply_resume_payload` + `confirmations` dict（full_restart 重跑保留），副作用步用 sentinel 文件幂等。

**离线验证**：dry-run 端到端跑通（3 道门→结题，batchCreateCombo 5 次 + batchMoveNodes 162 次各只执行一次，留痕 171 条）。smoke 脚本思路见会话历史（用 `AIDA_CHECKPOINT=memory` + 临时 `GUIHUA_ROOT`，循环 invoke + apply_resume_payload(confirm) 模拟 full_restart）。

**⚠️ 待用户到内网验证**：
- 置 env `SIM_API_LIVE=1` 接 `100.102.191.17:9091`（wapi 网关）+ `:9090`（nVisual Web UI iframe）真跑，业务代码零改。
- 两个**真跑假设**需核对：① 机柜命名 `A01..A18` 补零是否与真实 nVisual 一致（可先只跑 combo_create 看返回）；② batchMoveNodes 用 cabinets.json 中心点坐标是否对位。

详见记忆 `project_guihua_jmfz.md`。

---

## 3 · 会话框 ClawRail（已完成）

同事样式替换包整合（用户选「整体采用同事版」）。已落地：
- 覆盖 `components/claw-rail.tsx`、`components/left-nav-fdy.tsx`，新增 `data/left-nav-items.ts`、`styles/claw-rail.css`（行尾已规范 LF）。
- `main.tsx` 加 `import './styles/claw-rail.css'`（合并，未盲覆盖）。
- `lib/skillRunStore.ts`：`hitlType` 联合类型扩 `'edit'`（同事版前瞻的在线填表 HITL，否则 strict 报错）。
- `claw-rail.tsx`：`onTableSubmit`→`onRowsSubmit`（对齐现有 SduiRuntime 契约名）。
- `claw-rail.css` 的 6 处中文注释乱码（同事双重编码烤死的）已按上下文重写。

验收点：标题「AIDA助手·导航名」、完整时间戳、Enter 发送/Shift+Enter 换行、输入区 +/@/筛选图标。typecheck/build 通过。

---

## 4 · SDUI 组件样式优化（两轮已做，对齐 v4 设计稿）

**参考设计稿**：`docs/30_skill开发/31_手写规范/SDUI 组件库 v4.html`（与 visual-system 同一套 token 的「视觉升级版」）。
**设计真相**：`docs/80_设计UX/DESIGN.md`（**克制浅色企业级控制台**：slate+白面板+indigo 信号色，严格 token，**拒绝霓虹/赛博/渐变堆砌**）。本任务的「distinctive」= 体系内把精度做到极致，不是另搞炫酷风。

**双 token 现实（重要）**：SDUI 渲染器历史上用一套别名 token（`--surface`/`--border`/`--text-secondary`/`--text-xl`/`--zinc-*`/`--blue-600`），globals.css 里别名到 `--c-*`。v4 与 DESIGN.md 用 `--c-*`。**打磨方向 = 凡触碰处收敛到 `--c-*`**。注意 `--text-sm:12px`(别名) vs v4 fs-13、`--text-xl:18px` 等字阶有偏移。

**SDUI 全内联 style**（254 处，几乎 0 className）。加 hover 这类需 :hover 的，用 globals.css 里一条 `.sdui-tbl tbody tr:hover td` 规则 + 给容器加 className（已建此模式）。

**三方契约**（`lint_sdui_contract` 守门）：节点类型必须 builder.py ↔ frontend/src/lib/sdui.ts ↔ SduiNodeView.tsx switch 三处一致。**只改渲染样式不碰节点类型 → 契约不受影响**（本轮如此）。

### 已完成改动

**基座**：globals.css `:root` 加 8 个 v4 token：`--c-brand-active/-softer/-line` · `--fs-15/30` · `--shadow-xs` · `--sp-12` · `--r-xs`。

**第一轮节点**（`components/sdui/SduiNodeView.tsx`）：
- `StatRow`（KPI）：值 mono18 → sans24 tabular-nums + shadow-xs + 圆角色条
- `GoldenMetrics`：修退化（原=StatRow）→ 专属 v4 卡（顶 2px 状态色边 + 状态色值 + ★）；新增 `GoldenMetricsCards` 组件
- `Statistic`：sans24 tabular + 大写 eyebrow
- `ProgressBar`：token 化（track bg-soft、fill/pct 语义色）
- `SduiTable`：shadow-xs + 圆角 + 行 hover（`.sdui-tbl`）+ 数字列自动右对齐 tabular 加粗

**第二轮（amber=进行中 语义 + 节点打磨）**：
- **SduiStepper.tsx（整文件重写）**：done=绿 · running=**琥珀转圈环** · pending=灰 · error=红 · 徽标同步
- `Spinner`：默认琥珀、brand 变体品牌蓝
- `PlaneMatrix`：running 蓝→琥珀
- `Timeline`：warning(=进行中)琥珀 + token 化
- `Alert`：主色 token 化 + 字号 v4
- `NumberCard`：顶部渐变→实色语义条 + 值 mono→sans fs-30 tabular
- `SduiDataTable.tsx`：StatusBadge 进行中蓝→琥珀 · ProgressCell token · 容器 shadow-xs · 只读表行 hover · primaryBtn token

**⚠️ 需用户实机确认**：第二轮把「进行中」从品牌蓝**全局**改为琥珀（Stepper/Spinner/Timeline/PlaneMatrix/DataTable 徽标）——语义切换，让 indigo 只承载「可交互/选中」。用户尚未在 `npm run dev` 验收。若要回退某处，单点改回 `var(--c-brand)` 即可。

**全部验证绿**：typecheck · build · no-ts-nocheck(36) · lint_sdui_contract(60) · lint_sdui_gallery。

---

## 5 · 下一步（待用户定方向）

1. **B｜zhgk/guihua 页面呈现优化**（用户原计划的第三块，未开始）：布局层级 / 留白 / KPI / HITL 卡片在 screens 里的呈现。投影器在 `agent/skills/<name>/sdui.py`，承载在 `frontend/src/components/screens/`（如 `survey-agent.tsx`）。
2. **继续 SDUI 低频节点**：CodeBlock / LogStream / Accordion / RiskList / Tabs / KeyValueList 等仍用别名 token + 硬编码 hex，可继续按 v4 收敛。
3. **建模仿真内网真跑验证**（用户侧，见 §2 两个假设）。

**起手务必**：先问用户走哪个方向 + 是否已在 `npm run dev` 验收了 amber=running 的观感。
