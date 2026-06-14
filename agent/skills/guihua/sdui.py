"""
guihua SDUI 投影器 · SkillState → SduiDocument（纯函数 · 无副作用 · 可单测）

建模仿真（规划设计前半段）作业界面（精简版）：
  - Idle：流程说明引导卡
  - 执行态：三页签工作台（仿真软件 / 设备数据 / 输出文件）
  - data_confirm HITL：适配表展示 + 「设备数据准确」确认按钮
  - cabinet_move / handoff HITL：交互在左侧会话框，右侧不再重复上下文/进度卡
  - done 态：左侧 completion-card 引导输出文件（「确认输出文件」→ 切右侧「输出文件」页签）

依赖 step 写入 metrics：
  adapt_build  → combo_model / device_count / matched_count / compat_table_md / adapt_mode
  combo_create → created_count / pod_count / combo_base / move_total / sim_live / create_ok
  cabinet_move → move_total / move_sent / move_done
"""
from __future__ import annotations

from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode,
    SduiTextNode,
    SduiMarkdownNode, SduiTabGroupNode, SduiTabPanel, SduiEmbeddedWebNode,
    SduiDataTableNode,
    SduiOutputDocsGridNode, SduiOutputDocItem, SduiOutputDocCategory,
    SduiRowNode, SduiButtonNode,
    SduiPostUserMessage, dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics, overall_status,
    build_hitl,
)
from .services.sim_api import web_url

GUIHUA_STEP_NAMES: dict[str, str] = {
    "adapt_build":  "设备适配",
    "data_confirm": "数据确认",
    "combo_create": "创建超节点",
    "cabinet_move": "机柜落位",
    "handoff":      "生成参数面设备",
}
GUIHUA_STEP_ORDER = list(GUIHUA_STEP_NAMES.keys())

# nVisual 内嵌 iframe 固定高度（原 560，略增高以减少下方留白）
GUIHUA_SIM_IFRAME_HEIGHT = 780

# ── 输出文件（mock · 复刻 simulation_v3 app.jsx OUTPUT_DOCS）──────────────────────
GUIHUA_OUTPUT_CATEGORIES: list[tuple[str, str]] = [
    ("LLD", "LLD · 低阶设计"),
    ("设备安装", "设备安装"),
    ("交付准备", "交付准备"),
]
# 真实输出文件（随包样本 vendor/jmfz/output_files）：path=文件名 → 经 files.resolve_artifact_path 下载。
GUIHUA_OUTPUT_DOCS: list[dict[str, str]] = [
    {"no": "001", "name": "设备信息表", "fullName": "建模仿真输出文档001-设备信息表.xlsx",
     "path": "建模仿真输出文档001-设备信息表.xlsx",
     "category": "LLD", "tag": "LLD", "desc": "全量设备清单、型号规格、数量汇总"},
    {"no": "005", "name": "设备汇总表", "fullName": "建模仿真输出文档005-设备汇总表.xlsx",
     "path": "建模仿真输出文档005-设备汇总表.xlsx",
     "category": "LLD", "tag": "LLD", "desc": "机柜清单、设备归属与占位汇总"},
    {"no": "007", "name": "端口连线表", "fullName": "建模仿真输出文档007-端口连线表.xlsx",
     "path": "建模仿真输出文档007-端口连线表.xlsx",
     "category": "LLD", "tag": "LLD", "desc": "设备间端口到端口连接拓扑表"},
    {"no": "004", "name": "设备位置表", "fullName": "建模仿真输出文档004-设备位置表.xlsx",
     "path": "建模仿真输出文档004-设备位置表.xlsx",
     "category": "设备安装", "tag": "设备安装", "desc": "机房平面坐标与机柜 U 位分配"},
    {"no": "006", "name": "设备落位图", "fullName": "建模仿真输出文档006-设备落位图.xlsx",
     "path": "建模仿真输出文档006-设备落位图.xlsx",
     "category": "设备安装", "tag": "设备安装", "desc": "三维机房设备落位示意与路由"},
    {"no": "008", "name": "物理连线表", "fullName": "建模仿真输出文档008-物理连线表.xlsx",
     "path": "建模仿真输出文档008-物理连线表.xlsx",
     "category": "设备安装", "tag": "设备安装", "desc": "设备间物理链路连接明细"},
    {"no": "009", "name": "线缆需求表", "fullName": "建模仿真输出文档009-线缆需求表.xlsx",
     "path": "建模仿真输出文档009-线缆需求表.xlsx",
     "category": "交付准备", "tag": "交付准备", "desc": "全量线缆规格、长度与路由规划"},
    {"no": "010", "name": "布线临时标签表", "fullName": "建模仿真输出文档010-布线临时标签表.xlsx",
     "path": "建模仿真输出文档010-布线临时标签表.xlsx",
     "category": "交付准备", "tag": "交付准备", "desc": "施工期临时标签编码与张贴规则"},
]

