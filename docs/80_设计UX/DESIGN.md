---
version: alpha
name: AIDA 设计风格
description: >-
  一套可复用的浅色、数据密集型企业级控制台设计语言。slate 画布 + 白色面板，
  indigo 作为「AI / 可交互」信号色；克制、可信、无廉价特效。配套 visual-system.css 即可落地。

# ─────────────────────────────────────────────────────────────
# 用法：本套件只有一个样式文件 visual-system.css —— 它定义了全部
#   --c-*（颜色）/ --fs-*（字号）/ --r-*（圆角）/ --sp-*（间距）/ --shadow-* / 字体
# 以及一套通用组件（按钮 / 标签 / 卡片 / KPI / 输入 / 表格 / popover / callout…）。
# 下面 YAML 里的 token 是这份 CSS 的「忠实镜像」。
#   · 写页面 = 永远引用 var(--c-*) / var(--fs-*) / var(--r-*) / var(--sp-*)，不要硬编码 hex / px。
#   · 换肤 / 改品牌色 = 在你自己的 :root 里覆盖对应 token（如 --c-brand），一处生效、全局变。
# ─────────────────────────────────────────────────────────────

colors:
  # 中性 / 表面 (slate)
  bg: "#f6f8fb"            # 画布底色          → var(--c-bg)
  bg-soft: "#eef2f7"       # 卡片内凹陷/轨道    → var(--c-bg-soft)
  surface: "#ffffff"       # 面板/卡片表面      → var(--c-surface)
  surface-2: "#fafbfc"     # 次级表面/hover     → var(--c-surface-2)
  border: "#e3e8ef"        # 默认 1px 描边      → var(--c-border)
  border-strong: "#cbd5e1" # hover/强调描边     → var(--c-border-strong)
  divider: "#eef2f7"       # 分隔线            → var(--c-divider)
  # 文本
  text: "#0f172a"          # 主文本/标题        → var(--c-text)
  text-2: "#334155"        # 次文本/正文        → var(--c-text-2)
  text-muted: "#64748b"    # 弱化/元信息        → var(--c-text-muted)
  text-faint: "#94a3b8"    # 最弱/占位         → var(--c-text-faint)
  # 品牌 (indigo) — 同时是「AI / 可交互」信号色
  brand: "#3551d8"         # → var(--c-brand)
  brand-hover: "#2a44c2"   # → var(--c-brand-hover)
  brand-soft: "#eef1fc"    # 浅底/选中态        → var(--c-brand-soft)
  brand-text: "#1e34a8"    # 浅底上的品牌文字    → var(--c-brand-text)
  # 状态色（每档都是 主色 / soft 浅底 / text 文字 三件套）
  success: "#0f9d58"
  success-soft: "#e6f6ee"
  success-text: "#0a7d46"
  warning: "#d97706"
  warning-soft: "#fdf2dd"
  warning-text: "#9a5b08"
  danger: "#dc2626"
  danger-soft: "#fde8e8"
  danger-text: "#a31919"
  info: "#2563eb"
  info-soft: "#e6efff"
  info-text: "#1747b8"
  # 风险等级 (用于活动条 / 风险标签)
  risk-high: "#d92e2e"
  risk-high-bg: "#fde6e6"
  risk-mid: "#d98014"
  risk-mid-bg: "#fdeed6"
  risk-low: "#b58a0c"
  risk-low-bg: "#fbf3d3"
  # 品牌红 — 仅限 logo / 关键品牌标识；风险语义请改用 danger/warning
  aida-red: "#c7000a"

typography:
  display:    { fontFamily: "var(--font-sans)", fontSize: "24px", fontWeight: 600, letterSpacing: "-0.01em" }
  h1:         { fontFamily: "var(--font-sans)", fontSize: "22px", fontWeight: 600, letterSpacing: "-0.01em" }
  h2:         { fontFamily: "var(--font-sans)", fontSize: "18px", fontWeight: 600 }
  h3:         { fontFamily: "var(--font-sans)", fontSize: "14px", fontWeight: 600 }
  metric:     { fontFamily: "var(--font-sans)", fontSize: "26px", fontWeight: 600, letterSpacing: "-0.01em" }
  body:       { fontFamily: "var(--font-sans)", fontSize: "14px", fontWeight: 400, lineHeight: 1.6 }
  body-sm:    { fontFamily: "var(--font-sans)", fontSize: "13px", fontWeight: 400, lineHeight: 1.55 }
  meta:       { fontFamily: "var(--font-sans)", fontSize: "12px", fontWeight: 400 }
  label-caps: { fontFamily: "var(--font-sans)", fontSize: "11px", fontWeight: 600, letterSpacing: "0.06em" }
  mono:       { fontFamily: "var(--font-mono)", fontSize: "12px" }

