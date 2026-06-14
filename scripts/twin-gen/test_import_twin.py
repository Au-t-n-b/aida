"""TwinPackage 导入器单测。运行：python3 -m pytest scripts/twin-gen/test_import_twin.py -v"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_twin  # noqa: E402


def _make_pkg(tmp_path: Path, ver="1.0") -> Path:
    pkg = tmp_path / "twin-package"
    pkg.mkdir()
    (pkg / "room3d.json").write_text(json.dumps({"cabinets": []}), encoding="utf-8")
    (pkg / "survey-issues.json").write_text("[]", encoding="utf-8")
    (pkg / "plan.svg").write_text("<svg/>", encoding="utf-8")
    (pkg / "twin-manifest.json").write_text(json.dumps({
        "contract_version": ver, "package_id": "demo-abc12345",
        "site": None, "building": "2#楼", "floor": "4-5F", "rooms": ["机房1"],
        "artifacts": {"room3d": "room3d.json", "survey_issues": "survey-issues.json",
                      "plan": "plan.svg"},
    }, ensure_ascii=False), encoding="utf-8")
    return pkg


def test_validate_ok(tmp_path):
    mf, errors = import_twin.validate(_make_pkg(tmp_path))
    assert errors == [] and mf["package_id"] == "demo-abc12345"


def test_validate_rejects_major_mismatch(tmp_path):
    _, errors = import_twin.validate(_make_pkg(tmp_path, ver="2.0"))
    assert any("主版本" in e for e in errors)


def test_validate_rejects_missing_artifact(tmp_path):
    pkg = _make_pkg(tmp_path)
    (pkg / "plan.svg").unlink()
    _, errors = import_twin.validate(pkg)
    assert any("plan" in e for e in errors)


def test_import_copies_and_indexes(tmp_path):
    pkg = _make_pkg(tmp_path)
    assets = tmp_path / "twin-assets"
    dest = import_twin.import_package(pkg, assets_dir=assets)
    assert (dest / "twin-manifest.json").exists() and (dest / "room3d.json").exists()
    index = json.loads((assets / "index.json").read_text(encoding="utf-8"))
    assert index["packages"][0]["package_id"] == "demo-abc12345"
    assert index["packages"][0]["building"] == "2#楼"
    # 重复导入幂等：同 package_id 覆盖，不重复记账
    import_twin.import_package(pkg, assets_dir=assets)
    index = json.loads((assets / "index.json").read_text(encoding="utf-8"))
    assert len(index["packages"]) == 1
