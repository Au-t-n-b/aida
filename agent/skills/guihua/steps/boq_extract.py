"""
boq_extract · 规划设计第 1 步「BOQ 提取」（真 LLM + doc_read_xlsx）

移植自 nanobot jmfz 的 BOQ 提取阶段；jmfz 原版是写死占位，本版做**真实抽取**：
  - 用通用工具 doc_read_xlsx 读上传的 BOQ 表格
  - 走 ctx.invoke_llm 让模型抽出设备清单（结构化 JSON）
  - 结果缓存到 RunTime/device_list.json（full_restart 重跑时不重复调 LLM）
  - LLM 不可用/解析失败时优雅降级为启发式清单，保证线下也能跑通
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult

_BUNDLE_EXTS = {".xlsx", ".xls", ".csv", ".zip", ".pdf", ".doc", ".docx",
                ".stp", ".step", ".iges", ".stl", ".json", ".png", ".jpg"}
_TABLE_EXTS = {".xlsx", ".xls"}
CACHE_REL = "ProjectData/RunTime/device_list.json"


class BoqExtractStep(BaseStep):
    key = "boq_extract"
    name = "BOQ提取"
    artifacts_pattern = [CACHE_REL]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        """需要至少一个上传的资料包文件（落在 Input/）。空 → 文件型 HITL。"""
        ctx.ensure_dirs()
        found = [
            str(p.relative_to(ctx.work_root))
            for p in ctx.input_dir.glob("*")
            if p.is_file() and p.suffix.lower() in _BUNDLE_EXTS
        ]
        if not found:
            return {
                "ok": False,
                "missing": ["ProjectData/Input/<建模仿真资料包>（含 BOQ 表格 .xlsx）"],
                "found": [],
                "note": "请上传建模仿真资料包（可含 BOQ/几何/材料表），至少一个 .xlsx",
            }
        return {"ok": True, "missing": [], "found": found, "note": ""}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        cache = ctx.work_root / CACHE_REL
        redo = bool((ctx.project or {}).get("_redo_boq"))

        # 缓存命中且非重做 → 直接用（避免 full_restart 重复调 LLM）
        if cache.is_file() and not redo:
            try:
                devices = json.loads(cache.read_text(encoding="utf-8"))
                emit(f"[{self.key}] 命中缓存 device_list.json（{len(devices)} 项设备），跳过重复抽取")
                return self._result(devices, source="cache")
            except Exception:
                pass

        # 找一个表格文件
        xlsx = next(
            (p for p in sorted(ctx.input_dir.glob("*")) if p.suffix.lower() in _TABLE_EXTS),
            None,
        )
        if xlsx is None:
            emit(f"[{self.key}] 未找到 .xlsx 表格，按文件名生成占位设备清单")
            devices = self._fallback_from_filenames(ctx)
            self._write_cache(cache, devices)
            return self._result(devices, source="filenames")

        emit(f"[{self.key}] 读取 BOQ 表格：{xlsx.name}")
        table_text = ctx.call_tool(
            "doc_read_xlsx",
            {"path": str(xlsx), "as_json": False, "max_rows": 120},
            step_key=self.key,
            emit=emit,
        )
        table_text = str(table_text or "")[:4000]

        devices = self._extract_with_llm(ctx, table_text, emit)
        if not devices:
            emit(f"[{self.key}] LLM 抽取为空/失败，降级为表格启发式清单")
            devices = self._fallback_from_table(table_text)

        self._write_cache(cache, devices)
        emit(f"[{self.key}] 抽取完成：{len(devices)} 项设备")
        return self._result(devices, source="llm" if devices else "fallback")

    # ── LLM 抽取 ──
    def _extract_with_llm(self, ctx: SkillContext, table_text: str, emit: Emit) -> list[dict]:
        if not table_text.strip():
            return []
        try:
            resp = ctx.invoke_llm(
                [
                    ("system",
                     "你是数据中心建模仿真的 BOQ 解析助手。从 BOQ 表格文本中抽取设备清单，"
                     "只输出 JSON 数组，每项形如 "
                     '{"name":"设备名","type":"类别","qty":数量}。'
                     "类别从 {机柜,服务器,网络,配电,制冷,布线,其他} 里选最接近的。不要输出多余文字。"),
                    ("human", f"BOQ 表格内容（CSV）：\n{table_text}\n\n请输出设备清单 JSON 数组："),
                ],
                step_key=self.key,
            )
            content = resp.content if hasattr(resp, "content") else str(resp)
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            return self._parse_devices(str(content))
        except Exception as e:  # noqa: BLE001 — LLM 不可用时降级，不阻断线下流程
            emit(f"[{self.key}] LLM 调用异常（{type(e).__name__}），降级处理")
            return []

    @staticmethod
    def _parse_devices(text: str) -> list[dict]:
        # 容忍 ```json ... ``` 包裹
        m = re.search(r"\[.*\]", text, re.S)
        if not m:
            return []
        try:
            raw = json.loads(m.group(0))
        except Exception:
            return []
        out: list[dict] = []
        for it in raw if isinstance(raw, list) else []:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or it.get("名称") or "").strip()
            if not name:
                continue
            out.append({
                "name": name,
                "type": str(it.get("type") or it.get("类别") or "其他").strip(),
                "qty": it.get("qty") or it.get("数量") or 1,
            })
        return out

    # ── 降级路径 ──
    @staticmethod
    def _fallback_from_table(table_text: str) -> list[dict]:
        rows = [r for r in table_text.splitlines() if r.strip()][1:]  # 跳表头/注释
        out: list[dict] = []
        for r in rows[:30]:
            first = r.split(",")[0].strip().strip('"')
            if first:
                out.append({"name": first, "type": "其他", "qty": 1})
        return out or [{"name": "未识别设备", "type": "其他", "qty": 1}]

    @staticmethod
    def _fallback_from_filenames(ctx: SkillContext) -> list[dict]:
        return [
            {"name": p.stem, "type": "其他", "qty": 1}
            for p in sorted(ctx.input_dir.glob("*")) if p.is_file()
        ] or [{"name": "占位设备", "type": "其他", "qty": 1}]

    @staticmethod
    def _write_cache(cache: Path, devices: list[dict]) -> None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(devices, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _result(devices: list[dict], *, source: str) -> StepResult:
        cats: dict[str, int] = {}
        for d in devices:
            cats[d.get("type", "其他")] = cats.get(d.get("type", "其他"), 0) + 1
        # device_list_preview：SDUI device_confirm HITL 展示用（前 10 项），
        # qty 转字符串以保证 SduiTableNode rows: list[list[str]] 类型一致。
        preview = [
            {
                "name": str(d.get("name") or ""),
                "type": str(d.get("type") or "其他"),
                "qty": str(d.get("qty") or 1),
            }
            for d in devices[:10]
        ]
        return {
            "metrics": {
                "device_count": len(devices),
                "category_count": len(cats),
                "categories": cats,
                "extract_source": source,
                # SDUI 展示：前 10 项设备摘要，供 device_confirm HITL 渲染清单表
                "device_list_preview": preview,
                "device_list_truncated": len(devices) > 10,
            },
        }