rounded:
  sm: 4px       # → var(--r-sm)   chips / tags / 小控件
  md: 6px       # → var(--r-md)   按钮 / 输入框 / 导航项
  lg: 8px       # → var(--r-lg)   卡片 / 面板 / popover
  xl: 12px      # → var(--r-xl)   大容器
  pill: 999px   # → var(--r-pill) 胶囊 / 进度条 / 圆点

# 8pt 间距制，对应 var(--sp-1) … var(--sp-10)（注意跳过 7、9）
spacing:
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 20px
  6: 24px
  8: 32px
  10: 40px

components:
  button-primary:
    backgroundColor: "{colors.brand}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "7px 12px"
  button-primary-hover:
    backgroundColor: "{colors.brand-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-2}"
    rounded: "{rounded.md}"
    padding: "7px 12px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-2}"
    rounded: "{rounded.md}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "7px 10px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
  status-chip-success:
    backgroundColor: "{colors.success-soft}"
    textColor: "{colors.success-text}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  status-chip-warning:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning-text}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  status-chip-danger:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger-text}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  status-chip-brand:
    backgroundColor: "{colors.brand-soft}"
    textColor: "{colors.brand-text}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  risk-pill-high:
    backgroundColor: "{colors.risk-high}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    height: "16px"
    padding: "0 5px"
  kpi-value:
    textColor: "{colors.text}"
    typography: "{typography.metric}"
---

## Overview

这是一套可复用的**浅色、数据密集型企业级控制台**设计语言（源自 AIDA 交付编排系统，已抽出供任意前端项目复用）。目标：让多人 / 编码代理（Claude Code、Codex 等）在同一套风格下产出一致的页面。

**气质**：浅色「双层表面」——slate 画布（`--c-bg`）上浮着白色面板（`--c-surface`），用 1px 描边和**克制的**阴影分层；信息密集、企业级、可信，**不要**霓虹/发光/赛博/消费品风。一抹 indigo（`--c-brand`）专门承担「AI / 可交互」的信号。

**怎么用**：本套件只有一个样式文件 **`visual-system.css`**——引入它就拿到全部 token + 一套通用组件。本 `DESIGN.md` 是它的**忠实镜像 + 用法说明**。

> **写页面的铁律**：永远引用 `var(--c-*)` / `var(--fs-*)` / `var(--r-*)` / `var(--sp-*)`，**不要硬编码 hex 或像素**。这样换肤、改品牌色只需动 token。
> **换肤**：在你自己的 `:root`（引入 `visual-system.css` 之后）覆盖 `--c-brand` 等，一处改、全局变。

---

## Colors

调色板是「高对比中性 + 单一品牌色 + 语义状态色」。每个值在 YAML front matter 里有精确 hex，下面讲**何时用**。

### 中性与表面
- `--c-bg` `#f6f8fb`：页面/主内容区底色（slate，比纯白柔和）。
- `--c-surface` `#ffffff`：卡片、面板、弹层的表面。**白卡浮在 slate 上**是本系统的基本构图。
- `--c-bg-soft` `#eef2f7`：卡片**内部**的凹陷区（进度条轨道、次级分组底）。
- `--c-border` `#e3e8ef`：默认 1px 描边；`--c-border-strong` `#cbd5e1` 用于 hover / 强调；`--c-divider` `#eef2f7` 用于分隔线。

### 文本（四级灰阶）
`--c-text` `#0f172a`（标题/主文本）→ `--c-text-2` `#334155`（正文）→ `--c-text-muted` `#64748b`（元信息/标签）→ `--c-text-faint` `#94a3b8`（占位/最弱）。层级用**颜色深浅**拉开，而非字号堆叠。

### 品牌 indigo —— 同时是「AI / 可交互」信号
`--c-brand` `#3551d8` 是主品牌色，也专门表示「AI 在动作 / 可点击 / 当前选中」：导航 active、引用 chip、AI 圆点、live 脉冲、链接强调统统用它。配套：`--c-brand-hover`（按下/悬停加深）、`--c-brand-soft` `#eef1fc`（浅底，用于选中态与 chip）、`--c-brand-text` `#1e34a8`（浅底上的品牌文字，保证对比度）。

### 语义状态色（soft / 主色 / text 三件套）
每档都有三个角色，**组合方式固定**：浅底 `*-soft` + 文字 `*-text` + 透明描边 = 状态标签；实色 `*` = 进度段/强调条/图标。

