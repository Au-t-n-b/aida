#!/usr/bin/env python3
"""Offline: 项目信息收集表(ZTP配置) + ZTP_LLD → CloudOps API 请求 → 灵衢开局 zip。

业务来源：generated_ztp_api.ztp_cfg_generate_by_api
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cloudops_client import call_cloudops_export  # noqa: E402
from prerequisite_runner import resolved_inputs  # noqa: E402
from ztp_api_converter import ZTPConfigConverter  # noqa: E402
from ztp_lq_open_inputs import find_resource, find_ztp_lld  # noqa: E402


def _resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="离线生成灵衢开局文件")
    p.add_argument("--resource", help="项目信息收集表.xlsx")
    p.add_argument("--ztp-lld", help="ZTP_LLD.xlsx")
    p.add_argument("--project-sheet", default="ZTP配置")
    p.add_argument("--lld-sheet", default="网络IP规划")
    p.add_argument("--project-name", default="offline_project", help="zip 文件名前缀")
    p.add_argument("--scan-dir", help="输入扫描目录，默认 cwd")
    p.add_argument("--out-dir", default="output")
    p.add_argument(
        "--call-api",
        action="store_true",
        help="调用 CloudOps 导出 zip（需 CLOUDOPS_AUTHORIZATION、CLOUDOPS_X_HW_ID）",
    )
    p.add_argument("--test-env", action="store_true", help="使用 beta CloudOps 网关")
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

    def build(resource: Path, ztp_lld: Path) -> dict:
        converter = ZTPConfigConverter()
        return converter.convert_to_api_request(
            resource,
            ztp_lld,
            project_sheet=args.project_sheet,
            lld_sheet=args.lld_sheet,
        )

    if args.resource and args.ztp_lld:
        api_body = build(_resolve(Path(args.resource)), _resolve(Path(args.ztp_lld)))
    elif allow_auto:
        with resolved_inputs(scan_dir.resolve(), _SKILL_ROOT, allow_auto_prereq=True) as (
            ztp_lld,
            resource,
        ):
            api_body = build(resource, ztp_lld)
    else:
        ztp_lld = find_ztp_lld(scan_dir)
        resource = find_resource(scan_dir)
        if not ztp_lld or not resource:
            missing = []
            if not ztp_lld:
                missing.append("ZTP_LLD.xlsx")
            if not resource:
                missing.append("项目信息收集表.xlsx")
            raise FileNotFoundError(f"未找到必要输入件：{', '.join(missing)}")
        api_body = build(resource.resolve(), ztp_lld.resolve())

    run_dir = Path(args.out_dir).resolve()  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "api_request.json"
    json_path.write_text(
        json.dumps(api_body, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    device_count = len(api_body.get("ztpConfigList") or [])
    print(f"已生成 API 请求体: {json_path}")
    print(f"设备数: {device_count}")

    if not args.call_api:
        print("未调用 CloudOps（加 --call-api 可导出 zip）")
        return

    response = call_cloudops_export(api_body, test_env=args.test_env)
    if response.status_code != 200:
        raise ValueError(f"CloudOps 调用失败，状态码：{response.status_code}")

    content_type = response.headers.get("Content-Type", "")
    if "application/octet-stream" not in content_type:
        raise ValueError(f"CloudOps 返回非 zip 类型：{content_type}，内容：{response.content[:500]}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = run_dir / f"{args.project_name}_灵衢开局文件_{ts}.zip"
    zip_path.write_bytes(response.content)
    print(f"已生成: {zip_path}")


if __name__ == "__main__":
    main()
