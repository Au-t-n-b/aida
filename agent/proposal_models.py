"""
交付预案 · 第 5 章（组网配置）+ 第 7 章（机房信息）· Pydantic DTO

对齐：
  - 04-预案上下文.md §8（组网配置）、§10（机房信息）
  - 开发文档/第5章-组网配置/00-通用约定.md §6（共享 API 约定）
  - 开发文档/第7章-机房信息/00-通用约定.md §5（共享 API 约定）

风格对齐 agent/sdui/builder.py：Pydantic BaseModel + ConfigDict。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ─── 通用信封 ────────────────────────────────────────────────────────────────

class WarningItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str
    message: str


class DependencyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str
    message: str


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    project_id: str
    proposal_version: str = "draft"
    source_layer: Literal["parse", "draft", "output"] = "draft"
    warnings: list[WarningItem] = []
    dependencies: list[DependencyItem] = []


class ApiResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: Any
    meta: ResponseMeta


# ─── 5.1 网络平面配置 ────────────────────────────────────────────────────────

class DeviceRoleItem(BaseModel):
    """设备角色枚举项（供前端下拉）"""
    model_config = ConfigDict(extra="ignore")
    key: str
    label: str


class AvailableDeviceItem(BaseModel):
    """设备信息表投影（供网络平面配置选设备时自动填充厂家/型号/版本/数量）"""
    model_config = ConfigDict(extra="ignore")
    vendor: str
    device_model: str
    device_version: str
    boq_quantity: int


class NetPlaneRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    row_id: str
    type: str = Field(description="设备角色，即网络平面类型（如 参数面汇聚交换机）")
    vendor: str = Field(description="设备厂家")
    model: str = Field(description="设备型号")
    ver: str = Field(description="设备版本")
    qty: int = Field(description="数量", ge=0)
    source: str = Field(default="人工录入", description="数据来源")
    proposal_version: str | None = Field(default=None, description="预案版本号，Release 时写入")
    note: str | None = Field(default=None, description="备注")


class NetPlaneCreateReq(BaseModel):
    """行复制（「+」按钮）：取源行骨架，qty=0，note 清空"""
    model_config = ConfigDict(extra="forbid")
    source_row_id: str = Field(description="复制源行 ID")


class NetPlaneUpdateReq(BaseModel):
    """CELL 编辑：可编辑 vendor / type / model / ver / qty / source / note"""
    model_config = ConfigDict(extra="forbid")
    vendor: str | None = Field(default=None, description="设备厂家")
    type: str | None = Field(default=None, description="设备角色枚举值")
    model: str | None = Field(default=None, description="设备型号")
    ver: str | None = Field(default=None, description="设备版本")
    qty: int | None = Field(default=None, ge=0, description="数量")
    source: str | None = Field(default=None, description="数据来源")
    note: str | None = Field(default=None, description="备注")


# ─── 5.2 网管服务器配置 ──────────────────────────────────────────────────────

class NetMgmtRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    row_id: str
    server_role: Literal["NCE", "CCAE", "DME"]
    server_model: str = "通算服务器"
    quantity: int
    data_source: Literal["自动解析", "人工录入"] = "自动解析"
    proposal_version: str | None = None


class NetMgmtCreateReq(BaseModel):
    """人工新增行（非枚举角色场景）"""
    model_config = ConfigDict(extra="forbid")
    server_role: str
    server_model: str = "通算服务器"
    quantity: int = Field(default=1, ge=1)


class NetMgmtUpdateReq(BaseModel):
    """服务器角色由文件名识别，型号和数量手工维护。"""
    model_config = ConfigDict(extra="forbid")
    server_model: str | None = None
    quantity: int | None = Field(default=None, ge=1)


# ─── 5.3 集群设备清单表 ──────────────────────────────────────────────────────

class ClusterDeviceRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    row_id: str
    source_net_plane_id: str | None = Field(default=None, description="继承来源：5.1 网络平面行 ID")
    max_quantity: int = Field(default=0, description="5.1 来源行的原始数量，用于子行数量校验")
    cluster_id: str | None = None
    cluster_type: Literal["训练", "推理", "训推"] = "训练"
    super_pod_id: str | None = None
    storage_cluster_id: str | None = None
    zone_id: str | None = None
    ccae_cluster_id: str | None = None
    dme_cluster_id: str | None = None
    device_type: str = ""
    vendor: str = ""
    device_model: str = ""
    device_purpose: str | None = None
    start_device_name: str | None = None
    end_device_name: str | None = None
    quantity: int = 0
    data_source: Literal["自动解析", "人工录入"] = "人工录入"
    proposal_version: str | None = None


class ClusterDeviceCreateReq(BaseModel):
    """新增行：从 5.1 网络平面行继承厂家/型号/数量"""
    model_config = ConfigDict(extra="forbid")
    source_net_plane_id: str = Field(description="5.1 网络平面行 ID（继承来源）")


class ClusterDeviceUpdateReq(BaseModel):
    """CELL 编辑：ID 列 + 设备类型 + 用途 + 命名 + 数量"""
    model_config = ConfigDict(extra="forbid")
    cluster_id: str | None = None
    cluster_type: str | None = None
    super_pod_id: str | None = None
    storage_cluster_id: str | None = None
    zone_id: str | None = None
    ccae_cluster_id: str | None = None
    dme_cluster_id: str | None = None
    device_type: str | None = None
    device_purpose: str | None = None
    start_device_name: str | None = None
    end_device_name: str | None = None
    quantity: int | None = Field(default=None, ge=0)


# ─── 7.1 机房信息（PoD 机柜分配） ─────────────────────────────────────────────


class RoomRackRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    row_id: str
    pod_name: str = ""
    room_name: str = ""
    compute: str = ""
    bus: str = ""
    param_leaf: str = ""
    biz_leaf: str = ""
    mgmt: str = ""
    sample_leaf: str = ""
    data_source: Literal["自动解析", "人工录入"] = "人工录入"
    proposal_version: str | None = None


class RoomRackCreateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pod_name: str = ""
    room_name: str = ""
    compute: str = ""
    bus: str = ""
    param_leaf: str = ""
    biz_leaf: str = ""
    mgmt: str = ""
    sample_leaf: str = ""


class RoomRackUpdateReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pod_name: str | None = None
    room_name: str | None = None
    compute: str | None = None
    bus: str | None = None
    param_leaf: str | None = None
    biz_leaf: str | None = None
    mgmt: str | None = None
    sample_leaf: str | None = None


class DeviceInfoItem(BaseModel):
    """device_info_table.v0.json 中的单条记录（mock，后续从数据中心获取）"""
    model_config = ConfigDict(extra="ignore")
    section: str = ""
    device_model: str = ""
    device_role: str = ""
    device_qty: str = ""
    card_model: str = ""
    card_qty: int | None = None
    source_basename: str = ""


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    imported: int
    errors: list[dict[str, Any]]


# ─── Release 请求 ────────────────────────────────────────────────────────────

class ReleaseReq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapters: list[str] | None = Field(
        default=None,
        description="指定 release 的章节，如 ['5.1','5.2','5.3','7.1']；空=全部",
    )
