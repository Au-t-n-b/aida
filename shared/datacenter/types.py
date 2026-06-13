from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticFileRef:
    """数据中心语义寻址键（§3.1）。"""

    module_code: str
    file_stage: str | None = None
    folder_sub_path: str | None = None
    file_name: str | None = None
    project_id: str | None = None
    file_keyword: str | None = None

    def to_list_body(self, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        body: dict[str, Any] = {
            "moduleCode": self.module_code,
            "page": page,
            "pageSize": page_size,
        }
        if self.project_id:
            body["projectId"] = self.project_id
        if self.file_stage:
            body["fileStage"] = self.file_stage
        if self.folder_sub_path:
            body["folderSubPath"] = self.folder_sub_path
        if self.file_keyword:
            body["fileKeyword"] = self.file_keyword
        return body

    def to_download_params(self) -> dict[str, str]:
        if not self.file_name:
            raise ValueError("download 需要 file_name")
        params: dict[str, str] = {
            "moduleCode": self.module_code,
            "fileName": self.file_name,
        }
        if self.project_id:
            params["projectId"] = self.project_id
        if self.file_stage:
            params["fileStage"] = self.file_stage
        if self.folder_sub_path:
            params["folderSubPath"] = self.folder_sub_path
        return params

    def to_upload_form(self) -> dict[str, str]:
        form: dict[str, str] = {"moduleCode": self.module_code}
        if self.project_id:
            form["projectId"] = self.project_id
        if self.file_stage:
            form["fileStage"] = self.file_stage
        if self.folder_sub_path:
            form["folderSubPath"] = self.folder_sub_path
        return form
