"""批量创建机房组合模型（batchCreateCombo）— 独立可运行脚本。

POST http://100.102.191.17:9091/wapi/v1/ai/combo/batchCreateCombo

用法（仅需 Python + requests）：
  pip install requests
  python batch_create_combo.py
  python batch_create_combo.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 连接配置（按需修改）────────────────────────────────────────
BASE_URL = "http://100.102.191.17:9091"
TOKEN = (
    "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJqZF9wcm9qZWN0IiwibmFtZSI6ImpkX3Byb2plY3QiLCJleHAiOjE4MTI2ODE0MjksImlhdCI6MTc4MTE0NTQyOX0."
    "qeFt444mYHdJzc_wi-fNrU1eAtyHHRnDL6kFENPUkfah9oPUizXdXg1jg1nPrxDvpKdnNJIfnDf7MA0KGM9YYA"
)
TIMEOUT_SECONDS = 300
SLEEP_BETWEEN_CALLS = 0.3

EP_BATCH_CREATE_COMBO = "/wapi/v1/ai/combo/batchCreateCombo"

# 401 / 402 / 403 机房 A3 900 液冷384卡 组合模型落位
BATCH_CREATE_COMBO_PAYLOADS: list[dict[str, Any]] = [
    {
        "model": "A3 900 液冷384卡-上",
        "diagram": "JDJL1",
        "roomName": "401",
        "items": [
            {"x": 231.89, "y": 129.66, "sp_num": 1, "rack_prefix": "A"},
            {"x": 231.89, "y": 210.52, "sp_num": 3, "rack_prefix": "C"},
        ],
    },
    {
        "model": "A3 900 液冷384卡-下",
        "diagram": "JDJL1",
        "roomName": "401",
        "items": [
            {"x": 231.89, "y": 187.13, "sp_num": 2, "rack_prefix": "B"},
            {"x": 231.89, "y": 267.99, "sp_num": 4, "rack_prefix": "D"},
        ],
    },
    {
        "model": "A3 900 液冷384卡-上",
        "diagram": "JDJL1",
        "roomName": "402",
        "items": [
            {"x": 397.88, "y": 130.45, "sp_num": 5, "rack_prefix": "A"},
            {"x": 397.88, "y": 211.31, "sp_num": 7, "rack_prefix": "C"},
        ],
    },
    {
        "model": "A3 900 液冷384卡-下",
        "diagram": "JDJL1",
        "roomName": "402",
        "items": [
            {"x": 397.88, "y": 187.13, "sp_num": 6, "rack_prefix": "B"},
            {"x": 397.88, "y": 267.99, "sp_num": 8, "rack_prefix": "D"},
        ],
    },
    {
        "model": "A3 900 液冷384卡-上",
        "diagram": "JDJL1",
        "roomName": "403",
        "items": [
            {"x": 583.37, "y": 129.66, "sp_num": 9, "rack_prefix": "A"},
        ],
    },
]


def post_json(url: str, payload: dict[str, Any], token: str, timeout: int) -> tuple[int, Any]:
    import requests

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {"raw_text": resp.text}
    except Exception as exc:
        return 0, {"error": str(exc)}


def is_ok(status: int, body: Any) -> bool:
    if not (200 <= status < 300):
        return False
    if isinstance(body, dict):
        return body.get("code") in (None, 200, "200")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="批量创建机房 A3 组合模型 (batchCreateCombo)")
    parser.add_argument("--dry-run", action="store_true", help="仅打印请求体，不实际发送")
    parser.add_argument("--sleep", type=float, default=SLEEP_BETWEEN_CALLS, help="每次请求间隔秒数")
    args = parser.parse_args()

    url = f"{BASE_URL.rstrip('/')}{EP_BATCH_CREATE_COMBO}"
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(f"[dry-run] 将发送 {len(BATCH_CREATE_COMBO_PAYLOADS)} 次 POST -> {url}")
        for i, payload in enumerate(BATCH_CREATE_COMBO_PAYLOADS, 1):
            print(f"\n--- 请求 {i}/{len(BATCH_CREATE_COMBO_PAYLOADS)} ---")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not TOKEN:
        print("[error] TOKEN 为空，请在脚本顶部填写 TOKEN")
        return 1

    results: list[dict[str, Any]] = []
    ok_count = 0

    for i, payload in enumerate(BATCH_CREATE_COMBO_PAYLOADS, 1):
        label = f"{payload.get('roomName')}/{payload.get('model')}"
        print(f"[{i}/{len(BATCH_CREATE_COMBO_PAYLOADS)}] POST {label} ...")

        status, body = post_json(url, payload, TOKEN, TIMEOUT_SECONDS)
        success = is_ok(status, body)
        if success:
            ok_count += 1
            print(f"  -> OK (HTTP {status})")
        else:
            print(f"  -> FAIL (HTTP {status}) {body}")

        results.append(
            {
                "index": i,
                "label": label,
                "http_status": status,
                "ok": success,
                "request": payload,
                "response": body,
            }
        )

        if i < len(BATCH_CREATE_COMBO_PAYLOADS) and args.sleep > 0:
            time.sleep(args.sleep)

    result_path = output_dir / "batchCreateCombo.result.json"
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": url,
        "total": len(BATCH_CREATE_COMBO_PAYLOADS),
        "ok": ok_count,
        "failed": len(BATCH_CREATE_COMBO_PAYLOADS) - ok_count,
        "results": results,
    }
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n[done] 成功 {ok_count}/{len(BATCH_CREATE_COMBO_PAYLOADS)}，详情见 {result_path}")
    return 0 if ok_count == len(BATCH_CREATE_COMBO_PAYLOADS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
