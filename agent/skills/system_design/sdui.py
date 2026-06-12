"""
system_design SDUI 投影器 · SkillState → SduiDocument（纯函数 · 无副作用 · 可单测）

界面依据：《系统设计工作台-周二版》设计稿。严格对齐设计稿的**信息流程与展示内容**，
但**完全不使用设计稿里的 mock 数据**——所有数值/状态/文件名一律读自真实 graph 后端写入
state 的 metrics / files / steps / project（见各 step 写入字段）。

设计稿主面板布局顺序（与 ArtifactsPanel 三页签 + 时间卡 + 对话流一致），SDUI 单列堆叠呈现：
  header（AppBar：项目名 + 状态 + CTA）
  → sd-conversation（ConversationPane：guidance / file_request / result · 左侧会话框；运行日志不在此展示）
  → [hitl-card 置顶]（对话流内可交互卡：FilePicker / ChoiceCard / 校验并继续 · 路由到左侧）
  → [运行态通栏]（RunningCard → StatusBanner）
  → 任务时间规划安排（TaskTimelineStrip：计划/实际起止 + 设计进度）
  → 交付流程（ProgressPanel.StepRail：6 步用户视角蓝图 Stepper）
  → 规划覆盖（ProgressPanel.PlanningMatrix：分组平面 + 覆盖率 ProgressBar）
  → 风险与提示（ReminderCard / callout → RiskList 高/中/低）
  → 输入件清单（InputsPanel：自动/手动 · 必需 + 文件名 → Checklist）
  → 关键输出件 + 规划输出件（OutputsPanel：关键 vs 规划两组 → ArtifactGrid）
  → [输出空态]（OutputsPanel 空面板 → EmptyState）
  → 阶段摘要（对话流要点汇总 → Markdown）

设计稿用「6 步用户蓝图」（输入件准备 / 输入件检查 / LLD 生成 / 设备名称替换(可选) /
ZTP·开局文件 / 发布完成）承载交付流程；本投影器把后端真实 7 个 step 一一映射进蓝图，
每个蓝图步的状态由其对应后端 step（真实写入的 status）聚合得出（无 mock）：
  输入件准备   ← intent_recognition
  输入件检查   ← input_check
  LLD 生成     ← plane_planning + lld_integrate
  设备名称替换 ← naming_replace（可选）
  ZTP / 开局文件 ← ztp_generate
  发布完成     ← publish

各后端 step 真实写入 metrics/state 的键（投影器只读这些）：
  intent_recognition : intent_command / intent_status / intent_source
  input_check        : input_found / input_total / found_tags（+ files["input_<tag>"]）
                       HITL 时 hitl.found_files + need_files 反推就绪槽位（无 mock）
  plane_planning     : plane_total / plane_done / plane_skipped / plane_statuses / plane_notes / plane_summary
  lld_integrate      : lld_planes_merged / lld_file / lld_warnings
  ztp_generate       : ztp_file / ztp_auto_prereq / ztp_warnings
  naming_replace     : naming_status / naming_source
  publish            : publish_artifact_count / publish_xlsx_count / publish_manifest_count / publish_warnings
"""
from __future__ import annotations

import os
from typing import Any

from agent.sdui.builder import (
    SduiDocument, SduiNode, SduiStackNode, SduiCardNode, SduiRowNode,
    SduiTextNode, SduiDividerNode,
    SduiButtonNode, SduiPostUserMessage,
    SduiBadgeNode,
    SduiAlertNode,
    SduiFilePickerNode, SduiChoiceCardNode, SduiIoConfirmPanelNode,
    SduiPlaneMatrixNode, SduiPlaneCell,
    SduiRiskListNode, SduiRiskItem,
    SduiEmptyStateNode,
    SduiStatusBannerNode, SduiStatusItem,
    SduiArtifactGridNode, SduiArtifactItem,
    # Tier D（交付台 / 系统设计专用节点 · 对齐设计稿）
    SduiTaskTimelineStripNode,
    SduiMacroStepRailNode, SduiMacroStep,
    SduiInputSlotListNode, SduiInputSlot,
    SduiTabGroupNode, SduiTabPanel,
    choice_options,
    dump_sdui_json,
)
from agent.sdui.projector_base import (
    collect_metrics, artifact_kind, overall_status,
    backend_status_to_sdui,
    build_header,
)

# ── 后端真实步骤（顺序即 DAG 顺序，对齐 skill.py steps[]）────────────────────────
SD_STEP_NAMES: dict[str, str] = {
    "input_check": "输入件检查",
    "intent_recognition": "意图识别",
    "exec_confirm": "确认执行计划",
    "plane_planning": "平面规划",
    "lld_integrate": "LLD 融合",
    "stage_select": "输入执行计划",
    "naming_replace": "设备名称替换",
    "ztp_generate": "生成 ZTP 设计文件",
    "publish_confirm": "确认发布",
    "publish": "发布完成",
}
SD_STEP_ORDER = list(SD_STEP_NAMES.keys())


def _sd_overall_status(state: dict[str, Any]) -> tuple[str, str]:
    """系统设计整体状态：publish 步 completed 即视为交付完成（full_restart 续跑 steps 条数少于全量）。"""
    status_key, badge = overall_status(state, SD_STEP_ORDER)
    if status_key == "done":
        return status_key, badge
    if (state.get("hitl") or {}).get("step"):
        return status_key, badge
    by_key = {s.get("key"): s for s in (state.get("steps") or [])}
    pub = by_key.get("publish")
    if pub and pub.get("status") == "completed":
        return "done", "已完成"
    return status_key, badge

# ── 交付流程「6 步用户蓝图」（对齐设计稿 STEP_BLUEPRINT，展示顺序即设计稿顺序）──
# (蓝图 id, 标题, 提示文案, [映射的后端 step keys], 是否可选)
# 确认门折叠进相邻蓝图步（确认执行计划→LLD 生成；确认发布→发布完成）；
# 名称替换排在 ZTP 之前（对齐设计稿 s4 名称替换 → s5 ZTP，后端 step 顺序已同步调整）。
SD_BLUEPRINT: list[tuple[str, str, str, list[str], bool]] = [
    ("bp_inputs_ready", "输入件准备", "项目信息收集表 + 仿真输出件", ["input_check"], False),
    ("bp_inputs_check", "输入件检查", "校验平面配置与连线", ["input_check"], False),
    ("bp_lld", "LLD 生成", "确认执行计划 → 按平面规划并融合",
     ["intent_recognition", "exec_confirm", "plane_planning", "lld_integrate"], False),
    ("bp_naming", "设备名称替换", "选择执行计划并替换为现网设备名", ["stage_select", "naming_replace"], True),
    ("bp_ztp", "ZTP / 开局文件", "生成开局衍生件", ["ztp_generate"], False),
    ("bp_publish", "发布完成", "检查测试用例 → 确认发布 → 写回活动进度", ["publish_confirm", "publish"], False),
]
# 后端 step key → 蓝图标题（运行态通栏用真实当前步反查友好名）
_BACKEND_TO_BLUEPRINT: dict[str, str] = {
    bk: title for _, title, _, keys, _ in SD_BLUEPRINT for bk in keys
}

# CTA：{status_key: (按钮文案, variant, 指令)}；running 态自动不显示按钮
SD_CTA: dict[str, tuple[str, str, str]] = {
    "idle":   ("启动系统设计", "primary", "/start_system_design"),
    "paused": ("提交并继续",   "primary", "/resume_system_design"),
    "done":   ("导出交付",     "primary", "/view_result"),
    "failed": ("重试",         "primary", "/retry_system_design"),
}

_PLANE_STATUS_OK = {"done", "running", "pending", "error"}      # PlaneCell.status 取值域
# overall_status → StatusBanner.status（run/pause/fail/done）
_STATUS_TO_BANNER = {"running": "run", "paused": "pause", "failed": "fail", "done": "done"}


# 输入件展示槽（对齐设计稿 INPUT_SLOTS · tag 对应 pipelines/inputs.FILE_CONFIG）
# (backend_tag, 展示名, 设计稿必需标记, 设计稿 desc)
SD_INPUT_SLOTS: tuple[tuple[str, str, bool, str], ...] = (
    ("resource", "项目信息收集表", True, "地址规划的数据底座，需手动上传"),
    ("Interconnection_Relationship", "端口连线表", True, "设备端口互联关系，仿真自动输出"),
    ("Device_Info", "设备信息表", False, "设备型号 / 角色 / 序列号"),
    ("Location_Information", "设备位置表", False, "机房 / 机柜 / U 位"),
    ("Test_Case", "测试用例", False, "测试用例表（.xlsx / .docx）· 验收测试项 / 预期结果"),
)

from .pipelines.path_manifest import abs_input_dir, abs_artifacts_dir, abs_upload_dir, read_scan_dir_for_tag

_INPUT_CHECK_DIR = str(abs_upload_dir())
_SIM_SCAN_DIR = str(read_scan_dir_for_tag("Interconnection_Relationship"))


