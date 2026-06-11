"""
adapt_build · 建模仿真第 1 步「设备适配」（api_adapt 移植）

对应 Desktop/skill/jmfz/api_adapt：把《建模仿真设备信息表》经仿真 API（queryDeviceModel /
querySlotMapping，统一走 SimApiClient）模糊匹配设备型号 + 板卡评分，生成《建模仿真设备适配
信息表》。这是建模仿真的「BOQ 数据已解析完毕 → 查看详细数据」那张设备数据表。

确定性 + 调 API，**非 LLM**（区别于旧 boq_extract）。无内网（dry-run）时：queryDeviceModel
返回空 → 复用 fixtures/compat_table.md 样本适配表，保证骨架端到端可跑。
"""
from __future__ import annotations

from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..services import FIXTURE_DEVICE_INFO, FIXTURE_COMPAT_TABLE
from ..services.compat_table import build_compat_table
from ..services.sim_api import SimApiClient, is_live

COMPAT_TABLE_REL = "ProjectData/RunTime/compat_table.md"
_INPUT_MD_HINTS = ("设备信息表", "设备信息", "device_info", "boq")


class AdaptBuildStep(BaseStep):
    key = "adapt_build"
    name = "设备适配"
    artifacts_pattern = [COMPAT_TABLE_REL]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        """设备信息表来源：① Input/ 上传的 .md；② 内置 fixture 兜底（故不阻断）。"""
        ctx.ensure_dirs()
        src = self._find_input_md(ctx)
        note = (f"已找到设备信息表：{src.name}" if src
                else "未上传设备信息表，使用内置样本（fixtures/device_info.md）离线生成适配表")
        return {"ok": True, "missing": [], "found": [src.name] if src else [], "note": note}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        input_md = self._find_input_md(ctx) or FIXTURE_DEVICE_INFO
        if not Path(input_md).is_file():
            raise FileNotFoundError(f"设备信息表不存在：{input_md}")
        out = ctx.work_root / COMPAT_TABLE_REL

        emit(f"[{self.key}] 设备信息表：{Path(input_md).name}"
             + ("（内置样本）" if Path(input_md) == FIXTURE_DEVICE_INFO else "（上传）"))
        emit(f"[{self.key}] 仿真 API 模式：{'LIVE' if is_live() else 'dry-run（离线兜底 fixture）'}")

        client = SimApiClient(work_root=ctx.work_root, emit=emit)
        stats = build_compat_table(
            Path(input_md), out, client,
            emit=emit, fixture_path=FIXTURE_COMPAT_TABLE,
        )

        compat_md = out.read_text(encoding="utf-8") if out.is_file() else ""
        emit(f"[{self.key}] 适配表生成完毕 → {out.name}（组合={stats.get('combo_model') or '待确认'}）")
        return {
            "metrics": {
                "adapt_mode": stats.get("mode"),
                "section_count": stats.get("sections"),
                "device_row_count": stats.get("rows"),
                "device_count": stats.get("devices"),
                "matched_count": stats.get("matched"),
                "combo_model": stats.get("combo_model") or "待确认",
                # SDUI「设备数据」页签渲染用（截断防超大）
                "compat_table_md": compat_md[:12000],
                "compat_table_truncated": len(compat_md) > 12000,
            },
        }

    @staticmethod
    def _find_input_md(ctx: SkillContext) -> Path | None:
        mds = [p for p in sorted(ctx.input_dir.glob("*.md")) if p.is_file()]
        if not mds:
            return None
        for p in mds:
            if any(h in p.name.lower() for h in _INPUT_MD_HINTS):
                return p
        return mds[0]
