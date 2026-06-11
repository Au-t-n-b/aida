"""
智慧工勘 v4 — 问题管理模块接口

当前为 mock 实现，提供问题清单数据的接收和查询能力。
后续可对接实际问题管理系统（如 ITSM / Jira）。
"""
from __future__ import annotations

import os
from typing import Optional

from .issue_list_builder import get_open_issues_count, update_issue_status
from .types import IssueStatus


class IssueManager:
    """问题管理器（当前为本地文件模式）。"""

    def __init__(self, issue_list_path: Optional[str] = None):
        self._path = issue_list_path

    @property
    def path(self) -> Optional[str]:
        return self._path

    def set_path(self, path: str) -> None:
        self._path = path

    def get_open_count(self) -> int:
        """获取当前 open 问题数。"""
        if not self._path or not os.path.exists(self._path):
            return 0
        return get_open_issues_count(self._path)

    def close_issue(self, row_index: int) -> None:
        """关闭指定问题。"""
        if not self._path:
            raise ValueError("问题清单路径未设置")
        update_issue_status(self._path, row_index, IssueStatus.CLOSED)

    def get_summary(self) -> dict:
        """获取问题管理摘要。"""
        open_count = self.get_open_count()
        return {
            "issue_list_path": self._path,
            "open_count": open_count,
            "status": "has_issues" if open_count > 0 else "all_closed",
        }

    def can_approve(self) -> bool:
        """判断是否可以进入审批（所有问题已关闭）。"""
        return self.get_open_count() == 0