# ── 对话流（设计稿 ConversationPane · guidance / file_request / running / result）──

def _missing_tags_from_hitl(hitl: dict[str, Any]) -> set[str]:
    """从 input_check HITL 的 need_files 反推缺失 tag（graph 只写缺件路径）。"""
    from agent.skills.system_design.pipelines.inputs import FILE_CONFIG
    need_text = " ".join(str(p) for p in (hitl.get("need_files") or []))
    if not need_text:
        return set()
    missing: set[str] = set()
    for tag, cfg in FILE_CONFIG.items():
        label = str(cfg.get("label") or tag)
        kws = [label, tag, *(cfg.get("keywords") or [])]
        if any(kw and kw in need_text for kw in kws):
            missing.add(tag)
    return missing


def _tags_from_paths(paths: list[str]) -> dict[str, str]:
    """路径列表 → {tag: basename}（与 pipelines/inputs.FILE_CONFIG 关键词匹配）。"""
    from agent.skills.system_design.pipelines.inputs import FILE_CONFIG
    out: dict[str, str] = {}
    for raw in paths:
        p = str(raw)
        name = os.path.basename(p)
        for tag, cfg in FILE_CONFIG.items():
            if tag in out:
                continue
            kws = [*(cfg.get("keywords") or []), str(cfg.get("label") or "")]
            if any(kw and kw in name for kw in kws):
                out[tag] = name
                break
    return out


def _disk_input_index() -> dict[str, str]:
    """实时扫描各 tag 目录，返回 {tag: 相对 data_root 路径}（供 SDUI 预览）。"""
    from agent.skills.system_design.pipelines.path_manifest import relpath_for_artifact
    from agent.skills.system_design.pipelines.inputs import collect_inputs

    found = collect_inputs(None)
    out: dict[str, str] = {}
    for tag, entry in found.items():
        out[tag] = relpath_for_artifact(entry.path)
    return out


def _normalize_preview_path(raw: str | None) -> str | None:
    """统一为相对 data_root 的路径，供 /artifact?path= 使用。"""
    if not raw or not str(raw).strip():
        return None
    from agent.skills.system_design.pipelines.path_manifest import (
        relpath_for_artifact,
        resolve_artifact_file,
        resolve_data_root,
    )
    text = str(raw).strip()
    try:
        return relpath_for_artifact(resolve_artifact_file(text))
    except (ValueError, FileNotFoundError, PermissionError):
        pass
    root = resolve_data_root()
    candidate = (root / text.replace("\\", "/")).resolve()
    if candidate.is_file():
        return relpath_for_artifact(candidate)
    return text.replace("\\", "/")


def _resolve_found_tags(state: dict[str, Any]) -> set[str]:
    """已就绪输入件 tag：metrics.found_tags + state.files + HITL 反推 + 磁盘扫描（无 mock）。"""
    from agent.skills.system_design.pipelines.inputs import FILE_CONFIG
    m = collect_metrics(state)
    found = set(m.get("found_tags") or [])
    files = state.get("files") or {}
    for tag in FILE_CONFIG:
        fp = files.get(f"input_{tag}")
        if fp and isinstance(fp, str):
            found.add(tag)
    hitl = state.get("hitl") or {}
    for tag in _tags_from_paths(hitl.get("found_files") or []):
        found.add(tag)
    if hitl.get("step") == "input_check" and hitl.get("need_files"):
        missing = _missing_tags_from_hitl(hitl)
        for tag in FILE_CONFIG:
            if tag not in missing:
                found.add(tag)
    for tag in _disk_input_index():
        found.add(tag)
    return found


def _input_basename(state: dict[str, Any], tag: str) -> str | None:
    files = state.get("files") or {}
    fp = files.get(f"input_{tag}")
    if fp and isinstance(fp, str):
        return os.path.basename(fp)
    hitl = state.get("hitl") or {}
    from_hitl = _tags_from_paths(hitl.get("found_files") or []).get(tag)
    if from_hitl:
        return from_hitl
    disk = _disk_input_index().get(tag)
    return os.path.basename(disk) if disk else None


def _input_fullpath(state: dict[str, Any], tag: str) -> str | None:
    """输入件真实相对路径（供预览：磁盘扫描优先，其次 state.files / HITL）。"""
    disk = _disk_input_index().get(tag)
    if disk:
        norm = _normalize_preview_path(disk)
        if norm:
            return norm
    files = state.get("files") or {}
    fp = files.get(f"input_{tag}")
    if fp and isinstance(fp, str):
        norm = _normalize_preview_path(fp)
        if norm:
            return norm
    hitl = state.get("hitl") or {}
    name_map = _tags_from_paths(hitl.get("found_files") or [])
    bn = name_map.get(tag)
    if bn:
        for p in (hitl.get("found_files") or []):
            if os.path.basename(str(p)) == bn:
                return _normalize_preview_path(str(p))
    return None


def _build_input_slot_list(
    state: dict[str, Any], node_id: str, *,
    title: str | None = None,
    upload_step_id: str | None = None,
    upload_purpose: str | None = None,
) -> SduiInputSlotListNode:
    """file_request / 输入件页签共用的输入件槽位清单（对齐设计稿 InputSlotList · 读 state + HITL 反推，不 mock）。
    每槽位区分 必需/可选 × 自动检查/手动上传 × 就绪/缺失；前端缺件高亮 + 行内真实上传，就绪行可预览。
    upload_step_id / upload_purpose 非空 → 缺件「上传」走真实 onUpload(/upload/batch + resume)。"""
    from agent.skills.system_design.pipelines.inputs import FILE_CONFIG
    found_tags = _resolve_found_tags(state)
    slots: list[SduiInputSlot] = []
    for tag, display, required, _desc in SD_INPUT_SLOTS:
        cfg = FILE_CONFIG.get(tag) or {}
        auto = bool(cfg.get("from_simulation"))
        ready = tag in found_tags
        basename = _input_basename(state, tag) if ready else None
        fp = _input_fullpath(state, tag) if ready else None
        slots.append(SduiInputSlot(
            label=display,
            source="auto" if auto else "manual",
            required=required,
            ready=ready,
            fileName=basename,
            previewPath=fp if (ready and isinstance(fp, str)) else None,
            slotTag=tag,
        ))
    return SduiInputSlotListNode(
        id=node_id, slots=slots, title=title,
        uploadStepId=upload_step_id, uploadPurpose=upload_purpose,
    )


def _execution_failed(state: dict[str, Any], m: dict[str, Any]) -> bool:
    """本 run 是否已发生可展示的执行失败（state.error / failed step / 命令结果 error）。"""
    if str(state.get("error") or "").strip():
        return True
    if any(s.get("status") == "failed" for s in (state.get("steps") or [])):
        return True
    for rec in (m.get("command_results") or []):
        if isinstance(rec, dict) and rec.get("status") == "error":
            return True
    return False


def _round_error_text(state: dict[str, Any], m: dict[str, Any]) -> str:
    """本轮执行失败的可读说明（优先 state.error，退回 command_results；去噪 openpyxl 警告）。"""
    from .pipelines.exec_log import extract_actionable_error

    err = str(state.get("error") or "").strip()
    if err:
        cleaned = extract_actionable_error(errors=[err], log_tail=err)
        if cleaned and cleaned != "执行失败（详见执行日志）":
            return cleaned
    for rec in (m.get("command_results") or []):
        if not isinstance(rec, dict) or rec.get("status") != "error":
            continue
        cleaned = extract_actionable_error(errors=list(rec.get("errors") or []))
        if cleaned and cleaned != "执行失败（详见执行日志）":
            return cleaned
        if rec.get("summary"):
            return str(rec["summary"]).strip()
    return err or "规划执行失败"


def _cv_bubble(
    title: str | None,
    body: str,
    *,
    tone: str | None = None,
    bubble_id: str | None = None,
) -> SduiCardNode:
    children: list[SduiNode] = []
    if title:
        children.append(SduiTextNode(content=title, variant="heading"))
    children.append(SduiTextNode(content=body, variant="body"))
    return SduiCardNode(
        id=bubble_id or "cv-bubble",
        density="compact",
        tone=tone,  # type: ignore[arg-type]
        children=children,
    )


def _cv_user_message(text: str, *, bubble_id: str | None = None) -> SduiCardNode:
    return SduiCardNode(
        id=bubble_id or "cv-user",
        density="compact",
        children=[SduiTextNode(content=text, variant="body", color="accent")],
    )


