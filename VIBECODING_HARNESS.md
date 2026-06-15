# 团队 Vibecoding Harness · 设计与施工单一真相

> **状态**：设计已定向（4 个关键分叉已拍板，见 §5）/ 施工进行中。本文件是这整个 program 的**单一真相 + 决策记录(ADR) + 施工序(WORKPLAN)**，P0–P3 全部挂在它下面。
> **为什么放仓库根**：`gen_docs_site.py` 用 `rglob("*.md")` 扫 `docs/` 全树，本文若放进 `docs/` 会让 `docs/site/index.html` 过期、`lint_docs_site` 变红。放根目录则三个派生守门都不扫，零副作用（沿用 `PORTAL_REDESIGN_PROPOSAL.md` 同款做法）。
> **定稿后**：可迁入 `docs/90_决策ADR/` 归档。

---

## 1. 为什么要 harness（背景 · 根因）

几十人团队、全员 vibe coding。效率提升的代价 = **不感知 + 少约束**。需要一套 harness 让「快速前进的马跑在正确的路上」。

根因模型（前序分析）：
```
问题烈度 ≈ 合并速度 × AI 解冲突的非确定性 × 共享单一真相文件 + 派生制品的数量(本仓特别多)
```
「更勤同步」是治标，会喂养病（同步越勤 → CI 越堵 → 越想攒大合并 → 回根因）。真正的杠杆是**削乘数**：消冲突面、给 AI 解冲突上护栏、把质量门从「自觉」升到「强制」。

## 2. 已有资产（你已经有 ~70%）

| 资产 | 现状 | 在 harness 里的角色 |
|---|---|---|
| 团队门户 `portal.json → portal.html`（三道门）+ `PORTAL_REDESIGN_PROPOSAL.md`（产出导向里程碑 + 触发式深读 + 喂 agent 最小料+提示词） | 较成熟，覆盖「模块开发者门·建 skill」 | **支柱③ 交付面**的种子 |
| `02_module_boundaries.md`（模块清单/依赖矩阵/高冲突登记/红线区/运行时数据边界）+ `lint_module_boundaries` | 较成熟，但偏**空间** | **支柱①②**的种子 |
| 10 个守门 lint + 3 个生成器 + CI(`ci.yml`) + 本仓刚加的 git 钩子（pre-commit 自动 regen / post-merge / merge=ours） | 守门齐全但分散，强制层站错机器 | 治理底座 |

## 3. 核心模型

### 3.1 两种「定界」（整个设计的钥匙）
| | 空间定界（哪个文件属于谁） | 时间定界（此刻谁在动什么、并发怎么和解） |
|---|---|---|
| 现状 | ✅ 较成熟：NEW/MODIFY/红线、依赖矩阵、零横向依赖、运行时目录物理隔离、`lint_module_boundaries` | 🔴 几乎空白：全靠「架构师统一合并」把并发串行化到一个人 |

> 心智模型：**你们造了很好的「地图」(谁的地盘在哪)，但没有「红绿灯」(此刻谁过路口、怎么不撞)。20 人 vibe 撞的全是路口。**

### 3.2 四层正交治理（区分易混概念）
```
① 规范层(WHAT)  ──►  ② 守门层(查·lint)  ──►  ③ 触发层(WHEN·钩子/CI/手动)
                          │ 不过+可自动修
                          ▼
                     ④ 生成层(FIX·gen_*)
```
守门「查什么」⊥ 触发「何时跑」。守门分四类：**语义守门**（扫违规·只能拦）/ **契约守门**（两侧一致·只能拦）/ **新鲜度守门**（派生≡源·可 gen 自动修）/ **生成器**（产出，非检查）。

## 4. 目标架构：三支柱

```
支柱① 空间定界·工程消除  ──产出剧本──▶  支柱③ 交付面·场景库(portal)
  · registry 目录自动发现                   · portal: 角色门 × 场景库
  · 前端 map 从 skill 元数据派生              · 每场景=触发+指引+解法
  · 加模块=纯 NEW，零碰共享文件                +给人提示词+给agent提示词+关联守门
  · 架构师不再合并日常模块                     · 最高价值场景=①②产出的边界/合并剧本
支柱② 时间定界·服务端强制网  ───────────────────┘ 装的就是这些剧本
  · 并发感知: CODEOWNERS + 碰红线→RFC 标注守门 + PR 模板
  · 语义安全网: 全套守门(契约+eval live) 落 Gitea 强制层 + 修 fail-open
  · 治理自治: guardians manifest + 自治守门(scripts ≡ ci ≡ docs)
```
**依赖关系**：③ 装的是 ①② 的产出剧本 → ①② 先有机制，③ 才有肉。② 的「强制层落位」不依赖任何重构，**止血优先级最高**。

## 5. 决策记录（ADR · 4 个关键分叉已拍板 2026-06-15）

| # | 分叉 | 决定 | 理由 |
|---|---|---|---|
| **D1** | 3 个高冲突共享文件（registry / 前端 map / schemas） | **工程消除（目录自动发现）** | 把集中式注册 list 改成扫目录自动注册；冲突从根上消失，顺带蒸发架构师大半合并活 |
| **D2** | 「合并不丢特性、保连贯」安全网押在哪 | **语义守门落服务端强制层** | 从人眼审 diff 升级为「契约一致 + eval 不退化」机器验证，落 Gitea pre-receive/Actions（绕不过） |
| **D3** | 架构师瓶颈（Workflow A/B/C 串行统一合并） | **减流经量，架构师只管真架构** | D1 消热点后日常合并自动蒸发；架构师只在碰红线/改真架构时介入 |
| **D4** | 需求① 指引 HTML 怎么落 | **扩展现有 portal → 场景库** | 复用已被治理的 `portal.json→gen→lint` 派生管线，角色门泛化为「角色门 × 场景库」，零另起炉灶 |

