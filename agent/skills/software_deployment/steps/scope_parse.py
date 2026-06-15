"""设备范围 8 种文法规则解析（对齐 device_scope/SKILL.md · L1 规则路径）。"""
from __future__ import annotations

import re
from typing import Any, TypedDict


class ScopeParams(TypedDict, total=False):
    scope: str
    pod_ids: list[int]
    devices: list[str]
    task_no: str
    only_installed: bool


class ParseResult(TypedDict, total=False):
    ok: bool
    parsed: ScopeParams
    summary: str
    error: str


_SCOPE_KINDS = frozenset({
    "all", "pod", "exclude", "include", "param_file",
    "prev_failed", "prev_passed", "prev_same",
})


def _split_devices(raw: str) -> list[str]:
    return [s.strip() for s in re.split(r"[,，、;；\s]+", raw) if s.strip()]


def _extract_pod_ids(text: str) -> list[int]:
    pods: list[int] = []
    for m in re.finditer(r"pod\s*0*(\d+)", text, flags=re.I):
        n = int(m.group(1))
        if n not in pods:
            pods.append(n)
    return pods


def _extract_task_no(text: str) -> str:
    paren = re.search(r"[（(]([^）)]+)[）)]", text)
    if paren and paren.group(1):
        return paren.group(1).strip()
    labeled = re.search(r"任务\s*(?:号|ID)?\s*[:：]?\s*([A-Za-z0-9_.-]+)", text, flags=re.I)
    if labeled and labeled.group(1):
        return labeled.group(1).strip()
    return ""


def _ok(parsed: ScopeParams, summary: str) -> ParseResult:
    out: ScopeParams = {"only_installed": True, **parsed}
    return {"ok": True, "parsed": out, "summary": summary}


def format_scope_summary(p: ScopeParams) -> str:
    scope = str(p.get("scope") or "all")
    pod_ids = p.get("pod_ids") or []
    devices = p.get("devices") or []
    task_no = str(p.get("task_no") or "").strip()

    if scope == "all":
        return "全量（已初始化设备）"
    if scope == "pod":
        return f"POD {', '.join(str(x) for x in pod_ids) or '—'} 全量"
    if scope == "exclude":
        pod = f"POD {', '.join(str(x) for x in pod_ids)} " if pod_ids else ""
        dev = ", ".join(devices) or "—"
        return f"{pod}排除 {dev}"
    if scope == "include":
        return f"指定设备：{', '.join(devices) or '—'}"
    if scope == "param_file":
        return "按参数文件指定设备"
    if scope == "prev_failed":
        return f"任务 {task_no} · 未通过的设备" if task_no else "最近一次任务 · 未通过的设备"
    if scope == "prev_passed":
        return f"任务 {task_no} · 已通过的设备" if task_no else "最近一次任务 · 已通过的设备"
    if scope == "prev_same":
        return f"复用任务 {task_no} 的设备范围" if task_no else "复用最近一次任务的设备范围"
    return scope


def parse_commission_scope_text(text: str) -> ParseResult:
    t = (text or "").strip()
    if not t or re.fullmatch(r"全量|全部|所有|all|默认", t, flags=re.I):
        return _ok({"scope": "all"}, "全量（已初始化设备）")

    if re.search(r"参数文件|按参数文件|执行参数文件", t):
        return _ok({"scope": "param_file"}, "按参数文件指定设备")

    task_no = _extract_task_no(t)
    if re.search(r"未通过|失败|异常", t):
        return _ok(
            {"scope": "prev_failed", "task_no": task_no},
            f"任务 {task_no} · 未通过的设备" if task_no else "最近一次任务 · 未通过的设备",
        )
    if re.search(r"已通过|成功|正常", t):
        return _ok(
            {"scope": "prev_passed", "task_no": task_no},
            f"任务 {task_no} · 已通过的设备" if task_no else "最近一次任务 · 已通过的设备",
        )
    if task_no and not re.search(r"排除|去掉|除了|只测|仅|执行|指定", t):
        return _ok(
            {"scope": "prev_same", "task_no": task_no},
            f"复用任务 {task_no} 的设备范围",
        )

    pods = _extract_pod_ids(t)

    m_exec = re.match(r"^(?:执行|只测|仅测|仅|指定)\s+", t, flags=re.I)
    if m_exec:
        body = re.sub(r"^(?:执行|只测|仅测|仅|指定)\s+", "", t, flags=re.I).strip()
        devices = _split_devices(re.sub(r"pod\s*\d+", " ", body, flags=re.I).strip())
        if not devices:
            return {"ok": False, "error": "指定设备范围需列出 IP 或设备名"}
        parsed: ScopeParams = {"scope": "include", "devices": devices}
        if pods:
            parsed["pod_ids"] = pods
        return _ok(parsed, f"指定设备：{', '.join(devices)}")

    if re.search(r"排除|去掉|除了", t):
        dev_part = re.sub(r"pod\s*\d+", " ", t, flags=re.I)
        dev_part = re.sub(r"排除|去掉|除了", " ", dev_part, flags=re.I).strip()
        dev_part = re.sub(r"[,，、]+", ",", dev_part)
        devices = _split_devices(dev_part)
        if not devices and not pods:
            return {"ok": False, "error": "排除范围需写明设备或 POD"}
        ex: ScopeParams = {"scope": "exclude"}
        if pods:
            ex["pod_ids"] = pods
        if devices:
            ex["devices"] = devices
        pod_txt = f"POD {', '.join(str(x) for x in pods)} " if pods else ""
        return _ok(ex, f"{pod_txt}排除 {', '.join(devices) or '（待填设备）'}")

    if pods:
        return _ok({"scope": "pod", "pod_ids": pods}, f"POD {', '.join(str(x) for x in pods)} 全量")

    if re.search(r"[\d.]+", t) or re.search(r"[,，]", t):
        devices = _split_devices(t)
        if devices:
            return _ok({"scope": "include", "devices": devices}, f"指定设备：{', '.join(devices)}")

    return {
        "ok": False,
        "error": "无法识别范围。可用快捷项，或参考示例：POD01 / POD01 排除 10.1.1.1 / 只测 10.1.1.2",
    }


def normalize_parsed(raw: dict[str, Any] | None) -> ScopeParams | None:
    if not isinstance(raw, dict):
        return None
    scope = str(raw.get("scope") or "").strip()
    if scope not in _SCOPE_KINDS:
        return None
    out: ScopeParams = {
        "scope": scope,
        "only_installed": bool(raw.get("only_installed", True)),
    }
    if raw.get("pod_ids"):
        out["pod_ids"] = [int(p) for p in raw["pod_ids"] if str(p).strip() != ""]
    if raw.get("devices"):
        out["devices"] = [str(d).strip() for d in raw["devices"] if str(d).strip()]
    if raw.get("task_no"):
        out["task_no"] = str(raw["task_no"]).strip()
    return out
