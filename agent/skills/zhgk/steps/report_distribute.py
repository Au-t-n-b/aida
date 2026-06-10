"""
Step · 审批与分发（v4 · report_gen 意图专属）

意图: report_gen 专属

逻辑：
  1. 前置检查工勘报告.docx + 全量勘测结果表.xlsx + 风险识别结果表.xlsx
  2. 读 project_info.json（可选）
  3. 从人员信息.xlsx 筛 PD/TD/DC L1 收件人（可选）
  4. 组审批邮件包并发送（ZHGK_SEND_EMAIL=1 才真发）
"""
from __future__ import annotations
import os
import sys
import json
from datetime import datetime
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


# glob 模式 → 人类可读标签（实际文件名含 ACT001_... 前缀）
_REQUIRED_GLOBS: dict[str, str] = {
    "*工勘报告*.docx": "工勘报告.docx",
    "*全量勘测结果表*.xlsx": "全量勘测结果表.xlsx",
    "*风险识别结果表*.xlsx": "风险识别结果表.xlsx",
}


def _find_output_file(output_dir: Path, pattern: str) -> Path | None:
    """在 output_dir 下按 glob 模式查找，返回第一个匹配的文件路径，不存在返回 None。"""
    matches = sorted(output_dir.glob(pattern))
    return matches[0] if matches else None


class ReportDistributeStep(BaseStep):
    key = "report_distribute"
    name = "审批与分发"
    artifacts_pattern = []  # 不产文件

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        found, missing = [], []
        for pattern, label in _REQUIRED_GLOBS.items():
            if _find_output_file(ctx.output_dir, pattern) is not None:
                found.append(f"ProjectData/Output/{label}")
            else:
                missing.append(f"ProjectData/Output/{pattern}")

        # 可选输入：人员信息 + project_info（仅作提示，不阻断）
        opt_found, opt_missing = [], []
        for rel in [
            "ProjectData/Input/远近一体化人员信息.xlsx",
            "ProjectData/RunTime/project_info.json",
        ]:
            (opt_found if (ctx.work_root / rel).exists() else opt_missing).append(rel)

        note = f"可选缺失: {opt_missing}" if opt_missing else ""
        return {"ok": not missing, "missing": missing, "found": found + opt_found, "note": note}

    def _get_recipients(self, ctx: SkillContext, emit: Emit) -> list[dict]:
        """复用 zhgk path_config.get_recipients(ROLE_PD_TD_EXPERT)。失败返回 []。"""
        from ..bridge import get_zhgk_root
        try:
            root = str(Path(get_zhgk_root()))
            if root not in sys.path:
                sys.path.insert(0, root)
            from path_config import get_recipients, ROLE_PD_TD_EXPERT  # type: ignore
            return get_recipients(ROLE_PD_TD_EXPERT) or []
        except Exception as e:
            emit(f"  [提示] 读取收件人失败：{e}")
            return []


    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        # 按 glob 模式解析实际文件路径
        resolved: dict[str, Path] = {}
        glob_missing: list[str] = []
        for pattern, label in _REQUIRED_GLOBS.items():
            p = _find_output_file(ctx.output_dir, pattern)
            if p is None:
                glob_missing.append(label)
            else:
                resolved[label] = p

        if glob_missing:
            for f in glob_missing:
                emit(f"[错误] 缺少文件：{f}（需先执行 Step 3 report_gen）")
            return {"error": f"report_distribute 缺产物：{', '.join(glob_missing)}"}

        # 项目信息
        project_name, survey_date, surveyor = "未知项目", datetime.now().strftime("%Y/%m/%d"), "勘测工程师"
        proj_info = ctx.runtime_dir / "project_info.json"
        if proj_info.exists():
            try:
                info = json.loads(proj_info.read_text(encoding="utf-8"))
                project_name = info.get("项目名称", project_name)
                survey_date = info.get("勘察日期", survey_date)
                surveyor = info.get("参与人员", surveyor)
            except Exception as e:
                emit(f"  [提示] project_info.json 解析失败：{e}")

        # 收件人
        recipients = self._get_recipients(ctx, emit)
        emit(f"筛选到收件人：{len(recipients)} 人")
        for r in recipients:
            emit(f"  [{r.get('role','')}] {r.get('name','')} <{r.get('email','')}>")
        if not recipients:
            emit("[警告] 未找到 PD/TD/DC L1工勘专家，审批包仍生成但无收件人")

        date_str = datetime.now().strftime("%Y%m%d")
        subject = f"【智慧工勘审批】{project_name} 工勘报告 - {date_str}"
        attachments = [str(p) for p in resolved.values()]

        emit("-" * 40)
        emit(f"审批邮件主题：{subject}")
        emit(f"附件：{' / '.join(p.name for p in resolved.values())}")

        # 邮件（默认关闭）
        email_sent = False
        if os.environ.get("ZHGK_SEND_EMAIL", "").strip() == "1":
            emit("  [提示] ZHGK_SEND_EMAIL=1，但原生版邮件需另接 SMTP（暂未实现），跳过")
        else:
            emit("  [跳过] 审批邮件默认关闭（代发邮件需显式授权；设 ZHGK_SEND_EMAIL=1 启用）")

        emit("=== Step 4 完成 · 审批包就绪 ===")

        return {
            "metrics": {
                "recipients": len(recipients),
                "attachments": len(attachments),
                "email_sent": email_sent,
                "project_name": project_name,
            },
        }
