#!/usr/bin/env python3
"""007 + 网络资源需求表 → output/run_*/超平面网络规划.xlsx。

业务来源：a3_cpm_lq_ip_address.py
提示词来源：a3_cpm_L1_ip_prompt.py / a3_cpm_L2_ip_prompt.py

输出列严格对齐：
  设备名称 / LoopBack起始IP / LoopBack结束IP / BGP AS号 / 灵衢L1/L2平面 /
  超节点ID / 超节点规模 / 设备ESN / 交换机ID
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SUBSKILLS_ROOT = _SCRIPTS_DIR.parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_SUBSKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SUBSKILLS_ROOT))

from _runtime_shared.connect_007_structured import (  # noqa: E402
    structured_peer_devices,
    structured_source_devices,
    try_read_structured,
)

from cpm_lq_loopback_rules import (
    L1_IP_PER_DEVICE,
    L2_IP_PER_DEVICE,
    MAX_L1_PER_SP_INCLUSIVE,
    PLANE_L1,
    PLANE_L2,
    LoopbackAssignment,
    build_l1_template,
    build_l2_template,
    extract_sp_id_from_switch_name,
    map_template_to_sp_devices,
    parse_as_range_l1,
    parse_as_single_l2,
    parse_ip_pool_start,
)

SHEET_007_DEFAULT = "超平面端口互联"
SHEET_RES_DEFAULT_NAME = "网络资源需求表"

NET_PLANE_L1_DEFAULT = "L1交换机LoopBack地址"
NET_PLANE_L2_DEFAULT = "L2交换机LoopBack地址"

DEFAULT_PROMPT_L1 = Path("a3_cpm_L1_ip_prompt.py")
DEFAULT_PROMPT_L2 = Path("a3_cpm_L2_ip_prompt.py")

PROMPT_L1_MARKERS = (
    "每一个设备，要配7个loopback地址",
    "起始地址为从网络资源信息表的地址池ip+1",
    "BGP AS号根据设备数量",
    "灵衢L1/L2平面的字段为1",
)
PROMPT_L2_MARKERS = (
    "每一个设备，要配2个loopback地址",
    "所有交换机共用一个AS号",
    "灵衢L1/L2平面的字段为2",
)


def _resolve_local_only(p: Path) -> Path:
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def _require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = _resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be located under current working directory.\n"
            f"  resolved: {resolved}\n"
            f"  cwd:      {cwd}"
        )
    return resolved


def _list_excel_files_in_cwd() -> List[Path]:
    cwd = Path.cwd().resolve()
    files: List[Path] = []
    for ext in (".xlsx", ".xls", ".XLSX", ".XLS"):
        files.extend([p for p in cwd.rglob(f"*{ext}") if p.is_file()])
    uniq: List[Path] = []
    seen = set()
    for p in files:
        if p.name.startswith("~$"):
            continue
        rp = str(p.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq


def _autodetect_007_in_cwd() -> Path:
    cands = _list_excel_files_in_cwd()
    for p in cands:
        n = p.name
        if ("007" in n) or ("端口连线" in n) or ("端口互联" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect 007 excel in current working directory.")


def _autodetect_resource_in_cwd() -> Path:
    cands = _list_excel_files_in_cwd()
    for p in cands:
        n = p.name
        if ("项目信息收集" in n) or ("资源" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect resource excel in current working directory.")


def _find_header_row(df: "pd.DataFrame", needle: str = "设备命名") -> int:
    for i in range(len(df.index)):
        row = df.iloc[i].astype(str).tolist()
        if any(needle in (c or "") for c in row):
            return i
    raise ValueError(f"cannot locate header row by {needle!r}")


def _classify_by_sp(devices: Sequence[str]) -> "OrderedDict[int, List[str]]":
    """与原 python 的 classify_switches_by_sp 一致：按设备名中 -spN- 分组，并保留出现顺序。"""
    by_sp: "OrderedDict[int, List[str]]" = OrderedDict()
    seen: set = set()
    for dev in devices:
        if not dev:
            continue
        if dev in seen:
            continue
        seen.add(dev)
        sp_id = extract_sp_id_from_switch_name(dev)
        if sp_id is None:
            continue
        by_sp.setdefault(sp_id, []).append(dev)
    return by_sp


def _read_007_l1_l2_structured(
    path_007: Path, sheet: object
) -> Tuple["OrderedDict[int, List[str]]", "OrderedDict[int, List[str]]"]:
    """建模仿真双行表头：L2=目的端设备命名；L1=起始端中非计算服务器的交换机名（若有）。"""
    if try_read_structured(path_007, sheet) is None:
        raise ValueError("not structured 007")

    l2_values = structured_peer_devices(path_007, sheet)
    l2_by_sp = _classify_by_sp(l2_values)

    server_pat = re.compile(r"AT900|AT800|AT800T|AT800I", re.I)
    l1_candidates: List[str] = []
    for name in structured_source_devices(path_007, sheet):
        if server_pat.search(name):
            continue
        if re.search(r"-SP\d+-", name, re.I) or re.search(r"L1|LQS-L1", name, re.I):
            l1_candidates.append(name)
    l1_by_sp = _classify_by_sp(l1_candidates)

    if not l1_by_sp and not l2_by_sp:
        raise ValueError("007 structured: no L1/L2 devices with -SP<n>- in 目的端/起始端 设备命名")
    return l1_by_sp, l2_by_sp


def _read_007_l1_l2(
    path_007: Path, sheet_name: str
) -> Tuple["OrderedDict[int, List[str]]", "OrderedDict[int, List[str]]"]:
    """与原 python 一致：找'设备命名'行后，首列=L1 交换机、末列=L2 交换机，并按 sp 分组。
    建模仿真结构化表（起始端/目的端双行表头）走 _read_007_l1_l2_structured。"""

    def _read_one(sheet: object) -> Tuple["OrderedDict[int, List[str]]", "OrderedDict[int, List[str]]"]:
        if try_read_structured(path_007, sheet) is not None:
            return _read_007_l1_l2_structured(path_007, sheet)
        raw = pd.read_excel(path_007, sheet_name=sheet, header=None, dtype=str).fillna("")
        header_idx = _find_header_row(raw, "设备命名")
        data = raw.iloc[header_idx + 1 :].copy()
        if data.shape[1] < 2:
            raise ValueError("007 sheet: expected at least 2 columns (L1, L2)")
        l1_col = data.columns[0]
        l2_col = data.columns[data.shape[1] - 1]

        l1_values = [str(v).strip() for v in data[l1_col].tolist()]
        l2_values = [str(v).strip() for v in data[l2_col].tolist()]
        l1_values = [v for v in l1_values if v and v.lower() != "nan"]
        l2_values = [v for v in l2_values if v and v.lower() != "nan"]

        l1_by_sp = _classify_by_sp(l1_values)
        l2_by_sp = _classify_by_sp(l2_values)
        if not l1_by_sp and not l2_by_sp:
            raise ValueError("007 sheet: no -SP<n>- pattern found in either first or last column")
        return l1_by_sp, l2_by_sp

    sn = str(sheet_name).strip()
    if sn.lower() in ("auto", ""):
        sn = SHEET_007_DEFAULT
    sheet: object = int(sn) if sn.isdigit() else sn
    try:
        return _read_one(sheet)
    except Exception:
        xf = pd.ExcelFile(path_007)
        errors: List[str] = []
        for i, name in enumerate(xf.sheet_names):
            for candidate in (i, name):
                try:
                    return _read_one(candidate)
                except Exception as e:
                    errors.append(f"{candidate!r}: {e}")
        raise ValueError(
            "cannot parse 007 sheet; tried all sheets. Last errors: " + "; ".join(errors[-5:])
        )


def _read_plane_row(
    path_resource: Path, sheet: object, plane_name: str
) -> "pd.Series":
    df = pd.read_excel(path_resource, sheet_name=sheet, header=0)
    if "网络平面" not in df.columns:
        raise ValueError(f"resource: missing column '网络平面' (sheet={sheet!r})")
    rows = df[df["网络平面"].astype(str) == plane_name]
    if rows.empty:
        raise ValueError(
            f"resource: no row where 网络平面 == {plane_name!r} (sheet={sheet!r})"
        )
    return rows.iloc[0]


def _fuzzy_get(row: "pd.Series", *needles: str) -> Optional[object]:
    for needle in needles:
        for k in row.index:
            if needle in str(k):
                return row.get(k)
    return None


def _resolve_prompt_template_file(path_or_name: Path) -> Optional[Path]:
    if path_or_name.is_absolute():
        return path_or_name if path_or_name.is_file() else None
    cwd_candidate = (Path.cwd() / path_or_name).resolve()
    if cwd_candidate.is_file():
        return cwd_candidate
    repo_candidate = (_SCRIPTS_DIR.parent / path_or_name.name).resolve()
    if repo_candidate.is_file():
        return repo_candidate
    return None


def _extract_first_triple_quoted_block(py_text: str) -> str:
    m = re.search(r'"""([\s\S]*?)"""', py_text)
    return m.group(1) if m else ""


def _validate_prompt_markers(path: Path, markers: Sequence[str], label: str) -> None:
    body = _extract_first_triple_quoted_block(path.read_text(encoding="utf-8", errors="ignore"))
    missing = [x for x in markers if x not in body]
    if missing:
        raise ValueError(f"{label}: prompt template missing phrases {missing} in {path}")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def _emit_rows(
    *,
    assignments: List[LoopbackAssignment],
    sp_id: int,
    super_node_scale: int,
    switch_id_state: Dict[int, int],
) -> List[dict]:
    out: List[dict] = []
    for a in assignments:
        sid = switch_id_state.get(sp_id, 0)
        switch_id_state[sp_id] = sid + 1
        out.append(
            {
                "设备名称": a.device_name,
                "LoopBack起始IP": a.loopback_start,
                "LoopBack结束IP": a.loopback_end,
                "BGP AS号": int(a.bgp_as),
                "灵衢L1/L2平面": int(a.plane),
                "超节点ID": int(sp_id),
                "超节点规模": int(super_node_scale),
                "设备ESN": "",
                "交换机ID": int(sid),
            }
        )
    return out


def generate_cpm_lq_ip_address_xlsx(
    *,
    path_007: Optional[Path] = None,
    resource: Optional[Path] = None,
    sheet007: str = SHEET_007_DEFAULT,
    sheet_resource: str = SHEET_RES_DEFAULT_NAME,
    out_dir: Path = Path("output"),
    net_plane_l1: str = NET_PLANE_L1_DEFAULT,
    net_plane_l2: str = NET_PLANE_L2_DEFAULT,
    prompt_l1_file: Optional[Path] = DEFAULT_PROMPT_L1,
    prompt_l2_file: Optional[Path] = DEFAULT_PROMPT_L2,
    restrict_to_cwd: bool = True,
) -> Path:
    if path_007 is None:
        path_007 = _autodetect_007_in_cwd()
    if resource is None:
        resource = _autodetect_resource_in_cwd()

    if restrict_to_cwd:
        path_007 = _require_under_cwd(path_007, "007")
        resource = _require_under_cwd(resource, "resource")
        out_dir = _require_under_cwd(out_dir, "out-dir")
    else:
        path_007 = _resolve_local_only(path_007)
        resource = _resolve_local_only(resource)
        out_dir = _resolve_local_only(out_dir)

    if not path_007.is_file():
        raise ValueError(f"007 file not found: {path_007}")
    if not resource.is_file():
        raise ValueError(f"resource file not found: {resource}")

    if prompt_l1_file is not None:
        rp = _resolve_prompt_template_file(prompt_l1_file)
        if rp is not None:
            _validate_prompt_markers(rp, PROMPT_L1_MARKERS, "L1")
    if prompt_l2_file is not None:
        rp = _resolve_prompt_template_file(prompt_l2_file)
        if rp is not None:
            _validate_prompt_markers(rp, PROMPT_L2_MARKERS, "L2")

    l1_by_sp, l2_by_sp = _read_007_l1_l2(path_007, sheet007)

    sp_to_l1_count: Dict[int, int] = {sp: len(v) for sp, v in l1_by_sp.items()}
    sp_to_l2_count: Dict[int, int] = {sp: len(v) for sp, v in l2_by_sp.items()}

    if not sp_to_l1_count and not sp_to_l2_count:
        raise ValueError("007: cannot find any L1 or L2 devices grouped by sp")

    # 单超节点最大节点数校验（与原 python 校验等价）
    if sp_to_l1_count:
        max_l1_sp = max(sp_to_l1_count, key=lambda k: sp_to_l1_count[k])
        max_l1_count = sp_to_l1_count[max_l1_sp]
        if max_l1_count > MAX_L1_PER_SP_INCLUSIVE:
            raise ValueError(
                f"单超节点最大节点数 {max_l1_count}（sp{max_l1_sp}），超过最大规格 {MAX_L1_PER_SP_INCLUSIVE}，请检查原始数据"
            )
    else:
        max_l1_count = 0

    max_l2_count = max(sp_to_l2_count.values()) if sp_to_l2_count else 0

    # --- 资源表：L1 / L2 两个网络平面行 ---
    sheet_res: object = sheet_resource
    if isinstance(sheet_resource, str) and sheet_resource.strip().isdigit():
        sheet_res = int(sheet_resource.strip())

    row_l1 = _read_plane_row(resource, sheet_res, net_plane_l1)
    row_l2 = _read_plane_row(resource, sheet_res, net_plane_l2)

    l1_pool_raw = str(_fuzzy_get(row_l1, "地址池") or "").strip()
    if not l1_pool_raw:
        raise ValueError(f"resource: L1 行（网络平面={net_plane_l1!r}）的 地址池* 为空")
    l1_as_raw = _fuzzy_get(row_l1, "EBGP AS", "AS")
    if l1_as_raw is None or str(l1_as_raw).strip() == "":
        raise ValueError(f"resource: L1 行（网络平面={net_plane_l1!r}）的 EBGP AS 规划 为空")

    l2_pool_raw = str(_fuzzy_get(row_l2, "地址池") or "").strip()
    if not l2_pool_raw:
        raise ValueError(f"resource: L2 行（网络平面={net_plane_l2!r}）的 地址池* 为空")
    l2_as_raw = _fuzzy_get(row_l2, "EBGP AS", "AS")
    if l2_as_raw is None or str(l2_as_raw).strip() == "":
        raise ValueError(f"resource: L2 行（网络平面={net_plane_l2!r}）的 EBGP AS 规划 为空")

    l1_pool_start = parse_ip_pool_start(l1_pool_raw)
    l1_as_start, l1_as_end = parse_as_range_l1(l1_as_raw)

    l2_pool_start = parse_ip_pool_start(l2_pool_raw)
    l2_shared_as = parse_as_single_l2(l2_as_raw)

    # --- 构建模板：按"设备数最多的 sp"计算 ---
    l1_template = build_l1_template(
        max_l1_per_sp=max_l1_count,
        pool_start=l1_pool_start,
        as_start=l1_as_start,
        as_end=l1_as_end,
    )
    l2_template = build_l2_template(
        max_l2_per_sp=max_l2_count,
        pool_start=l2_pool_start,
        shared_as=l2_shared_as,
    )

    # --- 逐 sp 套用模板，组装输出 ---
    switch_id_state_l1: Dict[int, int] = {}
    switch_id_state_l2: Dict[int, int] = {}
    rows_final: List[dict] = []

    for sp_id, l1_devices in l1_by_sp.items():
        super_node_scale = sp_to_l1_count.get(sp_id, 0) * 8
        l1_rows = map_template_to_sp_devices(template=l1_template, sp_devices=l1_devices)
        rows_final.extend(
            _emit_rows(
                assignments=l1_rows,
                sp_id=sp_id,
                super_node_scale=super_node_scale,
                switch_id_state=switch_id_state_l1,
            )
        )

    for sp_id, l2_devices in l2_by_sp.items():
        # 超节点规模与 L1 一致地按"该 sp 的 L1 设备数 × 8"算（与原 python 对齐）
        super_node_scale = sp_to_l1_count.get(sp_id, 0) * 8
        l2_rows = map_template_to_sp_devices(template=l2_template, sp_devices=l2_devices)
        rows_final.extend(
            _emit_rows(
                assignments=l2_rows,
                sp_id=sp_id,
                super_node_scale=super_node_scale,
                switch_id_state=switch_id_state_l2,
            )
        )

    df_final = pd.DataFrame(
        rows_final,
        columns=[
            "设备名称",
            "LoopBack起始IP",
            "LoopBack结束IP",
            "BGP AS号",
            "灵衢L1/L2平面",
            "超节点ID",
            "超节点规模",
            "设备ESN",
            "交换机ID",
        ],
    )

    ts = _timestamp()
    run_dir = out_dir.resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    _ensure_out_dir(run_dir)
    # 统一 A3 前缀产物名（LLD 融合 / ZTP 扫描）；legacy「超平面网络规划.xlsx」由 lld_staging 别名兼容
    out_final = run_dir / "A3超平面网络规划.xlsx"
    with pd.ExcelWriter(out_final, engine="openpyxl") as w:
        df_final.to_excel(w, index=False, sheet_name="超平面网络规划")
    # 清理历史无 A3 前缀的同名产物，避免 Output 出现两份相同内容
    legacy = run_dir / "超平面网络规划.xlsx"
    if legacy.is_file() and legacy.resolve() != out_final.resolve():
        legacy.unlink(missing_ok=True)

    return out_final


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Offline A3 超平面（CPM/LQ）LoopBack & BGP AS planning pipeline"
    )
    p.add_argument(
        "--007",
        dest="path_007",
        default=None,
        type=Path,
        help="007 端口连线表 (.xlsx)。默认在 cwd 下自动探测。",
    )
    p.add_argument(
        "--resource",
        default=None,
        type=Path,
        help="项目信息收集表/网络资源需求表 (.xlsx)。默认在 cwd 下自动探测。",
    )
    p.add_argument(
        "--sheet007",
        default=SHEET_007_DEFAULT,
        help=f"007 的 sheet（默认 {SHEET_007_DEFAULT!r}；解析失败时自动扫描所有 sheet）",
    )
    p.add_argument(
        "--sheet-resource",
        default=SHEET_RES_DEFAULT_NAME,
        help=f"资源表 sheet 名（默认 {SHEET_RES_DEFAULT_NAME!r}；传入纯数字则按 index 解析）",
    )
    p.add_argument(
        "--out-dir",
        default=Path("output"),
        type=Path,
        help="输出目录（默认 ./output；必须位于 cwd 树下）",
    )
    p.add_argument(
        "--net-plane-l1",
        default=NET_PLANE_L1_DEFAULT,
        help=f"L1 网络平面行名（默认 {NET_PLANE_L1_DEFAULT!r}）",
    )
    p.add_argument(
        "--net-plane-l2",
        default=NET_PLANE_L2_DEFAULT,
        help=f"L2 网络平面行名（默认 {NET_PLANE_L2_DEFAULT!r}）",
    )
    p.add_argument(
        "--skip-prompt-check",
        action="store_true",
        help="跳过 a3_cpm_L1/L2 提示词关键短语的一致性校验",
    )
    args = p.parse_args(argv)

    try:
        out_final = generate_cpm_lq_ip_address_xlsx(
            path_007=args.path_007,
            resource=args.resource,
            sheet007=args.sheet007,
            sheet_resource=args.sheet_resource,
            out_dir=args.out_dir,
            net_plane_l1=args.net_plane_l1,
            net_plane_l2=args.net_plane_l2,
            prompt_l1_file=None if args.skip_prompt_check else DEFAULT_PROMPT_L1,
            prompt_l2_file=None if args.skip_prompt_check else DEFAULT_PROMPT_L2,
            restrict_to_cwd=True,
        )
        print(f"OK: wrote {out_final.name} under {out_final.parent}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
