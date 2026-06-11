"""sim_api · 建模仿真软件 API 统一出口（唯一对外副作用通道）

铁律④（外发副作用走唯一出口 + 留痕 + 默认 dry-run）落到建模仿真：
所有对仿真软件 wapi 网关（queryDeviceModel/querySlotMapping/batchCreateCombo/
batchMoveNodes）的调用一律经 SimApiClient，禁止业务 step 裸用 requests。

- **dry-run 默认开**：未设 env `SIM_API_LIVE=1` 时不发真请求，返回 mock 成功 + 全量留痕。
  内网可达时（用户到内网）置 `SIM_API_LIVE=1` 即真跑，业务代码零改。
- **留痕**：每次调用（含 dry-run）追加到 `RunTime/sim_api_calls.jsonl`，payload/响应可回溯。

配置（env，均有默认）：
  SIM_API_BASE   默认 http://100.102.191.17:9091
  SIM_API_TOKEN  默认内置 Bearer（exp≈2027）
  SIM_API_LIVE   "1"/"true" → 真发请求；否则 dry-run
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

DEFAULT_API_BASE = "http://100.102.191.17:9091"
# 软件 Web UI（iframe 用，区别于 :9091 的 wapi 网关）
DEFAULT_WEB_URL = "http://100.102.191.17:9090/access.html?v=2.25.6"
_DEFAULT_TOKEN = (
    "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ6anlkX3Rlc3QiLCJuYW1lIjoiemp5ZF90ZXN0IiwiZXhw"
    "IjoxODEyNTQ0MTI1LCJpYXQiOjE3ODEwMDgxMjV9.MOzbP2ctmgL49PduQFli_gwdabtacy9p3Nv8"
    "Xk7O80UtIWR6VTgigbftH40wEgR_xfb7KvwroiStbvQtOy2F6Q"
)

# 端点
PATH_QUERY_DEVICE = "/wapi/v1/ai/model/queryDeviceModel"
PATH_QUERY_SLOT = "/wapi/v1/ai/model/querySlotMapping"
PATH_CREATE_COMBO = "/wapi/v1/ai/combo/batchCreateCombo"
PATH_MOVE_NODES = "/wapi/v1/ai/nodes/batchMoveNodes"

_CALL_LOG_REL = "ProjectData/RunTime/sim_api_calls.jsonl"


def is_live() -> bool:
    return os.environ.get("SIM_API_LIVE", "").strip().lower() in ("1", "true", "yes")


def web_url() -> str:
    return os.environ.get("SIM_WEB_URL", "").strip() or DEFAULT_WEB_URL


class SimApiClient:
    """仿真 API 客户端。dry-run 时不发请求、返回 mock 成功、全量留痕。"""

    def __init__(
        self,
        work_root: str | Path | None = None,
        *,
        live: bool | None = None,
        api_base: str | None = None,
        token: str | None = None,
        emit: Callable[[str], None] | None = None,
    ) -> None:
        self.live = is_live() if live is None else live
        self.api_base = (api_base or os.environ.get("SIM_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        self.token = token or os.environ.get("SIM_API_TOKEN") or _DEFAULT_TOKEN
        self.work_root = Path(work_root) if work_root else None
        self.emit = emit

    # ── 留痕 ──────────────────────────────────────────────────────────────────
    def _log_call(self, record: dict[str, Any]) -> None:
        if not self.work_root:
            return
        log_path = self.work_root / _CALL_LOG_REL
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _emit(self, msg: str) -> None:
        if self.emit:
            self.emit(msg)

    # ── 底层 POST（dry-run / live 分流）────────────────────────────────────────
    def post(self, path: str, payload: dict, *, timeout: int = 240) -> tuple[int, Any]:
        url = self.api_base + path
        if not self.live:
            body = {"code": 200, "message": "dry-run", "data": [], "_dry_run": True}
            self._log_call({"mode": "dry-run", "path": path, "payload": payload, "response": body})
            self._emit(f"    [dry-run] POST {path}  payload={json.dumps(payload, ensure_ascii=False)[:200]}")
            return 200, body

        import requests  # 仅 live 分支需要

        self._emit(f"    [请求] POST {url}")
        try:
            resp = requests.post(
                url, json=payload,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.token}"},
                timeout=timeout,
            )
            try:
                body = resp.json()
            except Exception:
                body = {"raw_text": resp.text[:1000]}
            status = resp.status_code
        except Exception as exc:
            status, body = 0, {"error": str(exc)}
        self._log_call({"mode": "live", "path": path, "payload": payload,
                        "status": status, "response": body})
        self._emit(f"    [HTTP] {status}  {json.dumps(body, ensure_ascii=False)[:200]}")
        return status, body

    @staticmethod
    def ok(status: int, body: Any) -> bool:
        code = body.get("code") if isinstance(body, dict) else None
        return status == 200 and (code in (200, None))

    # ── 高层接口 ──────────────────────────────────────────────────────────────
    def query_device_model(self) -> list[Any]:
        """全量设备目录（model="all"）。dry-run 返回空列表。"""
        status, data = self.post(PATH_QUERY_DEVICE, {"model": "all"})
        if not self.ok(status, data):
            return []
        if isinstance(data, dict):
            v = data.get("data")
            return v if isinstance(v, list) else []
        return data if isinstance(data, list) else []

    def query_slot_mapping(self, sim_model: str) -> tuple[int, Any]:
        """板卡槽位清单（原始 data，调用方 flatten）。"""
        status, data = self.post(PATH_QUERY_SLOT, {"model": sim_model})
        raw = data.get("data") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        return status, (raw or [])

    def batch_create_combo(self, body: dict) -> tuple[int, Any]:
        return self.post(PATH_CREATE_COMBO, body)

    def batch_move_nodes(self, body: dict) -> tuple[int, Any]:
        return self.post(PATH_MOVE_NODES, body)
