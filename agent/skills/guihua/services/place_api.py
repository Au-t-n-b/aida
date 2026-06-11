"""place_api · 超节点创建 + 机柜落位编排（移植 jmfz/auto_dragd/run_place_api.py）

两阶段：
  创建：batchCreateCombo ×5（9 个 POD 平铺创建，按 roomName×model 分组）。
  落位：batchMoveNodes ×162（逐机柜，POD1 A01 → POD9 A18，按机柜中心点坐标）。

与原脚本差异（适配 AIDA）：
- 发送走 SimApiClient（统一出口 + dry-run + 留痕）。
- 机房机柜信息表.xlsx 缺失时回落预建 requests_fixture.json（POD 布局已固化）。
- 去掉 input() 刷新暂停 / CLI；刷新由 step 的 HITL 确认门承担。
- send_move 支持 on_each 进度回调，供 SDUI 实时回流。
纯构造函数（坐标/分组/补零命名）逐字保留原逻辑。
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Callable

from .sim_api import PATH_CREATE_COMBO, PATH_MOVE_NODES

ROOM_GRID_MAP = {"401": "F1-R1", "402": "F1-R2", "403": "F1-R3"}
COL_MODEL_SUFFIX = {"A": "-上", "C": "-上", "B": "-下", "D": "-下"}
SUFFIX_ORDER = {"-上": 0, "-下": 1, "": 2}
SPAWN_X0 = 150.0
SPAWN_Y = 60.0
SPAWN_DX = 100.0
DEFAULT_DIAGRAM = "机房视图"

_SS_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def combo_model_for_col(base_model: str, col: str) -> str:
    return base_model + COL_MODEL_SUFFIX.get(col.upper(), "")


# ── 解析：组合模型名 ──────────────────────────────────────────────────────────
def parse_combo_model(adapt_md: Path) -> str:
    lines = Path(adapt_md).read_text(encoding="utf-8").splitlines()
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
        if not cells:
            continue
        if not seen_header:
            if "超节点组合" in cells[0]:
                seen_header = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if cells[0]:
            return cells[0]
    raise ValueError(f"未能从 {adapt_md} 的【超节点概述】解析出组合模型名")


# ── 解析：xlsx POD 布局 ──────────────────────────────────────────────────────
def _read_shared_strings(z: zipfile.ZipFile) -> list[str]:
    out: list[str] = []
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return out
    for si in root.findall(_SS_NS + "si"):
        out.append("".join(t.text or "" for t in si.iter(_SS_NS + "t")))
    return out


def _cell_col(ref: str) -> str:
    m = re.match(r"[A-Z]+", ref or "")
    return m.group() if m else ""


def _sheet_rows(z: zipfile.ZipFile, sheet: str, shared: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    root = ET.fromstring(z.read(sheet))
    for row in root.iter(_SS_NS + "row"):
        cells: dict[str, str] = {}
        for c in row.findall(_SS_NS + "c"):
            v = c.find(_SS_NS + "v")
            if v is None or v.text is None:
                continue
            val = shared[int(v.text)] if c.get("t") == "s" else v.text
            cells[_cell_col(c.get("r"))] = val
        rows.append(cells)
    return rows


def parse_pod_layout(xlsx_path: Path) -> list[dict[str, Any]]:
    """sheet1：B=POD名 / C=机房号 / D-H=机柜编号 → 每 POD 的机房号 + 列字母。"""
    z = zipfile.ZipFile(xlsx_path)
    shared = _read_shared_strings(z)
    sheet_names = sorted(n for n in z.namelist()
                         if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
    pods: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sheet in sheet_names:
        for cells in _sheet_rows(z, sheet, shared):
            pod_name = (cells.get("B") or "").strip()
            m = re.fullmatch(r"(?i)POD\s*(\d+)", pod_name)
            if not m or pod_name.upper() in seen:
                continue
            room_raw = (cells.get("C") or "").strip()
            col = ""
            for key in ("D", "E", "F", "G", "H"):
                cm = re.match(r"([A-Za-z])", (cells.get(key) or "").strip())
                if cm:
                    col = cm.group(1).upper()
                    break
            if not room_raw or not col:
                continue
            seen.add(pod_name.upper())
            pods.append({"pod_index": int(m.group(1)), "pod_name": pod_name.upper(),
                         "room_raw": room_raw, "col": col})
    pods.sort(key=lambda p: p["pod_index"])
    if not pods:
        raise ValueError(f"未能从 {xlsx_path} 解析出任何 POD 行")
    return pods


# ── 解析：cabinets.json 几何 ──────────────────────────────────────────────────
def build_move_nodes(grid: list[dict], grid_room: str, col: str) -> list[dict[str, Any]]:
    pat = re.compile(rf"^{re.escape(col)}(\d+)$")
    nodes: list[dict[str, Any]] = []
    for c in grid:
        if str(c.get("room")) != grid_room:
            continue
        m = pat.match(str(c.get("code") or ""))
        if not m:
            continue
        num = int(m.group(1))
        nodes.append({"name": f"{col}{num:02d}", "x": float(c["ctr_x"]), "y": float(c["ctr_y"]),
                      "_num": num, "_grid_code": str(c.get("code"))})
    nodes.sort(key=lambda n: n["_num"])
    return nodes


# ── 构造请求 ──────────────────────────────────────────────────────────────────
def build_create_requests(pods: list[dict[str, Any]], combo_base: str, diagram: str) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for pod in pods:
        idx, col = pod["pod_index"], pod["col"]
        enriched.append({"pod_index": idx, "room_raw": pod["room_raw"], "col": col,
                         "model": combo_model_for_col(combo_base, col),
                         "x": SPAWN_X0 + (idx - 1) * SPAWN_DX, "sp_num": idx, "rack_prefix": col})
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in enriched:
        groups.setdefault((e["room_raw"], e["model"]), []).append(e)

    def gkey(k: tuple[str, str]) -> tuple[str, int]:
        room, model = k
        return (room, SUFFIX_ORDER.get(model[len(combo_base):], 9))

    create: list[dict[str, Any]] = []
    for key in sorted(groups, key=gkey):
        room, model = key
        items = sorted(groups[key], key=lambda e: e["sp_num"])
        body = {"model": model, "diagram": diagram, "roomName": room,
                "items": [{"x": e["x"], "y": SPAWN_Y, "sp_num": e["sp_num"], "rack_prefix": e["rack_prefix"]}
                          for e in items]}
        cols = ",".join(e["col"] for e in items)
        sps = ",".join(str(e["sp_num"]) for e in items)
        create.append({"_label": f"{model} @{room} 列[{cols}] sp_num[{sps}]",
                       "path": PATH_CREATE_COMBO, "body": body})
    return create


def build_move_requests(pods: list[dict[str, Any]], grid: list[dict], diagram: str) -> list[dict[str, Any]]:
    move: list[dict[str, Any]] = []
    for pod in sorted(pods, key=lambda p: p["pod_index"]):
        room_raw = pod["room_raw"]
        grid_room = ROOM_GRID_MAP.get(room_raw, room_raw)
        if grid_room not in {str(c.get("room")) for c in grid}:
            raise ValueError(f"cabinets.json 中无房间 {grid_room}（来自机房号 {room_raw}）")
        nodes = build_move_nodes(grid, grid_room, pod["col"])
        if not nodes:
            raise ValueError(f"cabinets.json 中未找到 {grid_room} 的 {pod['col']} 列机柜")
        for n in nodes:
            move.append({"_label": f"POD{pod['pod_index']} {room_raw} {n['name']}",
                         "_pod": pod["pod_index"], "_room": room_raw, "_col": pod["col"],
                         "_cabinet": n["name"], "_grid_code": n["_grid_code"], "path": PATH_MOVE_NODES,
                         "body": {"diagram": diagram, "roomName": room_raw,
                                  "nodes": [{"name": n["name"], "x": n["x"], "y": n["y"]}]}})
    return move


def build_requests(adapt_md: Path, xlsx_path: Path, grid_path: Path, diagram: str) -> dict[str, Any]:
    """从适配表 + xlsx + cabinets.json 生成完整 requests 文档。"""
    combo_base = parse_combo_model(adapt_md)
    pods = parse_pod_layout(xlsx_path)
    grid = json.loads(Path(grid_path).read_text(encoding="utf-8"))
    create = build_create_requests(pods, combo_base, diagram)
    move = build_move_requests(pods, grid, diagram)
    return {
        "meta": {"diagram": diagram, "combo_base_model": combo_base, "pod_count": len(pods),
                 "create_count": len(create), "move_count": len(move),
                 "spawn": {"x0": SPAWN_X0, "y": SPAWN_Y, "dx": SPAWN_DX}},
        "create": create, "move": move,
    }


def load_or_build_requests(
    *, adapt_md: Path, xlsx_path: Path | None, grid_path: Path | None,
    fixture_path: Path | None, diagram: str = DEFAULT_DIAGRAM,
    emit: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """优先用 xlsx+grid 现建；缺输入则回落预建 requests_fixture.json。"""
    def _say(m: str) -> None:
        if emit:
            emit(m)
    can_build = (xlsx_path and Path(xlsx_path).is_file()
                 and grid_path and Path(grid_path).is_file()
                 and Path(adapt_md).is_file())
    if can_build:
        try:
            doc = build_requests(Path(adapt_md), Path(xlsx_path), Path(grid_path), diagram)
            _say(f"[place] 现建请求：创建 {doc['meta']['create_count']} 条 / 移动 {doc['meta']['move_count']} 条")
            return doc
        except Exception as e:
            _say(f"[place] 现建失败（{e}），尝试回落 fixture")
    if fixture_path and Path(fixture_path).is_file():
        doc = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        _say(f"[place] 回落预建 requests：创建 {len(doc.get('create', []))} 条 / 移动 {len(doc.get('move', []))} 条")
        return doc
    raise RuntimeError("无法生成落位请求：缺机房机柜表.xlsx/cabinets.json 且无 requests_fixture.json")


# ── 发送 ──────────────────────────────────────────────────────────────────────
def send_create(client, requests_doc: dict, *, emit: Callable[[str], None] | None = None) -> dict[str, Any]:
    """发送创建阶段（5 条 batchCreateCombo，任一失败即停）。"""
    def _say(m: str) -> None:
        if emit:
            emit(m)
    create = requests_doc.get("create", [])
    for i, req in enumerate(create, 1):
        _say(f"[创建 {i}/{len(create)}] {req.get('_label', '')}")
        status, body = client.batch_create_combo(req["body"])
        if not client.ok(status, body):
            return {"phase": "create", "sent": i, "total": len(create), "ok": False,
                    "failed_at": i, "error": str(body)[:300]}
    return {"phase": "create", "sent": len(create), "total": len(create), "ok": True}


def send_move(
    client, requests_doc: dict, *, start: int = 1,
    emit: Callable[[str], None] | None = None,
    on_each: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """发送落位阶段（逐机柜 batchMoveNodes，前一条成功才发下一条）。"""
    def _say(m: str) -> None:
        if emit:
            emit(m)
    move = requests_doc.get("move", [])
    total = len(move)
    start = max(1, start)
    for i, req in enumerate(move, 1):
        if i < start:
            continue
        _say(f"[移动 {i}/{total}] {req.get('_label', '')}")
        status, body = client.batch_move_nodes(req["body"])
        if on_each:
            on_each(i, total)
        if not client.ok(status, body):
            return {"phase": "move", "sent": i, "total": total, "ok": False,
                    "failed_at": i, "error": str(body)[:300]}
    return {"phase": "move", "sent": total, "total": total, "ok": True}