> **关键前提更新**：Gitea 仓为团队自建、**有管理权限** → D2 的服务端强制层（P0）**无外部 ops 依赖**，可直接落。

## 6. 施工序（P0–P3）

| 阶段 | 干什么 | 解什么 | owner / 依赖 | 现状 |
|---|---|---|---|---|
| **P0 · 止血** | 全套守门搬上 Gitea 强制层（pre-receive 或 Gitea Actions 跑 `preflight`）+ 修 fail-open + guardians 自治 → **落地清单见 [`P0_GITEA强制层落地清单.md`](P0_GITEA强制层落地清单.md)** | D2 地基 · 断层 B/元 | 仓内脚本 + Gitea 配置（自建仓·可控） | 🔧 **§8.1-2 仓内完成**（`preflight.sh`/`preflight_redlines.sh` + `_guard.py` 堵 4 个 fail-open，strict 已单测）；待你配 Gitea Actions（§8.3-4） |
| **P1 · 消热点** | registry 目录自动发现（后端先）+ 前端 map 从 skill 元数据派生 + 配套守门 | D1 + D3 | 纯仓内代码 | ✅ **P1a 完成**（§7）· P1b/P1c 待做 |
| **P2 · 补感知** | CODEOWNERS + 碰红线文件守门 + PR 模板 | D2 的 B 面（并发感知） | 仓内 + 少量 Gitea 配置 | ☐ |
| **P3 · 交付面** | portal.json 泛化成「角色门 × 场景库」，装 P1/P2 剧本 | D4 · 需求① | 仓内，复用派生管线 | ☐ |

**两条腿并进**：P0（Gitea 强制层，需你操作 Gitea）与 P1（纯仓内代码，我可做）可并行。

## 7. P1 详细设计：registry 目录自动发现

### 7.1 现状（已勘察 · ground truth）
- **后端 `agent/skills/__init__.py`**：`_specs` 手维护列表，6 条，**命名 100% 规则**：`(name, ".{name}.skill:get_{name}_skill")`。已有「单个 skill 导入失败只跳过」的容错。→ **完美的自动发现候选**：扫 `agent/skills/*/skill.py`、找 `get_{dir}_skill` 工厂即注册。是**行为保持的忠实重构**。
- **前端 `data/module-skill-map.ts`** `MODULE_TO_SKILL`：5 条，`module_key → skill_id`，且 **module_key ≠ skill_id**（survey→zhgk）。→ 这层映射是**真实信息**，不能纯自动发现；最佳解 = skill 自声明 `module_key`，后端 `/agent/skills` 暴露，前端派生。
- **前端 `data/modules-data.ts`** `MODULE_SCHEMAS`：290 行，**大部分是 mock 演示内容**（welcome/假 metrics/scenario）；有 skill 的模块走 SDUI，不用这些。注册关键部分仅 name/subtitle/steps。→ 可瘦身/派生，但最乱、价值最低，留最后。

### 7.2 分步（按风险/价值）
- **P1a · 后端自动发现**（首选 · 低风险高价值）：`_register_all()` 改为 `glob("agent/skills/*/skill.py")` → import → `getattr(mod, f"get_{name}_skill")` → register。保留 per-skill try/except 跳过。删 `_specs` 列表。
  - 守门：新增/改造 lint → 校验「每个 `agent/skills/<dir>/skill.py` 有 `get_<dir>_skill` 工厂且 `skill.name == <dir>`」（约定即守门），替代「列表 ≡ 目录」。
  - 影响面：仅此一文件 + 一个 lint；`main.py`/`graph.py` 零改（它们读 registry，不读列表）。
- **P1b · 前端 map 派生**（次之）：skill 元数据加 `module_key` 字段 → `/agent/skills` 暴露 → 构建期/运行期派生 `MODULE_TO_SKILL`。需碰后端 skill 元数据 + 前端取数，单独评估。
- **P1c · MODULE_SCHEMAS 瘦身**（最后）：分离「mock 演示内容」与「真实展示元数据」，后者尽量派生。最乱，独立 PR。

### 7.3 验收
- P1a：`curl /agent/skills` 仍列出全部 6 个 skill（行为保持）；新增一个空 skill 目录能被自动发现；新 lint 绿；`lint_module_boundaries`（注册表↔边界图）仍绿。

## 8. 开放项 / 待确认
- P1a 的守门：是**改造** `lint_module_boundaries`（它本就校验注册表↔边界图）还是**新增**一个约定 lint？倾向改造，避免又多一个守门。
- P0 落地形态：Gitea **pre-receive**（强制、绕不过、需服务器 python/容器）vs Gitea **Actions**（接近现有 ci.yml、较易）——待定。
- `02_module_boundaries.md` §4 已与代码漂移（说 `MODULE_TO_SKILL` 在 `module.tsx`，实际在 `data/module-skill-map.ts`）→ P1 落地时顺手修，并由「治理自治」守门兜底。

---

*— 设计 v1 · 2026-06-15 · 决策见 §5，施工见 §6/§7 —*