def _build_file_request_card(state: dict[str, Any], hitl: dict[str, Any]) -> SduiCardNode:
    """输入件准备卡（HTML file_request · 缺件 HITL · 仅 InputSlotList，不展示 FilePicker 路径列表）。"""
    step_key = hitl.get("step", "input_check")
    children: list[SduiNode] = [
        SduiTextNode(
            content=hitl.get("reason") or "仅需手动上传「项目信息收集表」，其余仿真输出件已自动就绪。",
            variant="body", color="warning",
        ),
        SduiDividerNode(),
        _build_input_slot_list(
            state, "cv-input-slots",
            upload_step_id=step_key, upload_purpose=f"hitl_{step_key}",
        ),
        SduiTextNode(
            content="仿真输出件由系统自动检查；只需手动上传「项目信息收集表」。",
            variant="caption", color="subtle",
        ),
        SduiDividerNode(),
        SduiButtonNode(
            id="cv-confirm-inputs",
            label="校验并继续",
            variant="primary",
            action=SduiPostUserMessage(text="/resume_system_design"),
        ),
    ]
    return SduiCardNode(id="hitl-card", title="输入件准备", children=children)


# 确认型 HITL 卡标题（对齐设计稿各确认卡：confirm_request / next_stage / finalize）
_CONFIRM_CARD_TITLE: dict[str, str] = {
    "intent_recognition": "意图识别 · 请选择",
    "exec_confirm": "确认执行计划",
    "stage_select": "输入执行计划",
    "publish_confirm": "确认发布",
    "plane_planning": "下一步：继续规划 / 生成完整 LLD",
}


# 确认门「将读取 → 将生成」IO 提示（对齐设计稿 ConfirmCard 的 cv-io 双列）。
_CONFIRM_IO: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "exec_confirm": (
        ("端口连线表", "项目信息收集表", "网络平面配置"),
        ("各平面地址 / 互联 / 接入规划表", "完整 LLD 设计文件"),
    ),
    "publish_confirm": (
        ("完整 LLD 设计文件", "ZTP / 开局文件", "测试用例"),
        ("发布交付件", "写回项目活动进度"),
    ),
}


def _build_publish_finalize_card(state: dict[str, Any], hitl: dict[str, Any]) -> list[SduiNode]:
    """发布收尾卡（对齐设计稿 FinalizeCard / TestCheckCard）。"""
    ui = hitl.get("ui") or "finalize"
    m = collect_metrics(state)
    confs = (state.get("project") or {}).get("confirmations") or {}
    checked = bool(hitl.get("publish_checked") or confs.get("publish_checked"))

    if ui == "test_check":
        return [
            SduiBadgeNode(id="cv-test-tag", text="收尾", tone="default"),
            SduiTextNode(
                content=hitl.get("reason", "是否已经检查了测试用例？确认后即可继续发布。"),
                variant="body",
            ),
            SduiDividerNode(),
            SduiButtonNode(
                id="cv-test-check-confirm",
                label="确认",
                variant="primary",
                action=SduiPostUserMessage(text="check"),
            ),
        ]

    rename_skipped = m.get("naming_status") == "skipped"
    summary_lines = [
        f"{'–' if rename_skipped else '✓'} 设备名称替换{'已跳过' if rename_skipped else '已完成'}",
        "✓ ZTP / 开局文件已生成",
    ]
    return [
        SduiTextNode(
            content=hitl.get("reason", "收尾步骤已处理，确认发布后将写回项目活动进度。"),
            variant="body",
        ),
        SduiTextNode(content="\n".join(summary_lines), variant="caption", color="subtle"),
        SduiDividerNode(),
        SduiRowNode(
            id="cv-fin-foot",
            gap="sm",
            wrap=True,
            children=[
                SduiButtonNode(
                    id="cv-test-check-btn",
                    label="✓ 检查测试用例" if checked else "检查测试用例",
                    variant="secondary" if checked else "primary",
                    disabled=checked,
                    action=SduiPostUserMessage(text="request_test_check"),
                ),
                SduiButtonNode(
                    id="cv-publish-btn",
                    label="确认发布",
                    variant="primary",
                    disabled=not checked,
                    action=SduiPostUserMessage(text="confirm"),
                ),
            ],
        ),
    ]


def _build_exec_confirm_card(state: dict[str, Any], hitl: dict[str, Any]) -> SduiCardNode:
    """确认执行计划卡（对齐设计稿 confirm_request · cv-io 双列 + 确认/重新选择）。"""
    m = collect_metrics(state)
    cmd = str(hitl.get("command") or m.get("intent_command") or "").strip()
    reads = list(hitl.get("io_reads") or _CONFIRM_IO.get("exec_confirm", ([], []))[0])
    writes = list(hitl.get("io_writes") or _CONFIRM_IO.get("exec_confirm", ([], []))[1])
    return SduiCardNode(
        id="hitl-card",
        title=_CONFIRM_CARD_TITLE.get("exec_confirm", "确认执行计划"),
        children=[
            SduiIoConfirmPanelNode(
                id="hitl-exec-io",
                commandTitle=cmd or "规划任务",
                reads=reads,
                writes=writes,
                confirmLabel="确认执行",
                cancelLabel="重新选择",
                confirmValue="confirm",
                cancelValue="cancel",
                stepId="exec_confirm",
                hitlRequestId="exec_confirm",
            ),
        ],
    )


def _build_confirm_card(state: dict[str, Any], hitl: dict[str, Any]) -> SduiCardNode:
    """确认执行卡（HTML confirm_request / next_stage / finalize · need_inputs HITL）。"""
    step_key = hitl.get("step", "")
    if step_key == "exec_confirm":
        return _build_exec_confirm_card(state, hitl)
    need_inputs: list[dict] = hitl.get("need_inputs") or []
    children: list[SduiNode] = [
        SduiTextNode(content=hitl.get("reason", "请确认"), variant="body", color="warning"),
    ]
    # 将读取 → 将生成（对齐设计稿确认卡的输入/输出双列说明）
    io = _CONFIRM_IO.get(step_key)
    if io and step_key != "publish_confirm":
        reads, writes = io
        children.append(SduiTextNode(
            content="将读取：" + "、".join(reads) + "  →  将生成：" + "、".join(writes),
            variant="caption", color="subtle",
        ))
    if step_key == "publish_confirm":
        children = _build_publish_finalize_card(state, hitl)
    elif need_inputs:
        inp = need_inputs[0]
        options = choice_options(inp.get("options"))
        # 意图消歧：最多 3 项最相关候选 · 多选（对齐设计稿 DisambiguateCard）
        if step_key == "intent_recognition":
            options = options[:3]
        if options:
            is_multi = bool(inp.get("multi")) or step_key == "intent_recognition"
            children.extend([
                SduiDividerNode(),
                SduiChoiceCardNode(
                    id=f"hitl-choice-{step_key}",
                    title=inp.get("label", "请确认"),
                    options=options,
                    hitlRequestId=step_key,
                    stepId=step_key,
                    multiple=is_multi,
                    maxSelections=int(inp.get("max_selections") or 3) if is_multi else None,
                    submitLabel="确认选择" if not is_multi else None,
                ),
            ])
    if state.get("error"):
        children.append(SduiTextNode(
            content=f"错误：{state['error']}", variant="caption", color="error"))
    return SduiCardNode(
        id="hitl-card",
        title=hitl.get("title") or _CONFIRM_CARD_TITLE.get(step_key, "需要确认"),
        children=children,
    )


def _build_hitl_card(state: dict[str, Any]) -> SduiCardNode | None:
    """HITL 可交互卡（id=hitl-card · 前端路由到左侧会话框）。"""
    hitl = state.get("hitl") or {}
    step_key = hitl.get("step")
    if not step_key:
        return None
    # 选择规划任务：引导用户在对话框输入，不展示快捷按钮
    if step_key == "intent_recognition" and hitl.get("ui") == "plan_request":
        return SduiCardNode(
            id="hitl-card",
            title=hitl.get("title") or "选择规划任务",
            children=[
                SduiTextNode(
                    content=hitl.get("reason") or "请在下方对话框直接描述需求并发送即可执行规划。",
                    variant="body",
                ),
            ],
        )
    need_files = hitl.get("need_files") or []
    need_inputs = hitl.get("need_inputs") or []
    if need_files and step_key == "input_check":
        return _build_file_request_card(state, hitl)
    if need_files:
        return _build_file_request_card(state, hitl)
    if need_inputs:
        return _build_confirm_card(state, hitl)
    return _build_confirm_card(state, hitl)


def _latest_step_record(steps: list[Any] | None, key: str) -> dict[str, Any] | None:
    """steps 为 append-only；同 key 多次记录（HITL → completed）取最后一条。"""
    rec: dict[str, Any] | None = None
    for s in steps or []:
        if s.get("key") == key:
            rec = s
    return rec


def _step_completed(steps: list[Any] | None, key: str) -> bool:
    """任一条同 key 记录 status=completed 即视为该步已完成（兼容 step_retry 追加）。"""
    return any(
        s.get("key") == key and s.get("status") == "completed"
        for s in (steps or [])
    )