_DATA_CONFIRM_HINT = (
    "BOQ数据已经解析完毕，放到数据中心，可以查看详细数据以开启建模仿真"
)


def _parse_section_table(compat_md: str, section_keyword: str) -> tuple[list[str], list[list[str]]] | None:
    """解析适配表指定【…】段的 Markdown 表 → (columns, rows)。"""
    if not compat_md:
        return None
    in_section = False
    header: list[str] = []
    rows: list[list[str]] = []
    for line in compat_md.splitlines():
        s = line.strip()
        if s.startswith("【"):
            in_section = section_keyword in s
            if not in_section and header:
                break
            continue
        if not in_section or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if not header:
            header = cells
            continue
        rows.append(cells)
    if header and rows:
        return header, rows
    return None


def _parse_supernode_table(compat_md: str) -> tuple[list[str], list[list[str]]] | None:
    """解析【超节点概述】段 Markdown 表。"""
    return _parse_section_table(compat_md, "超节点概述")


def _parse_device_table(compat_md: str) -> tuple[list[str], list[list[str]]] | None:
    """解析适配表的【网络平面：参数面】段 Markdown 表 → (columns, rows)。

    列：设备型号 / 设备角色 / 设备数量 / 板卡型号 / 板卡数量。解析不到则返回 None（回退 Markdown）。
    """
    return _parse_section_table(compat_md, "网络平面")


# ── 仿真软件 / 设备数据 双页签 ─────────────────────────────────────────────────

def _build_sim_tabs(state: dict[str, Any]) -> SduiTabGroupNode | None:
    """右侧三页签（对齐 simulation_v3 SimAgentView）：
      ① 仿真软件（nVisual iframe + 刷新 / 新页打开 / 创建后自动刷新）
      ② 设备数据（适配信息表 → DataTable，Markdown 兜底 + 设备数据准确按钮）
      ③ 输出文件（分类输出文件网格，done 前锁定）
    适配表生成后（有 compat_table_md）才出现「设备数据」页。"""
    m = collect_metrics(state)
    compat_md = m.get("compat_table_md") or ""
    steps = state.get("steps") or []
    all_done = bool(steps) and all(s.get("status") == "completed" for s in steps)
    # 创建超节点成功后自增 reloadToken → 前端自动刷新仿真画布（对齐 v3 创建后刷新）。
    reload_token = 1 if m.get("create_ok") else 0

    # 真跑交付：仿真软件可达，始终内嵌实时画布（保留刷新 / 新页打开），不走离线占位。
    tabs: list[SduiTabPanel] = [
        SduiTabPanel(
            id="sim", label="仿真软件",
            children=[SduiEmbeddedWebNode(
                id="sim-iframe", url=web_url(), title="nVisual 仿真软件",
                height=GUIHUA_SIM_IFRAME_HEIGHT, openInNewTab=True, reloadToken=reload_token,
            )],
        ),
    ]
    hitl_step = (state.get("hitl") or {}).get("step")
    if compat_md:
        body: list[SduiNode] = []
        supernode = _parse_supernode_table(compat_md)
        parsed = _parse_device_table(compat_md)
        if supernode or parsed:
            if supernode:
                sn_cols, sn_rows = supernode
                body.append(SduiDataTableNode(
                    id="supernode-table", columns=sn_cols, rows=sn_rows,
                    title="超节点概述", subtitle=f"{len(sn_rows)} 组合行",
                ))
            if parsed:
                cols, rows = parsed
                body.append(SduiDataTableNode(
                    id="device-table", columns=cols, rows=rows,
                    title="参数面设备适配", subtitle=f"{len(rows)} 型号行",
                ))
        else:
            # 解析失败兜底：原样渲染适配表 Markdown。
            body.append(SduiMarkdownNode(id="compat-md", content=compat_md))
            if m.get("compat_table_truncated"):
                body.append(SduiTextNode(
                    id="compat-trunc", variant="caption", color="subtle",
                    content="表格较长已截断，完整见 ProjectData/RunTime/compat_table.md"))
        # 右下角「设备数据准确」按钮：仅在「数据准确？」确认门待办时出现，点击 = 确认 data 门。
        if hitl_step == "data_confirm":
            body.append(SduiRowNode(
                id="data-confirm-row", justify="end",
                children=[SduiButtonNode(
                    id="data-accurate-btn", label="设备数据准确", variant="primary",
                    action=SduiPostUserMessage(text="/resume_guihua"),
                )],
            ))
        tabs.append(SduiTabPanel(id="data", label="设备数据", children=body))

    # 输出文件页（mock 占位）：done 前锁定，done 后解锁。
    tabs.append(SduiTabPanel(
        id="docs", label="输出文件",
        badge=str(len(GUIHUA_OUTPUT_DOCS)) if all_done else None,
        children=[SduiOutputDocsGridNode(
            id="output-docs",
            unlocked=all_done,
            categories=[SduiOutputDocCategory(key=k, label=l) for k, l in GUIHUA_OUTPUT_CATEGORIES],
            docs=[SduiOutputDocItem(**d) for d in GUIHUA_OUTPUT_DOCS],
        )],
    ))

    # 默认停在「仿真软件」；「查看详细数据」按钮 / 直接点页签 切到「设备数据」（前端本地切换）。
    return SduiTabGroupNode(id="guihua-tabs", tabs=tabs, activeTab="sim", keepAlive=True)