| 语义 | 主色 | 浅底 soft | 文字 text |
|:--|:--|:--|:--|
| success 成功 | `--c-success` | `--c-success-soft` | `--c-success-text` |
| warning 警告 | `--c-warning` | `--c-warning-soft` | `--c-warning-text` |
| danger 危险 | `--c-danger` | `--c-danger-soft` | `--c-danger-text` |
| info 信息 | `--c-info` | `--c-info-soft` | `--c-info-text` |

### 风险等级
活动条/风险标签专用三档：`--c-risk-high`（实色配 `-bg` 浅底）、`--c-risk-mid`、`--c-risk-low`。实色版用在彩色背景上，ghost 版（`*-bg` 底 + 主色字）用在浅色背景上。

### 品牌红（例外，慎用）
`--aida-red` `#c7000a` 是品牌标识色，**只**用于 logo 与极少数关键品牌标识。**不要**用它表达「风险/错误」——风险语义一律走 `--c-danger` / `--c-warning`。（换成你自己的品牌时，这条规则照搬：保留一个仅供品牌标识的强色，不参与状态语义。）

---

## Typography

**字体**：正文走 `--font-sans`（系统字体栈，含 PingFang SC / Microsoft YaHei 等 CJK 回退）；数字、ID、代号走 `--font-mono`。页面基准 14px / 行高 1.55。

### 字阶（见 front matter `typography`）
| Token | 字号/字重 | 用途 |
|:--|:--|:--|
| `display` | 24 / 600 / -.01em | 大标题、欢迎语 |
| `h1` | 22 / 600 / -.01em | 页面标题 |
| `h2` | 18 / 600 | 区块标题 |
| `h3` | 14 / 600 | 卡片/面板标题 |
| `metric` | 26 / 600 / -.01em | KPI / 大数值 |
| `body` | 14 / 1.6 | 正文 |
| `body-sm` | 13 | 紧凑正文、表格、按钮 |
| `meta` | 12 | 元信息、副标题（多配 `--c-text-muted`） |
| `label-caps` | 11 / 600 / .06em 大写 | **eyebrow 小标签** |
| `mono` | 12 等宽 | ID / 代号 / 时间戳 |

### 三条硬规则
1. **所有数字都要 `font-variant-numeric: tabular-nums`**（KPI、表格、日期、计数、ID）。等宽数字让纵向对齐、跳动不抖动——这是本系统的标志性细节。
2. **eyebrow 小标签**：11px、`letter-spacing` .04–.06em、`text-transform: uppercase`、配 `--c-text-muted`。用于 KPI label、区块眉题。
3. **大标题用负字距**（`letter-spacing: -0.01em`），收紧观感；小字不加。

---

## Layout

### 8pt 间距制
所有内外边距、间隔取自 `--sp-*`（`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40`，对应 `--sp-1…--sp-10`，跳过 7、9）。常用节奏：
- 卡片/面板内边距：`12px 16px`（头）/ `14px 16px`（体）
- 区块内边距：`14–18px`
- chip / 小控件内边距：`2px 7px` ~ `4px 10px`
- 元素间隙 `gap`：`6 / 8 / 10 / 12`

### 构图原则
- **双层表面**：slate 画布托白色面板；面板之间靠 `--c-border` + `--shadow-sm` 分层，**不靠重阴影、不用深色块**。
- **对齐**：文本左对齐；数字右对齐。
- **密度**：信息密集但留白克制——宁可多分组、多分隔线，也不要堆字号。

> 应用外壳（侧边栏 / 主区 / 侧栏等具体栅格）由各项目自定，本规范不约束，只约束上面的间距与构图原则。

---

## Elevation & Depth

分层主要靠**描边**，阴影是点缀，**没有霓虹/发光**。

| Token | 值 | 用途 |
|:--|:--|:--|
| `--shadow-sm` | `0 1px 2px rgba(15,23,42,.04)…` | 卡片、面板等的静置态 |
| `--shadow-md` | `0 4px 14px rgba(15,23,42,.06)…` | 抬起态、次级浮层 |
| `--shadow-lg` | `0 12px 28px rgba(15,23,42,.10)…` | popover / 抽屉等真正悬浮的层 |

阴影颜色统一用 slate（`rgba(15,23,42,*)`）的低透明度，而非纯黑。**焦点态**全站统一：`outline: 2px solid var(--c-brand-soft); border-color: var(--c-brand);`。遮罩用 `rgba(15,23,42,.32)`。

