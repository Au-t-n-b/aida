"""``oob-interconnect`` 入口（pyproject 的 console_script 调用）。"""
from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_oob_interconnect.py"
    runpy.run_path(str(script), run_name="__main__")
