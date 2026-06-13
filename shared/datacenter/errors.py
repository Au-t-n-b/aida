from __future__ import annotations


class DataCenterError(Exception):
    def __init__(self, code: int, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