def _build_result_cards(state: dict[str, Any]) -> list[SduiNode]:
    """最近完成步骤的结果卡（HTML result · 产物摘要）。"""
    out: list[SduiNode] = []
    m = collect_metrics(state)
    for step_key, title, paths in (
        ("lld_integrate", "LLD 融合完成", [m.get("lld_file")] if m.get("lld_file") else []),
        ("ztp_generate", "ZTP 设计文件已生成", [m.get("ztp_file")] if m.get("ztp_file") else []),
        ("publish", "发布完成", []),
    ):
        if not _step_completed(state.get("steps") or [], step_key):
            continue
        arts = _artifact_items([p for p in paths if p], f"cv-res-{step_key}")
        body = ""
        if step_key == "publish" and m.get("publish_artifact_count"):
            body = f"已发布 {m['publish_artifact_count']} 个产物，写回活动进度。"
        elif step_key == "lld_integrate":
            body = f"已融合 {m.get('lld_planes_merged', 0)} 个平面。"
        children: list[SduiNode] = []
        if body:
            children.append(SduiTextNode(content=body, variant="body"))
        if arts:
            children.append(SduiArtifactGridNode(
                id=f"cv-art-{step_key}", mode="output", artifacts=arts))
        if children:
            out.append(SduiCardNode(id=f"cv-result-{step_key}", title=title, density="compact", children=children))
    return out


def _startup_guidance_body(state: dict[str, Any]) -> str:
    """启动引导文案：按真实已扫描输入件动态生成（对齐设计稿 start reducer）。"""
    found = _resolve_found_tags(state)
    auto_ready = [
        disp for tag, disp, _req, _desc in SD_INPUT_SLOTS
        if tag != "resource" and tag in found
    ]
    if auto_ready:
        names = "、".join(auto_ready)
        return (
            f"{names}已由系统自动检查并就绪。"
            "请上传「项目信息收集表」，我会自动校验后进入规划流水线。"
        )
    return (
        "端口连线表、设备信息表、设备位置表、测试用例由系统自动检查；"
        "若缺「项目信息收集表」请在上传后继续；齐备后将自动进入规划流水线。"
    )


def _build_conversation(state: dict[str, Any]) -> SduiStackNode | None:
    """AIDA 助手对话流（对齐 HTML ConversationPane · 纯读 state/logs/steps）。

    每个阶段一条独立气泡卡（不再合并进同一个「AIDA 助手」大卡）：返回一个透明 Stack，
    其每个子节点都是独立对话框，对齐设计稿「每条消息单独成框」。"""
    status_key, _ = _sd_overall_status(state)
    steps = state.get("steps") or []
    m = collect_metrics(state)
    project = state.get("project") or {}
    children: list[SduiNode] = []

    # idle：设计稿 cv-empty 引导（CTA 在 header，此处给说明）
    if not steps and status_key == "idle":
        children.append(_cv_bubble(
            None,
            "我可以读取项目仿真输出件，自动完成 IP 地址规划、网络互联 / 接入规划，"
            "并融合生成可下载的《LLD 设计文件》。",
        ))
        children.append(SduiTextNode(
            content="将自动检查端口连线表等仿真件，并提示你上传项目信息收集表",
            variant="caption", color="subtle",
        ))
        return SduiStackNode(id="sd-conversation", gap="sm", children=children)

    # ── 问答模式（聊天流）：AI 问候 → 输入件就绪引导 → 逐轮「用户提问 → 系统回答」──
    hitl = state.get("hitl") or {}
    chat = [t for t in (project.get("chat") or []) if str(t.get("text") or "").strip()]
    result_cards = _build_result_cards(state)
    input_done = _step_completed(steps, "input_check")
    plane_rec = _latest_step_record(steps, "plane_planning")
    plane_started = bool(plane_rec and plane_rec.get("status") in ("running", "completed"))
    cur_cmd = str(m.get("intent_command") or "")

    # 1) AI 问候（启动）
    if steps and status_key != "done":
        scenario = project.get("scenario") or "A3"
        children.append(_cv_bubble(
            f"系统设计助手已启动 · {scenario} 场景",
            _startup_guidance_body(state),
            bubble_id="cv-greeting",
        ))

    # 2) 输入件检查完成（仅首次进入规划前展示一次，避免续跑 / 多 Banner 重复刷屏）
    if input_done and not plane_started and not chat and status_key != "done":
        children.append(_cv_bubble(
            "输入件检查完成",
            "端口连线表与项目信息收集表校验通过，网络平面配置已读取。请选择要执行的规划任务。",
            bubble_id="cv-input-done",
        ))
        children.append(_cv_bubble(
            "选择规划任务",
            "请在下方对话框直接描述需求并发送即可执行规划，"
            "完成多项规划后可一键生成完整 LLD。",
            bubble_id="cv-plan-request",
        ))

    # 2.5) 已取消执行计划（设计稿 cancel_confirm）：提示重新选择 + 给出快捷指令
    if project.get("reselect_pending") and status_key != "done":
        children.append(_cv_bubble(
            "已取消执行计划",
            "可重新选择规划任务：在输入框直接描述需求"
            "（支持用「、」分隔一次输入多个任务）。",
            bubble_id="cv-reselect",
        ))

    # 3) 逐轮问答：每条用户指令 → 紧跟系统回答（最近一轮按当前实时状态回答）
    n = len(chat)
    for i, turn in enumerate(chat):
        text = str(turn.get("text") or "").strip()
        children.append(_cv_user_message(text, bubble_id=f"cv-user-{i}"))   # 用户气泡
        is_last = (i == n - 1)
        if not is_last:
            children.append(_cv_bubble(
                f"「{text}」已执行", "结果已并入输出件，可在右侧「输出件」查看 / 下载。",
                bubble_id=f"cv-bubble-done-{i}",
            ))
            continue
        # 最近一轮：失败优先于 running / HITL（避免 paused+failed 仍显示「请确认」）
        if _execution_failed(state, m):
            err_text = _round_error_text(state, m)
            log_hint = str(m.get("exec_log_path") or "").strip()
            body = err_text
            if log_hint and log_hint not in body:
                body += f"\n\n详细日志：{log_hint}"
            children.append(_cv_bubble(
                f"「{cur_cmd or text}」执行失败",
                body,
                tone="danger",
            ))
        elif status_key == "running":
            children.append(_cv_bubble("已识别", f"识别为「{cur_cmd or text}」，正在执行规划…"))
        elif hitl.get("step") == "plane_planning":
            queue_progress = m.get("queue_progress") or []
            done_cmds = [qp.get("command") for qp in queue_progress if qp.get("status") == "ok"]
            err_cmds = [qp.get("command") for qp in queue_progress if qp.get("status") == "error"]
            skip_cmds = [qp.get("command") for qp in queue_progress if qp.get("status") == "skipped"]
            if m.get("lld_status") == "skipped_no_input":
                reason = str(hitl.get("reason") or "").strip()
                log_hint = str(m.get("exec_log_path") or "").strip()
                body = reason or "未找到可融合的平面规划表，未能生成完整 LLD。"
                if log_hint and log_hint not in body:
                    body += f"\n\n详细日志：{log_hint}"
                children.append(_cv_bubble(
                    f"「{cur_cmd or text}」未能生成完整 LLD",
                    body,
                    tone="warning",
                ))
            elif skip_cmds and not done_cmds and not err_cmds:
                log_hint = str(m.get("exec_log_path") or "").strip()
                body = (
                    f"本批次 {len(skip_cmds)} 项因 007 缺少对应 sheet 已跳过。"
                    "可更换输入件后重试，或继续选择其它规划任务。"
                )
                if log_hint:
                    body += f"\n\n详细日志：{log_hint}"
                children.append(_cv_bubble(
                    f"「{cur_cmd or text}」部分平面已跳过",
                    body,
                    tone="warning",
                ))
            elif err_cmds and not done_cmds:
                err_text = _round_error_text(state, m)
                log_hint = str(m.get("exec_log_path") or "").strip()
                body = err_text
                if log_hint and log_hint not in body:
                    body += f"\n\n详细日志：{log_hint}"
                children.append(_cv_bubble(
                    f"「{cur_cmd or text}」执行失败",
                    body,
                    tone="danger",
                ))
            else:
                title = (
                    f"已完成 {len(done_cmds)} 项规划：{('、'.join(done_cmds))}"
                    if len(done_cmds) > 1 else f"「{cur_cmd or text}」已完成"
                )
                children.append(_cv_bubble(
                    title,
                    "结果已生成（见右侧「规划覆盖 / 输出件」）。尚未生成完整 LLD 设计文件，"
                    "可继续选择其它规划任务累积（可用「、」分隔一次输入多个），"
                    "或选择「生成完整 LLD 设计」融合后进入交付收尾。",
                ))
        elif hitl.get("step") == "exec_confirm":
            display_cmd = cur_cmd or text
            children.append(_cv_bubble(
                "已理解你的需求",
                f"识别为「{display_cmd}」，请确认执行计划。",
                bubble_id="cv-understood",
            ))
        elif hitl.get("step") == "intent_recognition" and hitl.get("ui") != "plan_request":
            children.append(_cv_bubble("已收到", f"已识别「{cur_cmd or text}」，请在下方卡片确认后继续。"))
        elif hitl.get("step") in ("stage_select", "publish_confirm"):
            children.append(_cv_bubble("已收到", "请在下方卡片确认后继续。"))
        elif result_cards:
            children.extend(result_cards)
        else:
            children.append(_cv_bubble("已收到", f"正在处理「{text}」…"))

    # 4) 无显式用户指令（默认完整交付）：直接展示结果（运行日志不在左侧会话展示）
    if not chat:
        if _execution_failed(state, m):
            err_text = _round_error_text(state, m)
            log_hint = str(m.get("exec_log_path") or "").strip()
            body = err_text
            if log_hint and log_hint not in body:
                body += f"\n\n详细日志：{log_hint}"
            children.append(_cv_bubble("执行失败", body, tone="danger"))
        children.extend(result_cards)

    # 5) 收尾：可选步跳过 / 发布完成
    if m.get("naming_status") == "skipped":
        children.append(_cv_bubble(
            "设备名称替换（可选）",
            "未提供设备清单 / 命名映射，可选步骤已跳过。",
        ))
    if status_key == "done":
        children.append(_cv_bubble(
            "交付完成",
            "收尾步骤已处理，LLD 设计已发布并写回项目活动进度，本次系统设计任务完成。",
            tone="success",
        ))

    if not children:
        return None
    return SduiStackNode(id="sd-conversation", gap="sm", children=children)


