---
name: lld-intent-recognition
description: >-
  Step 0 意图识别（Claw 显式 Read 时）：将 LLD 相关 NL 归一化为标准命令。
  线上快路径见 subskills/SKILL.md Claw 契约；本包无 Python entrypoint，driver 不 subprocess 调用。
disable-model-invocation: true
metadata:
  package: lld_identy_skill/
  taxonomy: intent-taxonomy.md
  aliases: intent-aliases.md
  keywords: intent-keywords.md
  examples: intent-examples.md
  source_reference: ../prompt/lld_intent_classification.py
---
> **Claw 专用 · 仅 MD**：本包**无 Python entrypoint**，driver **不会** subprocess 调用此目录。  
> 按下方 **Read 策略** 读取 intent 资料，输出标准命令后发 `skill_runtime_start`。  
> 编排入口：[subskills/SKILL.md](../SKILL.md) Section B / Claw 契约。

# LLD 意图识别 · Step 0

## Read 策略（控制上下文）

### 跳过 Step 0（不 Read 本目录任何文件）

- 用户输入与 [intent-taxonomy.md](./intent-taxonomy.md) 某条**标准命令精确一致**（大小写不敏感）→ 直接查 [subskills/SKILL.md](../SKILL.md) Section B 发 `skill_runtime_start`
- `ProjectData/RunTime/pipeline_state.json` 有 `pending_command` 且与当前意图一致 → 按 HITL `resumeAction` 续跑

### 首次 NL（本 session 尚未加载 intent MD）

Read 顺序（**仅一次**）：

1. 本 SKILL.md
2. [intent-taxonomy.md](./intent-taxonomy.md)
3. [intent-keywords.md](./intent-keywords.md)

**不读**：[intent-examples.md](./intent-examples.md)（除非进入 CLARIFYING 需举例）  
**不读**：[intent-aliases.md](./intent-aliases.md)（除非 taxonomy/keywords 未命中）

### 同 session 后续轮次

若本会话已 Read 过上述文件 → **禁止重复 Read**，直接复用已有分类规则与 memory。

### aliases 按需

仅当 keywords 匹配失败时，再 Read [intent-aliases.md](./intent-aliases.md)（仍须遵守 session 不重复读）。

---

## 概述

- **输入**：用户自然语言问题（仅此一项）。
- **输出**：一段文本，三选一：
  1. 标准命令字符串（识别成功）
  2. 一句追问话术（多候选竞争）
  3. 固定失败话术（无法识别）
- **职责**：将用户口语归一化为 [intent-taxonomy.md](./intent-taxonomy.md) 中的标准命令，供 [subskills/SKILL.md](../SKILL.md) Section B 路由。
- **不输出**：JSON、state、action、event、hasSubIntents 等内部字段。

## 触发条件

- 用户 NL，且**非** [subskills/SKILL.md](../SKILL.md) Claw 契约中的快路径
- 尚未进入 Step 1/2/3/4 的 runtime 执行

## 前置要求

- 无硬性文件依赖
- 分类词汇表齐全：`intent-taxonomy.md`、`intent-aliases.md`、`intent-keywords.md`

## 执行

### 状态机

```text
INIT
  -> CLASSIFYING
      -> RESOLVED     输出标准命令
      -> CLARIFYING   输出追问话术
      -> FAILED       输出固定失败话术
```

| State | 含义 |
| --- | --- |
| INIT | 接收用户自然语言问题 |
| CLASSIFYING | 精确匹配、别名匹配、关键词匹配、语义近似匹配 |
| RESOLVED | 识别到单一明确命令 |
| CLARIFYING | 存在多个合理候选，需用户补充 |
| FAILED | 无法找到合理分类 |

### 1. INIT — 预处理

- 接收用户自然语言问题。
- 去除无关寒暄（如"帮我""请""让我们执行"）。
- **保留**关键业务动作词：`生成`、`融合`、`检查`、`查询`、`替换`。
- 大小写归一化：匹配时统一转大写比较（如 `mlag` → `MLAG`）。

### 2. CLASSIFYING — 匹配

按以下优先级依次尝试，命中即停止当前层级搜索：

