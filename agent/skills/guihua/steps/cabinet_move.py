"""
cabinet_move · 建模仿真第 4 步「机柜落位」（确认型 HITL 门 gate=move + 真跑 --only-move）

交互：「超节点已经创建完毕，是否开始机柜落位？」是/否。其中夹一次手动刷新 nVisual——
收敛成本步的确认门：用户在「仿真软件」页刷新确认超节点已显示后点「是，开始落位」。

是（gate=move）→ run() 子进程真跑 vendored run_place_api.py run --only-move：
逐机柜 batchMoveNodes ×162（前一条成功才发下一条）。解析 stdout「[移动 i/162]」回流
move_progress.json + SDUI 进度条；失败可续跑（--start-move）。
同 run 内 full_restart 已完成可跳过；跨 run 或旧文件无 run_id 则重新落位。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..path_config import get_parse_dir
from ..services import VENDOR_AUTODRAGD
from ..services.sentinel import is_same_run, read_json
from ..services.sim_api import is_live
from ..services.subproc import run_script, _subproc_failure_hint

_MOVE_RE = re.compile(r"\[移动\s+(\d+)\s*/\s*(\d+)\]")


class CabinetMoveStep(BaseStep):
    key = "cabinet_move"
    name = "机柜落位"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("move"):
            return {"ok": True, "missing": [], "found": ["confirmations.move"], "note": ""}
        if confs.get("combo"):
            created = read_json(get_parse_dir() / "combo_created.json")
            if not created.get("ok"):
                code = created.get("exit_code")
                err = (created.get("error") or "").strip()
                detail = err or (f"exit_code={code}" if code is not None else "未写入成功留痕")
                return {
                    "ok": False,
                    "missing": ["解析结果/combo_created.json"],
                    "found": [],
                    "note": (
                        f"超节点创建尚未成功（{detail}）。"
                        "请先重试「创建超节点」，确认 nVisual 已显示超节点后再进行机柜落位。"
                    ),
                }
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": "超节点已经创建完毕。请在「仿真软件」页刷新 nVisual，确认超节点已显示后开始机柜落位。",
            "need_inputs": [{
                "id": "move",
                "label": "超节点已经创建完毕，是否开始机柜落位？",
                "options": [
                    {"label": "是，已刷新，开始落位", "value": "confirm"},
                    {"label": "否，暂不落位", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        progress = get_parse_dir() / "move_progress.json"
        redo = bool((ctx.project or {}).get("_redo_move"))
        total = self._move_total()

        prev = read_json(progress)
        if is_same_run(prev, ctx.run_id) and prev.get("done") and not redo:
            emit(f"[{self.key}] 本 run 机柜落位已完成（{prev.get('sent', total)}/{total}），跳过")
            return {"metrics": self._metrics(prev, total)}

        if redo or not is_same_run(prev, ctx.run_id):
            start = 1
        else:
            start = max(1, int(prev.get("sent", 0)) + 1)
        args = ["scripts/run_place_api.py", "run", "--only-move"]
        if start > 1:
            args += ["--start-move", str(start)]
            emit(f"[{self.key}] 断点续跑：从第 {start}/{total} 条机柜继续")

        emit(f"[{self.key}] 仿真 API 模式：{'LIVE（真发仿真网关）' if is_live() else 'dry-run'}")
        emit(f"[{self.key}] 开始逐机柜落位，共 {total} 条")

        last_sent = {"i": start - 1}

        def on_line(line: str) -> None:
            m = _MOVE_RE.search(line)
            if not m:
                return
            i, tot = int(m.group(1)), int(m.group(2))
            last_sent["i"] = i
            self._write_progress(progress, run_id=ctx.run_id, sent=i, total=tot, done=False)

        result = run_script(
            VENDOR_AUTODRAGD, args, emit=emit, on_line=on_line,
        )
        done = result.get("ok", False)
        sent = total if done else last_sent["i"]
        self._write_progress(progress, run_id=ctx.run_id, sent=sent, total=total, done=done,
                             ok=done, error="" if done else f"exit_code={result.get('exit_code')}")

        if not done:
            hint = _subproc_failure_hint(result)
            emit(f"[{self.key}] ⚠ 落位中断于第 {sent} 条：{hint}")
            return {"metrics": self._metrics(read_json(progress), total), "error": hint}
        emit(f"[{self.key}] 机柜落位完成：{sent}/{total} 条")
        return {"metrics": self._metrics(read_json(progress), total)}

    # ── helpers ──
    @staticmethod
    def _move_total() -> int:
        req = Path(VENDOR_AUTODRAGD) / "requests.json"
        if req.is_file():
            try:
                doc = json.loads(req.read_text(encoding="utf-8"))
                return int(doc.get("meta", {}).get("move_count") or len(doc.get("move", [])))
            except Exception:
                return 0
        return 0

    @staticmethod
    def _write_progress(path: Path, *, run_id: str, sent: int, total: int, done: bool,
                        ok: bool | None = None, error: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rec: dict = {"run_id": run_id, "sent": sent, "total": total, "done": done}
        if ok is not None:
            rec["ok"] = ok
        if error:
            rec["error"] = error
        path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _metrics(prog: dict, total: int) -> dict:
        return {
            "move_total": prog.get("total", total),
            "move_sent": prog.get("sent", 0),
            "move_done": bool(prog.get("done")),
        }
