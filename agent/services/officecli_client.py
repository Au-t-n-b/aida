"""
officecli CLI 封装 · 解析 docx/xlsx
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "officecli"
REFERENCE_DIR = SKILL_ROOT / "reference"
SCRIPTS_DIR = SKILL_ROOT / "scripts"

OFFICECLI_ENV = {
    **os.environ,
    "OFFICECLI_NO_AUTO_RESIDENT": "1",
}


def officecli_binary() -> Path:
    system = platform.system().lower()
    if system == "windows":
        candidates = [
            REFERENCE_DIR / "officecli-win-x64.exe",
            Path("officecli-win-x64.exe"),
            Path("officecli.exe"),
        ]
    else:
        candidates = [
            REFERENCE_DIR / "officecli-linux-arm64",
            Path("/usr/local/bin/officecli"),
            Path("officecli"),
        ]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(
        f"未找到 officecli binary，请确认 {REFERENCE_DIR} 下已放置对应平台可执行文件"
    )


def run_officecli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    exe = str(officecli_binary())
    return subprocess.run(
        [exe, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=OFFICECLI_ENV,
        timeout=timeout,
    )


def view_text(filepath: Path) -> str:
    r = run_officecli("view", str(filepath), "text")
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "officecli view text failed")
    return r.stdout


def get_json(filepath: Path, selector: str, depth: int = 3) -> dict[str, Any]:
    r = run_officecli("get", str(filepath), selector, f"--depth={depth}", "--json")
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or f"officecli get {selector} failed")
    return json.loads(r.stdout)


def list_docx_tables(filepath: Path) -> list[int]:
    """从 outline/stats 推断表格数量；失败时扫描 tbl[1..20]。"""
    r = run_officecli("view", str(filepath), "outline")
    if r.returncode == 0:
        m = re.search(r"(\d+)\s+tables", r.stdout)
        if m:
            return list(range(1, int(m.group(1)) + 1))
    found: list[int] = []
    for i in range(1, 21):
        try:
            get_json(filepath, f"/body/tbl[{i}]", depth=1)
            found.append(i)
        except Exception:
            break
    return found


def extract_table_matrix(table_json: dict[str, Any]) -> list[list[str]]:
    """将 officecli table JSON 转为二维文本矩阵。"""
    results = table_json.get("data", {}).get("results", [])
    if not results:
        return []
    root = results[0]
    rows_map: dict[int, dict[int, str]] = {}

    def walk(node: dict[str, Any]) -> None:
        path = node.get("path", "")
        text = str(node.get("text", "") or "").strip()
        typ = node.get("type", "")
        if typ == "cell" and text:
            m = re.search(r"/tr\[(\d+)\]/tc\[(\d+)\]", path)
            if m:
                ri, ci = int(m.group(1)), int(m.group(2))
                rows_map.setdefault(ri, {})[ci] = text
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                walk(child)

    walk(root)
    if not rows_map:
        return []
    max_col = max(max(cols.keys()) for cols in rows_map.values())
    return [
        [rows_map.get(r, {}).get(c, "") for c in range(1, max_col + 1)]
        for r in sorted(rows_map.keys())
    ]


def xlsx_sheet_rows(filepath: Path, sheet_name: str, max_row: int = 500, max_col: int = 30) -> list[list[str]]:
    """用 officecli 读取 xlsx 区域为二维数组。"""
    from openpyxl.utils import get_column_letter

    end_col = get_column_letter(max_col)
    r = run_officecli(
        "get",
        str(filepath),
        f"{sheet_name}!A1:{end_col}{max_row}",
        "--json",
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "officecli xlsx get failed")
    data = json.loads(r.stdout)
    children = data.get("data", {}).get("results", [{}])[0].get("children", [])
    cells: dict[tuple[int, int], str] = {}
    for cell in children:
        m = re.match(r"/[^/]+/([A-Z]+)(\d+)", cell.get("path", ""))
        if not m:
            continue
        col_letters, row_num = m.group(1), int(m.group(2))
        col_num = 0
        for ch in col_letters:
            col_num = col_num * 26 + (ord(ch) - ord("A") + 1)
        cells[(row_num, col_num)] = str(cell.get("text", "") or "")
    if not cells:
        return []
    max_r = max(r for r, _ in cells)
    max_c = max(c for _, c in cells)
    return [[cells.get((r, c), "") for c in range(1, max_c + 1)] for r in range(1, max_r + 1)]