# ── 通用：整体进度（设计稿 tl-prog「设计进度」/ 覆盖计算复用）──────────────────────

def _progress_pct(state: dict[str, Any]) -> int:
    """整体设计进度 %：优先 overall_progress，否则按已完成后端步骤比例。"""
    overall = state.get("overall_progress") or 0
    if overall:
        try:
            return max(0, min(100, int(overall)))
        except (TypeError, ValueError):
            pass
    steps = state.get("steps") or []
    total = len(SD_STEP_ORDER)
    done = sum(1 for s in steps if s.get("status") == "completed")
    return round(done / total * 100) if total else 0


# ── 交付流程（设计稿 ProgressPanel.StepRail · 6 步蓝图 Stepper）────────────────────

def _agg_blueprint_status(state: dict[str, Any], keys: list[str]) -> str:
    """把一个蓝图步映射的后端 step（真实 status）聚合为 Stepper 状态。
    waiting → 等待；running → 进行中（含 HITL 挂起）；done → 已完成；error → 失败。"""
    by_key = {s.get("key", ""): s for s in (state.get("steps") or [])}
    hitl_step = (state.get("hitl") or {}).get("step")
    # 发布蓝图：publish 已完成且无 publish_confirm HITL → done（续跑 route_to 可能缺 confirm 记录）
    if set(keys) == {"publish_confirm", "publish"}:
        pub = by_key.get("publish")
        if pub and backend_status_to_sdui(pub.get("status", "")) == "done" and hitl_step != "publish_confirm":
            return "done"
    if hitl_step in keys:
        return "running"
    recs = [by_key[k] for k in keys if k in by_key]
    if not recs:
        return "waiting"
    raw = [r.get("status", "pending") for r in recs]
    sdui = [backend_status_to_sdui(s) for s in raw]
    if "error" in sdui:
        return "error"
    if "running" in sdui:
        return "running"
    # 全部映射步骤都齐备且完成 → done；部分完成 → 进行中
    if len(recs) == len(keys) and all(s == "done" for s in sdui):
        return "done"
    if any(s == "done" for s in sdui):
        return "running"
    return "waiting"


# 蓝图聚合状态（waiting/running/done/error）→ MacroStep 状态（done/running/pending）
_BLUEPRINT_TO_MACRO = {"waiting": "pending", "running": "running", "done": "done", "error": "running"}


def _build_stepper(state: dict[str, Any]) -> SduiCardNode:
    """交付流程（设计稿图4 · MacroStepRail）：6 步用户视角蓝图，状态由真实后端 step 聚合。
    可选步「设备名称替换」跳过时置 done 并以 hint 标注（前端据此显示「已跳过」）。
    线性推进：若后续蓝图步已在 running/done，则前面未完成的非可选步回填为 done。"""
    m = collect_metrics(state)
    steps: list[SduiMacroStep] = []
    current_id: str | None = None
    for bp_id, title, _hint, keys, optional in SD_BLUEPRINT:
        agg = _agg_blueprint_status(state, keys)
        macro_status = _BLUEPRINT_TO_MACRO.get(agg, "pending")
        # hint 仅保留「可选已跳过」标记（前端识别「已跳过」状态字）；不展示描述性副文案
        step_hint: str | None = None
        if optional and m.get("naming_status") == "skipped":
            macro_status = "done"
            step_hint = "可选步骤已跳过"
        if macro_status == "running" and current_id is None:
            current_id = bp_id
        steps.append(SduiMacroStep(
            id=bp_id, title=title, hint=step_hint, optional=optional or None,
            status=macro_status,  # type: ignore[arg-type]
        ))

    # 线性回填：交付流程按顺序推进，不应出现「后步进行中、前步仍等待」
    max_active_idx = -1
    for i, st in enumerate(steps):
        if st.status in ("running", "done"):
            max_active_idx = i
    if max_active_idx >= 0:
        for j in range(max_active_idx):
            st = steps[j]
            if st.status != "pending":
                continue
            if st.optional:
                steps[j] = SduiMacroStep(
                    id=st.id, title=st.title, hint="可选步骤已跳过",
                    optional=st.optional, status="done",
                )
            else:
                steps[j] = SduiMacroStep(
                    id=st.id, title=st.title, hint=None,
                    optional=st.optional, status="done",
                )

    return SduiCardNode(
        id="sd-stepper", title="交付流程",
        children=[SduiMacroStepRailNode(id="sd-steps", steps=steps, currentId=current_id)],
    )


# ── 运行态通栏（设计稿 RunningCard 概要 → StatusBanner）────────────────────────────

def _build_status_banner(state: dict[str, Any]) -> SduiStatusBannerNode | None:
    status_key, badge_text = _sd_overall_status(state)
    bn = _STATUS_TO_BANNER.get(status_key)
    if not bn:
        return None
    running = next((s for s in (state.get("steps") or []) if s.get("status") == "running"), None)
    hitl_step = (state.get("hitl") or {}).get("step")
    cur = (running or {}).get("key") or hitl_step or ""
    cur_name = _BACKEND_TO_BLUEPRINT.get(cur) or SD_STEP_NAMES.get(cur, cur)
    text = f"{badge_text}：{cur_name}" if cur_name else badge_text
    return SduiStatusBannerNode(
        id="sd-status-banner",
        items=[SduiStatusItem(status=bn, text=text)],  # type: ignore[arg-type]
    )


# ── 任务时间规划安排（设计稿 TaskTimelineStrip）──────────────────────────────────
# 计划/实际起止 + 设计进度。日期仅读 project.schedule（graph 写入）；无数据用「—」，不用 mock 日期。

def _sched_val(sched: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        v = sched.get(k)
        if v:
            return str(v)
    return None


def _build_schedule(state: dict[str, Any]) -> SduiTaskTimelineStripNode | None:
    """任务时间规划安排（设计稿图1 · TaskTimelineStrip）。
    日期读 project.schedule（skill.initial_project 锚定真实开工日写入）；
    剩余天数 / 状态标签 / 提示横幅由前端按浏览器当日派生（保持投影器纯函数）。
    实际结束日仅在整体完成时回填（actual_end = 计划结束作为占位，前端据 progressPct 判完成）。"""
    sched = (state.get("project") or {}).get("schedule") or {}
    if not isinstance(sched, dict):
        sched = {}
    planned_start = _sched_val(sched, "planned_start", "plannedStart")
    planned_end = _sched_val(sched, "planned_end", "plannedEnd")
    if not planned_start or not planned_end:
        return None  # 无排期不渲染（不造 mock 日期）

    pct = _progress_pct(state)
    status_key, _ = _sd_overall_status(state)
    actual_start = _sched_val(sched, "actual_start", "actualStart")
    actual_end = _sched_val(sched, "actual_end", "actualEnd")
    if not actual_end and status_key == "done":
        actual_end = planned_end  # 已完成但无显式完工日 → 用计划结束占位（前端显示「已完成」）

    return SduiTaskTimelineStripNode(
        id="sd-schedule",
        plannedStart=planned_start,
        plannedEnd=planned_end,
        actualStart=actual_start,
        actualEnd=actual_end,
        progressPct=pct,
    )


# ── 规划覆盖（设计稿 ProgressPanel.PlanningMatrix · 分组规划任务目录）───────────────
# 规划任务目录（完全对齐设计稿 PLAN_GROUPS：计算面 8 / 网络面 20 / 存储面 4 / 管理衍生件 3）。
# 这是「展示目录」（覆盖矩阵列出的全部规划任务）。点亮逻辑严格对齐设计稿：
#   执行了哪个规划指令 + 输出路径中读到对应产物文件 → 点亮「该指令」对应的目录框（一对一）。
# 数据源 = plane_planning 落盘累积的 metrics.plan_commands（指令名→产物，已校验文件仍存在），
# 不使用设计稿 mock 状态，也不再按粗粒度平面聚合（避免一个聚合平面点亮整组指令的过度点亮）。
SD_PLAN_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("计算面", (
        "计算样本面地址规划", "计算管理面地址规划", "计算管存面地址规划", "计算业务面地址规划",
        "计算参数面地址规划", "计算超平面地址规划", "计算带外管理地址规划", "灵衢带外管理地址规划",
    )),
    ("网络面", (
        "网络业务地址规划", "网络设备ASN规划", "交换机MLAG规划",
        "计算业务面互联规划", "计算管理面互联规划", "计算管存面互联规划", "计算样本面互联规划", "计算参数面互联规划",
        "计算管理面接入规划", "计算业务面接入规划", "计算样本面接入规划", "计算参数面接入规划", "计算管存面接入规划",
        "存储管理面互联规划", "存储业务面互联规划", "存储样本面互联规划",
        "存储管理面接入规划", "存储业务面接入规划", "存储样本面接入规划", "网络带外管理地址规划",
    )),
    ("存储面", (
        "存储带外管理面地址规划", "存储管理面地址规划", "存储业务面地址规划", "存储样本面地址规划",
    )),
    ("管理 / 衍生件", (
        "CCAE 规划", "NCE 规划", "DME 规划",
    )),
)

