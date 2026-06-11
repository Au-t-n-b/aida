"""compat_table · 设备信息表 → 设备适配信息表（移植 jmfz/api_adapt/build_compat_table.py）

从《建模仿真设备信息表》（含 【...】 章节的原始 md）调仿真 API（经 SimApiClient），
模糊匹配设备型号 + 板卡评分 → 生成《建模仿真设备适配信息表》。

与原脚本差异（适配 AIDA）：
- HTTP 走 SimApiClient（统一出口 + dry-run + 留痕），不再裸用 requests。
- 离线/ dry-run（catalog 为空）时：若给了 fixture_path 则直接复用样本适配表，保证骨架可跑。
- print → emit 回调；去掉 CLI main。
纯匹配/解析/渲染函数逐字保留原逻辑（已实跑校准）。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable

# ═══ 内联知识 · A3 超节点组合仿真模型锚定表 ═══
_A3_COMBO_TABLE: list[dict] = [
    {"servers": 2,  "lingqu": 0,  "series": "800I", "cooling": "air",    "model": "A3 800I 风冷16卡 B2B"},
    {"servers": 2,  "lingqu": 0,  "series": "800T", "cooling": "air",    "model": "A3 800T 风冷16卡 B2B"},
    {"servers": 8,  "lingqu": 14, "series": "800I", "cooling": "air",    "model": "A3 800I 风冷64卡"},
    {"servers": 8,  "lingqu": 14, "series": "800T", "cooling": "air",    "model": "A3 800T 风冷64卡"},
    {"servers": 12, "lingqu": 14, "series": "800I", "cooling": "air",    "model": "A3 800I 风冷96卡"},
    {"servers": 12, "lingqu": 14, "series": "800T", "cooling": "air",    "model": "A3 800T 风冷96卡"},
    {"servers": 24, "lingqu": 28, "series": "800I", "cooling": "air",    "model": "A3 800I 风冷192卡"},
    {"servers": 24, "lingqu": 28, "series": "800T", "cooling": "air",    "model": "A3 800T 风冷192卡"},
    {"servers": 48, "lingqu": 56, "series": "800I", "cooling": "air",    "model": "A3 800I 风冷384卡"},
    {"servers": 48, "lingqu": 56, "series": "800T", "cooling": "air",    "model": "A3 800T 风冷384卡"},
    {"servers": 8,  "lingqu": 14, "series": "900",  "cooling": "liquid", "model": "A3 900 液冷64卡"},
    {"servers": 12, "lingqu": 14, "series": "900",  "cooling": "liquid", "model": "A3 900 液冷96卡"},
    {"servers": 48, "lingqu": 56, "series": "900",  "cooling": "liquid", "model": "A3 900 液冷384卡"},
    {"servers": 48, "lingqu": 56, "series": "900",  "cooling": "liquid", "extra_planes": True,
     "model": "A3 900 液冷384卡+参数面+管存面"},
]


def _server_series(model: str) -> str:
    m = str(model or "")
    if re.search(r"800I", m, re.I):
        return "800I"
    if re.search(r"800T", m, re.I):
        return "800T"
    return "900"


def resolve_sim_combo_model(server_model: str, server_qty: int, lingqu_qty: int,
                             extra_planes: bool = False) -> str:
    """按服务器型号/台数/灵衢数量查锚定表，未命中则按台数×8卡推导。"""
    series = _server_series(server_model)
    cooling = "liquid" if series == "900" else "air"
    for entry in _A3_COMBO_TABLE:
        if (entry["servers"] == server_qty
                and entry["lingqu"] == lingqu_qty
                and entry["series"] == series
                and entry["cooling"] == cooling
                and bool(entry.get("extra_planes")) == extra_planes):
            return entry["model"]
    cards = server_qty * 8
    if cards > 0:
        return f"A3 900 液冷{cards}卡" if cooling == "liquid" else f"A3 {series} 风冷{cards}卡"
    return ""


# ═══ 板卡定稿名规则（desc → 仿真型号）═══
_CARD_LABEL_RULES: list[dict] = [
    {"desc_all": ["200Gb RoCE", "I/O模块"],    "label": "PCIe 2x200GE-横"},
    {"desc_all": ["25Gb ETH", "I/O模块"],      "label": "PCIe 2x25GE-横"},
    {"desc_all": ["40Gb/100Gb ETH"],           "label": "存储2口100GE-竖接口卡"},
    {"desc_all": ["100GE(ConnectX"],           "label": "PCIe 2x100GE-横"},
    {"desc_all": ["10/25GE"],                  "label": "PCIe 2x25GE-横"},
    {"desc_all": ["100GE", "两端口"],          "label": "PCIe 2x100GE-横"},
    {"desc_all": ["100GE", "双端口"],          "label": "PCIe 2x100GE-横"},
    {"desc_all": ["25GE",  "双端口"],          "label": "PCIe 2x25GE-横"},
    {"desc_all": ["25GE",  "两端口"],          "label": "PCIe 2x25GE-横"},
    {"desc_all": ["200GE", "QSFP56"],          "label": "PCIe 2x200GE-横"},
    {"desc_all": ["10GE",  "板载"],            "label": "板载10GE"},
    {"desc_all": ["25GE",  "板载"],            "label": "板载25GE"},
    {"desc_all": ["存储控制框"],               "label": "控制框"},
    {"desc_all": ["控制框"], "desc_any": ["8U", "双控"],  "label": "控制框"},
    {"desc_any": ["Palm硬盘", "硬盘单元", "SSD", "NVMe"], "label": "存储硬盘单元"},
]


def resolve_card_label(desc: str) -> str:
    d = str(desc or "")
    for rule in _CARD_LABEL_RULES:
        must = rule.get("desc_all", [])
        any_of = rule.get("desc_any", [])
        if all(k in d for k in must):
            if not any_of or any(k in d for k in any_of):
                return rule["label"]
    return ""


# ═══ 设备型号匹配 ═══
_BOQ_VERSION_SUFFIX_RE = re.compile(r"\s+V\d+R\d+[A-Za-z0-9._-]*\s*$", re.IGNORECASE)
_XH_CHASSIS_RE = re.compile(r"(XH\d{4,5}-\d+)", re.IGNORECASE)
_CE_FAMILY_RE = re.compile(r"(CE\d{4,5})")


def _norm_token(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum())


def _strip_version(model: str) -> str:
    text = str(model or "").strip()
    return _BOQ_VERSION_SUFFIX_RE.sub("", text).strip() if text else text


def _model_of(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("model") or item.get("name") or "")
    return str(item)


def match_device_model(target: str, candidates: list[Any]) -> str:
    """BoQ 设备型号模糊匹配到 queryDeviceModel 目录。精确→XH→CE族→token。"""
    target = str(target or "").strip()
    if not target or not candidates:
        return ""
    target_base = _strip_version(target)
    t_norm = _norm_token(target_base)

    for item in candidates:
        m = _model_of(item)
        if m == target or m == target_base:
            return m

    xh_m = _XH_CHASSIS_RE.search(target_base)
    if xh_m:
        xh_tok = xh_m.group(1).upper()
        xh_norm = _norm_token(xh_tok)
        for item in candidates:
            m = _model_of(item)
            if m.upper().startswith(xh_tok) or xh_norm in _norm_token(m):
                return m

    ce_m = _CE_FAMILY_RE.search(target_base.upper())
    if ce_m:
        ce_tok = ce_m.group(1)
        for item in candidates:
            m = _model_of(item)
            if m.upper() == ce_tok:
                return m
        if ce_tok.startswith("CE168"):
            xs = re.search(r"-X(\d+)", target_base, re.IGNORECASE)
            if xs:
                preferred = f"CE168{xs.group(1)}"
                for item in candidates:
                    m = _model_of(item)
                    if m.upper().startswith(preferred):
                        return m
        for item in candidates:
            m = _model_of(item)
            if ce_tok in m.upper() and not m.lower().endswith("-import"):
                return m
        for item in candidates:
            m = _model_of(item)
            if ce_tok in m.upper():
                return m

    for item in candidates:
        m = _model_of(item)
        mn = _norm_token(m)
        if t_norm and (t_norm in mn or mn in t_norm):
            return m
    return ""


# ═══ 板卡匹配（多维评分）═══
def flatten_cards(slot_payload: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(slot_payload, list):
        return out
    for slot in slot_payload:
        if not isinstance(slot, dict):
            continue
        for card in slot.get("slot_mapping", []) or []:
            model = str(card.get("model") or "").strip()
            if not model:
                continue
            out.append({"model": model, "description": str(card.get("description") or "").strip()})
    return out


def parse_boq_spec(merged: str) -> dict[str, Any]:
    t = merged
    u = merged.upper()
    spec: dict[str, Any] = {
        "ports": None, "speed": None,
        "storage_vertical": False, "pcie_horizontal": False, "cex_substring": None,
    }
    cx = re.search(r"(CEX8-[A-Z0-9]+|CEX-L[0-9A-Z]+|CE98[A-Z0-9-]+|CE168[A-Z0-9-]+|CE\d{4,5}[A-Z0-9-]*)", u)
    if cx:
        spec["cex_substring"] = cx.group(1)
    m400 = re.search(r"(\d+)\s*端口\s*400\s*G[E]?", t, re.I)
    if m400:
        spec["ports"] = int(m400.group(1))
        spec["speed"] = "400GE"
    elif re.search(r"(2口|两端口|双端口|2端口|2\s*[xX]\s*)", t):
        spec["ports"] = 2
    elif re.search(r"(4口|四端口|4端口|4\s*[xX]\s*)", t):
        spec["ports"] = 4
    for label, pat in [
        ("400GE", r"400\s*G[E]?|400GE"),
        ("200GE", r"200\s*G[E]?|200GE"),
        ("100GE", r"100\s*G[E]?|100GE|QSFP28|40\s*/\s*100|100GB"),
        ("25GE",  r"25\s*G[E]?|25GE|10\s*/\s*25"),
        ("10GE",  r"10\s*G[E]?|10GE(?!0)|\b10G\b"),
    ]:
        if re.search(pat, u):
            spec["speed"] = label
            break
    if "竖" in t:
        spec["storage_vertical"] = True
    if "PCIe" in u or "网卡" in t or "NIC" in u or "横" in t:
        spec["pcie_horizontal"] = True
    return spec


def _refine_spec(hints: list[str], spec: dict[str, Any], row: dict[str, Any]) -> None:
    cm = str(row.get("card_model") or "")
    pinned = False
    if cm:
        has_400_and_100 = bool(re.search(r"400GE", cm, re.I) and re.search(r"100GE", cm, re.I))
        if re.search(r"25GE", cm) and not re.search(r"100GE", cm):
            spec["speed"] = "25GE"; spec["ports"] = 2; pinned = True
        elif re.search(r"200GE", cm) and not re.search(r"100GE", cm):
            spec["speed"] = "200GE"; spec["ports"] = 2; pinned = True
        elif re.search(r"100GE", cm) and not re.search(r"25GE", cm) and not has_400_and_100:
            spec["speed"] = "100GE"; spec["ports"] = 2; pinned = True
        elif re.search(r"10GE", cm) and "100GE" not in cm:
            spec["speed"] = "10GE"; pinned = True
    dm0 = str(row.get("device_model") or "")
    if not pinned and not dm0.startswith("CE"):
        for h in hints:
            if "100GE" in h.upper() and ("2端口" in h or "两端口" in h or "双端口" in h):
                spec["speed"] = "100GE"; spec["ports"] = 2; break
    sec = str(row.get("section") or "")
    dm = str(row.get("device_model") or "")
    if "CE9860" in dm:
        if "参数面" in sec:
            spec.setdefault("plane_speed_bias", "400GE")
            if spec.get("speed") not in ("100GE", "25GE", "10GE"):
                spec["speed"] = "400GE"
        elif "样本面" in sec:
            spec["plane_speed_bias"] = "100GE"; spec["speed"] = "100GE"
    if "CE16880" in dm or "CE16816" in dm or "CE16800" in dm:
        if "参数面" in sec:
            spec["plane_speed_bias"] = "400GE"; spec["speed"] = "400GE"
        elif "样本面" in sec:
            spec["plane_speed_bias"] = "100GE"; spec["speed"] = "100GE"


def _speed_in(cm: str, cd: str, speed: str | None) -> bool:
    if not speed:
        return False
    blob = (cm + " " + cd).upper()
    pats = {
        "400GE": r"400\s*G[E]?|400GE", "200GE": r"200\s*G[E]?|200GE",
        "100GE": r"100\s*G[E]?|100GE", "25GE":  r"25\s*G[E]?|25GE",
        "10GE":  r"10\s*G[E]?|10GE",
    }
    pat = pats.get(speed)
    return bool(re.search(pat, blob)) if pat else speed in blob


def _port_hint_in(cm: str, cd: str, ports: int | None) -> bool:
    if ports is None:
        return True
    blob = (cm + " " + cd).upper().replace(" ", "")
    txt = cm + cd
    if ports == 2:
        return "2X" in blob or "2口" in txt or "双端口" in txt
    if ports == 4:
        return "4X" in blob or "4口" in txt or "四端口" in txt
    if ports and ports > 4:
        return f"L{ports}" in blob or f"{ports}口" in txt
    return False


def _pick_mpu(cards: list[dict]) -> str:
    for c in cards:
        cm, cd = c.get("model", "").upper(), c.get("description", "").upper()
        if "MPU" in cm or "MPU" in cd:
            return c.get("model", "")
    return ""


def pick_best_sim_card(boq_hints: list[str], cards: list[dict], row: dict[str, Any]) -> tuple[str, int, str]:
    if not cards:
        return "", 0, "无仿真板卡清单"
    cm_row = str(row.get("card_model") or "").strip().upper()
    if cm_row in {"MPU", "主控板"}:
        mpu = _pick_mpu(cards)
        return (mpu, 1600, "MPU模型命中") if mpu else ("", 0, "MPU模型未命中")

    merged = " ".join(boq_hints)
    spec = parse_boq_spec(merged)
    _refine_spec(boq_hints, spec, row)

    best_model, best_score, best_note = "", -1, ""
    for card in cards:
        cm, cd = card["model"], card["description"]
        score, notes = 0, []
        if spec.get("cex_substring") and spec["cex_substring"].upper() in cm.upper():
            score += 5000; notes.append("CEX子串命中")
        if spec.get("speed") and _speed_in(cm, cd, spec["speed"]):
            score += 900; notes.append(f"速率{spec['speed']}")
        elif spec.get("plane_speed_bias") and _speed_in(cm, cd, str(spec["plane_speed_bias"])):
            score += 500; notes.append(f"平面速率偏好{spec['plane_speed_bias']}")
        if spec.get("speed") == "100GE" and ("CQJ" in cm.upper() or "CQJ" in cd.upper()) and "DQ2" not in cm.upper():
            score += 350; notes.append("100GE线卡族(CQJ)")
        if spec.get("speed") == "100GE" and "DQ2" in cm.upper():
            score -= 450
        if spec.get("speed") == "400GE" and "DQ2" in cm.upper():
            score += 350; notes.append("400GE线卡族(DQ2)")
        if spec.get("ports") is not None and _port_hint_in(cm, cd, spec["ports"]):
            score += 400; notes.append(f"端口数{spec['ports']}")
        if spec.get("storage_vertical"):
            score += (600 if ("竖" in cm or "竖" in cd or "存储" in cm) else -200)
        if spec.get("pcie_horizontal") and cm.upper().startswith("PCIE"):
            score += 220; notes.append("PCIe网卡族")
        if spec.get("pcie_horizontal") and not spec.get("storage_vertical") and "竖" in cm:
            score -= 300
        if boq_hints and any(h and h.upper() in cm.upper() for h in boq_hints if len(h) > 6):
            score += 350; notes.append("BoQ型号子串一致")
        boq_ce = next((h.upper() for h in boq_hints if re.search(r"CEX8?-[A-Z0-9]+", h.upper())), "")
        if boq_ce:
            if "L36" in boq_ce and "L36" in cm.upper():
                score += 480; notes.append("L36一致")
            if "L36" in boq_ce and "L48" in cm.upper():
                score -= 420
        if score > best_score:
            best_score, best_model, best_note = score, cm, "；".join(notes) if notes else "默认最高分"

    if best_score < 80 and cards:
        if str(row.get("section") or "") == "智算服务器" and not _is_missing_pcie(str(row.get("card_model") or "")):
            return cards[0]["model"], max(best_score, 0), "弱匹配：取仿真清单首项"
        return "", max(best_score, 0), "置信度不足"
    return best_model, best_score, best_note


# ═══ PCIE 门禁 / 框式盒式判定 ═══
def _is_missing_pcie(text: str) -> bool:
    t = str(text or "").strip()
    if not t or t in {"-", "待确认", "待规则C确认"}:
        return True
    return ("PCIE" in t.upper() and "需项目组确认" in t) or ("网卡" in t and "需项目组确认" in t)


def _should_skip_pcie(section: str, card_model: str) -> bool:
    return "智算服务器" in section and _is_missing_pcie(card_model)


def _is_chassis_switch(model: str) -> bool:
    up = str(model or "").upper()
    return any(k in up for k in ("CE16800", "CE16880", "CE16816", "CE16808", "CE16804", "-X16", "-X8"))


# ═══ 章节 & 列定义 ═══
_KNOWN_SECTIONS = {
    "【超节点概述】", "【网络平面：参数面】", "【网络平面：样本面】",
    "【网络平面：管理面】", "【网络平面：业务面】", "【灵衢面】",
    "【智算服务器】", "【存储服务器】", "【通算服务器】", "【通算面】",
}
_SERVER_SECTIONS = {"【智算服务器】", "【存储服务器】", "【通算服务器】", "【通算面】"}
_SWITCH_SECTIONS = {
    "【网络平面：参数面】", "【网络平面：样本面】",
    "【网络平面：管理面】", "【网络平面：业务面】", "【灵衢面】",
}
_DEVICE_COL_ALIASES = ["设备型号", "来源设备型号"]
_ROLE_COL_ALIASES   = ["设备角色", "来源设备角色"]
_QTY_COL_ALIASES    = ["设备数量", "服务器数量"]
_CARD_COL_ALIASES   = ["板卡/插卡型号", "节点/网卡型号"]
_CARD_QTY_ALIASES   = ["板卡/插卡数量", "节点/网卡数量"]
_SP_SERVER_ALIASES  = ["Atlas A3服务器", "算服务器", "智算服务器", "设备型号"]
_SP_COMBO_ALIASES   = ["组合仿真模型"]


def _first_col(row: dict, aliases: list[str], default: str = "") -> str:
    for a in aliases:
        v = row.get(a)
        if v is not None:
            return str(v)
    return default


def _detect_col(headers: list[str], aliases: list[str]) -> str:
    for a in aliases:
        if a in headers:
            return a
    return aliases[0]


# ═══ Markdown 解析（多章节，保留顺序）═══
def _parse_table(lines: list[str]) -> tuple[list[dict], list[str]]:
    headers: list[str] = []
    rows: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not headers:
            headers = cells
            continue
        if all(re.match(r"^[-: ]+$", c) for c in cells if c):
            continue
        if len(cells) >= len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows, headers


def parse_device_info_md(md_path: Path) -> list[dict]:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    result: list[dict] = []
    current_marker: str | None = None
    buf: list[str] = []

    def _flush():
        if current_marker and buf:
            rows, headers = _parse_table(buf)
            result.append({"marker": current_marker, "rows": rows, "headers": headers})

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("【") and "】" in stripped:
            marker = re.match(r"(【[^】]+】)", stripped)
            if marker:
                m = marker.group(1)
                _flush()
                current_marker = m if m in _KNOWN_SECTIONS else None
                buf = []
                continue
        if stripped.startswith("## "):
            _flush(); current_marker = None; buf = []; continue
        if stripped.startswith("### "):
            continue
        if current_marker and stripped.startswith("|"):
            buf.append(stripped)
    _flush()
    return result


# ═══ 渲染 ═══
def _render_superpod(section_data: dict, device_sim_map: dict) -> list[str]:
    rows = section_data["rows"]
    lines = ["【超节点概述】", "",
             "| 超节点组合 | 超节点数量 | 智算服务器 | 服务器数量 | 灵衢交换机 | 灵衢数量 |",
             "|---|---|---|---|---|---|"]
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for row in rows:
        server = _first_col(row, _SP_SERVER_ALIASES)
        try:
            sq = int(_first_col(row, _QTY_COL_ALIASES, "0"))
        except ValueError:
            sq = 0
        try:
            lq = int(row.get("灵衢数量", "0") or "0")
        except ValueError:
            lq = 0
        combo = resolve_sim_combo_model(server, sq, lq)
        if not combo:
            combo = _first_col(row, _SP_COMBO_ALIASES, "待确认")
        if combo not in groups:
            groups[combo] = []
            order.append(combo)
        groups[combo].append(row)

    for combo in order:
        g = groups[combo]
        first = g[0]
        server_boq = _first_col(first, _SP_SERVER_ALIASES)
        server_qty = _first_col(first, _QTY_COL_ALIASES, "-")
        lingqu_boq = first.get("灵衢交换机", "").strip()
        lingqu_qty = first.get("灵衢数量", "-").strip()
        server = device_sim_map.get(server_boq, {}).get("sim_model") or "待确认"
        lingqu = device_sim_map.get(lingqu_boq, {}).get("sim_model") or "待确认"
        lines.append(f"| {combo} | {len(g)} | {server} | {server_qty} | {lingqu} | {lingqu_qty} |")
    return lines


def _render_device_section(section_data: dict, device_sim_map: dict) -> list[str]:
    marker = section_data["marker"]
    headers = section_data["headers"]
    rows = section_data["rows"]
    card_col     = _detect_col(headers, _CARD_COL_ALIASES)
    card_qty_col = _detect_col(headers, _CARD_QTY_ALIASES)
    lines = [marker, "",
             f"| 设备型号 | 设备角色 | 设备数量 | {card_col} | {card_qty_col} |",
             "|---|---|---|---|---|"]
    section_clean = marker.strip("【】")
    for row in rows:
        boq_model = _first_col(row, _DEVICE_COL_ALIASES)
        role      = _first_col(row, _ROLE_COL_ALIASES)
        qty       = _first_col(row, _QTY_COL_ALIASES, "-")
        card_hint = row.get(card_col, "").strip()
        card_qty  = row.get(card_qty_col, "-").strip()
        info = device_sim_map.get(boq_model, {})
        sim_model = info.get("sim_model", "") or "待确认"
        is_switch_section = marker in _SWITCH_SECTIONS
        if is_switch_section and not _is_chassis_switch(boq_model):
            lines.append(f"| {sim_model} | {role} | {qty} | - | - |")
            continue
        cards = info.get("cards", [])
        skip_pcie = _should_skip_pcie(section_clean, card_hint)
        if skip_pcie:
            sim_card = "待确认"
        elif not card_hint or card_hint == "-":
            sim_card = "-"
        else:
            norm_row = {"card_model": card_hint, "device_model": boq_model, "section": section_clean}
            best_card, _score, _ = pick_best_sim_card([card_hint, role], cards, norm_row)
            if not best_card:
                best_card = resolve_card_label(card_hint)
            sim_card = best_card if best_card else "待确认"
        lines.append(f"| {sim_model} | {role} | {qty} | {sim_card} | {card_qty} |")
    return lines


def render_compat_table_md(sections: list[dict], device_sim_map: dict) -> str:
    all_lines: list[str] = ["# 建模仿真设备适配信息表", ""]
    for sec in sections:
        block = (_render_superpod(sec, device_sim_map) if sec["marker"] == "【超节点概述】"
                 else _render_device_section(sec, device_sim_map))
        all_lines.extend(block)
        all_lines.append("")
        all_lines.append("")
    return "\n".join(all_lines).rstrip() + "\n"


# ═══ 主流程（AIDA 版）═══
def _collect_boq_models(sections: list[dict]) -> dict[str, str]:
    models: dict[str, str] = {}
    for sec in sections:
        if sec["marker"] == "【超节点概述】":
            for row in sec["rows"]:
                server = _first_col(row, _SP_SERVER_ALIASES)
                lingqu = row.get("灵衢交换机", "").strip()
                for m in [server, lingqu]:
                    if m and m not in models:
                        models[m] = "【超节点概述】"
            continue
        for row in sec["rows"]:
            m = _first_col(row, _DEVICE_COL_ALIASES)
            if m and m not in models:
                models[m] = sec["marker"]
    return models


def _needs_slot_query(boq_model: str, section_marker: str) -> bool:
    if section_marker in _SERVER_SECTIONS:
        return True
    if section_marker in _SWITCH_SECTIONS:
        return _is_chassis_switch(boq_model)
    return False


def build_compat_table(
    input_path: Path,
    output_path: Path,
    client,                       # SimApiClient
    *,
    emit: Callable[[str], None] | None = None,
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    """生成适配信息表。返回统计 dict（供 step 写 metrics）。

    离线/dry-run（queryDeviceModel 返回空）时：若给了 fixture_path 直接复用样本适配表。
    """
    def _say(m: str) -> None:
        if emit:
            emit(m)

    sections = parse_device_info_md(input_path)
    total_rows = sum(len(s["rows"]) for s in sections)
    _say(f"[compat] 解析章节 {len(sections)} 个，合计 {total_rows} 行")
    if total_rows == 0:
        raise RuntimeError("设备信息表解析为空，请检查 Markdown 格式")

    boq_model_section = _collect_boq_models(sections)
    catalog = client.query_device_model()
    _say(f"[compat] queryDeviceModel 目录 {len(catalog)} 条"
         + ("（dry-run/离线为空）" if not catalog else ""))

    # 离线兜底：无目录且有 fixture → 直接复用样本适配表
    if not catalog:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if fixture_path and Path(fixture_path).is_file():
            shutil.copyfile(fixture_path, output_path)
            _say(f"[compat] 离线：复用样本适配表 → {output_path.name}")
            mode = "fixture"
        else:
            # 仍渲染骨架（所有 sim_model=待确认），保证有产物
            md = render_compat_table_md(sections, {})
            output_path.write_text(md, encoding="utf-8")
            _say("[compat] 离线无 fixture：渲染骨架表（型号待确认）")
            mode = "skeleton"
        combo = _parse_combo_from_md(output_path)
        return {"mode": mode, "sections": len(sections), "rows": total_rows,
                "devices": len(boq_model_section), "combo_model": combo}

    # 在线：真实匹配
    device_sim_map: dict[str, dict] = {}
    for boq, sec_marker in boq_model_section.items():
        sim = match_device_model(boq, catalog)
        device_sim_map[boq] = {"sim_model": sim, "cards": [], "sec_marker": sec_marker}

    queried: set[str] = set()
    for boq, info in device_sim_map.items():
        sim = info.get("sim_model", "")
        sec_marker = info.get("sec_marker", "")
        if not sim or not _needs_slot_query(boq, sec_marker):
            continue
        if sim in queried:
            for other in device_sim_map.values():
                if other.get("sim_model") == sim and other.get("cards"):
                    info["cards"] = other["cards"]
                    break
            continue
        _status, raw = client.query_slot_mapping(sim)
        info["cards"] = flatten_cards(raw)
        queried.add(sim)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    md = render_compat_table_md(sections, device_sim_map)
    output_path.write_text(md, encoding="utf-8")
    matched = sum(1 for v in device_sim_map.values() if v.get("sim_model"))
    _say(f"[compat] 在线匹配完成：{matched}/{len(device_sim_map)} 命中 → {output_path.name}")
    return {"mode": "live", "sections": len(sections), "rows": total_rows,
            "devices": len(device_sim_map), "matched": matched,
            "combo_model": _parse_combo_from_md(output_path)}


def _parse_combo_from_md(adapt_md: Path) -> str:
    """从已生成的适配表【超节点概述】首数据行取「超节点组合」。"""
    try:
        lines = Path(adapt_md).read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    in_section = False
    seen_header = False
    for line in lines:
        s = line.strip()
        if s.startswith("【") and "超节点概述" in s:
            in_section = True
            continue
        if in_section and s.startswith("【"):
            break
        if not in_section or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not seen_header:
            if cells and "超节点组合" in cells[0]:
                seen_header = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if cells and cells[0]:
            return cells[0]
    return ""
