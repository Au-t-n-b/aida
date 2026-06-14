"""AIDA 物理孪生页生成器。

输入：TwinPackage（契约 v1，经 import_twin.py 收入资产库；真相源 uniEx docs/uniEx-v2/06-twin-contract.md）。
输出：frontend/public/twin/physical-twin.html —— 孪生世界 iframe 直接加载，
支持 ?compact=1（概览半屏·问题光点闪烁）/ ?build=1（图纸躺倒+生长构建动画）/
?instant=1（直达成品），并向父页 postMessage twin:stats / twin:built。

用法：
  python3 scripts/twin-gen/gen_physical_twin.py <TwinPackage目录> [--title 标题] [-o 输出.html]

模板/动画归 AIDA 维护（scripts/twin-gen/template.html）；uniEx 只负责解析与数据。
"""
import argparse
import base64
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
THREE_JS = HERE / "assets" / "three.min.js"
TEX_DIR = HERE / "assets" / "tex"

TEX_FILES = {
    "cab_compute_front": "计算柜前视图.jpg", "cab_compute_back": "计算柜后视图.jpg",
    "cab_net_front": "网络柜前视图.jpg", "cab_net_back": "网络柜后视图.jpg",
    "odf_front": "ODF正面.jpg", "odf_back": "ODF 背面.jpg",
    "cdu_front": "CDU正面.jpg", "cdu_back": "CDU背面.jpg",
}

KM = 0.001  # mm → m


def build_data(r3):
    """room3d.json → 模板数据（米制、含 ghost 标记 / 机房列号注记 / 设备区范围）。"""
    nm = (r3["frame_wh"][0] / 1000.0) / 1000.0

    def fp_m(fp_mm):
        return [round(v * KM, 3) for v in fp_mm]

    def fp_norm_m(fp_n):
        return [round(v * nm, 3) for v in fp_n]

    room_names = sorted({c.get("room") for c in r3["cabinets"]})
    room3 = room_names[2] if len(room_names) >= 3 else None
    ghost_bands = []
    if room3:
        bands = {}
        for c in r3["cabinets"]:
            if c.get("room") != room3:
                continue
            m = re.match(r"([A-Z])\d", c.get("code") or "")
            if not m:
                continue
            zc = (c["footprint_mm"][1] + c["footprint_mm"][3]) / 2
            b = bands.setdefault(m.group(1), [zc, zc])
            b[0] = min(b[0], zc); b[1] = max(b[1], zc)
        ghost_bands = [v for k, v in bands.items() if k in {"B", "C", "D"}]

    def is_ghost(c):
        if c.get("room") != room3:
            return False
        zc = (c["footprint_mm"][1] + c["footprint_mm"][3]) / 2
        return any(z0 - 800 <= zc <= z1 + 800 for z0, z1 in ghost_bands)

    cabinets = [{
        "id": c["id"], "c": c.get("code"), "t": c.get("dev_type"),
        "f": c.get("facing"), "r": c.get("room"),
        "p": (f"{c['power_kw']:g}kW" if c.get("power_kw") else None),
        "fp": fp_m(c["footprint_mm"]),
        **({"g": 1} if is_ghost(c) else {}),
    } for c in r3["cabinets"]]

    cooling = [{"id": u["id"], "k": u["kind"], "fp": fp_m(u["footprint_mm"])} for u in r3["cooling"]]
    columns = [fp_m(c["footprint_mm"]) for c in r3["columns"]]

    trays = []
    for t in r3["trays"]:
        fp = t.get("footprint_mm")
        if not fp:
            continue
        ls = [{"e": round((ly.get("elevation_mm") or 3600) * KM, 3),
               "h": round((ly["size_mm"][1] if ly.get("size_mm") else 150) * KM, 3)}
              for ly in (t.get("layers") or [])]
        trays.append({"id": t["id"], "z": t.get("axis") == "Z", "fp": fp_m(fp),
                      "ls": ls, "tt": t.get("tray_type")})

    aisles = [{"fp": fp_norm_m(a["footprint_norm"])} for a in r3["aisles"] if a.get("footprint_norm")]
    walls = [[round(w["p0_norm"][0] * nm, 3), round(w["p0_norm"][1] * nm, 3),
              round(w["p1_norm"][0] * nm, 3), round(w["p1_norm"][1] * nm, 3)]
             for w in r3["walls"] if w.get("p0_norm") and w.get("p1_norm")]

    rooms = {}
    for c in cabinets:
        rooms.setdefault(c["r"], []).append(c["fp"])
    room_labels = []
    for i, (_, fps) in enumerate(sorted(rooms.items()), 1):
        xs = [v for fp in fps for v in (fp[0], fp[2])]
        zs = [v for fp in fps for v in (fp[1], fp[3])]
        room_labels.append({"n": f"机房{i}", "x": round(sum(xs) / len(xs), 2), "z": round(sum(zs) / len(zs), 2)})

    row_groups = {}
    for c in r3["cabinets"]:
        m = re.match(r"([A-Z])(\d+)", c.get("code") or "")
        if m:
            row_groups.setdefault((c.get("room"), m.group(1)), []).append(
                (int(m.group(2)), c["footprint_mm"]))
    row_labels = []
    for (_, letter), members in sorted(row_groups.items()):
        fps = [f for _, f in members]
        zc = sum((f[1] + f[3]) / 2 for f in fps) / len(fps) * KM
        x_lo = min(f[0] for f in fps) * KM
        x_hi = max(f[2] for f in fps) * KM
        fmin = min(members)[1]
        cmin = (fmin[0] + fmin[2]) / 2 * KM
        x = (x_lo - 1.2) if abs(cmin - x_lo) <= abs(cmin - x_hi) else (x_hi + 1.2)
        row_labels.append({"n": letter, "x": round(x, 2), "z": round(zc, 2)})

    ex = [v for c in cabinets for v in (c["fp"][0], c["fp"][2])] + \
         [v for u in cooling for v in (u["fp"][0], u["fp"][2])]
    ez = [v for c in cabinets for v in (c["fp"][1], c["fp"][3])] + \
         [v for u in cooling for v in (u["fp"][1], u["fp"][3])]

    return {
        "scale_m": round(nm, 6),
        "frame_m": [round(r3["frame_wh"][0] * KM, 2), round(r3["frame_wh"][1] * KM, 2)],
        "eq_bounds": [round(min(ex), 2), round(min(ez), 2), round(max(ex), 2), round(max(ez), 2)],
        "cabinets": cabinets, "cooling": cooling, "columns": columns,
        "trays": trays, "aisles": aisles, "walls": walls,
        "room_labels": room_labels, "row_labels": row_labels,
    }


