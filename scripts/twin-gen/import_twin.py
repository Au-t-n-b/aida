"""AIDA TwinPackage 导入器：校验契约（v1）→ 收入资产库 agent/data/twin-assets/。

契约真相源：uniEx 仓库 docs/uniEx-v2/06-twin-contract.md。校验只看必需字段，
容忍未知字段（minor 演进）；主版本不匹配拒绝导入（major 演进）。

用法：
  python3 scripts/twin-gen/import_twin.py <twin-package目录或含 twin-package/ 的文档目录>
"""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_MAJOR = "1"
REPO = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS = REPO / "agent" / "data" / "twin-assets"


def validate(pkg: Path):
    """返回 (manifest|None, errors)。errors 非空即拒绝导入。"""
    mf_path = pkg / "twin-manifest.json"
    if not mf_path.exists():
        return None, [f"缺少 twin-manifest.json: {pkg}"]
    try:
        mf = json.loads(mf_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, [f"twin-manifest.json 非法 JSON: {e}"]

    errors = []
    major = str(mf.get("contract_version", "")).split(".")[0]
    if major != CONTRACT_MAJOR:
        errors.append(f"契约主版本不匹配: 期望 {CONTRACT_MAJOR}.x，实际 {mf.get('contract_version')!r}（请升级 import_twin 或重产包）")
    if not mf.get("package_id"):
        errors.append("manifest 缺少 package_id")
    artifacts = mf.get("artifacts") or {}
    if "room3d" not in artifacts:
        errors.append("artifacts 缺少必需项 room3d")
    for role, rel in artifacts.items():
        fp = pkg / rel
        if not fp.exists():
            errors.append(f"artifacts.{role} 文件不存在: {rel}")
        elif rel.endswith(".json"):
            try:
                json.loads(fp.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"{rel} 非法 JSON: {e}")
    return mf, errors


def import_package(pkg: Path, assets_dir: Path = DEFAULT_ASSETS) -> Path:
    mf, errors = validate(pkg)
    if errors:
        for e in errors:
            print(f"  [契约校验] {e}")
        raise SystemExit(1)

    dest = assets_dir / mf["package_id"]
    dest.mkdir(parents=True, exist_ok=True)
    for f in pkg.iterdir():
        if f.is_file():
            shutil.copy(f, dest / f.name)

    index_path = assets_dir / "index.json"
    index = {"version": 1, "packages": []}
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = {"package_id": mf["package_id"], "site": mf.get("site"),
             "building": mf.get("building"), "floor": mf.get("floor"),
             "rooms": mf.get("rooms") or [],
             "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    index["packages"] = [p for p in index["packages"]
                         if p.get("package_id") != mf["package_id"]] + [entry]
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK 导入 {mf['package_id']} → {dest} · 资产库共 {len(index['packages'])} 包")
    return dest


def main():
    ap = argparse.ArgumentParser(description="TwinPackage → AIDA 资产库导入")
    ap.add_argument("pkg_dir", help="twin-package 目录（或含 twin-package/ 的文档目录）")
    args = ap.parse_args()
    p = Path(args.pkg_dir)
    pkg = p / "twin-package" if (p / "twin-package" / "twin-manifest.json").exists() else p
    import_package(pkg)


if __name__ == "__main__":
    main()
