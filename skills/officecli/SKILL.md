---
name: officecli
version: "1.0.94"
description: "OfficeCLI — 统一 Office 文档解析与操作 CLI 工具。支持 docx/xlsx/pptx/pdf/doc/eml 等格式的创建、读取、修改。DSXW 项目用于验收表证据提取与测试用例结构化解析。"
license: Apache-2.0
repository: https://github.com/iOfficeAI/OfficeCLI/tree/main
install: Local binary — see Install section below
---

# OfficeCLI Skill

**OfficeCLI** 是一个 CLI 工具，提供对 Office 文档（Word/Excel/PPT/PDF/邮件）的统一创建、读取、修改能力。它封装了 python-docx、openpyxl、python-pptx、pdfplumber 等底层库，提供更精准的路径定位和结构化输出。

> 项目地址：[iOfficeAI/OfficeCLI](https://github.com/iOfficeAI/OfficeCLI/tree/main)
> 下载地址：[GitHub Releases](https://github.com/iOfficeAI/OfficeCLI/releases)
> 当前版本：v1.0.94

## PPTX 矢量 SVG 导出

**officecli 自带 SVG 导出（`officecli view <pptx> svg`）对华为定制主题 PPT 存在配色丢失问题**：华为主题的 `clrScheme` 将 `lt1`(bg1) 设为 `#666666`、`dk2`(bg2) 设为 `#FFFFFF`（与标准主题相反），officecli 误将 scheme:bg1 解析为白色，导致底色和背景高亮丢失。

**解决方案：** 使用 `scripts/pptx2svg.py` 脚本，走 **PPTX → PDF (PowerPoint COM) → SVG (PyMuPDF)** 路径，完整保留底色、背景高亮和每个元素为独立可选中矢量路径。

```bash
uv run python src/skills/officecli/scripts/pptx2svg.py <input.pptx> [output_dir]
```

| 平台 | PPTX→PDF | PDF→SVG | 说明 |
|---|---|---|---|
| **Windows** | PowerPoint COM (pywin32) | PyMuPDF | 完整保真，含华为定制主题 |
| **Linux** | LibreOffice headless | PyMuPDF | 已实现，需 `apt install libreoffice` |

**平台差异（必须了解）：**

| 维度 | Windows (PowerPoint COM) | Linux (LibreOffice headless) |
|---|---|---|
| **华为主题保真** | ✅ 完整支持 `clrScheme` 定制主题 | ⚠️ 部分主题可能渲染偏差，建议验证 |
| **字体替换** | 使用系统已安装字体 | 需安装对应字体（如 `fonts-wqy-microhei` 用于中文） |
| **Group icon 补注入** | ✅ 支持 | ✅ 支持（共用同一套 PPTX 提取逻辑） |
| **性能** | ~2-5s/页 | ~3-8s/页（受 CPU 影响） |
| **依赖** | pywin32（已含） | libreoffice（需单独安装） |

**Linux 安装 LibreOffice：**

```bash
# Debian/Ubuntu
sudo apt install libreoffice fonts-wqy-microhei

# RHEL/CentOS/Fedora
sudo dnf install libreoffice langpacks-zh_CN

# Alpine (Docker)
apk add libreoffice ttf-wqy-zenhei
```

输出产物：单个 `index.html` 文件，6 页矢量 SVG 直接内嵌（每页元素可单独选中，无需额外 SVG 文件）。

**转换要求（必须遵守）：**

1. **文字保留为 `<text>` 元素** — PyMuPDF `get_svg_image(text_as_path=0)`，禁止将文字转成 path 描边（默认 `text_as_path=1` 会导致文字不可选、不可搜索、渲染异常）
2. **字体映射** — PyMuPDF 将系统字体替换为 `Nimbus Sans`，必须替换回 `Microsoft YaHei`（`s.replace("Nimbus Sans", "Microsoft YaHei")`），否则 Windows 浏览器无法渲染英文字符
3. **SVG 内嵌到 HTML** — 所有页面的 SVG 直接嵌入单个 `index.html`，不生成独立的 `.svg` 文件
4. **多页 ID 防冲突** — 多页 SVG 内嵌时，`id` 和 `url(#)` 引用自动加 slide 前缀（`s1_`, `s2_`, ...）
5. **华为主题保真** — 走 COM 导出 PDF 路径，确保定制 `clrScheme`（如 lt1=#666666）的底色和背景高亮正确渲染

依赖：`pywin32`（已含 pyproject.toml）、`pymupdf`（已含 pyproject.toml）

## 与 uniEx 现有 Skills 的关系

OfficeCLI 是 `src/skills/` 下 pdf/docx/pptx/xlsx/canvas 五个 skill 的**合集升级**：

| 现有 Skill | OfficeCLI 对应能力 | uniEx 使用场景 |
|---|---|---|
| `pdf/` | `officecli view <file> text` + `officecli get` | PDF 文本提取、表单解析 |
| `docx/` | `officecli view <file> outline` + `officecli get /body/tbl[N]` | Word 标题层级、表格精准提取 |
| `pptx/` | `officecli view <file> slides` + 嵌入附件提取 | PPT 幻灯片、OLE 对象解析 |
| `xlsx/` | `officecli view <file> stats` + `officecli query /Sheet1/*` | Excel 逐单元格路径定位 |
| `canvas/` | `officecli create` | 文档创建（uniEx 暂不使用） |

**uniEx 中优先使用 OfficeCLI 的场景：**
- DTRB PPT 内嵌 OLE 附件提取与递归解析
- 需要精准路径定位的深度解析（如 `/body/tbl[1]/tr[2]/tc[3]/p[@paraId=xxx]`）
- 跨格式嵌入对象识别（OLE → MSG/ZIP/RAR）

**保留现有 Skill 的场景：**
- openpyxl 直接操作单元格（证据粒度控制更精细）
- pdfplumber 表格识别（无需额外安装）
- 批量自动化 pipeline（officecli 适合交互式，pipeline 用 Python API 更高效）

---

# officecli

AI-friendly CLI for .docx, .xlsx, .pptx. Single binary, no dependencies, no Office installation needed.

## Install

### 本地 binary（推荐，华为内网免外网访问）

Binary 存放在 `src/skills/officecli/reference/` 目录，按平台区分：

| 平台 | 文件 | 安装命令 |
|---|---|---|
| **Windows x64** | `officecli-win-x64.exe` | `cp src/skills/officecli/reference/officecli-win-x64.exe /usr/local/bin/officecli.exe && chmod +x /usr/local/bin/officecli.exe` |
| **Linux ARM64** | `officecli-linux-arm64` | `cp src/skills/officecli/reference/officecli-linux-arm64 /usr/local/bin/officecli && chmod +x /usr/local/bin/officecli` |

Verify: `officecli --version`

### 从 GitHub Releases 下载更新

访问 [iOfficeAI/OfficeCLI Releases](https://github.com/iOfficeAI/OfficeCLI/releases) 下载对应平台的 binary，替换 `reference/` 目录下的文件：

| 平台 | Releases 中的文件名 | 替换目标 |
|---|---|---|
| **Windows x64** | `officecli-win-x64.exe` | `src/skills/officecli/reference/officecli-win-x64.exe` |
| **Linux ARM64** | `officecli-linux-arm64` | `src/skills/officecli/reference/officecli-linux-arm64` |

```bash
# 下载最新 release（需外网访问，替换 <TAG> 为实际版本号）
TAG="1.0.94"
cd src/skills/officecli/reference

# Windows x64
curl -fSL -o officecli-win-x64.exe "https://github.com/iOfficeAI/OfficeCLI/releases/download/${TAG}/officecli-win-x64.exe"

# Linux ARM64
curl -fSL -o officecli-linux-arm64 "https://github.com/iOfficeAI/OfficeCLI/releases/download/${TAG}/officecli-linux-arm64"
chmod +x officecli-linux-arm64
```

下载替换后重新执行上面的本地安装命令即可。更新版本后需同步修改本文件 frontmatter 的 `version` 字段。

---

## Strategy

**L1 (read) → L2 (DOM edit) → L3 (raw XML)**. Always prefer higher layers. Add `--json` for structured output.

**Before doc work, check Specialized Skills** (bottom of this file). Fundraising decks, academic papers, financial models, dashboards, and Morph animations need their own skill loaded first — `load_skill` once, then proceed.

---

## Help System (IMPORTANT)

**When unsure about property names, value formats, or command syntax, ALWAYS run help instead of guessing.** One help query beats guess-fail-retry loops.

`officecli help` ≡ `officecli --help`, and `officecli <cmd> --help` ≡ `officecli help <cmd>` — same content.

```bash
officecli help                                  # All commands + global options + schema entry points
officecli help docx                             # List all docx elements
officecli help docx paragraph                   # Full schema: properties, aliases, examples, readbacks
officecli help docx set paragraph               # Verb-filtered: only props usable with `set`
officecli help docx paragraph --json            # Structured schema (machine-readable)
```

Format aliases: `word`→`docx`, `excel`→`xlsx`, `ppt`/`powerpoint`→`pptx`. Verbs: `add`, `set`, `get`, `query`, `remove`. MCP exposes the same schema via `{"command":"help","format":"docx","type":"paragraph"}`.

---

## Performance: Resident Mode

**Every command auto-starts a resident on first access** (60s idle timeout) — file-lock conflicts are automatically avoided. Explicit `open`/`close` is still recommended for longer sessions (12min idle):
```bash
officecli open report.docx       # explicitly keep in memory
officecli set report.docx ...    # no file I/O overhead
officecli close report.docx      # save and release
```

Opt out of auto-start: `OFFICECLI_NO_AUTO_RESIDENT=1`.

---

## Quick Start

**PPT:**
```bash
officecli create slides.pptx
officecli add slides.pptx / --type slide --prop title="Q4 Report" --prop background=1A1A2E
officecli add slides.pptx '/slide[1]' --type shape --prop text="Revenue grew 25%" --prop x=2cm --prop y=5cm --prop font=Arial --prop size=24 --prop color=FFFFFF
```

**Word:**
```bash
officecli create report.docx
officecli add report.docx /body --type paragraph --prop text="Executive Summary" --prop style=Heading1
officecli add report.docx /body --type paragraph --prop text="Revenue increased by 25% year-over-year."
```

**Excel:**
```bash
officecli create data.xlsx
officecli set data.xlsx /Sheet1/A1 --prop value="Name" --prop bold=true
officecli set data.xlsx /Sheet1/A2 --prop value="Alice"
```

---

## L1: Create, Read & Inspect

```bash
officecli create <file>               # Create blank .docx/.xlsx/.pptx (type from extension)
officecli view <file> <mode>          # outline | stats | issues | text | annotated | html
officecli get <file> <path> --depth N # Get a node and its children [--json]
officecli query <file> <selector>     # CSS-like query
officecli validate <file>             # Validate against OpenXML schema
```

### view modes

| Mode | Description | Useful flags |
|------|-------------|-------------|
| `outline` | Document structure | |
| `stats` | Statistics (pages, words, shapes) | |
| `issues` | Formatting/content/structure problems | `--type format\|content\|structure`, `--limit N` |
| `text` | Plain text extraction | `--start N --end N`, `--max-lines N` |
| `annotated` | Text with formatting annotations | |
| `html` | Static HTML snapshot — same renderer as `watch`, no server needed | `--browser`, `--page N` (docx), `--start N --end N` (pptx) |

Use `view html` for one-shot snapshots (CI artifacts, archival, diffing); use `watch` when you need live refresh or browser-side click-to-select.

### get

Any XML path via element localName. Use `--depth N` to expand children. Add `--json` for structured output. Default text output is grep-friendly: `path (type) "text" key=val key=val ...`

```bash
officecli get report.docx '/body/p[3]' --depth 2 --json
officecli get slides.pptx '/slide[1]' --depth 1          # list all shapes on slide 1
officecli get data.xlsx '/Sheet1/B2' --json
```

### Stable ID Addressing

Elements with stable IDs return `@attr=value` paths instead of positional indices. Prefer these in multi-step workflows — positional indices shift on insert/delete, stable IDs do not.

```
/slide[1]/shape[@id=550950021]                    # PPT shape
/slide[1]/table[@id=1388430425]/tr[1]/tc[2]       # PPT table
/body/p[@paraId=1A2B3C4D]                         # Word paragraph
/comments/comment[@commentId=1]                    # Word comment
```

PPT also accepts `@name=` (e.g. `shape[@name=Title 1]`), with morph `!!` prefix awareness. Elements without stable IDs (slide, run, tr/tc, row) fall back to positional indices.

### query

CSS-like selectors: `[attr=value]`, `[attr!=value]`, `[attr~=text]`, `[attr>=value]`, `[attr<=value]`, `:contains("text")`, `:empty`, `:has(formula)`, `:no-alt`.

```bash
officecli query report.docx 'paragraph[style=Normal] > run[font!=Arial]'
officecli query slides.pptx 'shape[fill=FF0000]'
```

For large documents, use `--max-lines` to limit output.

---

## Watch & Interactive Selection

Live HTML preview that auto-refreshes on every file change. Browsers can click / shift-click / box-drag to select shapes; the CLI can read the current browser selection and act on it.

```bash
officecli watch <file> [--port N]      # Start preview server (default port 18080)
officecli unwatch <file>               # Stop
officecli goto <file> <path>           # Scroll watching browser(s) to element (docx: p / table / tr / tc)
```

Open the printed `http://localhost:N` URL. Click to select; shift/cmd/ctrl+click to multi-select; drag from empty space to box-select. PPT/Word use blue outline; Excel uses native-style green selection (double-click cell to edit inline; drag a chart to reposition).

### `get <file> selected` — read what the user clicked

```bash
officecli get <file> selected [--json]
```

Returns DocumentNodes for whatever is currently selected. Empty result if nothing selected. Exit code != 0 if no watch is running.

```bash
# User clicks shapes in the browser, then asks "make these red"
PATHS=$(officecli get deck.pptx selected --json | jq -r '.data.Results[].path')
for p in $PATHS; do officecli set deck.pptx "$p" --prop fill=FF0000; done
```

### Key properties

- **Selection survives file edits.** Paths use stable `@id=` form.
- **All connected browsers share one selection.** Last-write-wins.
- **Same-file single-watch.** A given file can have only one watch process at a time.
- **Group shapes select as a whole.** Drilling into individual children of a group is not supported in v1.
- **Coverage:** `.pptx` shapes/pictures/tables/charts/connectors/groups; `.docx` top-level paragraphs and tables. Inherited layout/master decorations and Word nested elements (table cells, run-level) are not addressable. **`.xlsx` does not emit `data-path`** — `mark`/`selection` on xlsx always resolve `stale=true` (v2 candidate).

### Marks — edit proposals waiting for review

Use `mark` when changes need human review BEFORE they hit the file. Marks live in the watch process only; a separate `set` pipeline applies accepted ones. For one-shot changes use `set` directly; for permanent file annotations use `add --type comment` (Word native).

```bash
officecli mark <file> <path> [--prop find=... color=... note=... tofix=... regex=true] [--json]
officecli unmark <file> [--path <p> | --all] [--json]
officecli get-marks <file> [--json]
```

Props: `find` (literal or regex when `regex=true`; raw form `find='r"[abc]"'`), `color` (hex / `rgb(...)` / 22 named whitelist), `note`, `tofix` (drives apply pipeline). **Path** must be `data-path` format from watch HTML — see subskills for full pipeline.

---

## L2: DOM Operations

### set — modify properties

```bash
officecli set <file> <path> --prop key=value [--prop ...]
```

**Any XML attribute is settable** via element path (found via `get --depth N`) — even attributes not currently present. Without `find=`, `set` applies format to the entire element.

**Value formats:**

| Type | Format | Examples |
|------|--------|---------|
| Colors | Hex (with/without `#`), named, RGB, theme | `FF0000`, `#FF0000`, `red`, `rgb(255,0,0)`, `accent1`..`accent6` |
| Spacing | Unit-qualified | `12pt`, `0.5cm`, `1.5x`, `150%` |
| Dimensions | EMU or suffixed | `914400`, `2.54cm`, `1in`, `72pt`, `96px` |

**Dotted-attr aliases** — `font.<attr>` forms accepted on shape/run/paragraph/table/row/cell/section/styles, e.g. `--prop font.color=red --prop font.bold=true --prop font.size=14pt`. Run `officecli help <fmt> <element>` for the full list.

### find — format or replace matched text

Use `find=` with `set` to target specific text for formatting or replacement. Format props are separate `--prop` flags — do NOT nest them.

```bash
# Format matched text (auto-splits runs)
officecli set doc.docx '/body/p[1]' --prop find=weather --prop bold=true --prop color=red

# Regex matching
officecli set doc.docx '/body/p[1]' --prop 'find=\d+%' --prop regex=true --prop color=red

# Replace text (use `/` for whole-document scope)
officecli set doc.docx / --prop find=draft --prop replace=final

# PPT — same syntax, different paths
officecli set slides.pptx / --prop find=draft --prop replace=final
```

**Path controls search scope:** `/` = whole document, `/body/p[1]` or `/slide[N]/shape[M]` = specific element, `/header[1]` / `/footer[1]` = headers/footers.

**Notes:**
- Case-sensitive by default. Case-insensitive: `--prop 'find=(?i)error' --prop regex=true`
- Matches work across run boundaries
- No match = silent success. `--json` includes `"matched": N`
- **Excel:** only `find` + `replace` supported (no find + format props)

### add — add elements or clone

```bash
officecli add <file> <parent> --type <type> [--prop ...]
officecli add <file> <parent> --type <type> --after <path> [--prop ...]   # insert after anchor
officecli add <file> <parent> --type <type> --before <path> [--prop ...]  # insert before anchor
officecli add <file> <parent> --type <type> --index N [--prop ...]        # 0-based position (legacy)
officecli add <file> <parent> --from <path>                               # clone existing element
```

`--after`, `--before`, `--index` are mutually exclusive. No position flag = append to end.

**Element types (with aliases):**

| Format | Types |
|--------|-------|
| **pptx** | slide (incl. hidden), shape (textbox — font.latin/ea/cs, direction=rtl), picture (SVG, brightness/contrast/glow/shadow), chart (direction=rtl), table (cell direction=rtl), row (tr), connector (connection/line), group, video (audio/media, trim), equation (formula/math), notes (direction=rtl, lang), comment (RTL via U+200F bidi mark; full CRUD via /slide[N]/comment[M]), paragraph (para), run, zoom (slidezoom), ole (oleobject/object/embed), placeholder (phType=title/body/subtitle/footer/...). slideLayout/slideMaster direction inheritance. |
| **docx** | paragraph (para — direction/font.latin/ea/cs, bold.cs/italic.cs/size.cs for RTL/CJK; lang.latin/ea/cs BCP-47 tags on run; wordWrap toggle), run, table (direction=rtl → bidiVisual), row (tr), cell (td), image (picture/img — SVG supported), header (direction), footer (direction), section (pageNumFmt full ECMA-376 enum incl. Hindi/Arabic/Thai/CJK numerals; direction=rtl on Add/Set; rtlGutter; pgBorders=box shorthand), bookmark, comment, footnote, endnote, formfield (text/checkbox/dropdown), sdt (contentcontrol), chart, equation, field (28 types incl. mergefield/ref/seq/styleref/docproperty/if), hyperlink, style (direction round-trip), toc, watermark, break (pagebreak/columnbreak), ole, **num / abstractNum / lvl** (numbering/list system), **tab** (paragraph or paragraph/table style tab stops). docDefaults.rtl document-wide override; `get /` exposes `locale`. Document protection: `set / --prop protection=forms\|readOnly\|comments\|trackedChanges\|none` |
| **xlsx** | sheet (visible/hidden/veryHidden, print margins, printTitleRows/Cols, rightToLeft sheetView, cascade-aware rename), row, cell (type=richtext+runs, merge=range/sweep, direction=rtl, phonetic guide on add), chart (direction=rtl on per-axis txPr / title; incl. pareto), image (picture — SVG), comment (direction=rtl), table (listobject), namedrange (definedname, volatile, `[@name=X]` selector), pivottable (pivot, calculatedField), sparkline, validation (datavalidation), autofilter, shape, textbox, databar/colorscale/iconset/formulacf/cellIs/topN/aboveAverage (conditional formatting), ole, csv (tsv). Query supports `merge`/`mergedrange` aliases for `mergeCell`. Workbook: password. `value="=SUM(...)"` auto-detects as formula. Chart/picture/shape/slicer accept `anchor=A1:E10`. |

### Pivot tables (xlsx)

```bash
officecli add data.xlsx /Sheet1 --type pivottable \
  --prop source="Sheet1!A1:E100" --prop rows=Region,Category \
  --prop cols=Year --prop values="Sales:sum,Qty:count" \
  --prop grandTotals=rows --prop subtotals=off --prop sort=asc
```

Key props: `rows`, `cols`, `values` (Field:func[:showDataAs]), `filters`, `source`, `position`, `layout` (compact/outline/tabular), `repeatLabels`, `blankRows`, `aggregate`, `showDataAs` (percent_of_total/row/col, running_total), `grandTotals`, `subtotals`, `sort`. Aggregators: sum, count, average, max, min, product, stdDev, stdDevp, var, varp, countNums. Date columns auto-group. Run `officecli help xlsx pivottable` for full schema.

### Document-level properties (all formats)

```bash
officecli set doc.docx / --prop docDefaults.font=Arial --prop docDefaults.fontSize=11pt
officecli set doc.docx / --prop protection=forms --prop evenAndOddHeaders=true
officecli set data.xlsx / --prop calc.mode=manual --prop calc.refMode=r1c1
officecli set slides.pptx / --prop defaultFont=Arial --prop show.loop=true --prop print.what=handouts
```

Run `officecli help <format> /` for all document-level properties (docDefaults, docGrid, CJK spacing, calc, print, show, theme, extended).

### Sort (xlsx)

```bash
officecli set data.xlsx /Sheet1 --prop sort="C desc" --prop sortHeader=true
officecli set data.xlsx '/Sheet1/A1:D100' --prop sort="A asc" --prop sortHeader=true
```

Format: `COL DIR[, COL DIR ...]`. Rejects ranges with merged cells or formulas. Sidecar metadata (hyperlinks, comments, conditional formatting, drawings) follows rows automatically.

### Text-anchored insert (`--after find:X` / `--before find:X`)

Locate an insertion point by text match within a paragraph. Inline types (run, picture, hyperlink) insert within the paragraph; block types (table, paragraph) auto-split it. PPT only supports inline.

```bash
# Word: inline run after matched text
officecli add doc.docx '/body/p[1]' --type run --after find:weather --prop text=" (sunny)"

# Word: block table after matched text (auto-splits paragraph)
officecli add doc.docx '/body/p[1]' --type table --after "find:First sentence." --prop rows=2 --prop cols=2
```

### Clone

`officecli add <file> / --from '/slide[1]'` — copies with all cross-part relationships.

### move, swap, remove

```bash
officecli move <file> <path> [--to <parent>] [--index N] [--after <path>] [--before <path>]
officecli swap <file> <path1> <path2>
officecli remove <file> '/body/p[4]'
```

When using `--after` or `--before`, `--to` can be omitted — the target container is inferred from the anchor.

### batch — multiple operations in one save cycle

Continues on error by default (returns exit 1 if any item fails). Use `--stop-on-error` to abort on the first failure. `--force` is the docx-protection bypass.

`officecli dump <file.docx>` emits a replayable batch JSON for full-document round-trip; `officecli refresh <file.docx>` recalculates TOC page numbers / PAGE / cross-references after replay (Word backend on Windows; headless-HTML fallback elsewhere).

```bash
echo '[
  {"command":"set","path":"/Sheet1/A1","props":{"value":"Name","bold":"true"}},
  {"command":"set","path":"/Sheet1/B1","props":{"value":"Score","bold":"true"}}
]' | officecli batch data.xlsx --json

officecli batch data.xlsx --commands '[{"op":"set","path":"/Sheet1/A1","props":{"value":"Done"}}]' --json
officecli batch data.xlsx --input updates.json --force --json
```

Supports: `add`, `set`, `get`, `query`, `remove`, `move`, `swap`, `view`, `raw`, `raw-set`, `validate`. Fields: `command` (or `op`), `path`, `parent`, `type`, `from`, `to`, `index`, `after`, `before`, `props`, `selector`, `mode`, `depth`, `part`, `xpath`, `action`, `xml`.

---

## L3: Raw XML

Use when L2 cannot express what you need. No xmlns declarations needed — prefixes auto-registered.

```bash
officecli raw <file> <part>                          # view raw XML
officecli raw-set <file> <part> --xpath "..." --action replace --xml '<w:p>...</w:p>'
officecli add-part <file> <parent>                   # create new document part (returns rId)
```

`raw-set` actions: `append`, `prepend`, `insertbefore`, `insertafter`, `replace`, `remove`, `setattr`. Run `officecli help <format> raw` for available parts.

---

## Common Pitfalls

| Pitfall | Correct Approach |
|---------|-----------------|
| `--name "foo"` | Use `--prop name="foo"` — all attributes go through `--prop` |
| Unquoted `[N]` paths in zsh/bash | Always quote: `'/slide[1]'` or `"/slide[1]"` (shell glob-expands brackets) |
| PPT `shape[1]` for content | `shape[1]` is typically the title placeholder. Use `shape[2]+` for content shapes |
| `/shape[myname]` | Name indexing not supported. Use numeric index or `@name=` (PPT only) |
| Guessing property names | Run `officecli help <format> <element>` to see exact names |
| Modifying an open file | Close the file in PowerPoint/WPS first |
| `\n` in shell strings | Use `\\n` for newlines in `--prop text="..."` |
| `$` in shell text | `--prop text="$15M"` strips `$15`. Use single quotes: `--prop text='$15M'`, or heredoc batch |

---

## Specialized Skills

`officecli load_skill <name>` — output is a SKILL.md, follow its rules.

**Loading rule**:
- Pick the most specific match in "When to use"; if none fits, load the format default (`word` / `pptx` / `excel`).
- Scenes already contain the format default's rules — load **one** skill per artifact, never stack.
- Loaded rules persist across turns; don't re-load each reply.
- Two distinct artifacts → two separate loads.

### Word (.docx)

| Name | When to use |
|------|-------------|
| `word` | Reports, letters, memos, proposals, generic documents |
| `academic-paper` | Journal / conference / thesis: APA / Chicago / IEEE / MLA citations, equations, SEQ + PAGEREF cross-refs, multi-column journal layout, bibliography. NOT for business reports or letters (route those to `word`) |

### PowerPoint (.pptx)

| Name | When to use |
|------|-------------|
| `pptx` | Generic decks: board reviews, sales decks, all-hands, product launches |
| `pitch-deck` | **Fundraising only** — seed / Series A-C / SAFE / convertible / strategic raise. NOT for sales / product / board decks (route those to `pptx`) |
| `morph-ppt` | Cinematic Morph-animated presentations. NOT for static decks (route those to `pptx`) |
| `morph-ppt-3d` | 3D Morph: GLB models, camera moves, depth. NOT for 2D-only Morph (route those to `morph-ppt`) |

### Excel (.xlsx)

| Name | When to use |
|------|-------------|
| `excel` | Generic workbooks, formulas, pivots, trackers |
| `financial-model` | Financial models, scenarios, projections. NOT for general data analysis (route those to `excel`) |
| `data-dashboard` | CSV/tabular data → KPI / analytics / executive dashboards with charts and sparklines. NOT for raw data tracking (route those to `excel`) |

Example: a fundraising deck task → `officecli load_skill pitch-deck` → use the printed rules.

---

## Notes

- Paths are **1-based** (XPath convention): `'/body/p[3]'` = third paragraph
- `--index` is **0-based** (array convention): `--index 0` = first position
- After modifications, verify with `validate` and/or `view issues`
- **When unsure**, run `officecli help <format> <element>` instead of guessing

---

## uniEx 专用：DTRB Case 实战用法

DTRB 评审 PPT（`全J超算中心项目_DTRB 评审2025.12.18.pptx`）包含 6 个嵌入附件：

```bash
# 1. 查看 PPT 结构
officecli view "全J超算中心项目_DTRB 评审2025.12.18.pptx" outline

# 2. 标准嵌入文件（ppt/embeddings/ 解压后直接用 officecli）
officecli view ppt/embeddings/Microsoft_Word_Document.docx outline
officecli view ppt/embeddings/Microsoft_Excel_Worksheet.xlsx stats
officecli get ppt/embeddings/Microsoft_Excel_Worksheet.xlsx "/Sheet1/A1:F50" --json

# 3. OLE .bin 需先 olefile 解包，再 officecli 解析内含文件
#    oleObject1.bin → Outlook MSG  (extract-msg 解析)
#    oleObject2.bin → RAR5         (unrar 解压后 officecli 解析 xlsx)
#    oleObject3.bin → ZIP          (解压后 officecli 解析 xlsx)
```

## uniEx 专用：常见陷阱

1. **OLE .bin 不是直接可读文件** — 需先用 `olefile` 解析 OLE 复合文档，再从 `Ole10Native` 流提取实际内容
2. **华为网络代理** — 公司环境可能需要配置 `no_proxy` 或离线安装（优先从 `reference/` 目录本地安装）
3. **大文件性能** — 1000+ 行 Excel 使用 `--json` 输出较慢，建议用 `query` + 范围限定

## uniEx 专用：依赖

```bash
# officecli 本身是单 binary，无外部依赖（见上方 Install 章节）

# OLE 解析额外依赖（DTRB Case 必需，已包含在 pyproject.toml）
# olefile, extract-msg

# RAR 解压（DTRB Case oleObject2.bin）
# Linux: apt install unrar
# macOS: brew install unrar
# Windows: 下载 unrar.exe 或使用 7-Zip
```

---

## uniEx 专用：项目建议书验收方案抽取

通用的项目建议书与验收方案文档解析管线。从 `.docx` 服务建议书中提取验收条款及原文证据，从测试用例文档中结构化提取用例，不限于特定项目。

### 架构

```
officecli view text (全文)
    ├── 服务建议书 → 关键词搜索 + 章节定位 → 验收条款 + 原文证据 (JSON/MD/HTML)
    └── 测试用例   → TOC解析 + Heading3→Table匹配 → 结构化用例列表 (JSON/MD/HTML)
```

### 核心原则

1. **统一引擎**: 使用 `officecli` 解析 `.docx`，不再依赖 `python-docx` 或 `pandoc`
2. **独立提取**: 验收表与测试用例互不交叉关联，各自独立输出
3. **证据溯源**: 每条验收条款附带原文关键词命中 + 章节定位作为支撑
4. **三格式输出**: 每种产出默认同时输出 JSON + Markdown + HTML，HTML 必须生成不可跳过，可通过 `--format` 缩减

### 输出格式

| 格式 | 目录 | 说明 |
|:---|:---|:---|
| JSON | `json/` | 结构化数据，供程序消费 |
| Markdown | `md/` | 纯文本表格，供 Git 版本管理 |
| HTML | `html/` | 带 CSS 样式，供浏览器查看 |

> **强制要求**: HTML 不是可选项，必须与 JSON、MD 同时生成，除非用户显式指定 `--format` 跳过。

### 管线A：服务建议书 → 验收证据

验收条款采用硬编码模板（可按项目定制），每条配置专属关键词集合。全文搜索命中行向上查找最近章节标题作为归属，同章节去重后输出为证据列表。

#### 5 类验收条款 (硬编码模板)

| 序号 | 分类 | 验收方案 | 验收入口标准 | 合同验收里程碑 | 验收文档 | 回款条款 |
|:---:|:---|:---|:---|:---|:---|:---|
| 1 | 硬件设备 | POD | 硬件到货 | 硬件到货 | 硬件设备接收文档 | 100% |
| 2 | 软件部分 | License激活完成软件验收 | License加载完成 | License加载 | License加载证明 | 100% |
| 3 | 服务部分 | 对应服务条目交付完成 | 对应服务条目交付完成 | 完工验/PAC | 完工验/PAC报告 | 100% |
| 4 | 培训服务 | 培训课程完成即验收 | 培训课程完成 | 培训完成 | 签到表 | 100% |
| 5 | 维保服务 | 硬件到货和License激活后30天 | OM起算 | 直线法 | — | 月度 |

#### 关键词搜索规则

| 分类 | 搜索关键词 |
|:---|:---|
| 硬件设备 | 设备到货、POD、SuperPoD、硬件验收、设备验收、到货验收、设备签收、开箱验收、设备安装调试、现场验收 |
| 软件部分 | License、软件激活、商用永久授权、软件许可、集群软件、管理系统、CANN、MindSpore、NPU驱动 |
| 服务部分 | 完工验收、PAC、服务交付、部署服务、实施服务、调测、验收标准、项目验收、安装部署、系统集成 |
| 培训服务 | 培训、培训课程、技术培训、培训计划、赋能培训、现场培训、培训服务 |
| 维保服务 | 维保、售后服务、质保期、维护服务、技术支持、故障处理、备件服务、巡检、运维 |

#### 验收表 JSON Schema

```json
{
  "source": { "file": "...docx", "parsed_at": "...", "engine": "officecli" },
  "acceptance_table": [
    {
      "id": "1", "category": "硬件设备", "acceptance_scheme": "POD",
      "entry_criteria": "硬件到货", "contract_milestone": "硬件到货",
      "acceptance_documents": ["硬件设备接收文档"], "payment_terms": "100%",
      "total_keyword_matches": 42,
      "evidence": [{ "chapter": "...", "matched_keywords": [...], "content": "原文段落..." }]
    }
  ]
}
```

### 管线B：测试用例 → 结构化提取

利用 TOC 建立 `case_id → 标题名` 映射，内容区匹配 `Heading 3 → 紧随 Table` 关联。逐表 `officecli get /body/tbl[N] --depth 3 --json` 提取字段，再按关键词投票进行分类与三层分层。

#### 分类规则

| 分类 | 关键词 | 排除词 |
|:---|:---|:---|
| 硬件设备 | 设备到货、Pod、硬件、上架、配电、指示灯、BIOS、RAID、机柜、开箱、电源框、风扇、硬盘 | 软件、License、iBMC、OS |
| 软件部分 | License、激活、OS、iBMC、驱动、固件、ZTP、软件版本、管理模块、Web界面、远程控制 | — |
| 服务部分 | 网络、灵衢、BGP、光模块、CloudOps、集群、集合通信、模型训练、PyTorch、HCCS、RoCE | — |

服务部分三层分层：
- **下路-计算存储网络**: 网络、BGP、光模块、CPLD、PRBS、压力、互通性
- **中路-平台建立**: CloudOps、集群、集合通信、健康检查、带宽性能、HCCS
- **上路-业务应用**: 模型训练、PyTorch、摸高、稳定性测试、qwen

#### 测试用例 JSON Schema

```json
{
  "source": { "filename": "...docx", "total_cases": 54, "parsed_at": "...", "engine": "officecli" },
  "cases": [
    {
      "case_id": "1.1.1", "chapter": "§1.1 基本功能测试",
      "test_purpose": "...", "preconditions": [...],
      "test_steps": [...], "expected_result": [...],
      "pass_fail_criteria": { "pass": "...", "fail": "..." },
      "test_network": "NA", "remarks": "...",
      "category": "硬件设备", "layer": null
    }
  ]
}
```

### 输出目录结构

```
uniEx-Output/{project}/
├── md/     # Markdown 格式
├── html/   # HTML 格式 (含CSS样式)
└── json/   # 结构化 JSON
```

### officecli 路径注意事项 (Windows + Git Bash)

`officecli get /body` 路径在 Windows + Git Bash 环境会被误解析为 `D:/app/Git/body`。绕过方式：
- 使用具体路径：`officecli get '/body/tbl[N]' --depth 3 --json`
- `officecli view text` 不受影响
- subprocess 调用时指定 `encoding='utf-8', errors='replace'`

### 执行命令

```bash
# 完整流水线 (默认 JSON + MD + HTML 三格式)
python scripts/pipeline.py --pipeline all

# 仅服务验收表
python scripts/pipeline.py --pipeline proposal

# 仅测试用例
python scripts/pipeline.py --pipeline testcases

# 指定输出目录
python scripts/pipeline.py --out-dir uniEx-Output
```
