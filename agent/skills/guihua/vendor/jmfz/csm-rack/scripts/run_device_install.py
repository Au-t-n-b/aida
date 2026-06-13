"""参数面 Leaf 跨视图上架编排入口（真实调用新 wapi 网关）。

业务流（跨视图）：
  0) reset 参数面：deleteTopology(参数面) -> createShape(顶层, 参数面)
     （硬保护：deleteTopology 的目标视图绝不允许等于 room_diagram“机房”）
  1) build_leaf_device  -> POST createDevice（diagram=参数面，54 台 CE9866）
  2) read_servers       -> DataGrid.xlsx 获取 432 个有序 server 名
  3) build_rack_payloads-> POST batchRackDevices x18
     （device_diagram=参数面，cabinet_diagram=机房，每柜一次精确落位）
  4) （可选）search 校验：确认 leaf 已进入“机房”
  5) build_server_leaf_topo -> POST batchCreateLink x2（递归，diagram=机房，server→leaf 奇/偶双轨）
  6) 汇总每次调用的 HTTP 状态码，落盘 output/

为什么顺序是 建 leaf -> 上架 -> 连线：
  跨视图连线只能在单个视图内进行；leaf 建在“参数面”、server 在“机房”，
  必须先上架把 leaf 带进“机房”，再在“机房”内用 batchCreateLink（递归）连线。

绝对约束：
  - deleteTopology 只作用于“参数面”（leaf_diagram），绝不作用于“机房”（room_diagram）。
  - 不对“机房”做任何删除；server/机柜/组合模型为预建资产。

落盘到 output/：
  resetView.result.json
  createDevice.params.json
  batchRackDevices.params.json
  batchCreateLink.params.json
  execution-result.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sim_api_client import (  # noqa: E402
    extract_data,
    is_ok,
    normalize_base_url,
    post_sim_json,
    resolve_token,
)
from read_servers import server_names  # noqa: E402
from build_leaf_device import build_create_leaf_payload  # noqa: E402
from build_server_leaf_topo import build_server_leaf_payloads  # noqa: E402
from build_rack_payloads import build_rack_payloads  # noqa: E402

_ROOT = _HERE.parent
_DEFAULT_CONFIG = _ROOT / "config.json"
_DEFAULT_CONFIG_EXAMPLE = _ROOT / "config.example.json"
_OUTPUT_DIR = _ROOT / "output"

EP_QUERY_PORT = "/wapi/v1/ai/model/queryPort"
EP_CREATE_DEVICE = "/wapi/v1/ai/device/createDevice"
EP_CREATE_SHAPE = "/wapi/v1/ai/shape/createShape"
EP_DELETE_TOPO = "/wapi/v1/ai/topology/deleteTopology"
EP_BATCH_RACK = "/wapi/v1/ai/device/batchRackDevices"
EP_CREATE_TOPO = "/wapi/v1/ai/link/createTopoLink"
EP_BATCH_LINK = "/wapi/v1/ai/link/batchCreateLink"
EP_SEARCH = "/wapi/v1/search"

# 拓扑端点名 -> 路径
_TOPO_ENDPOINTS = {
    "batchCreateLink": EP_BATCH_LINK,
    "createTopoLink": EP_CREATE_TOPO,
}


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        if _DEFAULT_CONFIG_EXAMPLE.exists():
            print(f"[warn] {path.name} 不存在，回退到 config.example.json（请复制并填写真实配置）")
            path = _DEFAULT_CONFIG_EXAMPLE
        else:
            raise FileNotFoundError(f"找不到配置: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def make_port_querier(base_url: str, token: str, timeout: int):
    """返回 queryPort querier：model -> (http_status, port_rows)。"""
    def port_querier(model: str):
        status, body = post_sim_json(
            f"{base_url}{EP_QUERY_PORT}", {"model": model}, token=token, timeout=timeout
        )
        data = extract_data(body)
        return status, data if isinstance(data, list) else []
    return port_querier


def _strip_meta(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != "_meta"}


def _delete_not_found(body: Any) -> bool:
    """业务面不存在时 deleteTopology 可能报错，视为无需清理。"""
    if not isinstance(body, dict):
        return False
    code = body.get("code")
    msg = str(body.get("message") or "")
    return code in (800005,) or "not found" in msg.lower() or "不存在" in msg


def reset_leaf_view(
    base_url: str,
    token: str,
    leaf_diagram: str,
    parent_diagram: str,
    room_diagram: str,
    timeout: int,
) -> dict[str, Any]:
    """重置“参数面”视图：deleteTopology(参数面) -> createShape(顶层, 参数面)。

    硬保护：leaf_diagram 绝不允许等于 room_diagram（机房），否则立即中止。
    """
    info: dict[str, Any] = {
        "leaf_diagram": leaf_diagram,
        "parent_diagram": parent_diagram,
        "room_diagram": room_diagram,
    }
    if not leaf_diagram or leaf_diagram == room_diagram:
        info["aborted"] = True
        info["reason"] = (
            f"安全中止：待重置视图({leaf_diagram!r}) 不能等于机房视图({room_diagram!r})；"
            f"deleteTopology 绝不允许作用于机房。"
        )
        return info

    # 1) deleteTopology(参数面)
    d_status, d_body = post_sim_json(
        f"{base_url}{EP_DELETE_TOPO}", {"diagram": leaf_diagram}, token=token, timeout=timeout
    )
    delete_ok = is_ok(d_status, d_body) or _delete_not_found(d_body)
    info["delete_http"] = d_status
    info["delete_ok"] = delete_ok
    info["delete_response"] = d_body

    # 2) createShape(顶层, 参数面)
    c_status, c_body = post_sim_json(
        f"{base_url}{EP_CREATE_SHAPE}",
        {"diagram": parent_diagram, "shape_name": leaf_diagram},
        token=token,
        timeout=timeout,
    )
    create_ok = is_ok(c_status, c_body)
    info["create_http"] = c_status
    info["create_ok"] = create_ok
    info["create_response"] = c_body
    info["action"] = "reset" if (delete_ok and create_ok) else "reset_failed"
    return info


def verify_leaves_in_room(
    base_url: str,
    token: str,
    room_diagram: str,
    sample_leaf: str,
    timeout: int,
) -> dict[str, Any]:
    """上架后用全局 search 校验某台 leaf 是否已落到“机房”内（best-effort，仅告警）。"""
    info: dict[str, Any] = {"sample_leaf": sample_leaf, "room_diagram": room_diagram}
    status, body = post_sim_json(
        f"{base_url}{EP_SEARCH}",
        {"keywords": sample_leaf, "exactMatch": True},
        token=token,
        timeout=timeout,
    )
    info["http"] = status
    data = extract_data(body)
    results = []
    if isinstance(data, dict):
        results = data.get("result_list") or []
    info["found"] = bool(results)
    if results:
        first = results[0] if isinstance(results[0], dict) else {}
        info["parent_name"] = first.get("parentname")
    return info


def execute_calls(
    url: str,
    payloads: list[dict[str, Any]],
    token: str,
    timeout: int,
    sleep_s: float,
    *,
    extra_ok_codes: set[int] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for i, payload in enumerate(payloads, 1):
        meta = payload.get("_meta", {})
        body_to_send = _strip_meta(payload)
        status, body = post_sim_json(url, body_to_send, token=token, timeout=timeout)
        ok = is_ok(status, body, extra_ok_codes=extra_ok_codes)
        results.append({
            "index": i,
            "http_status": status,
            "ok": ok,
            "meta": meta,
            "response": body,
        })
        print(f"  [{i}/{len(payloads)}] http={status} ok={ok}"
              + (f" meta={json.dumps(meta, ensure_ascii=False)}" if meta else ""))
        if sleep_s:
            time.sleep(sleep_s)
    return results


def _summ(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok = sum(1 for r in results if r["ok"])
    codes: dict[str, int] = {}
    for r in results:
        codes[str(r["http_status"])] = codes.get(str(r["http_status"]), 0) + 1
    return {"total": len(results), "ok": ok, "status_code_histogram": codes}


def main() -> int:
    ap = argparse.ArgumentParser(description="参数面 Leaf 跨视图上架（reset参数面 + 建leaf + 上架机房 + 连线，不删机房）")
    ap.add_argument("--config", default=str(_DEFAULT_CONFIG))
    ap.add_argument("--output-dir", default=str(_OUTPUT_DIR))
    ap.add_argument("--skip-reset", action="store_true", help="跳过 reset 参数面（视图已就绪时可用）")
    ap.add_argument("--skip-device", action="store_true", help="跳过 createDevice（leaf 已建时可用）")
    ap.add_argument("--skip-rack", action="store_true", help="跳过 batchRackDevices（上架已完成时可用）")
    ap.add_argument("--skip-topo", action="store_true", help="跳过拓扑连线（拓扑已建时可用）")
    args = ap.parse_args()

    config = load_config(Path(args.config))
    base_url = normalize_base_url(config.get("base_url", ""))
    leaf_diagram = str(config.get("leaf_diagram") or "参数面")
    room_diagram = str(config.get("room_diagram") or "机房")
    parent_diagram = str(config.get("parent_diagram") or "顶层")
    reset_enabled = bool(config.get("reset_leaf_view", True))
    token = resolve_token(config.get("auth"))
    server_source = str(config.get("server_source", ""))
    req = dict(config.get("request") or {})
    timeout = int(req.get("timeout_seconds", 300))
    sleep_s = float(req.get("sleep_between_calls_seconds", 0.3))

    topo_cfg = dict(config.get("topo") or {})
    topo_endpoint_name = str(topo_cfg.get("endpoint") or "batchCreateLink")
    topo_path = _TOPO_ENDPOINTS.get(topo_endpoint_name, EP_BATCH_LINK)

    out_dir = Path(args.output_dir)

    if not token:
        print("[error] 未配置 Bearer Token（config.auth.token 或 token_env 环境变量），无法真实调用")
        return 2
    if leaf_diagram == room_diagram:
        print(f"[error] leaf_diagram({leaf_diagram!r}) 不能等于 room_diagram({room_diagram!r})，配置有误")
        return 2

    print(f"[config] base_url={base_url}  leaf_diagram={leaf_diagram}  room_diagram={room_diagram}  parent={parent_diagram}")
    print(f"[config] topo_endpoint={topo_endpoint_name} -> {topo_path}")

    result: dict[str, Any] = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "leaf_diagram": leaf_diagram,
        "room_diagram": room_diagram,
        "parent_diagram": parent_diagram,
        "note": "leaf 建在参数面->上架到机房->机房内连线；deleteTopology 仅作用于参数面，机房绝不删除。",
    }

    # ---- Step 0: reset 参数面 ----
    if not args.skip_reset and reset_enabled:
        print(f"[execute] reset 参数面：deleteTopology({leaf_diagram}) -> createShape({parent_diagram}, {leaf_diagram}) ...")
        reset_info = reset_leaf_view(base_url, token, leaf_diagram, parent_diagram, room_diagram, timeout)
        result["reset_view"] = reset_info
        if reset_info.get("aborted"):
            print(f"[error] {reset_info.get('reason')}")
            return 2
        print(f"[done] reset_view action={reset_info.get('action')} "
              f"(delete_ok={reset_info.get('delete_ok')} create_ok={reset_info.get('create_ok')})")
        if reset_info.get("action") == "reset_failed":
            print("[error] 参数面视图重置失败，中止")
            _write_json(out_dir / "resetView.result.json", reset_info)
            _write_json(out_dir / "execution-result.json", result)
            return 2
        _write_json(out_dir / "resetView.result.json", reset_info)
    else:
        print("[skip] reset 参数面（--skip-reset 或 reset_leaf_view=false）")
        result["reset_view"] = {"skipped": True}

    # ---- 加载 server 名 ----
    if not server_source:
        print("[error] 未配置 server_source（DataGrid.xlsx 路径）")
        return 2
    print(f"[servers] 读取 {server_source} ...")
    servers = server_names(server_source)
    print(f"[servers] 共 {len(servers)} 台：{servers[0]} .. {servers[-1]}")
    result["server_count"] = len(servers)

    port_querier = make_port_querier(base_url, token, timeout)

    # ---- 生成 createDevice payload（leaf，参数面） ----
    leaf_doc = build_create_leaf_payload(servers, config)
    leaf_names_all = leaf_doc["leaf_names"]
    result["leaf_count"] = leaf_doc["leaf_count"]
    print(f"[leaf] leaf_count={leaf_doc['leaf_count']}  diagram={leaf_doc.get('diagram')}  "
          f"first={leaf_names_all[0]}  last={leaf_names_all[-1]}")
    _write_json(out_dir / "createDevice.params.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": f"POST {base_url}{EP_CREATE_DEVICE}",
        "diagram": leaf_doc.get("diagram"),
        "api": "createDevice",
        "leaf_count": leaf_doc["leaf_count"],
        "leaf_names": leaf_names_all,
        "warnings": leaf_doc.get("warnings", []),
        "payloads": [leaf_doc["payload"]],
    })

    # ---- 生成 batchRackDevices payload（18 条，跨视图） ----
    rack_doc = build_rack_payloads(config, leaf_names_all)
    print(f"[rack] calls={rack_doc['counts']['total_calls']}  mode={rack_doc['call_mode']}  "
          f"device_diagram={rack_doc['device_diagram']}  cabinet_diagram={rack_doc['cabinet_diagram']}")
    _write_json(out_dir / "batchRackDevices.params.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": f"POST {base_url}{EP_BATCH_RACK}",
        **rack_doc,
    })

    # ---- 生成拓扑 payload（server→leaf，机房，2 条） ----
    topo_doc = build_server_leaf_payloads(servers, leaf_names_all, config, querier=port_querier)
    print(f"[topo] calls={topo_doc['counts']['total_calls']}  diagram={topo_doc.get('diagram')}  "
          f"warnings={topo_doc.get('warnings', [])}  rule_c={topo_doc.get('rule_c', [])}")
    _write_json(out_dir / "batchCreateLink.params.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": f"POST {base_url}{topo_path}",
        "topo_endpoint": topo_endpoint_name,
        **topo_doc,
    })

    result["warnings"] = {
        "device": leaf_doc.get("warnings", []),
        "topo": topo_doc.get("warnings", []),
    }
    result["rule_c"] = topo_doc.get("rule_c", [])

    # ---- Step 1: createDevice（leaf，参数面） ----
    if not args.skip_device:
        print(f"[execute] POST createDevice x1 (leaf {leaf_doc['leaf_count']} 台 @ {leaf_doc.get('diagram')}) ...")
        device_results = execute_calls(
            f"{base_url}{EP_CREATE_DEVICE}", [leaf_doc["payload"]], token, timeout, sleep_s
        )
        result["create_device"] = {"summary": _summ(device_results), "results": device_results}
        d = result["create_device"]["summary"]
        print(f"[done] create_device ok={d['ok']}/{d['total']} codes={d['status_code_histogram']}")
        if d["ok"] < d["total"]:
            print("[warn] createDevice 存在失败，继续执行后续步骤（可用 --skip-device 跳过重试）")
    else:
        print("[skip] createDevice（--skip-device）")
        result["create_device"] = {"summary": {"skipped": True}, "results": []}

    # ---- Step 2: batchRackDevices（上架到机房，18 次） ----
    if not args.skip_rack:
        print(f"[execute] POST batchRackDevices x{rack_doc['counts']['total_calls']} (每柜一次，参数面->机房) ...")
        rack_results = execute_calls(
            f"{base_url}{EP_BATCH_RACK}", rack_doc["payloads"], token, timeout, sleep_s
        )
        result["batch_rack"] = {"summary": _summ(rack_results), "results": rack_results}
        r = result["batch_rack"]["summary"]
        print(f"[done] batch_rack ok={r['ok']}/{r['total']} codes={r['status_code_histogram']}")
    else:
        print("[skip] batchRackDevices（--skip-rack）")
        result["batch_rack"] = {"summary": {"skipped": True}, "results": []}

    # ---- Step 2.5: 上架后校验 leaf 是否进入机房（best-effort） ----
    if not args.skip_topo and leaf_names_all:
        verify = verify_leaves_in_room(base_url, token, room_diagram, leaf_names_all[0], timeout)
        result["verify_leaf_in_room"] = verify
        if verify.get("found"):
            print(f"[verify] leaf {verify['sample_leaf']} 已找到，parent={verify.get('parent_name')}")
        else:
            print(f"[warn] 未通过 search 命中 leaf {verify.get('sample_leaf')}，"
                  f"batchCreateLink 可能找不到 leaf（请人工核对机房内 leaf 落位）")

    # ---- Step 3: 拓扑连线（机房内，batchCreateLink 递归，2 次） ----
    if not args.skip_topo:
        print(f"[execute] POST {topo_endpoint_name} x{topo_doc['counts']['total_calls']} (@ {topo_doc.get('diagram')}) ...")
        # 800114=线缆规格不匹配，连线已建立，视为成功（告警级别）
        topo_results = execute_calls(
            f"{base_url}{topo_path}", topo_doc["payloads"], token, timeout, sleep_s,
            extra_ok_codes={800114},
        )
        result["create_topo"] = {"summary": _summ(topo_results), "results": topo_results}
        t = result["create_topo"]["summary"]
        print(f"[done] create_topo ok={t['ok']}/{t['total']} codes={t['status_code_histogram']}")
    else:
        print("[skip] 拓扑连线（--skip-topo）")
        result["create_topo"] = {"summary": {"skipped": True}, "results": []}

    _write_json(out_dir / "execution-result.json", result)

    # 最终状态判定
    all_ok = True
    for key in ("create_device", "batch_rack", "create_topo"):
        s = result.get(key, {}).get("summary", {})
        if s.get("skipped"):
            continue
        if s.get("ok", 0) < s.get("total", 0):
            all_ok = False
    rv = result.get("reset_view", {})
    if not rv.get("skipped") and rv.get("action") == "reset_failed":
        all_ok = False

    print(f"[{'DONE OK' if all_ok else 'DONE WITH ERRORS'}] 结果见 {out_dir / 'execution-result.json'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
