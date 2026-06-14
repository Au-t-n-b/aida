#!/usr/bin/env python3
"""上传本地文件到 AIDA 数据中心（POST /api/v1/files/upload）。

规范: 需求开发/AIDA数据中心API调用规范2.md §5.3

示例:
  # 上传到交付预案「输出结果」（需先配置 agent/.env 中 DATA_CENTER_BASE_URL）
  python 需求开发/upload_datacenter_file.py \\
    --file data/delivery/mock/mock_project/早期介入/交付预案/输出结果/项目责任矩阵.xlsx \\
    --project-id 70e5ca737ae5433e9f0f3134d216acf7 \\
    --module-code proposal \\
    --file-stage 输出结果

  # 使用账号密码自动登录（也可设置环境变量 DC_USERNAME / DC_PASSWORD）
  python 需求开发/upload_datacenter_file.py \\
    --file ./test.txt \\
    --project-id 70e5ca737ae5433e9f0f3134d216acf7 \\
    --module-code proposal \\
    --file-stage 输出结果 \\
    --username admin --password 'admin@123'

  # 上传到组织资产（不传 project-id / file-stage）
  python 需求开发/upload_datacenter_file.py \\
    --file data/delivery/mock/组织资产/责任矩阵/责任矩阵模板.xlsx \\
    --module-code org-assets \\
    --folder-sub-path 责任矩阵
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

# 将 aida 根目录加入 sys.path，以便 import shared.*
_AIDA_ROOT = Path(__file__).resolve().parents[1]
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))

from shared.datacenter import DataCenterClient, DataCenterError, SemanticFileRef
from shared.datacenter.config import datacenter_base, http_proxy, ssl_verify


async def _login(username: str, password: str) -> str:
    base = datacenter_base()
    async with httpx.AsyncClient(
        base_url=base,
        timeout=httpx.Timeout(30.0, connect=10.0),
        proxy=http_proxy(),
        verify=ssl_verify(),
        trust_env=False,
    ) as client:
        resp = await client.post(
            "/api/v1/users/login",
            json={"username": username, "password": password},
        )
        if resp.status_code >= 400:
            raise DataCenterError(
                resp.status_code,
                f"登录失败: HTTP {resp.status_code} {resp.text[:200]}",
                status_code=resp.status_code,
            )
        body = resp.json()
        if int(body.get("code", -1)) != 0:
            raise DataCenterError(
                int(body.get("code", -1)),
                str(body.get("message") or "登录失败"),
            )
        token = (body.get("data") or {}).get("token")
        if not token:
            raise DataCenterError(500, "登录响应缺少 token")
        return str(token)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="上传本地文件到 AIDA 数据中心（语义寻址）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "环境变量:\n"
            "  DATA_CENTER_BASE_URL  数据中心地址（agent/.env 会自动加载）\n"
            "  DC_USERNAME / DC_PASSWORD  未传 --token 时用于登录\n"
            "  DC_TOKEN                   可直接指定 Bearer token\n"
        ),
    )
    p.add_argument(
        "-f",
        "--file",
        required=True,
        type=Path,
        help="待上传的本地文件路径",
    )
    p.add_argument(
        "--module-code",
        required=True,
        help="目标模块代码，如 proposal / contract / org-assets",
    )
    p.add_argument(
        "--file-stage",
        default="",
        help="IPO 阶段：输入文件 / 解析结果 / 输出结果；组织资产与 flat 模块不传",
    )
    p.add_argument(
        "--project-id",
        default="",
        help="目标项目 UUID32；组织资产上传时不传",
    )
    p.add_argument(
        "--folder-sub-path",
        default="",
        help="阶段目录下的子目录相对路径，如 责任矩阵",
    )
    p.add_argument(
        "--remote-name",
        default="",
        help="远端文件名（含扩展名），默认取本地文件名",
    )
    p.add_argument(
        "--file-display-name",
        default="",
        help="文件业务显示名（可选）",
    )
    p.add_argument("--token", default="", help="Bearer token（可选，鉴权为可选）")
    p.add_argument("--username", default="", help="登录用户名（未传 token 时使用）")
    p.add_argument("--password", default="", help="登录密码")
    p.add_argument(
        "--no-auth",
        action="store_true",
        help="不带 token 上传（可信内网机机调用）",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 输出上传结果",
    )
    return p


async def _run(args: argparse.Namespace) -> dict:
    local_path = args.file.expanduser().resolve()
    if not local_path.is_file():
        raise SystemExit(f"本地文件不存在: {local_path}")

    module_code = args.module_code.strip()
    file_stage = args.file_stage.strip() or None
    project_id = args.project_id.strip() or None
    folder_sub_path = args.folder_sub_path.strip() or None
    remote_name = args.remote_name.strip() or local_path.name

    if module_code != "org-assets" and not project_id:
        raise SystemExit("非组织资产上传必须指定 --project-id")

    token: str | None = None
    if not args.no_auth:
        token = (
            args.token.strip()
            or os.environ.get("DC_TOKEN", "").strip()
            or None
        )
        if not token:
            username = args.username.strip() or os.environ.get("DC_USERNAME", "").strip()
            password = args.password or os.environ.get("DC_PASSWORD", "")
            if username and password:
                print(f"正在登录数据中心 ({datacenter_base()}) …")
                token = await _login(username, password)
                print("登录成功")

    content = local_path.read_bytes()
    ref = SemanticFileRef(
        module_code=module_code,
        file_stage=file_stage,
        folder_sub_path=folder_sub_path,
        project_id=project_id,
    )

    print(
        f"上传 {local_path} ({len(content)} bytes) → "
        f"module={module_code}"
        + (f" stage={file_stage}" if file_stage else "")
        + (f" subPath={folder_sub_path}" if folder_sub_path else "")
        + f" name={remote_name}"
    )

    client = DataCenterClient(token)
    result = await client.upload_file(
        ref,
        content,
        remote_name,
        file_display_name=args.file_display_name.strip() or None,
    )
    return result


def main() -> None:
    args = _build_parser().parse_args()
    try:
        result = asyncio.run(_run(args))
    except DataCenterError as exc:
        raise SystemExit(f"数据中心错误 [{exc.code}]: {exc.message}") from exc
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("上传成功:")
        print(f"  fileId      : {result.get('fileId')}")
        print(f"  fileName    : {result.get('fileName')}")
        print(f"  logicalPath : {result.get('logicalPath')}")
        print(f"  sizeBytes   : {result.get('sizeBytes')}")
        print(f"  checksum    : {result.get('checksum')}")


if __name__ == "__main__":
    main()
