#!/usr/bin/env python3
"""Resolve cherry-pick 7fd4ed5: zhgk HITL (incoming) + delivery/contract (HEAD)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "7fd4ed5"


def normalize_git_text(text: str) -> str:
    """HEAD blob may contain \\r\\r\\n from a bad commit; normalize before splicing."""
    return text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")


def git_show(path: str, rev: str = COMMIT) -> str:
    return normalize_git_text(
        subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT).decode("utf-8", errors="replace")
    )


def git_head(path: str) -> str:
    return normalize_git_text(
        subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT).decode("utf-8", errors="replace")
    )


def take_incoming(text: str) -> str:
    if "<<<<<<< HEAD" not in text:
        return text
    out: list[str] = []
    while "<<<<<<< HEAD" in text:
        before, rest = text.split("<<<<<<< HEAD", 1)
        _head, rest = rest.split("=======", 1)
        incoming_part, rest = rest.split(">>>>>>>", 1)
        rest = re.sub(r"^[^\n]*\n?", "", rest, count=1)
        out.append(before)
        out.append(incoming_part)
        text = rest
    out.append(text)
    return "".join(out)


def resolve_main() -> None:
    incoming = git_show("agent/main.py")
    head = git_head("agent/main.py")

    if "proposal_mock_router" not in incoming:
        incoming = incoming.replace(
            "from .sog_routes import router as sog_router\n",
            "from .sog_routes import router as sog_router\n"
            "from .routers.proposal_mock import router as proposal_mock_router\n",
            1,
        )
        incoming = incoming.replace(
            "app.include_router(sog_router)\n",
            "app.include_router(sog_router)\napp.include_router(proposal_mock_router)\n",
            1,
        )

    if "DELIVERY_PLAN_PATH" not in incoming:
        incoming = incoming.replace(
            "from .routers.proposal_mock import router as proposal_mock_router\n\n",
            "from .routers.proposal_mock import router as proposal_mock_router\n\n"
            "PROJECT_ROOT = Path(__file__).resolve().parent.parent\n"
            'DELIVERY_PLAN_PATH = PROJECT_ROOT / "data" / "delivery" / "delivery-plan.xlsx"\n\n',
            1,
        )

    p_start = head.find("class PreviewBoqUploadResp")
    p_end = head.find("def _excel_date(value)")
    preview_block = head[p_start:p_end].rstrip() + "\n\n\n" if p_start != -1 and p_end > p_start else ""

    d_start = head.find("def _excel_date(value)")
    d_end = head.find("def _run_evals_bundle(")
    delivery_block = head[d_start:d_end].rstrip() + "\n\n\n" if d_start != -1 and d_end > d_start else ""

    insert = preview_block + delivery_block
    if insert and "PreviewBoqUploadResp" not in incoming:
        incoming = incoming.replace("def _run_evals_bundle(", insert + "def _run_evals_bundle(", 1)
        if "Field" not in incoming.split("class PreviewBoqUploadResp", 1)[0]:
            incoming = incoming.replace(
                "from pydantic import BaseModel, ConfigDict\n",
                "from pydantic import BaseModel, ConfigDict, Field\n",
                1,
            )
        if ", Any," not in incoming and "Any, AsyncIterator" not in incoming:
            incoming = incoming.replace(
                "from typing import AsyncIterator\n",
                "from typing import Any, AsyncIterator\n",
                1,
            )

    old_snap = """def get_ui_snapshot(skill: str, run_id: str):
    \"\"\"返回指定 run 的当前 SDUI 文档（JSON）。前端断线重连或初始化时调用。\"\"\"
    if run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    state = RUNS[run_id]["state"]
    skill_id = state.get("skill_id", skill)
    proj_fn = _get_sdui_projector(skill_id)
    if proj_fn is None:
        raise HTTPException(501, f"skill '{skill_id}' has no SDUI projector")
    try:
        return JSONResponse(_sdui_json_safe(proj_fn(state)))
    except Exception as e:
        import sys, traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.write(f"[sdui] get_ui_snapshot failed for {run_id}: {e}\\n")
        raise"""

    new_snap = """def get_ui_snapshot(skill: str, run_id: str):
    \"\"\"返回指定 run 的当前 SDUI 文档（JSON）。前端断线重连或初始化时调用。\"\"\"
    if run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    entry = RUNS[run_id]
    task = entry.get("task")
    if entry.get("display_state") and task is not None and not task.done():
        state = entry["display_state"]
    else:
        state = entry["state"]
    skill_id = state.get("skill_id", skill)
    proj_fn = _get_sdui_projector(skill_id)
    if proj_fn is None:
        raise HTTPException(501, f"skill '{skill_id}' has no SDUI projector")
    try:
        return JSONResponse(_sdui_json_safe(proj_fn(state)))
    except Exception as e:
        import sys, traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.write(f"[sdui] get_ui_snapshot failed for {run_id}: {e}\\n")
        raise"""

    if old_snap in incoming:
        incoming = incoming.replace(old_snap, new_snap, 1)

    (ROOT / "agent" / "main.py").write_text(incoming.rstrip() + "\n", encoding="utf-8")
    print(f"main.py: {len(incoming.splitlines())} lines")


def patch_survey_agent(incoming: str, head: str) -> str:
    """7fd4ed5 survey-agent + HEAD reset/dispatchRailSend."""
    # imports
    if "resetWorkspace" not in incoming:
        incoming = incoming.replace(
            "import { useSduiStream, startRun, resumeRun, uploadBatch, runPatchRun, type StartReq } from '@/hooks/useSduiStream';",
            "import { useSduiStream, startRun, resumeRun, uploadBatch, runPatchRun, resetWorkspace, type StartReq } from '@/hooks/useSduiStream';\n"
            "import { clearRunLog } from '@/lib/runLogStore';",
            1,
        )
    if "dispatchRailSend" not in incoming:
        incoming = incoming.replace(
            "import { setSkillHitl, clearSkillHitl } from '@/lib/skillHitlStore';",
            "import { setSkillHitl, clearSkillHitl } from '@/lib/skillHitlStore';\n"
            "import { dispatchRailSend } from '@/lib/claw-send';",
            1,
        )

    # handleResetSession from HEAD
    rs_start = head.find("  // ── 重置会话")
    rs_end = head.find("  // ── 动作处理")
    reset_block = head[rs_start:rs_end].rstrip() + "\n\n" if rs_start != -1 and rs_end > rs_start else ""
    if reset_block and "handleResetSession" not in incoming:
        incoming = incoming.replace(
            "  // ── 动作处理 ──────────────────────────────────────────────────────────────",
            reset_block + "  // ── 动作处理 ──────────────────────────────────────────────────────────────",
            1,
        )

    # dispatchRailSend in handleAction
    if "dispatchRailSend(text)" not in incoming:
        incoming = incoming.replace(
            "      } else if (text === '/overview') {\n        setViewMode('overview');\n      }",
            "      } else if (text === '/overview') {\n        setViewMode('overview');\n      } else {\n        dispatchRailSend(text);\n      }",
            1,
        )

    # reset_session → call handleResetSession
    old_reset = """    } else if (action.kind === 'reset_session') {
      void handleResetSession();
    }
  }, [handleStart, doResume, handleResetSession, handleIntent, skillId]);"""
    inline_reset = re.compile(
        r"    \} else if \(action\.kind === 'reset_session'\) \{.*?\n    \}\n"
        r"  \}, \[handleStart, doResume, handleIntent, skillId\]\);",
        re.S,
    )
    if "void handleResetSession()" not in incoming:
        if inline_reset.search(incoming):
            incoming = inline_reset.sub(
                "    } else if (action.kind === 'reset_session') {\n"
                "      void handleResetSession();\n"
                "    }\n"
                "  }, [handleStart, doResume, handleResetSession, handleIntent, skillId]);",
                incoming,
                count=1,
            )
        elif "handleResetSession," not in incoming:
            incoming = incoming.replace(
                "}, [handleStart, doResume, handleIntent, skillId]);",
                "}, [handleStart, doResume, handleResetSession, handleIntent, skillId]);",
                1,
            )

    return incoming


def resolve_survey_agent() -> None:
    incoming = git_show("frontend/src/components/screens/survey-agent.tsx")
    head = git_head("frontend/src/components/screens/survey-agent.tsx")
    merged = patch_survey_agent(incoming, head)
    (ROOT / "frontend/src/components/screens/survey-agent.tsx").write_text(merged, encoding="utf-8")
    print(f"survey-agent.tsx: {len(merged.splitlines())} lines")


def resolve_simple_incoming(rel: str) -> None:
    path = ROOT / rel.replace("/", "\\") if False else ROOT / rel
    path = ROOT / Path(rel)
    if path.is_file() and "<<<<<<< HEAD" in path.read_text(encoding="utf-8"):
        path.write_text(take_incoming(path.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{rel}: incoming")


def main() -> None:
    resolve_main()
    resolve_survey_agent()
    for rel in [
        "frontend/src/lib/skillHitlStore.ts",
        "frontend/src/hooks/useSduiStream.ts",
    ]:
        resolve_simple_incoming(rel)


if __name__ == "__main__":
    main()