def _build_guihua_hitl(state: dict[str, Any]) -> SduiCardNode | None:
    """HITL 卡：data_confirm 为引导文案 + 查看详细数据；其余步走通用 build_hitl。"""
    hitl = state.get("hitl") or {}
    step_key = hitl.get("step")
    if not step_key:
        return None
    if step_key == "data_confirm":
        return SduiCardNode(
            id="hitl-card", title="建模仿真",
            children=[
                SduiTextNode(
                    id="data-confirm-hint", variant="body",
                    content=hitl.get("reason") or _DATA_CONFIRM_HINT,
                ),
                SduiRowNode(
                    id="data-view-row", justify="start",
                    children=[SduiButtonNode(
                        id="boq-view-btn-left", label="查看详细数据", variant="primary",
                        action=SduiPostUserMessage(text="__activate_tab__:data"),
                    )],
                ),
            ],
        )
    return build_hitl(state, card_title="需要确认", default_choice_title="请确认")


def _build_completion_card() -> SduiCardNode:
    """全流程完成：左侧引导用户查看输出文件（按钮切右侧 docs 页签）。"""
    return SduiCardNode(
        id="completion-card", title="建模仿真",
        children=[
            SduiTextNode(
                id="completion-hint", variant="body",
                content="已完成建模仿真，请问是否输出文件？",
            ),
            SduiRowNode(
                id="output-confirm-row", justify="start",
                children=[SduiButtonNode(
                    id="output-confirm-btn", label="确认输出文件", variant="primary",
                    action=SduiPostUserMessage(text="__activate_tab__:docs"),
                )],
            ),
        ],
    )


def _build_intro_card() -> SduiCardNode:
    return SduiCardNode(
        id="guihua-intro", title="建模仿真任务说明（规划设计前半段）",
        children=[SduiMarkdownNode(content=(
            "· **BOQ 已解析**：载入《建模仿真设备适配信息表》→「查看详细数据」核对设备数据\n"
            "· **数据准确（HITL）** → **是否创建超节点（HITL）**：batchCreateCombo ×5（9 个 POD 平铺创建）\n"
            "· **机柜落位（HITL）**：刷新 nVisual 后 batchMoveNodes ×162 逐机柜落位\n"
            "· **生成参数面设备（HITL）**：csm-rack 建 Leaf 54 台 → 跨视图上架 18 次 → batchCreateLink 双轨拓扑\n\n"
            "> 真跑模式经 subprocess 调 jmfz 脚本真发仿真网关（100.102.191.17:9091）。"
        ))],
    )


# ── 顶层入口 ──────────────────────────────────────────────────────────────────

def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument JSON-compatible dict。"""
    status_key, _ = overall_status(state, GUIHUA_STEP_ORDER)
    is_idle = status_key == "idle"

    if is_idle:
        doc = SduiDocument(
            root=SduiStackNode(id="guihua-root", gap="md", children=[_build_intro_card()]),
            meta={"skill": "guihua", "run_id": state.get("run_id", "")},
        )
        return dump_sdui_json(doc)

    # ── 执行态：右侧仅三页签工作台（无顶栏 header 卡；HITL 路由左侧）──
    nodes: list[SduiNode] = []
    hitl_card = _build_guihua_hitl(state)
    if hitl_card:
        nodes.append(hitl_card)
    elif status_key == "done":
        nodes.append(_build_completion_card())

    sim_tabs = _build_sim_tabs(state)
    if sim_tabs:
        nodes.append(sim_tabs)

    doc = SduiDocument(
        root=SduiStackNode(id="guihua-root", gap="md", children=nodes),
        meta={"skill": "guihua", "run_id": state.get("run_id", "")},
    )
    return dump_sdui_json(doc)