1. **三级分类精准匹配**（完全相等，大小写不敏感）
2. **LLD 特殊规则**（见下方）
3. **二级分类精准匹配**
4. **一级分类精准匹配**
5. **别名匹配**（见 [intent-aliases.md](./intent-aliases.md)）
6. **关键词匹配**（见 [intent-keywords.md](./intent-keywords.md)）
7. **语义近似匹配**（单一高置信候选才输出）

**LLD 特殊规则**：

- 用户输入同时含 `生成` + `LLD` → 输出 `生成完整LLD设计`
- 用户输入同时含 `融合` + `LLD` → 输出 `融合完整LLD设计`
- 单独 `LLD` **不能**匹配 `LLD设计`

**动作词剥离规则**：

- `生成参数面地址规划` → 剥离后为 `参数面地址规划`（二级）
- `生成LLD` → 保留，走 LLD 特殊规则

**关键词匹配**（第 6 步，未命中别名时）：

1. 按 [intent-keywords.md](./intent-keywords.md) 对用户输入做归一化（去寒暄、剥动作词、忽略可选尾缀、同义归一）。
2. 遍历 taxonomy 全部标准命令，用表中「身份关键词」做全包含检测；`{可选}` 词可不出现。
3. 命中多条时取身份关键词总数最多者；仍并列则 CLARIFYING。
4. 用户仅给出「角色 + 平面」、未指明地址/互联/接入时：若仅地址族唯一命中则 RESOLVED；若地址/互联/接入并列命中则 CLARIFYING。
5. 示例：`计算带外管理面` → 归一化含 `计算`、`带外管理`；若上下文无互联/接入词且按消歧规则唯一 → `计算带外管理地址规划`；若三类并列 → 追问地址/互联/接入。

### 3. 结果判定

| 条件 | 状态 | 输出 |
| --- | --- | --- |
| 精准、别名或关键词命中单一命令 | RESOLVED | 标准命令字符串 |
| 语义近似后单一高置信候选 | RESOLVED | 标准命令字符串 |
| 精准命中一级/二级/三级均可 | RESOLVED | 该级标准命令（不强制落到三级） |
| 多个合理候选，无法唯一确定 | CLARIFYING | 一句追问话术 |
| 无任何合理分类 | FAILED | 固定失败话术 |

## 输出约束

**成功（RESOLVED）**：只输出标准命令，例如：

```text
交换机MLAG规划
```

**追问（CLARIFYING）**：只输出一句自然语言追问，列出候选选项，例如：

```text
请问您要做地址规划、互联规划、接入规划还是路由规划？
```

**失败（FAILED）**：固定话术：

```text
当前问题不属于LLD设计支持范围，请输入地址规划、互联规划、接入规划、LLD设计等相关指令。
```

## 匹配原则摘要

1. 输出命令**必须**来自 [intent-taxonomy.md](./intent-taxonomy.md)，禁止自造命令。
2. 不强制识别到三级；精准匹配到一级或二级时直接输出该级命令。
3. 允许语义近似匹配；单一高置信直接输出，多候选竞争则追问。
4. 大小写不敏感；`交换机mlag规划` 等价于 `交换机MLAG规划`。
5. 关键词匹配覆盖 taxonomy 全部命令；用户省略「地址」「规划」等可选尾缀，或只说「角色+平面」（如 `计算带外管理面`）时，按 [intent-keywords.md](./intent-keywords.md) 归一化与消歧。

## 完成后

返回主 Skill [subskills/SKILL.md](../SKILL.md) Section B 智能路由：

- 三级叶子 / direct 二级 → Step 3 对应 `sd_*`
- L1 / L2 → Step 2 对应 `sd_*`
- 生成/融合 LLD → Section D `sd_lld_*`
- 查询/检查输入件 → `sd_query_inputs`

## 参考资料

- 分类树：[intent-taxonomy.md](./intent-taxonomy.md)
- 别名映射：[intent-aliases.md](./intent-aliases.md)
- 关键词映射：[intent-keywords.md](./intent-keywords.md)
- 输入输出样例：[intent-examples.md](./intent-examples.md)

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
