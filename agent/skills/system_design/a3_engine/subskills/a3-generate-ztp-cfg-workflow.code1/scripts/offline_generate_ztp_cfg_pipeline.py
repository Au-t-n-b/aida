#!/usr/bin/env python3
"""Offline: ZTP_LLD + 项目信息收集表(ZTP配置) → ZTP 配置文件 zip。

业务来源：generate_ztp_lld.ztp_cfg_generate
注：「生成灵衢开局文件」走 generated_ztp_api.py，不在本 skill。
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from config_parser import Config  # noqa: E402
from offline_cfg_reader import OfflineCfgDataReader  # noqa: E402
from offline_cfg_writer import OfflineCfgFileCreater  # noqa: E402
from offline_common_dict import generate_common_dict  # noqa: E402
from prerequisite_runner import resolved_inputs  # noqa: E402
from ztp_cfg_inputs import find_resource, find_ztp_lld  # noqa: E402


def _resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def discover_inputs(scan_dir: Path, *, allow_auto_prereq: bool = True) -> tuple[Path, Path]:
    missing = []
    ztp_lld = find_ztp_lld(scan_dir)
    resource = find_resource(scan_dir)
    if not ztp_lld:
        missing.append("ZTP_LLD.xlsx")
    if not resource:
        missing.append("项目信息收集表.xlsx")
    if missing:
        raise FileNotFoundError(f"未找到必要输入件：{', '.join(missing)}")
    return ztp_lld.resolve(), resource.resolve()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="离线生成 ZTP 配置文件（zip）")
    p.add_argument("--ztp-lld", help="ZTP LLD Excel，sheet=网络IP规划")
    p.add_argument("--resource", help="项目信息收集表.xlsx")
    p.add_argument("--ztp-sheet", default="ZTP配置", help="公共配置 sheet")
    p.add_argument("--lld-sheet", default="网络IP规划")
    p.add_argument("--project-name", default="offline_project", help="zip 文件名前缀")
    p.add_argument("--scan-dir", help="自动扫描目录，默认 cwd")
    p.add_argument("--out-dir", default="output")
    p.add_argument(
        "--no-auto-prereq",
        action="store_true",
        help="缺失输入时不自动运行/检索前置 skill",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    scan_dir = Path(args.scan_dir) if args.scan_dir else Path.cwd()
    allow_auto = not args.no_auto_prereq

    def _generate(ztp_lld_path: Path, resource_path: Path) -> None:
        configuration = Config(_SKILL_ROOT / "conf")
        reader = OfflineCfgDataReader(configuration.confElements, ztp_lld_path, args.lld_sheet)
        cfg_list = reader.load()
        common_dict = generate_common_dict(resource_path, args.ztp_sheet)

        run_dir = Path(args.out_dir).resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
        run_dir.mkdir(parents=True, exist_ok=True)

        l1_tpl = _SKILL_ROOT / "template" / "Ztp_L1_optical_template.cfg"
        l2_tpl = _SKILL_ROOT / "template" / "Ztp_L2_optical_template.cfg"

        with tempfile.TemporaryDirectory(prefix="ztp_cfg_build_") as tmp:
            build_root = Path(tmp)
            creater = OfflineCfgFileCreater(
                cfg_list,
                common_dict,
                configuration.replaceLabel,
                l1_tpl,
                l2_tpl,
                build_root,
            )
            cfg_dir = creater.write_data_to_cfg()
            zip_base = run_dir / f"{args.project_name}_ZTP配置文件_{cfg_dir.name}"
            shutil.make_archive(str(zip_base), "zip", root_dir=cfg_dir)

        zip_path = Path(f"{zip_base}.zip")
        print(f"已生成: {zip_path}")
        print(f"设备数: {len(cfg_list)}")

    if args.ztp_lld and args.resource:
        _generate(_resolve(Path(args.ztp_lld)), _resolve(Path(args.resource)))
        return

    if allow_auto:
        with resolved_inputs(scan_dir.resolve(), _SKILL_ROOT, allow_auto_prereq=True) as (
            ztp_lld_path,
            resource_path,
        ):
            _generate(ztp_lld_path, resource_path)
        return

    ztp_lld_path, resource_path = discover_inputs(scan_dir.resolve(), allow_auto_prereq=False)
    _generate(ztp_lld_path, resource_path)


if __name__ == "__main__":
    main()