def _norm_plan(s: str) -> str:
    """归一化规划名：去空格 + 去连接词「面」。
    使后端 L3 指令名与设计稿目录项可精确对齐（如指令「存储带外管理地址规划」↔
    目录「存储带外管理面地址规划」、指令「计算业务面互联规划」↔ 目录同名）。"""
    return str(s).replace(" ", "").replace("面", "")


def _build_catalog_norm_index() -> dict[str, list[str]]:
    """目录项归一名 → 原目录项（同名聚合，便于按指令名反查应点亮的目录框）。"""
    idx: dict[str, list[str]] = {}
    for _grp, items in SD_PLAN_GROUPS:
        for it in items:
            idx.setdefault(_norm_plan(it), []).append(it)
    return idx


_CATALOG_NORM_INDEX: dict[str, list[str]] = _build_catalog_norm_index()


def _match_catalog_items(command: str) -> list[str]:
    """规划指令名 → 命中的目录项（先精确归一匹配，未命中再退化为包含匹配）。"""
    nc = _norm_plan(command)
    if not nc:
        return []
    hit = _CATALOG_NORM_INDEX.get(nc)
    if hit:
        return list(hit)
    res: list[str] = []
    for nk, items in _CATALOG_NORM_INDEX.items():
        if nc == nk or nc in nk or nk in nc:
            res.extend(items)
    return res


def _catalog_file_keyword_groups(name: str) -> list[list[str]]:
    """目录项 → 产物文件名关键词组（命中任一组即视为该目录项已有产物文件）。
    每组内所有词须同时出现在某个归一化文件名中。对齐真实产物命名：
    地址面→「地址 / 网段」、互联→「互联 / 互连」、接入→「接入」；
    超平面产物名省略「计算」前缀且为「超平面网络规划.xlsx」，单独以「超平」兜底。"""
    n = name.replace(" ", "").replace("面", "")
    if "ASN" in n:
        return [["ASN"]]
    if "MLAG" in n:
        return [["MLAG"]]
    if "CCAE" in n:
        return [["CCAE"]]
    if "NCE" in n:
        return [["NCE"]]
    if "DME" in n:
        return [["DME"]]
    if "互联" in n:
        plane, cats = n[: n.index("互联")], ("互联", "互连")
    elif "接入" in n:
        plane, cats = n[: n.index("接入")], ("接入",)
    else:  # 地址规划
        plane = n.replace("地址规划", "").replace("地址", "").replace("规划", "")
        cats = ("地址", "网段")
    groups = [[plane, c] for c in cats]
    if "超平" in plane:
        groups.append(["超平"])
    return groups


_CATALOG_FILE_KW: dict[str, list[list[str]]] = {
    it: _catalog_file_keyword_groups(it)
    for _grp, items in SD_PLAN_GROUPS for it in items
}


# 规划输出件去重：同一平面 legacy 名与 A3 名并存时只展示 A3 版本
_PLAN_OUTPUT_CANONICAL: dict[str, str] = {
    "超平面网络规划.xlsx": "A3超平面网络规划.xlsx",
}


def _dedupe_plan_output_paths(paths: list[str]) -> list[str]:
    by_name: dict[str, str] = {}
    for p in paths:
        by_name[os.path.basename(p)] = p
    for legacy, canonical in _PLAN_OUTPUT_CANONICAL.items():
        if legacy in by_name and canonical in by_name:
            del by_name[legacy]
    return list(by_name.values())


def _scan_output_dir_rel() -> list[str]:
    """直接扫描 ProjectData/Output（磁盘真值）→ 相对 work_root 的产物路径列表。
    作为 state.files['out::*'] 的兜底：确保「输出路径里有哪些文件，前端就展示 / 点亮哪些」，
    不受 full_restart 后当前 run 的 state 尚未回填 out:: 影响（子 skill 产物始终可见）。"""
    try:
        from .pipelines.path_manifest import abs_artifacts_dir, resolve_data_root

        root = resolve_data_root()
        out_dir = abs_artifacts_dir()
        if not out_dir.is_dir():
            return []
        keep_ext = (".xlsx", ".xls", ".docx", ".doc", ".pdf", ".zip")
        skip_meta = {"run_meta.csv", "layer_detection.txt", "scenario_detection.txt"}
        skip_name_fragments = ("计算参数面网段规划",)
        res: list[str] = []
        for p in sorted(out_dir.rglob("*")):
            if not p.is_file() or p.name.startswith("~$") or p.name in skip_meta:
                continue
            if any(frag in p.name for frag in skip_name_fragments):
                continue
            if p.suffix.lower() not in keep_ext:
                continue
            try:
                res.append(str(p.relative_to(root)).replace("\\", "/"))
            except Exception:
                pass
        return res
    except Exception:
        return []


def _all_output_paths(state: dict[str, Any]) -> list[str]:
    """汇集输出路径下全部产物（相对 work_root）：state.files['out::*' / 'plane_*'] ∪ 磁盘扫描。
    磁盘扫描兜底保证「Output 有什么就展示什么」，与设计稿/需求一致。"""
    files = state.get("files") or {}
    paths: list[str] = []
    for k, v in files.items():
        if isinstance(v, str) and v and (k.startswith("out::") or k.startswith("plane_")):
            paths.append(v)
    paths.extend(_scan_output_dir_rel())
    # 按 basename 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        bn = os.path.basename(p)
        if bn in seen:
            continue
        seen.add(bn)
        out.append(p)
    return out


def _output_basenames(state: dict[str, Any]) -> list[str]:
    """输出路径全部产物 → 归一化文件名（去空格 + 去「面」），供规划覆盖矩阵按文件点亮。"""
    names: list[str] = []
    for p in _all_output_paths(state):
        base = os.path.basename(p)
        if base.lower().endswith((".xlsx", ".xls", ".csv")):
            names.append(base.replace(" ", "").replace("面", ""))
    return names


def _catalog_status_map(state: dict[str, Any]) -> dict[str, str]:
    """目录任务名 → 状态（done/running/pending）· 全部来自真实后端信号（无 mock）。

    点亮逻辑（严格对齐设计稿 & 需求②）：输出路径（ProjectData/Output）里有哪个规划产物文件，
    就点亮对应的指令框。主信号 = 扫描 Output 文件名按平面 + 类别关键词匹配目录项；
    辅信号 = metrics.plan_commands（已执行且产物仍在的指令账本，用于互联/接入等聚合产物的精确点亮）。
    """
    m = collect_metrics(state)
    out: dict[str, str] = {}

    # 1) 输出路径已生成的产物文件 → 点亮对应目录框（done）· 需求②核心
    out_names = _output_basenames(state)
    if out_names:
        for item, groups in _CATALOG_FILE_KW.items():
            for grp in groups:
                if any(all(tok in fn for tok in grp) for fn in out_names):
                    out[item] = "done"
                    break

    # 2) 已执行且产物仍在输出路径的规划指令 → 按指令名精确点亮（补充互联/接入聚合产物）
    for rec in (m.get("plan_commands") or []):
        if not isinstance(rec, dict):
            continue
        if rec.get("status") != "ok" or not rec.get("files"):
            continue
        for it in _match_catalog_items(str(rec.get("command") or "")):
            out.setdefault(it, "done")

    # 3) 兼容旧信号：project.completed（执行过的规划命令名）→ 点亮（不覆盖已 done）
    completed = (state.get("project") or {}).get("completed") or state.get("completed") or []
    for c in completed:
        for it in _match_catalog_items(str(c or "")):
            out.setdefault(it, "done")

    # 4) 本批次失败指令 → 目录框标记 error（不覆盖已 done）
    for rec in (m.get("command_results") or []):
        if not isinstance(rec, dict) or rec.get("status") != "error":
            continue
        for it in _match_catalog_items(str(rec.get("command") or "")):
            out.setdefault(it, "error")

    # 5) plane_planning 正在执行的单条指令 → 其目录框标记「执行中」（不覆盖已 done/error）
    plane_running = any(
        s.get("key") == "plane_planning" and s.get("status") == "running"
        for s in (state.get("steps") or [])
    )
    if plane_running:
        for it in _match_catalog_items(str(m.get("intent_command") or "")):
            out.setdefault(it, "running")
    return out


