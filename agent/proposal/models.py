"""Proposal module DTOs and enums."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DeliveryChannel(str, Enum):
    HUAWEI = "华为"
    CUSTOMER = "客户"


class DataSource(str, Enum):
    AUTO = "自动解析"
    MANUAL = "人工录入"


class ProductPartCategory(str, Enum):
    PRODUCT = "产品"
    PART = "部件"


class HardwareSubtype(str, Enum):
    MAIN_DEVICE = "主设备"
    CARD = "板卡·线卡·主控"
    COMPONENT = "网卡·CPU 等部件"
    OPTICAL = "光模块"
    POWER_FAN_DISK = "电源·风机·硬盘"


class DeviceInfoRow(BaseModel):
    row_id: str = Field(alias="rowId")
    device_model: str = Field(alias="deviceModel")
    product_code: str = Field(alias="productCode")
    quantity: float
    version: str = ""
    lifecycle_status: str = Field(default="", alias="lifecycleStatus")
    ga_actual_date: str | None = Field(default=None, alias="gaActualDate")
    ga_plan_date: str | None = Field(default=None, alias="gaPlanDate")
    eom_actual_date: str | None = Field(default=None, alias="eomActualDate")
    eom_plan_date: str | None = Field(default=None, alias="eomPlanDate")
    eos_actual_date: str | None = Field(default=None, alias="eosActualDate")
    eos_plan_date: str | None = Field(default=None, alias="eosPlanDate")
    device_u_height: float | None = Field(default=None, alias="deviceUHeight")
    data_source: DataSource = Field(alias="dataSource")
    proposal_version: str | None = Field(default=None, alias="proposalVersion")
    product_part_category: ProductPartCategory = Field(alias="productPartCategory")
    part_code: str = Field(default="", alias="partCode")
    hardware_subtype: HardwareSubtype = Field(alias="hardwareSubtype")
    device_role: str = Field(default="", alias="deviceRole")
    source_file: str | None = Field(default=None, alias="sourceFile")

    model_config = {"populate_by_name": True}


class DeviceInfoListResponse(BaseModel):
    rows: list[DeviceInfoRow]
    total: int


class PatchDeviceInfoBody(BaseModel):
    device_model: str | None = Field(default=None, alias="deviceModel")
    product_code: str | None = Field(default=None, alias="productCode")
    quantity: float | None = None
    version: str | None = None
    lifecycle_status: str | None = Field(default=None, alias="lifecycleStatus")
    ga_actual_date: str | None = Field(default=None, alias="gaActualDate")
    ga_plan_date: str | None = Field(default=None, alias="gaPlanDate")
    eom_actual_date: str | None = Field(default=None, alias="eomActualDate")
    eom_plan_date: str | None = Field(default=None, alias="eomPlanDate")
    eos_actual_date: str | None = Field(default=None, alias="eosActualDate")
    eos_plan_date: str | None = Field(default=None, alias="eosPlanDate")
    device_u_height: float | None = Field(default=None, alias="deviceUHeight")

    model_config = {"populate_by_name": True}


class ServiceDeliveryUiRow(BaseModel):
    row_id: str = Field(alias="rowId")
    service_major: str = Field(alias="serviceMajor")
    service_item: str = Field(alias="serviceItem")
    delivery_channel: DeliveryChannel = Field(alias="deliveryChannel")
    data_source: DataSource = Field(alias="dataSource")
    proposal_version: str | None = Field(default=None, alias="proposalVersion")

    model_config = {"populate_by_name": True}


class ServiceDeliveryUiListResponse(BaseModel):
    rows: list[ServiceDeliveryUiRow]


class PatchServiceDeliveryUiBody(BaseModel):
    delivery_channel: DeliveryChannel = Field(alias="deliveryChannel")

    model_config = {"populate_by_name": True}


class InitializeQuery(BaseModel):
    strategy: Literal["skip", "merge"] = "skip"


class ChangeRecord(BaseModel):
    seq: int
    chapter: str
    description: str


class CumulativeChangeEntry(BaseModel):
    seq: int | None = None
    proposal_version: str | None = Field(default=None, alias="proposalVersion")
    chapter: str | None = None
    change_description: str = Field(default="", alias="changeDescription")

    model_config = {"populate_by_name": True}


class PutDraftBody(BaseModel):
    change_description: str | None = Field(default=None, alias="changeDescription")
    change_records: list[ChangeRecord] | None = Field(default=None, alias="changeRecords")
    manual_change_log: list[CumulativeChangeEntry] | None = Field(
        default=None, alias="manualChangeLog"
    )
    chapters: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class ReleaseBody(BaseModel):
    chapters: list[str] | None = None
    change_description: str | None = Field(default=None, alias="changeDescription")

    model_config = {"populate_by_name": True}


class ReleaseAndDecideBody(BaseModel):
    change_description: str | None = Field(default=None, alias="changeDescription")
    change_records: list[ChangeRecord] | None = Field(default=None, alias="changeRecords")
    review_tag_hint: str | None = Field(default=None, alias="reviewTagHint")
    acknowledge_warnings: list[str] | None = Field(default=None, alias="acknowledgeWarnings")
    generate_document: bool = Field(default=True, alias="generateDocument")

    model_config = {"populate_by_name": True}


class RowLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"


class OverEos(str, Enum):
    YES = "是"
    NO = "否"


class ServiceContentRow(BaseModel):
    row_id: str = Field(alias="rowId")
    service_name: str = Field(alias="serviceName")
    service_content: str = Field(alias="serviceContent")
    quantity: float = Field(alias="quantity")
    unit: str = Field(alias="unit")
    row_level: RowLevel = Field(alias="rowLevel")
    parent_row_id: str | None = Field(default=None, alias="parentRowId")
    sale_code: str | None = Field(default=None, alias="saleCode")
    internal_seq: str | None = Field(default=None, alias="internalSeq")
    data_source: DataSource = Field(alias="dataSource")
    proposal_version: str | None = Field(default=None, alias="proposalVersion")

    model_config = {"populate_by_name": True}


class ServiceContentListResponse(BaseModel):
    rows: list[ServiceContentRow]
    total: int


class PatchServiceContentBody(BaseModel):
    service_name: str | None = Field(default=None, alias="serviceName")
    service_content: str | None = Field(default=None, alias="serviceContent")
    quantity: float | None = None
    unit: str | None = None

    model_config = {"populate_by_name": True}


class PostServiceContentBody(BaseModel):
    service_name: str = Field(alias="serviceName")
    service_content: str = Field(alias="serviceContent")
    quantity: float
    unit: str = ""
    parent_row_id: str | None = Field(default=None, alias="parentRowId")

    model_config = {"populate_by_name": True}


class MaintenanceStrategyRow(BaseModel):
    row_id: str = Field(alias="rowId")
    seq: int
    product_model: str = Field(alias="productModel")
    warranty_policy: str = Field(alias="warrantyPolicy")
    maintenance_policy: str = Field(alias="maintenancePolicy")
    maint_years: int | None = Field(default=None, alias="maintYears")
    maint_type_code: str | None = Field(default=None, alias="maintTypeCode")
    maint_start_date: str = Field(alias="maintStartDate")
    maint_end_date: str = Field(alias="maintEndDate")
    product_eos_date: str | None = Field(default=None, alias="productEosDate")
    over_eos: OverEos = Field(alias="overEos")
    over_eos_approval: str = Field(default="—", alias="overEosApproval")
    data_source: DataSource = Field(alias="dataSource")
    proposal_version: str | None = Field(default=None, alias="proposalVersion")

    model_config = {"populate_by_name": True}


class MaintenanceStrategyListResponse(BaseModel):
    rows: list[MaintenanceStrategyRow]


class PatchMaintenanceStrategyBody(BaseModel):
    product_model: str | None = Field(default=None, alias="productModel")
    warranty_policy: str | None = Field(default=None, alias="warrantyPolicy")
    maintenance_policy: str | None = Field(default=None, alias="maintenancePolicy")
    maint_start_date: str | None = Field(default=None, alias="maintStartDate")
    maint_end_date: str | None = Field(default=None, alias="maintEndDate")
    product_eos_date: str | None = Field(default=None, alias="productEosDate")
    over_eos_approval: str | None = Field(default=None, alias="overEosApproval")
    recalculate_end: bool = Field(default=True, alias="recalculateEnd")

    model_config = {"populate_by_name": True}


class MaintenanceSlaRow(BaseModel):
    row_id: str = Field(alias="rowId")
    seq: str = Field(default="1")
    severity_level: str = Field(alias="severityLevel")
    coverage_period: str = Field(alias="coveragePeriod")
    response_time: str = Field(alias="responseTime")
    restore_time: str = Field(alias="restoreTime")
    resolve_time: str = Field(alias="resolveTime")
    service_item: str | None = Field(default=None, alias="serviceItem")
    data_source: DataSource = Field(alias="dataSource")
    proposal_version: str | None = Field(default=None, alias="proposalVersion")

    model_config = {"populate_by_name": True}


class MaintenanceSlaResponse(BaseModel):
    hardware_support: str = Field(default="", alias="hardwareSupport")
    service_level: str = Field(default="", alias="serviceLevel")
    rows: list[MaintenanceSlaRow] = Field(default_factory=list)
    meta: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class PatchMaintenanceSlaBody(BaseModel):
    severity_level: str | None = Field(default=None, alias="severityLevel")
    coverage_period: str | None = Field(default=None, alias="coveragePeriod")
    response_time: str | None = Field(default=None, alias="responseTime")
    restore_time: str | None = Field(default=None, alias="restoreTime")
    resolve_time: str | None = Field(default=None, alias="resolveTime")

    model_config = {"populate_by_name": True}


class PatchMaintenanceSlaHardwareSupportBody(BaseModel):
    hardware_support: str = Field(alias="hardwareSupport")

    model_config = {"populate_by_name": True}


class PatchMetadataBody(BaseModel):
    document_summary: str | None = Field(default=None, alias="documentSummary")
    manual_change_log: list[CumulativeChangeEntry] | None = Field(
        default=None, alias="manualChangeLog"
    )

    model_config = {"populate_by_name": True}


class PutManualChangeLogBody(BaseModel):
    entries: list[CumulativeChangeEntry] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
