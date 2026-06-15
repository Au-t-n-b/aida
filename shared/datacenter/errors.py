from __future__ import annotations

from typing import Any


class DataCenterError(Exception):
    def __init__(
        self,
        code: int,
        message: str,
        *,
        status_code: int = 400,
        debug: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.debug = debug or {}