---

## Shapes

圆角取自 `--r-*`，按尺寸递进选用：

| Token | 值 | 用在 |
|:--|:--|:--|
| `--r-sm` | 4px | chip / tag / 状态标签 / 小控件 |
| `--r-md` | 6px | 按钮 / 输入框 / 导航项 / seg |
| `--r-lg` | 8px | 卡片 / 面板 / popover |
| `--r-xl` | 12px | 大容器 |
| `--r-pill` | 999px | 过滤胶囊 / 进度条 / live 圆点 |

描边：默认 `1px solid var(--c-border)`；hover/强调换 `--c-border-strong`；**状态 chip 用透明描边**（靠 soft 底色成形）。不要随意发明新的圆角值，从 scale 里取。

---

## Components

`visual-system.css` 内置了下列通用组件，新页面直接复用其类名即可（打开 `index.html` 可看到真实样子）：

- **按钮 `.btn`**：默认＝白底 `--c-surface` + `--c-text-2` + `--c-border`；`.primary`＝`--c-brand` 实底白字（hover→`--c-brand-hover`）；`.ghost`＝透明底；`.sm`＝紧凑尺寸。圆角 `--r-md`。
- **状态标签 `.tag.solid-{brand|info|green|amber|red}`**：本系统最核心的小组件——`*-soft` 浅底 + `*-text` 文字 + 透明描边，圆角 `--r-sm`。任何「绿/黄/红/蓝」状态都套这个公式。
- **风险胶囊 `.risk-pill`**：`.high/.mid/.low` 实色配白字（用于彩色背景）；`.ghost-*` 浅底配主色（用于浅背景）。16px 高、10px 加粗。
- **输入 `.input` / `.select`**：白底 + `--c-border`，聚焦＝`--c-brand` 描边 + `--c-brand-soft` 2px outline；配 `.field-label` / `.field-hint`。
- **卡片 / 面板 `.card`**：白底、`--c-border`、`--r-lg`；`.card-head`（含 `.card-title`）带 `--c-divider` 底分隔，`.card-body` 放内容。
- **KPI `.kpi`**：`metric` 字阶数值 + `tabular-nums`；`.kpi-label` 是 eyebrow 小标签；`.kpi-delta.up/.down` 表升降。`.kpi.warn/.risk` 用极浅渐变底 + 对应描边。
- **分段控件 `.seg`** / **过滤胶囊 `.pill`**：`.active` 态用白底+阴影 / 品牌软底。
- **表格 `.vs-table`**：表头 11px 大写 muted；`td.num` 右对齐 + 等宽数字。
- **浮层 `.popover`**：白底 + `--c-border` + `--shadow-lg`，圆角 `--r-lg`；内部 `.pv-row` 的 `.k`/`.v` 做键值对，`.pv-risk` 做风险提示条。
- **提示条 `.callout`**（`.red/.green/.info`）：浅底 + 左侧 3px 同色边。

**两个反复出现的范式**（自定义组件时照搬）：
- **左侧彩条**：用 `::before` 画 2–3px 左侧色条表严重度/分类，比整块染色更克制。
- **行/卡片 hover**：背景转 `--c-bg`，描边转 `--c-border-strong`，可选 `translateY(-1px)` + `--shadow-sm`。

---

## Do's and Don'ts

**Do**
- ✅ 颜色/字号/圆角/间距一律用 token：`var(--c-*)`、`var(--fs-*)`、`var(--r-*)`、`var(--sp-*)`。
- ✅ 状态标签用「`*-soft` 底 + `*-text` 字 + 透明边」公式。
- ✅ 所有数字加 `font-variant-numeric: tabular-nums`。
- ✅ 把 indigo（`--c-brand`）留给「AI / 可交互 / 选中」语义。
- ✅ 换品牌色：在 `:root` 覆盖 `--c-brand`（及可选的 `--c-brand-hover/-soft/-text`）。

**Don't**
- ❌ 不要硬编码 hex / px——一旦写死，换肤和改品牌色就失效。
- ❌ 不要用品牌强色（如 `--aida-red`）表达风险/错误；风险走 `--c-danger` / `--c-warning`。
- ❌ 不要用大面积深色块、霓虹/发光阴影、或赛博/消费品风格。
- ❌ 不要临时发明圆角/间距数值，从既有 scale 里取。

---

<sub>本文件遵循 [DESIGN.md](https://github.com/google-labs-code/design.md) 格式（YAML token + Markdown 说明）。可用 `npx @google/design.md lint DESIGN.md` 校验对比度与 token 引用。</sub>
