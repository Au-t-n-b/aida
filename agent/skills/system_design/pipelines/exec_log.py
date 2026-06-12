"""系统设计执行日志 · 仅内存/界面展示，不落盘（无 runtime 目录）。"""
from __future__ import annotations

from pathlib import Path

# stderr 捕获时 openpyxl 等库会输出 UserWarning，不应作为用户可见错误
_NOISE_MARKERS = (
    "userwarning",
    "openpyxl",
    "apply openpyxl",
    "styles/stylesheet.py",
    "warn(",
)


def is_noise_line(line: str) -> bool:
    """过滤 stderr 噪音行（openpyxl UserWarning 等）。"""
    s = str(line or "").strip()
    if not s:
        return True
    low = s.lower()
    return any(m in low for m in _NOISE_MARKERS)


def extract_actionable_error(
    *,
    log_tail: str = "",
    errors: list[str] | None = None,
) -> str:
    """从 pipeline stderr/print 中提取可展示的错误说明（去噪 + 优先 ERROR/失败原因）。"""
    candidates: list[str] = []
    for src in errors or []:
        text = str(src or "").strip()
        if not text:
            continue
        # 逐行去噪：错误串可能内嵌子进程 stderr（含 openpyxl UserWarning 等噪音），
        # 不能因整段含噪音子串就丢弃，否则会连同「ERROR: ... not found」这类关键行一起被吞。
        for line in text.splitlines():
            s = line.strip()
            if s and not is_noise_line(s):
                candidates.append(s)

    for line in (log_tail or "").splitlines():
        s = line.strip()
        if is_noise_line(s):
            continue
        if (
            s.startswith(("ERROR:", "ERROR ", "失败原因", "ValueError:", "FileNotFoundError:"))
            or "无法" in s
            or "失败" in s
            or s.startswith("- ")
        ):
            candidates.append(s)

    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    if unique:
        return "\n".join(unique[:12])

    for line in reversed((log_tail or "").splitlines()):
        s = line.strip()
        if s and not is_noise_line(s):
            return s[:800]
    return "执行失败（详见步骤日志）"


def log_path(work_root: Path | str) -> Path:
    """兼容旧调用；不再写文件，恒返回空路径。"""
    _ = work_root
    return Path()


def append_log(
    work_root: Path | str,
    message: str,
    *,
    level: str = "INFO",
    command: str | None = None,
    detail: str | None = None,
    exc: BaseException | None = None,
) -> Path:
    """兼容 a3_bridge / plane_planning 调用；不落盘。"""
    _ = (work_root, message, level, command, detail, exc)
    return Path()
