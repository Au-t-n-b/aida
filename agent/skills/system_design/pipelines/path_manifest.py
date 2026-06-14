"""系统设计路径清单 · 从 project_paths.json 加载（全部为绝对路径）。"""

from __future__ import annotations



import json

from functools import lru_cache

from pathlib import Path

from typing import Any



_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "project_paths.json"

# 工程根（aida 仓库根）= project_paths.json 的 parents[3]
#   project_paths.json → system_design → skills → agent → aida
# project_paths.json 里的相对路径一律相对工程根解析（与进程 CWD 无关 ——
# a3_bridge 执行子 pipeline 时会 os.chdir 到 data_root，CWD 不稳定，
# 故不能用 Path(raw).resolve() 的 CWD 锚定）。
_PROJECT_ROOT = _MANIFEST_PATH.parents[3]



INPUT_TAGS = (

    "resource",

    "Interconnection_Relationship",

    "Device_Info",

    "Location_Information",

    "Test_Case",

)





@lru_cache(maxsize=1)

def load_manifest() -> dict[str, Any]:

    with _MANIFEST_PATH.open(encoding="utf-8") as f:

        return json.load(f)





def manifest_path() -> Path:

    return _MANIFEST_PATH





def reload_manifest() -> dict[str, Any]:

    load_manifest.cache_clear()

    return load_manifest()





def _section(key: str) -> dict[str, Any]:

    block = load_manifest().get(key) or {}

    return block if isinstance(block, dict) else {}





def _path(raw: str) -> Path:

    s = str(raw or "").strip()

    p = Path(s) if s else Path(".")

    # 绝对路径原样 resolve；相对路径锚定工程根（CWD 无关）。

    if not p.is_absolute():

        p = _PROJECT_ROOT / p

    return p.resolve()





def resolve_data_root() -> Path:

    return _path(str(load_manifest().get("data_root") or ""))





def read_scan_dir_for_tag(tag: str) -> Path:

    by_tag = _section("read").get("scan_by_tag") or {}

    raw = by_tag.get(tag) or by_tag.get("resource") or _section("upload").get("save_dir") or ""

    return _path(str(raw))





def read_scan_dirs() -> list[Path]:

    dirs: list[Path] = []

    seen: set[str] = set()

    for tag in INPUT_TAGS:

        p = read_scan_dir_for_tag(tag)

        key = str(p)

        if key in seen:

            continue

        seen.add(key)

        dirs.append(p)

    return dirs





def abs_upload_dir() -> Path:

    return _path(str(_section("upload").get("save_dir") or ""))





def abs_input_dir() -> Path:

    return abs_upload_dir()





def abs_artifacts_dir() -> Path:

    return _path(str(_section("output").get("artifacts_dir") or ""))


def scan_artifacts_rel_paths() -> list[str]:
    """扫描 output/artifacts_dir 磁盘 → 相对 data_root 路径（唯一真相 · 不读 run state）。"""
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
        except ValueError:
            pass
    return res





def ensure_parent_dir(path: Path | str) -> None:

    Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)





def ensure_dir(path: Path | str) -> None:

    Path(path).resolve().mkdir(parents=True, exist_ok=True)





def ensure_project_data_dirs() -> None:

    return





def relpath_from_data_root(abs_path: Path | str) -> str:

    root = resolve_data_root()

    p = Path(abs_path).resolve()

    try:

        return str(p.relative_to(root)).replace("\\", "/")

    except ValueError:

        return str(p).replace("\\", "/")





def artifact_allowed_roots() -> tuple[Path, ...]:

    seen: set[str] = set()

    out: list[Path] = []

    for p in (resolve_data_root(), abs_upload_dir(), abs_artifacts_dir(), *read_scan_dirs()):

        rp = p.resolve()

        key = str(rp)

        if key in seen:

            continue

        seen.add(key)

        out.append(rp)

    return tuple(out)





def resolve_artifact_file(path: str) -> Path:

    raw = (path or "").strip()

    if not raw:

        raise ValueError("empty path")

    norm = raw.replace("\\", "/")
    candidates: list[Path] = []
    p = Path(raw)
    if p.is_absolute():
        candidates.append(p.resolve())
    else:
        candidates.append((resolve_data_root() / norm).resolve())
        if norm.startswith("ProjectData/"):
            candidates.append((resolve_data_root() / norm.split("ProjectData/", 1)[-1]).resolve())

    data_root = resolve_data_root().resolve()

    def _allowed(full: Path) -> bool:
        if not full.is_file():
            return False
        try:
            full.relative_to(data_root)
            return True
        except ValueError:
            pass
        for root in artifact_allowed_roots():
            try:
                full.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    for full in candidates:
        if _allowed(full):
            return full

    name = Path(norm).name
    if name:
        for root in artifact_allowed_roots():
            if not root.is_dir():
                continue
            for hit in root.rglob(name):
                if hit.is_file() and not hit.name.startswith("~$") and _allowed(hit.resolve()):
                    return hit.resolve()

    raise FileNotFoundError(raw)





def relpath_for_artifact(abs_path: Path | str) -> str:

    return relpath_from_data_root(abs_path)





default_data_root = resolve_data_root

rel_read_scan_dirs = lambda: [str(p) for p in read_scan_dirs()]

rel_primary_input_dir = lambda: str(abs_input_dir())

rel_upload_save_dir = lambda: str(abs_upload_dir())

rel_artifacts_dir = lambda: str(abs_artifacts_dir())

