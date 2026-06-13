#!/usr/bin/env python3
"""run_place_api.py — auto_dragd skill 编排入口（纯 API 版 / 批量化）。

两阶段、两子命令：

  build : 从《适配信息表》《机房机柜信息表.xlsx》《cabinets.json》生成 requests.json，
          含全部请求体（5 条批量创建 + 162 条逐机柜移动），可人工核对、可重复使用。
  run   : 读取 requests.json 按序发送 ——
            1) 创建阶段：5 次 batchCreateCombo 把 9 个 POD 一次性平铺创建（POD1 在 x=150，
               之后每个 POD x+100、y=60 不变）；
            2) 暂停等待你手动刷新 nVisual 一次；
            3) 移动阶段：batchMoveNodes 一次只移 1 个机柜，从 401 A01 → 403 A18 串行调用，
               前一个返回 code==200 才发下一个，失败即停（可用 --start-move 续跑）。

为何分组创建：batchCreateCombo 的 model 与 roomName 是请求体顶层字段，一次调用内所有 items
共用同一 model/roomName。9 个 POD 跨「-上/-下」两种 model、401/402/403 三个 roomName，
故最少按 (roomName × model) 分 5 次创建调用，但创建阶段全部跑完后只需刷新一次。

坐标约定：cabinets.json 的 ctr_x/ctr_y（机柜中心点）与仿真软件画布同原点同比例。
命名约定：组合模型创建的机柜假定为 A01..A18（两位补零），与 grid 的 A1..A18 按
         「字母 + 去前导零数字」对应（A01 ↔ A1）。
朝向后缀：组合模型名按列字母加后缀，A/C 列 → 「-上」，B/D 列 → 「-下」。

用法：
  python scripts/run_place_api.py build --diagram 机房视图
  python scripts/run_place_api.py run --dry-run
  python scripts/run_place_api.py run                 # 正式：创建→刷新→逐个移动
  python scripts/run_place_api.py run --start-move 37 # 从第 37 条移动续跑
  python scripts/run_place_api.py run --only-create   # 只跑创建阶段
  python scripts/run_place_api.py run --only-move     # 只跑移动阶段（已创建并刷新过）
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent

# ── 默认配置 ────────────────────────────────────────────────────────────────
DEFAULT_API_BASE = os.environ.get("SIM_API_BASE", "http://100.102.191.17:9091")
DEFAULT_TOKEN = os.environ.get(
    "SIM_API_TOKEN",
    "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJqZF9wcm9qZWN0IiwibmFtZSI6ImpkX3Byb2plY3QiLCJleHAiOjE4MTI2ODE0MjksImlhdCI6MTc4MTE0NTQyOX0.qeFt444mYHdJzc_wi-fNrU1eAtyHHRnDL6kFENPUkfah9oPUizXdXg1jg1nPrxDvpKdnNJIfnDf7MA0KGM9YYA",
)

CREATE_PATH = "/wapi/v1/ai/combo/batchCreateCombo"
MOVE_PATH = "/wapi/v1/ai/nodes/batchMoveNodes"

# xlsx 机房号(401/402/403) → cabinets.json 房间名(F1-R1/F1-R2/F1-R3)
ROOM_GRID_MAP = {"401": "F1-R1", "402": "F1-R2", "403": "F1-R3"}

# 因机柜朝向不同，组合模型名按列字母加后缀：A/C 列用「-上」，B/D 列用「-下」。
COL_MODEL_SUFFIX = {"A": "-上", "C": "-上", "B": "-下", "D": "-下"}
# 创建分组排序：同一 roomName 下「-上」先于「-下」。
SUFFIX_ORDER = {"-上": 0, "-下": 1, "": 2}

# 平铺创建坐标：POD1 在 (150,60)，之后每个 POD x+100、y 不变。
SPAWN_X0 = 150.0
SPAWN_Y = 60.0
SPAWN_DX = 100.0

_SS_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def combo_model_for_col(base_model: str, col: str) -> str:
    """按列字母给组合模型名加朝向后缀（A/C→-上, B/D→-下，其余不变）。"""
    return base_model + COL_MODEL_SUFFIX.get(col.upper(), "")


# ── 解析：组合模型名 ──────────────────────────────────────────────────────────
def parse_combo_model(adapt_md: Path) -> str:
    """从《建模仿真设备适配信息表》【超节点概述】表首数据行取「超节点组合」列。"""
    lines = adapt_md.read_text(encoding="utf-8").splitlines()
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
    """解析 xlsx sheet1，输出每个 POD 的机房号与列字母。

    列约定：B=POD名(POD1..) / C=机房号(401..) / D-H=机柜编号(如 A01,A02 / A18)。
    返回按 POD 序号升序的列表，元素：{pod_index, pod_name, room_raw, col}。
    """
    z = zipfile.ZipFile(xlsx_path)
    shared = _read_shared_strings(z)
    sheet_names = sorted(
        n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
    )

    pods: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sheet in sheet_names:
        for cells in _sheet_rows(z, sheet, shared):
            pod_name = (cells.get("B") or "").strip()
            m = re.fullmatch(r"(?i)POD\s*(\d+)", pod_name)
            if not m:
                continue
            if pod_name.upper() in seen:
                continue
            room_raw = (cells.get("C") or "").strip()
            col = ""
            for key in ("D", "E", "F", "G", "H"):
                val = (cells.get(key) or "").strip()
                cm = re.match(r"([A-Za-z])", val)
                if cm:
                    col = cm.group(1).upper()
                    break
            if not room_raw or not col:
                continue
            seen.add(pod_name.upper())
            pods.append({
                "pod_index": int(m.group(1)),
                "pod_name": pod_name.upper(),
                "room_raw": room_raw,
                "col": col,
            })
    pods.sort(key=lambda p: p["pod_index"])
    if not pods:
        raise ValueError(f"未能从 {xlsx_path} 解析出任何 POD 行")
    return pods


# ── 解析：cabinets.json 几何 ──────────────────────────────────────────────────
def load_grid(grid_path: Path) -> list[dict]:
    return json.loads(grid_path.read_text(encoding="utf-8"))


def build_move_nodes(grid: list[dict], grid_room: str, col: str) -> list[dict[str, Any]]:
    """取某 POD 目标列全部机柜，按编号升序返回。

    取 grid 中 room==grid_room 且 code 匹配 ^{col}\\d+$ 的机柜：
      节点名 = f"{col}{编号:02d}"（与组合模型补零命名对齐，如 A1 → A01）
      坐标   = (ctr_x, ctr_y)  机柜中心点
    """
    pat = re.compile(rf"^{re.escape(col)}(\d+)$")
    nodes: list[dict[str, Any]] = []
    for c in grid:
        if str(c.get("room")) != grid_room:
            continue
        m = pat.match(str(c.get("code") or ""))
        if not m:
            continue
        num = int(m.group(1))
        nodes.append({
            "name": f"{col}{num:02d}",
            "x": float(c["ctr_x"]),
            "y": float(c["ctr_y"]),
            "_num": num,
            "_grid_code": str(c.get("code")),
        })
    nodes.sort(key=lambda n: n["_num"])
    return nodes


# ── 构造请求 ──────────────────────────────────────────────────────────────────
def build_create_requests(pods: list[dict[str, Any]], combo_base: str,
                          diagram: str) -> list[dict[str, Any]]:
    """按 (roomName × model) 分组生成批量创建请求。

    x 按全局 POD 序号平铺：x = SPAWN_X0 + (pod_index-1)*SPAWN_DX，y = SPAWN_Y。
    分组顺序：roomName 升序，同房间内「-上」先于「-下」。
    """
    enriched: list[dict[str, Any]] = []
    for pod in pods:
        idx = pod["pod_index"]
        col = pod["col"]
        enriched.append({
            "pod_index": idx,
            "room_raw": pod["room_raw"],
            "col": col,
            "model": combo_model_for_col(combo_base, col),
            "x": SPAWN_X0 + (idx - 1) * SPAWN_DX,
            "sp_num": idx,
            "rack_prefix": col,
        })

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in enriched:
        groups.setdefault((e["room_raw"], e["model"]), []).append(e)

    def gkey(k: tuple[str, str]) -> tuple[str, int]:
        room, model = k
        suffix = model[len(combo_base):]
        return (room, SUFFIX_ORDER.get(suffix, 9))

    create: list[dict[str, Any]] = []
    for key in sorted(groups, key=gkey):
        room, model = key
        items = sorted(groups[key], key=lambda e: e["sp_num"])
        body = {
            "model": model,
            "diagram": diagram,
            "roomName": room,
            "items": [
                {"x": e["x"], "y": SPAWN_Y, "sp_num": e["sp_num"],
                 "rack_prefix": e["rack_prefix"]}
                for e in items
            ],
        }
        cols = ",".join(e["col"] for e in items)
        sps = ",".join(str(e["sp_num"]) for e in items)
        create.append({
            "_label": f"{model} @{room} 列[{cols}] sp_num[{sps}]",
            "path": CREATE_PATH,
            "body": body,
        })
    return create


def build_move_requests(pods: list[dict[str, Any]], grid: list[dict],
                        diagram: str) -> list[dict[str, Any]]:
    """逐机柜生成移动请求：POD1..POD9，每个 POD 内 A01..A18，每条只含 1 个机柜。"""
    move: list[dict[str, Any]] = []
    for pod in sorted(pods, key=lambda p: p["pod_index"]):
        room_raw = pod["room_raw"]
        grid_room = ROOM_GRID_MAP.get(room_raw, room_raw)
        if grid_room not in {str(c.get("room")) for c in grid}:
            raise ValueError(f"cabinets.json 中无房间 {grid_room}（来自 xlsx 机房号 {room_raw}）")
        nodes = build_move_nodes(grid, grid_room, pod["col"])
        if not nodes:
            raise ValueError(f"cabinets.json 中未找到 {grid_room} 的 {pod['col']} 列机柜")
        for n in nodes:
            move.append({
                "_label": f"POD{pod['pod_index']} {room_raw} {n['name']}",
                "_pod": pod["pod_index"],
                "_room": room_raw,
                "_col": pod["col"],
                "_cabinet": n["name"],
                "_grid_code": n["_grid_code"],
                "path": MOVE_PATH,
                "body": {
                    "diagram": diagram,
                    "roomName": room_raw,
                    "nodes": [{"name": n["name"], "x": n["x"], "y": n["y"]}],
                },
            })
    return move


# ── API ──────────────────────────────────────────────────────────────────────
def _post(api_base: str, token: str, path: str, payload: dict,
          timeout: int = 240, verbose: bool = True) -> tuple[int, Any]:
    import requests

    url = api_base.rstrip("/") + path
    if verbose:
        print(f"    [请求] POST {url}")
        print(f"    [请求体] {json.dumps(payload, ensure_ascii=False)}")
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        try:
            body = resp.json()
        except Exception:
            body = {"raw_text": resp.text[:1000]}
        if verbose:
            print(f"    [HTTP] {resp.status_code}  [返回体] {json.dumps(body, ensure_ascii=False)}")
        return resp.status_code, body
    except Exception as exc:
        if verbose:
            print(f"    [异常] {exc}")
        return 0, {"error": str(exc)}


def _ok(status: int, body: Any) -> bool:
    code = body.get("code") if isinstance(body, dict) else None
    return status == 200 and (code in (200, None))


# ── 子命令：build ─────────────────────────────────────────────────────────────
def cmd_build(args: argparse.Namespace) -> None:
    adapt_md = (SKILL_ROOT / args.adapt_md).resolve()
    xlsx_path = (SKILL_ROOT / args.xlsx).resolve()
    grid_path = (SKILL_ROOT / args.grid).resolve()
    out_path = (SKILL_ROOT / args.out).resolve()

    for path, label in ((adapt_md, "适配信息表"),
                        (xlsx_path, "机房机柜信息表"),
                        (grid_path, "cabinets.json")):
        if not path.exists():
            print(f"ERROR: {label}文件不存在: {path}")
            sys.exit(1)

    combo_base = parse_combo_model(adapt_md)
    pods = parse_pod_layout(xlsx_path)
    grid = load_grid(grid_path)

    create = build_create_requests(pods, combo_base, args.diagram)
    move = build_move_requests(pods, grid, args.diagram)

    doc = {
        "meta": {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "diagram": args.diagram,
            "combo_base_model": combo_base,
            "api_base": args.api_base,
            "create_path": CREATE_PATH,
            "move_path": MOVE_PATH,
            "spawn": {"x0": SPAWN_X0, "y": SPAWN_Y, "dx": SPAWN_DX},
            "pod_count": len(pods),
            "create_count": len(create),
            "move_count": len(move),
            "note": "逐机柜移动用机柜中心点 ctr_x/ctr_y；创建后需手动刷新 nVisual 一次再移动。",
        },
        "create": create,
        "move": move,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"组合模型名(基准): {combo_base}  ← A/C列加「-上」, B/D列加「-下」")
    print(f"视图(diagram): {args.diagram}")
    print(f"POD 数: {len(pods)}  创建请求: {len(create)} 条  移动请求: {len(move)} 条")
    print("\n创建分组：")
    for i, req in enumerate(create, 1):
        items = req["body"]["items"]
        xs = ",".join(f"{it['x']:.0f}" for it in items)
        print(f"  [{i}] {req['_label']}  x=[{xs}] y={SPAWN_Y:.0f}")
    print(f"\n移动顺序：{move[0]['_label']} ... {move[-1]['_label']}（每条 1 个机柜，共 {len(move)} 条）")
    print(f"\n已写入 {out_path}")


# ── 子命令：run ───────────────────────────────────────────────────────────────
def _pause_for_refresh(refresh_wait: float) -> None:
    if refresh_wait > 0:
        print(f"\n>>> 创建完成。等待 {refresh_wait:.0f}s 后自动进入移动阶段，请此间手动刷新 nVisual(F5)...")
        for sec in range(int(refresh_wait), 0, -1):
            print(f"    {sec} ...", end="\r", flush=True)
            time.sleep(1)
        print(" " * 24, end="\r")
    else:
        try:
            input("\n>>> 创建完成。请手动刷新 nVisual(F5) 等组合模型显现，然后回车继续移动阶段...")
        except EOFError:
            print("（无交互输入，直接继续）")


def cmd_run(args: argparse.Namespace) -> None:
    file_path = (SKILL_ROOT / args.file).resolve()
    if not file_path.exists():
        print(f"ERROR: requests 文件不存在: {file_path}（请先运行 build 子命令）")
        sys.exit(1)
    doc = json.loads(file_path.read_text(encoding="utf-8"))
    create = doc.get("create", [])
    move = doc.get("move", [])
    meta = doc.get("meta", {})

    print(f"读取 {file_path}")
    print(f"  diagram={meta.get('diagram')}  创建 {len(create)} 条  移动 {len(move)} 条")
    if args.dry_run:
        print("\n[dry-run] 创建阶段：")
        for i, req in enumerate(create, 1):
            print(f"  [{i}/{len(create)}] {req['_label']}")
            print(f"        {json.dumps(req['body'], ensure_ascii=False)}")
        print("\n[dry-run] 移动阶段（前 3 / 后 3）：")
        preview = list(enumerate(move, 1))
        for i, req in preview[:3] + ([("...", None)] if len(move) > 6 else []) + preview[-3:]:
            if req is None:
                print("  ...")
                continue
            print(f"  [{i}/{len(move)}] {req['_label']}  -> "
                  f"{json.dumps(req['body']['nodes'][0], ensure_ascii=False)}")
        print("\n[dry-run] 未发送任何请求。")
        return

    # ── 创建阶段 ──
    if not args.only_move and not args.skip_create:
        print("\n=== 创建阶段（平铺一次性创建，仅需刷新一次）===")
        for i, req in enumerate(create, 1):
            print(f"\n[创建 {i}/{len(create)}] {req['_label']}")
            status, body = _post(args.api_base, args.token, req["path"], req["body"])
            if not _ok(status, body):
                print(f"  [ERROR] batchCreateCombo 失败：HTTP={status} body={body}")
                print("  中止。请检查 组合模型名/视图名(diagram)/token，修复后可 --skip-create 跳过已成功的创建。")
                sys.exit(1)
        if args.only_create:
            print("\n[--only-create] 仅创建完成，未进入移动阶段。")
            return
        _pause_for_refresh(args.refresh_wait)

    # ── 移动阶段 ──
    if args.only_create:
        return
    print("\n=== 移动阶段（逐个机柜，前一个成功才发下一个）===")
    start = max(1, args.start_move)
    for i, req in enumerate(move, 1):
        if i < start:
            continue
        print(f"\n[移动 {i}/{len(move)}] {req['_label']}")
        status, body = _post(args.api_base, args.token, req["path"], req["body"])
        if not _ok(status, body):
            print(f"  [ERROR] batchMoveNodes 失败：HTTP={status} body={body}")
            print(f"  中止。组合模型已创建过，修复后用 run --only-move --start-move {i} 从本条续跑。")
            sys.exit(1)
        msg = body.get("message") if isinstance(body, dict) else ""
        if msg and msg != "success":
            print(f"  [警告] 返回 message: {msg}")
        if i < len(move) and args.move_wait > 0:
            time.sleep(args.move_wait)
    print("\n全部完成。")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(
        description="auto_dragd skill：平铺批量创建组合模型 + 逐机柜 batchMoveNodes 落位"
    )
    sub = p.add_subparsers(dest="command", required=True)

    pb = sub.add_parser("build", help="生成 requests.json（创建 + 移动请求体）")
    pb.add_argument("--diagram", required=True, help="目标视图名称（必填）")
    pb.add_argument("--adapt-md", default="../api_adapt/output/建模仿真设备适配信息表.md")
    pb.add_argument("--xlsx", default="../../auto_drag/机房机柜信息表.xlsx")
    pb.add_argument("--grid", default="../cad-analysis/cabinets.json")
    pb.add_argument("--out", default="requests.json", help="输出文件（相对 skill 根目录）")
    pb.add_argument("--api-base", default=DEFAULT_API_BASE, help="仅写入 meta 供参考")
    pb.set_defaults(func=cmd_build)

    pr = sub.add_parser("run", help="读取 requests.json 按序发送（创建→刷新→逐个移动）")
    pr.add_argument("--file", default="requests.json", help="requests 文件（相对 skill 根目录）")
    pr.add_argument("--api-base", default=DEFAULT_API_BASE)
    pr.add_argument("--token", default=DEFAULT_TOKEN)
    pr.add_argument("--dry-run", action="store_true", help="只打印计划，不发送任何请求")
    pr.add_argument("--refresh-wait", type=float, default=0.0,
                    help="创建后等待刷新的秒数；0=交互式按回车继续（默认）")
    pr.add_argument("--move-wait", type=float, default=0.5,
                    help="每条移动成功后等待秒数再发下一条（默认 0.5）")
    pr.add_argument("--start-move", type=int, default=1, help="从第几条移动续跑（1 基）")
    pr.add_argument("--skip-create", action="store_true", help="跳过创建阶段，直接移动")
    pr.add_argument("--only-create", action="store_true", help="只跑创建阶段")
    pr.add_argument("--only-move", action="store_true", help="只跑移动阶段")
    pr.set_defaults(func=cmd_run)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
