"""
adapt_build · 建模仿真第 1 步「设备适配」（载入已解析的适配信息表）

按本次交付要求：进入建模仿真模块即「BOQ 数据已解析完毕」。本步不再现跑仿真 API，
而是直接载入 vendored 的《建模仿真设备适配信息表》（jmfz/api_adapt 的产物），落到
解析结果/compat_table.md 供下游（data_confirm / SDUI 设备数据页）复用，
并解析【超节点概述】首数据行得到 BOQ 概览（超节点组合 / 超节点数 / 服务器数 / 灵衢数）。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..path_config import get_input_dir, get_parse_dir
from ..services import FIXTURE_COMPAT_TABLE, VENDOR_ADAPT_MD

_INPUT_MD_HINTS = ("设备适配信息表", "适配信息表", "compat", "适配")


class AdaptBuildStep(BaseStep):
    key = "adapt_build"
    name = "设备适配"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        src = self._resolve_adapt_md()
        note = (f"已就绪适配信息表：{src.name}" if src
                else "未找到适配信息表，使用内置样本离线渲染")
        return {"ok": True, "missing": [], "found": [src.name] if src else [], "note": note}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        src = self._resolve_adapt_md()
        if not src or not Path(src).is_file():
            raise FileNotFoundError("找不到建模仿真设备适配信息表（vendored / 上传 / fixture 均缺失）")

        out = get_parse_dir() / "compat_table.md"
        shutil.copyfile(src, out)
        compat_md = out.read_text(encoding="utf-8")

        ov = _parse_superpod_overview(compat_md)
        emit(f"[{self.key}] BOQ 已解析：超节点组合「{ov.get('combo_model') or '待确认'}」，"
             f"{ov.get('pod_count', 0)} 个超节点 / 服务器 {ov.get('server_count', 0)} / 灵衢 {ov.get('lingqu_count', 0)}")
        emit(f"[{self.key}] 适配信息表已载入 → 解析结果/{out.name}（来源：{Path(src).name}）")

        return {
            "metrics": {
                "adapt_mode": "vendored",
                "boq_parsed": True,
                "combo_model": ov.get("combo_model") or "待确认",
                "pod_count": ov.get("pod_count", 0),
                "device_count": ov.get("server_count", 0),
                "boq_server_count": ov.get("server_count", 0),
                "boq_server_model": ov.get("server_model", ""),
                "boq_lingqu_count": ov.get("lingqu_count", 0),
                "boq_lingqu_model": ov.get("lingqu_model", ""),
                # SDUI「设备数据」页签渲染用（截断防超大）
                "compat_table_md": compat_md[:12000],
                "compat_table_truncated": len(compat_md) > 12000,
            },
        }

    # ── helpers ──
    @staticmethod
    def _resolve_adapt_md() -> Path | None:
        """适配表来源优先级：① 输入文件/ 上传的适配表 .md；② vendored jmfz 产物；③ fixture。"""
        for p in sorted(get_input_dir().glob("*.md")):
            if p.is_file() and any(h in p.name.lower() or h in p.name for h in _INPUT_MD_HINTS):
                return p
        if Path(VENDOR_ADAPT_MD).is_file():
            return Path(VENDOR_ADAPT_MD)
        if Path(FIXTURE_COMPAT_TABLE).is_file():
            return Path(FIXTURE_COMPAT_TABLE)
        return None


def _parse_superpod_overview(md_text: str) -> dict:
    """解析【超节点概述】首数据行：
    | 超节点组合 | 超节点数量 | 智算服务器 | 服务器数量 | 灵衢交换机 | 灵衢数量 |
    """
    out: dict = {}
    in_section = False
    seen_header = False
    for line in md_text.splitlines():
        s = line.strip()
        if s.startswith("【") and "超节点概述" in s:
            in_section = True
            continue
        if in_section and s.startswith("【"):
            break
        if not in_section or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not seen_header:
            if cells and "超节点组合" in cells[0]:
                seen_header = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if cells and cells[0]:
            out["combo_model"] = cells[0]
            out["pod_count"] = _to_int(cells[1] if len(cells) > 1 else "")
            out["server_model"] = cells[2] if len(cells) > 2 else ""
            out["server_count"] = _to_int(cells[3] if len(cells) > 3 else "")
            out["lingqu_model"] = cells[4] if len(cells) > 4 else ""
            out["lingqu_count"] = _to_int(cells[5] if len(cells) > 5 else "")
            break
    return out


def _to_int(s: str) -> int:
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0