def _build_coverage(state: dict[str, Any]) -> SduiCardNode | None:
    """规划覆盖（设计稿图3 · PlaneMatrix）：完整列出 4 组规划任务目录（对齐设计稿 PLAN_GROUPS）。
    流程启动后即展示全部任务（默认「待执行」pending），随真实后端进度逐个点亮
    （done/running）。不展示覆盖率进度条（按需求删除）。"""
    if not (state.get("steps") or state.get("hitl")):
        return None
    cat_status = _catalog_status_map(state)
    cells: list[SduiPlaneCell] = []
    for group, items in SD_PLAN_GROUPS:
        for name in items:
            st = cat_status.get(name, "pending")
            cells.append(SduiPlaneCell(
                label=name,
                status=st if st in _PLANE_STATUS_OK else "pending",
                group=group,
            ))
    return SduiCardNode(
        id="sd-coverage", title="规划覆盖",
        children=[SduiPlaneMatrixNode(id="sd-plane-matrix", cells=cells)],
    )


# ── 风险与提示（设计稿 ReminderCard / callout → RiskList 高/中/低）─────────────────
# 后端「风险」表现为非阻断 warning（资源不足 / 缺平面 / ZTP 自动补齐 / 降级产物）。

_HIGH_HINTS = ("不足", "失败", "错误", "缺失", "未生成", "无法")
_LOW_HINTS = ("自动补齐", "降级", "manifest", "跳过", "占位")


def _classify_level(text: str) -> str:
    if any(h in text for h in _HIGH_HINTS):
        return "high"
    if any(h in text for h in _LOW_HINTS):
        return "low"
    return "mid"


def _collect_warnings(state: dict[str, Any]) -> list[str]:
    m = collect_metrics(state)
    # publish_warnings 已聚合 lld+ztp+manifest；未到 publish 时退回各步 warning 并集
    if m.get("publish_warnings"):
        return [str(w) for w in m["publish_warnings"]]
    out: list[str] = []
    for k in ("plane_warnings", "plane_skip_notes", "ztp_warnings"):
        out.extend(str(w) for w in (m.get(k) or []) if str(w).strip())
    # LLD 已成功融合时不展示历史失败文案（避免 state 残留 lld_warnings 误报）
    if m.get("lld_status") != "ok":
        out.extend(str(w) for w in (m.get("lld_warnings") or []) if str(w).strip())
    if m.get("lld_status") == "skipped_no_input":
        out.append(
            "未生成完整 LLD：007 缺少对应 sheet 或无可融合平面规划表。"
            "请检查输入件或先执行地址规划。"
        )
    return out


def _build_risk_list(state: dict[str, Any]) -> SduiRiskListNode | None:
    warnings = _collect_warnings(state)
    if not warnings:
        return None
    order = {"high": 0, "mid": 1, "low": 2}
    items = [SduiRiskItem(title=w, level=_classify_level(w)) for w in warnings]  # type: ignore[arg-type]
    items.sort(key=lambda r: order.get(r.level, 9))
    return SduiRiskListNode(id="sd-risk", title=f"风险与提示（{len(items)} 条）", items=items)


# ── 输入件清单（设计稿 InputsPanel · 自动/手动 · 必需 + 文件名 → Checklist）──────────

def _build_input_slots(state: dict[str, Any]) -> SduiCardNode | None:
    """输入件清单（设计稿图2「输入件」页签 · InputSlotList · run 启动后即展示，数据来自 graph state + 磁盘）。"""
    if not (state.get("run_id") or state.get("steps") or state.get("hitl")):
        return None
    return SduiCardNode(
        id="sd-inputs", title="输入件清单",
        children=[
            _build_input_slot_list(
                state, "sd-inputs-list",
                upload_step_id="input_check", upload_purpose="hitl_input_check",
            ),
            SduiTextNode(
                content=(
                    f"仿真三表扫描：{_SIM_SCAN_DIR}；测试用例扫描：{read_scan_dir_for_tag('Test_Case')}；"
                    f"上传目录：{_INPUT_CHECK_DIR}。"
                    "仿真输出件（端口连线表 / 设备信息表 / 设备位置表 / 测试用例表）由系统自动检查就绪；"
                    "项目信息收集表需手动上传，是地址规划的数据底座。"
                ),
                variant="caption", color="subtle",
            ),
        ],
    )


# ── 输出件（设计稿 OutputsPanel · 关键输出件 vs 规划输出件；空态 EmptyState）────────

def _artifact_items(
    paths: list[str],
    prefix: str,
    *,
    highlight_ids: set[str] | None = None,
) -> list[SduiArtifactItem]:
    out: list[SduiArtifactItem] = []
    seen: set[str] = set()
    highlight_ids = highlight_ids or set()
    for i, p in enumerate(paths):
        if not p or not isinstance(p, str) or p in seen:
            continue
        seen.add(p)
        label = os.path.basename(p)
        art_id = (
            "art-testcase"
            if any(k in label for k in ("测试用例", "验收用例", "Test_Case", "008"))
            else f"{prefix}-{i}"
        )
        highlighted = art_id in highlight_ids
        if art_id == "art-testcase" and highlighted:
            display = label if any(k in label for k in ("测试用例", "验收用例")) else f"测试用例 · {label}"
        else:
            display = label
        out.append(SduiArtifactItem(
            id=art_id,
            label=display,
            path=p,
            kind=artifact_kind(p),  # type: ignore[arg-type]
            status="ready",
            highlight=highlighted or None,
            badge="本环节生成" if highlighted else None,
        ))
    return out


def _resolve_highlight_artifact_ids(state: dict[str, Any]) -> set[str]:
    """对齐设计稿 highlightArtifacts · test_check 时高亮 art-testcase。"""
    project = state.get("project") or {}
    hitl = state.get("hitl") or {}
    ids = {str(x) for x in (project.get("highlight_artifacts") or []) if x}
    if hitl.get("step") == "publish_confirm" and hitl.get("ui") == "test_check":
        ids.add("art-testcase")
    return ids


def _is_test_case_basename(name: str) -> bool:
    return any(k in name for k in ("测试用例", "验收用例", "Test_Case", "008"))


def _input_artifact_paths(state: dict[str, Any]) -> set[str]:
    """state.files 中 input_* 登记的路径（输入件，不得混入输出件面板）。"""
    files = state.get("files") or {}
    paths: set[str] = set()
    for k, v in files.items():
        if not k.startswith("input_") or not isinstance(v, str) or not v.strip():
            continue
        paths.add(v.replace("\\", "/"))
    return paths


def _should_show_test_case_in_outputs(state: dict[str, Any]) -> bool:
    """测试用例属输入件；仅「检查测试用例」拷贝到 Output 后才在关键输出件展示。"""
    project = state.get("project") or {}
    confs = project.get("confirmations") or {}
    if confs.get("publish_test_check_pending") or confs.get("publish_checked"):
        return True
    if str(project.get("test_case_output") or "").strip():
        return True
    files = state.get("files") or {}
    return bool(str(files.get("test_case_file") or "").strip())


# 关键输出件判定关键词（其余 Output 产物归「规划输出件」）
_KEY_OUTPUT_HINTS = (
    "LLD", "lld", "ZTP", "ztp", "开局", "设备名称", "命名对照",
    "TestCase", "test_case", "exec_summary", "执行摘要",
)


def _classify_output(path: str) -> str:
    name = os.path.basename(path)
    if _is_test_case_basename(name):
        return "plan"
    return "key" if any(h in path or h in name for h in _KEY_OUTPUT_HINTS) else "plan"


