# -*- coding: utf-8 -*-
"""十一步主线：统一的完成/待办引导文案（仅 GuidanceCard，避免与 ConfirmCard 重复）。"""

from __future__ import annotations

TOTAL_STEPS = 11

STEP_TITLES: dict[int, str] = {
    1: "接收二级任务",
    2: "拆分调测计划",
    3: "下发设备底表",
    4: "CloudOps 初配",
    5: "补充 CloudOps 配置",
    6: "生成 CloudOps 完整配置",
    7: "配置调测设备",
    8: "导入 CloudOps 到 Toolkit",
    9: "初始化与软件安装",
    10: "子系统测试",
    11: "集群系统测试",
}


def step_done_banner(step: int, *, detail: str = "") -> str:
    title = STEP_TITLES.get(step, f"步骤 {step}")
    lines = [f"✅ **步骤 {step}/{TOTAL_STEPS} 已完成 · {title}**"]
    if detail.strip():
        lines.append(detail.strip())
    lines.append("_（进度已写入 Skill 内 state / deploy_chain）_")
    return "\n".join(lines)


def step_gate_banner(step: int, *, body: str, prev_done_step: int | None = None, prev_detail: str = "") -> str:
    title = STEP_TITLES.get(step, f"步骤 {step}")
    lines: list[str] = []
    if prev_done_step is not None:
        lines.append(step_done_banner(prev_done_step, detail=prev_detail))
        lines.append("")
    lines.extend(
        [
            f"📋 **当前待办 · 步骤 {step}/{TOTAL_STEPS}：{title}**",
            "",
            body.strip(),
            "",
            f"请点下方按钮执行本步；完成后会再次出现 **「步骤 {step}/{TOTAL_STEPS} 已完成」** 提示。",
        ]
    )
    return "\n".join(lines)


def step_all_done_banner() -> str:
    return (
        f"✅ **步骤 {TOTAL_STEPS}/{TOTAL_STEPS} 已完成 · 软件部署与调测主线已贯通**\n"
        "可在 plan/Output 查看 CloudOps 完整配置；ZTP、测试参数与 Toolkit 联调材料见步骤 6 和后续 Tab。"
    )