def main():
    ap = argparse.ArgumentParser(description="uniEx 产物 → AIDA 物理孪生页（physical-twin.html）")
    ap.add_argument("doc_dir", help="TwinPackage 目录（资产库 twin-assets/<package_id>/ 或含 twin-package/ 的文档目录）")
    ap.add_argument("--title", default="2#楼四五层智算机房", help="页面标题")
    ap.add_argument("-o", "--out", default=None,
                    help="输出路径（默认 <repo>/frontend/public/twin/physical-twin.html）")
    args = ap.parse_args()

    doc = Path(args.doc_dir)
    out = Path(args.out) if args.out else HERE.parent.parent / "frontend" / "public" / "twin" / "physical-twin.html"
    sys.path.insert(0, str(HERE))
    import import_twin
    pkg = doc / "twin-package" if (doc / "twin-package" / "twin-manifest.json").exists() else doc
    mf, errors = import_twin.validate(pkg)
    if errors:
        for e in errors:
            print(f"  [契约校验] {e}")
        raise SystemExit(1)
    art = mf["artifacts"]
    r3 = json.loads((pkg / art["room3d"]).read_text(encoding="utf-8"))

    data = build_data(r3)
    issues_rel = art.get("survey_issues")
    issues = (json.loads((pkg / issues_rel).read_text(encoding="utf-8"))
              if issues_rel and (pkg / issues_rel).exists() else [])
    data["issues"] = [it for it in issues if it.get("pos") is not None]  # unlocated 不打 3D 浮标

    tex = {k: "data:image/jpeg;base64," + base64.b64encode((TEX_DIR / f).read_bytes()).decode()
           for k, f in TEX_FILES.items()}
    plan_rel = art.get("plan")
    plan_path = pkg / plan_rel if plan_rel else None
    plan = ("data:image/svg+xml;base64," + base64.b64encode(plan_path.read_bytes()).decode()
            if plan_path and plan_path.exists() else None)

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__TITLE__", args.title)
    html = html.replace("__THREE__", THREE_JS.read_text(encoding="utf-8"))
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__TEX__", json.dumps(tex, separators=(",", ":")))
    html = html.replace("__PLAN__", json.dumps(plan))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    unlocated = len(issues) - len(data["issues"])
    print(f"OK {out} ({out.stat().st_size // 1024} KB) · cab {len(data['cabinets'])} "
          f"issue {len(data['issues'])} plan {'✓' if plan else '✗'}"
          + (f" (unlocated 过滤 {unlocated})" if unlocated else ""))


if __name__ == "__main__":
    main()