def _collect_outputs(state: dict[str, Any]) -> tuple[list[str], list[str]]:
    """汇集「全部已生成文件」并分类 关键/规划。
    来源（按预览/下载友好度优先）：Output 目录全量扫描（files['out::<rel>']，相对路径）
    → 各平面产物（files['plane_*']）→ 显式关键产物（metrics.lld_file/ztp_file + 执行摘要）。
    输入件（files['input_*']）不得出现在输出件面板；测试用例仅在发布前检查环节拷贝后才展示。"""
    m = collect_metrics(state)
    files = state.get("files") or {}
    input_paths = _input_artifact_paths(state)
    show_test_case = _should_show_test_case_in_outputs(state)
    explicit_key_names: set[str] = set()
    explicit: list[str] = []
    for k in ("lld_file", "ztp_file"):
        v = m.get(k) or files.get(k)
        if v and isinstance(v, str):
            explicit.append(v)
            explicit_key_names.add(os.path.basename(v))
    for fk in ("test_case_file", "exec_summary"):
        if fk == "test_case_file" and not show_test_case:
            continue
        v = files.get(fk)
        if v and isinstance(v, str):
            explicit.append(v)
            explicit_key_names.add(os.path.basename(v))
    # 输出路径全部产物（state.files ∪ 磁盘扫描兜底）：保证子 skill 产物始终展示在「规划输出件」
    scanned = _all_output_paths(state)

    key_map: dict[str, str] = {}
    plan_map: dict[str, str] = {}
    seen: set[str] = set()
    for p in [*scanned, *explicit]:   # 相对路径(scan) 优先去重，便于预览/下载
        bn = os.path.basename(p)
        norm = p.replace("\\", "/")
        if norm in input_paths:
            continue
        if _is_test_case_basename(bn) and not show_test_case:
            continue
        if bn in seen:
            continue
        seen.add(bn)
        if (
            bn in explicit_key_names
            or _classify_output(p) == "key"
            or (show_test_case and _is_test_case_basename(bn))
        ):
            key_map[bn] = p
        else:
            plan_map[bn] = p
    key_paths = [key_map[k] for k in sorted(key_map)]
    plan_paths = _dedupe_plan_output_paths([plan_map[k] for k in sorted(plan_map)])
    return key_paths, plan_paths


def _build_key_outputs(state: dict[str, Any]) -> SduiCardNode | None:
    """关键输出件：完整 LLD / ZTP 开局文件 / 验收用例 / 设备名称表 / 执行摘要。"""
    highlight_ids = _resolve_highlight_artifact_ids(state)
    key_paths, _ = _collect_outputs(state)
    arts = _artifact_items(key_paths, "sd-key-art", highlight_ids=highlight_ids)
    if not arts:
        return None
    return SduiCardNode(
        id="sd-key-outputs", title="关键输出件",
        children=[SduiArtifactGridNode(id="sd-key-grid", mode="output", artifacts=arts)],
    )


def _build_plan_outputs(state: dict[str, Any]) -> SduiCardNode | None:
    """规划输出件：各平面规划产物（地址 / 互联 / 接入规划表等，全量累积展示）。"""
    _, plan_paths = _collect_outputs(state)
    arts = _artifact_items(plan_paths, "sd-plan-art")
    if not arts:
        return None
    return SduiCardNode(
        id="sd-plan-outputs", title="规划输出件",
        children=[SduiArtifactGridNode(id="sd-plan-grid", mode="output", artifacts=arts)],
    )


def _build_outputs_empty(state: dict[str, Any], has_output: bool) -> SduiEmptyStateNode | None:
    """流程已启动但还没有任何产物时，给「暂无输出件」空态（对齐设计稿空面板）。"""
    if has_output or not (state.get("steps") or []):
        return None
    return SduiEmptyStateNode(
        id="sd-outputs-empty", title="暂无输出件",
        subtitle="完成任意规划任务后，结果文件将在此汇总，可随时下载或融合为完整 LLD。",
    )


# ── 三页签容器（设计稿图2 · ArtifactsPanel：进度 / 输入件 / 输出件）────────────────

def _count_output_artifacts(*nodes: SduiCardNode | None) -> int:
    """统计输出件卡内 ArtifactGrid 的产物总数（供页签角标）。"""
    n = 0
    for card in nodes:
        if not card:
            continue
        for child in card.children or []:
            if isinstance(child, SduiArtifactGridNode):
                n += len(child.artifacts or [])
    return n


def _build_tab_group(state: dict[str, Any]) -> SduiTabGroupNode | None:
    """ArtifactsPanel 三页签：进度（交付流程 + 规划覆盖 + 风险）/ 输入件 / 输出件（带角标）。
    activeTab 由后端引导：已完成且有产物→输出件；否则进度。"""
    # run 已创建但首步尚未写入 steps 时也要展示交付台（避免右侧仅 header/时间条而显空白）
    if not (state.get("run_id") or state.get("steps") or state.get("hitl")):
        return None
    status_key, _ = _sd_overall_status(state)

    # ── 进度页 ──
    progress_children: list[SduiNode] = []
    banner = _build_status_banner(state)
    if banner:
        progress_children.append(banner)
    progress_children.append(_build_stepper(state))            # 交付流程（图4）
    coverage = _build_coverage(state)
    if coverage:
        progress_children.append(coverage)                     # 规划覆盖（图3）

    # ── 输入件页 ──
    inputs_children: list[SduiNode] = []
    inputs_card = _build_input_slots(state)
    if inputs_card:
        inputs_children.append(inputs_card)

    # ── 输出件页 ──
    key_outputs = _build_key_outputs(state)
    plan_outputs = _build_plan_outputs(state)
    out_count = _count_output_artifacts(key_outputs, plan_outputs)
    outputs_children: list[SduiNode] = []
    if key_outputs:
        outputs_children.append(key_outputs)
    if plan_outputs:
        outputs_children.append(plan_outputs)
    if not outputs_children:
        empty = _build_outputs_empty(state, False)
        if empty:
            outputs_children.append(empty)

    active = "progress"
    project = state.get("project") or {}
    hitl = state.get("hitl") or {}
    focus_token: int | None = None
    outputs_view = int(project.get("request_outputs_view") or 0)
    progress_view = int(project.get("request_progress_view") or 0)
    # 默认停留「进度」；仅显式引导才切页（检查测试用例 → 输出件；确认后 → 进度）
    if hitl.get("step") == "publish_confirm" and hitl.get("ui") == "test_check":
        active = "outputs"
        if outputs_view > 0:
            focus_token = outputs_view
    elif (
        progress_view > 0
        and hitl.get("step") == "publish_confirm"
        and hitl.get("ui") != "test_check"
    ):
        active = "progress"
        focus_token = progress_view

    return SduiTabGroupNode(
        id="sd-artifacts",
        activeTab=active,
        focusToken=focus_token,
        tabs=[
            SduiTabPanel(id="progress", label="进度", children=progress_children),
            SduiTabPanel(id="inputs", label="输入件", children=inputs_children),
            SduiTabPanel(
                id="outputs", label="输出件",
                badge=out_count or None,
                children=outputs_children,
            ),
        ],
    )


# ── 主入口 ──────────────────────────────────────────────────────────────────────

def project(state: dict[str, Any]) -> dict[str, Any]:
    """SkillState → SduiDocument JSON-compatible dict（严格对齐《系统设计工作台-周二版》）。

    布局（对齐设计稿左右分栏 · 左侧会话框 + 右侧面板）：
      header（AppBar）
      → sd-conversation（左侧 ClawRail 渲染 · 对话流 ①）
      → hitl-card（左侧 ClawRail 渲染 · 可交互弹框 ①）
      → 任务时间规划安排（TaskTimelineStrip · 图1 ②）
      → ArtifactsPanel 三页签（TabGroup · 图2 ③）
          · 进度：交付流程（MacroStepRail · 图4 ⑤）+ 规划覆盖（PlaneMatrix · 图3 ④）+ 风险
          · 输入件：InputSlotList
          · 输出件：关键 / 规划输出件（带角标）
    """
    nodes: list[SduiNode] = [
        build_header(state, default_name="系统设计 · 交付作业", cta_map=SD_CTA, step_order=SD_STEP_ORDER),
    ]

    # 对话流（左侧 ClawRail 同步渲染 sd-conversation / hitl-card）
    conv = _build_conversation(state)
    if conv:
        nodes.append(conv)

    hitl = _build_hitl_card(state) if not state.get("error") else None
    if hitl:
        nodes.append(hitl)

    # 任务时间规划安排（图1 · 顶部自含头部的时间条，不再包外层卡）
    schedule = _build_schedule(state)
    if schedule:
        nodes.append(schedule)

    # 三页签面板（图2/3/4/输入输出）
    tabs = _build_tab_group(state)
    if tabs:
        nodes.append(tabs)

    meta: dict[str, Any] = {
        "skill": "system_design",
        "run_id": state.get("run_id", ""),
    }
    if state.get("error"):
        meta["error"] = str(state["error"])
        meta["phase"] = "error"
    m_end = collect_metrics(state)
    if m_end.get("exec_log_path"):
        meta["exec_log_path"] = m_end["exec_log_path"]

    doc = SduiDocument(
        root=SduiStackNode(id="system-design-root", gap="sm", children=nodes),
        meta=meta,
    )
    return dump_sdui_json(doc)
