"""
交付预案 · 第 5 章（组网配置）+ 第 7 章（机房信息）· 内存存储层

对标 agent/sog_assets.py：Store 类管理数据，内存存储（mock），不依赖数据库。
后续可替换为文件/数据库持久化，API 层无需改动。

数据结构对齐：
  - 04-预案上下文.md §8（组网配置）、§10（机房信息）
  - 开发文档/第5章-组网配置/*.md
  - 开发文档/第7章-机房信息/*.md
"""
from __future__ import annotations

import json
import os
import uuid

from pathlib import Path
from typing import Any

from .proposal_models import (
    AvailableDeviceItem,
    ClusterDeviceRow,
    DeviceRoleItem,
    NetMgmtRow,
    NetPlaneRow,
    RoomRackRow,
    WarningItem,
)


# ─── 枚举常量 ────────────────────────────────────────────────────────────────


CLUSTER_TYPE_ENUM = {"训练", "推理", "训推"}
NET_MGMT_ROLE_ENUM = {"NCE", "CCAE", "DME"}

DEVICE_ROLE_ENUM: list[DeviceRoleItem] = [
    DeviceRoleItem(key="param-access", label="参数面（接入）"),
    DeviceRoleItem(key="sample-access", label="样本面（接入）"),
    DeviceRoleItem(key="biz-access", label="业务面（接入）"),
    DeviceRoleItem(key="storage-access", label="存储面（接入）"),
    DeviceRoleItem(key="mgmt-access", label="网管面（接入）"),
    DeviceRoleItem(key="param-agg", label="参数面（汇聚）"),
    DeviceRoleItem(key="sample-agg", label="样本面（汇聚）"),
    DeviceRoleItem(key="biz-agg", label="业务面（汇聚）"),
    DeviceRoleItem(key="storage-agg", label="存储面（汇聚）"),
    DeviceRoleItem(key="mgmt-agg", label="网管面（汇聚）"),
]

DEVICE_ROLE_LABELS = {item.label for item in DEVICE_ROLE_ENUM}

DEVICE_INFO_PATH = Path(__file__).resolve().parent.parent / "data" / "delivery" / "device-info.xlsx"


def load_available_devices() -> list[AvailableDeviceItem]:
    """读取项目目录中的设备型号/版本字典。"""
    if not DEVICE_INFO_PATH.is_file():
        return []

    from openpyxl import load_workbook

    sheet = load_workbook(DEVICE_INFO_PATH, data_only=True, read_only=True).active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []

    headers = {str(value or "").strip(): index for index, value in enumerate(rows[0])}
    model_index = headers.get("设备型号", headers.get("device_model"))
    version_index = headers.get("设备版本", headers.get("device_version"))
    if model_index is None or version_index is None:
        return []

    devices = []
    for row in rows[1:]:
        model = str(row[model_index] or "").strip()
        version = str(row[version_index] or "").strip()
        if model:
            devices.append(
                AvailableDeviceItem(
                    vendor="",
                    device_model=model,
                    device_version=version,
                    boq_quantity=0,
                )
            )
    return devices


# ─── 校验函数 ────────────────────────────────────────────────────────────────




def validate_cluster_type(cluster_type: str) -> None:
    if cluster_type not in CLUSTER_TYPE_ENUM:
        raise ValueError(f"BR_PROPOSAL_V15: 无效集群类型 '{cluster_type}'，允许值：{CLUSTER_TYPE_ENUM}")


def validate_cluster_ids(row: dict[str, Any]) -> None:
    """校验集群设备清单的 ID 列（V10）"""
    required_ids = [
        ("cluster_id", "集群 ID"),
        ("super_pod_id", "超节点 ID"),
        ("storage_cluster_id", "存储集群 ID"),
        ("zone_id", "ZONE ID"),
        ("ccae_cluster_id", "CCAE 集群 ID"),
        ("dme_cluster_id", "DME 集群 ID"),
    ]
    for field, label in required_ids:
        value = row.get(field)
        if not value or not str(value).strip():
            raise ValueError(f"BR_PROPOSAL_V10: {label}不可为空")


def validate_device_purpose(device_purpose: str | None) -> None:
    if not device_purpose or not device_purpose.strip():
        raise ValueError("BR_PROPOSAL_V11: 设备用途不可为空")


def validate_device_naming(start_name: str | None, end_name: str | None) -> list[WarningItem]:
    """校验起止设备命名区间（V17）"""
    warnings = []
    if start_name and end_name:
        if start_name > end_name:
            raise ValueError(f"BR_PROPOSAL_V17: 起始设备命名 '{start_name}' 不可大于截止设备命名 '{end_name}'")
    return warnings



# ─── ProposalStore ───────────────────────────────────────────────────────────

class ProposalStore:
    """
    交付预案内存存储（mock）。

    数据结构：
      - net_plane_rows: dict[project_id, list[NetPlaneRow]]
      - net_mgmt_rows: dict[project_id, list[NetMgmtRow]]
      - cluster_device_rows: dict[project_id, list[ClusterDeviceRow]]
      - room_rack_rows: dict[project_id, list[RoomRackRow]]

    后续可替换为文件/数据库持久化，API 层无需改动。

    本地持久化：每次变更后自动写入 data/proposal_store.json；
    启动时优先从文件恢复，若无文件则走 mock 初始化。
    """

    _DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

    @classmethod
    def _get_data_dir(cls) -> Path:
        env_dir = os.environ.get("PROPOSAL_DATA_DIR")
        if env_dir:
            return Path(env_dir)
        return cls._DATA_DIR

    def __init__(self) -> None:
        self.net_plane_rows: dict[str, list[NetPlaneRow]] = {}
        self.net_mgmt_rows: dict[str, list[NetMgmtRow]] = {}
        self.cluster_device_rows: dict[str, list[ClusterDeviceRow]] = {}
        self.room_rack_rows: dict[str, list[RoomRackRow]] = {}
        self._load()

    # ─── 持久化 ──────────────────────────────────────────────────────────────

    def _path(self) -> Path:
        return self._get_data_dir() / "proposal_store.json"

    def _load(self) -> None:
        path = self._path()
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text("utf-8"))
            for pid, rows_data in raw.get("net_plane_rows", {}).items():
                self.net_plane_rows[pid] = [NetPlaneRow(**r) for r in rows_data]
            for pid, rows_data in raw.get("room_rack_rows", {}).items():
                self.room_rack_rows[pid] = [RoomRackRow(**r) for r in rows_data]
            for pid, rows_data in raw.get("net_mgmt_rows", {}).items():
                self.net_mgmt_rows[pid] = [NetMgmtRow(**r) for r in rows_data]
            for pid, rows_data in raw.get("cluster_device_rows", {}).items():
                self.cluster_device_rows[pid] = [ClusterDeviceRow(**r) for r in rows_data]
        except Exception:
            pass

    def _save(self) -> None:
        data_dir = self._get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "net_plane_rows": {
                pid: [r.model_dump() for r in rows]
                for pid, rows in self.net_plane_rows.items()
            },
            "room_rack_rows": {
                pid: [r.model_dump() for r in rows]
                for pid, rows in self.room_rack_rows.items()
            },
            "net_mgmt_rows": {
                pid: [r.model_dump() for r in rows]
                for pid, rows in self.net_mgmt_rows.items()
            },
            "cluster_device_rows": {
                pid: [r.model_dump() for r in rows]
                for pid, rows in self.cluster_device_rows.items()
            },
        }
        self._path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")

    # ─── 5.1 网络平面配置 ────────────────────────────────────────────────────

    def list_net_plane(self, project_id: str) -> list[NetPlaneRow]:
        """获取网络平面配置列表；首次访问时自动初始化 mock 数据"""
        if project_id not in self.net_plane_rows:
            self._init_net_plane_mock(project_id)
        return self.net_plane_rows.get(project_id, [])

    def _init_net_plane_mock(self, project_id: str) -> None:
        """自动初始化网络平面 mock 数据（对齐前端 NETWORK_PLANES 静态数据）"""
        self.net_plane_rows[project_id] = [
            NetPlaneRow(
                row_id="np-001",
                type="参数面汇聚交换机",
                vendor="华为",
                model="XH9330-128EO",
                ver="V100R001C020",
                qty=64,
                source="人工录入",
                note="",
            ),
            NetPlaneRow(
                row_id="np-002",
                type="参数面接入交换机",
                vendor="华为",
                model="XH9930-128DQ",
                ver="V100R001C020",
                qty=174,
                source="人工录入",
                note="",
            ),
            NetPlaneRow(
                row_id="np-003",
                type="样本面-存储接入交换机",
                vendor="华为",
                model="XH9930-128DQ",
                ver="V100R001C020",
                qty=6,
                source="人工录入",
                note="",
            ),
            NetPlaneRow(
                row_id="np-004",
                type="样本面-汇聚交换机",
                vendor="华为",
                model="XH9930-128DQ",
                ver="V100R001C020",
                qty=16,
                source="人工录入",
                note="",
            ),
            NetPlaneRow(
                row_id="np-005",
                type="样本面-计算接入交换机",
                vendor="华为",
                model="XH9930-128DQ",
                ver="V100R001C020",
                qty=22,
                source="人工录入",
                note="",
            ),
        ]

    def list_device_roles(self) -> list[DeviceRoleItem]:
        """返回设备角色枚举值列表（供前端下拉）"""
        return list(DEVICE_ROLE_ENUM)

    def list_available_devices(self) -> list[AvailableDeviceItem]:
        """返回设备信息表可用设备（供前端选设备时自动填充厂家/型号/版本/数量）"""
        return load_available_devices()

    def create_net_plane(self, project_id: str, source_row_id: str) -> NetPlaneRow:
        """行复制（「+」按钮）：取源行骨架，qty=0，note 清空，source=人工录入"""
        rows = self.net_plane_rows.setdefault(project_id, [])
        source = next((r for r in rows if r.row_id == source_row_id), None)
        if not source:
            raise ValueError(f"源行 {source_row_id} 不存在")

        new_row = NetPlaneRow(
            row_id=str(uuid.uuid4()),
            type=source.type,
            vendor=source.vendor,
            model=source.model,
            ver=source.ver,
            qty=0,
            source="人工录入",
            note=None,
        )
        source_index = rows.index(source)
        rows.insert(source_index + 1, new_row)
        self._save()
        return new_row

    def update_net_plane(self, project_id: str, row_id: str, data: dict[str, Any]) -> tuple[NetPlaneRow, list[WarningItem]]:
        """CELL 编辑：更新 vendor / type / model / ver / qty / source / note，触发数量校验（V7-V9）"""
        rows = self.net_plane_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")

        if "vendor" in data and data["vendor"] is not None:
            row.vendor = data["vendor"]

        if "type" in data and data["type"] is not None:
            row.type = data["type"]

        if "model" in data and data["model"] is not None:
            row.model = data["model"]

        if "ver" in data and data["ver"] is not None:
            row.ver = data["ver"]

        if "qty" in data and data["qty"] is not None:
            row.qty = data["qty"]

        if "source" in data and data["source"] is not None:
            row.source = data["source"]

        if "note" in data:
            row.note = data["note"]

        self._save()
        return row, []

    def delete_net_plane(self, project_id: str, row_id: str, confirm: bool = False) -> None:
        rows = self.net_plane_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")
        if row.source == "自动解析" and not confirm:
            raise ValueError("自动解析行需要 confirm=true 才能删除")
        rows.remove(row)
        self._save()

    # ─── 5.2 网管服务器配置 ──────────────────────────────────────────────────

    def list_net_mgmt(self, project_id: str) -> list[NetMgmtRow]:
        if project_id not in self.net_mgmt_rows:
            self.initialize_net_mgmt(project_id)
        return self.net_mgmt_rows.get(project_id, [])

    def initialize_net_mgmt(self, project_id: str) -> list[NetMgmtRow]:
        """扫描 data/delivery/net-mgmt 文件名，识别 NCE/CCAE/DME 角色。"""
        existing_by_role = {
            row.server_role: row
            for row in self.net_mgmt_rows.get(project_id, [])
        }
        source_dir = Path(__file__).resolve().parent.parent / "data" / "delivery" / "net-mgmt"
        detected_roles = {
            role
            for path in source_dir.rglob("*") if path.is_file()
            for role in NET_MGMT_ROLE_ENUM if role in path.name.upper()
        } if source_dir.is_dir() else set()
        rows: list[NetMgmtRow] = []
        for role in sorted(detected_roles):
            rows.append(
                existing_by_role.get(role)
                or NetMgmtRow(
                    row_id=str(uuid.uuid4()),
                    server_role=role,
                    server_model="",
                    quantity=1,
                    data_source="自动解析",
                )
            )
        self.net_mgmt_rows[project_id] = rows
        self._save()
        return rows

    def create_net_mgmt(self, project_id: str, data: dict[str, Any]) -> NetMgmtRow:
        """人工新增行（非枚举角色场景）"""
        rows = self.net_mgmt_rows.setdefault(project_id, [])
        new_row = NetMgmtRow(
            row_id=str(uuid.uuid4()),
            server_role=data["server_role"],
            server_model=data.get("server_model", "通算服务器"),
            quantity=data.get("quantity", 1),
            data_source="人工录入",
        )
        rows.append(new_row)
        self._save()
        return new_row

    def update_net_mgmt(self, project_id: str, row_id: str, data: dict[str, Any]) -> NetMgmtRow:
        """角色由文件名识别；服务器型号和数量由用户手工维护。"""
        rows = self.net_mgmt_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")
        if data.get("server_model") is not None:
            row.server_model = data["server_model"]
        if data.get("quantity") is not None:
            row.quantity = data["quantity"]
        row.data_source = "人工录入"
        self._save()
        return row

    def delete_net_mgmt(self, project_id: str, row_id: str) -> None:
        rows = self.net_mgmt_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")
        rows.remove(row)
        self._save()

    # ─── 5.3 集群设备清单表 ──────────────────────────────────────────────────

    def list_cluster_device(self, project_id: str) -> list[ClusterDeviceRow]:
        if project_id not in self.cluster_device_rows:
            self._init_cluster_device_from_net_plane(project_id)
        return self.cluster_device_rows.get(project_id, [])

    def _init_cluster_device_from_net_plane(self, project_id: str) -> None:
        """首次访问时自动从 5.1 网络平面行继承初始化 5.3 行"""
        np_rows = self.list_net_plane(project_id)
        cd_rows: list[ClusterDeviceRow] = []
        for np_row in np_rows:
            cd_rows.append(
                ClusterDeviceRow(
                    row_id=str(uuid.uuid4()),
                    source_net_plane_id=np_row.row_id,
                    max_quantity=np_row.qty,
                    cluster_id=None,
                    cluster_type="训练",
                    super_pod_id=None,
                    storage_cluster_id=None,
                    zone_id=None,
                    ccae_cluster_id=None,
                    dme_cluster_id=None,
                    device_type="",
                    vendor=np_row.vendor,
                    device_model=np_row.model,
                    device_purpose=None,
                    start_device_name=None,
                    end_device_name=None,
                    quantity=np_row.qty,
                    data_source="人工录入",
                )
            )
        self.cluster_device_rows[project_id] = cd_rows
        self._save()

    def create_cluster_device(self, project_id: str, source_net_plane_id: str) -> ClusterDeviceRow:
        """从 5.1 网络平面行继承厂家/型号/数量，创建 5.3 新行"""
        np_rows = self.list_net_plane(project_id)
        source = next((r for r in np_rows if r.row_id == source_net_plane_id), None)
        if not source:
            raise ValueError(f"5.1 网络平面行 {source_net_plane_id} 不存在")

        rows = self.cluster_device_rows.setdefault(project_id, [])
        new_row = ClusterDeviceRow(
            row_id=str(uuid.uuid4()),
            source_net_plane_id=source_net_plane_id,
            max_quantity=source.qty,
            cluster_id=None,
            cluster_type="训练",
            super_pod_id=None,
            storage_cluster_id=None,
            zone_id=None,
            ccae_cluster_id=None,
            dme_cluster_id=None,
            device_type="",
            vendor=source.vendor,
            device_model=source.model,
            device_purpose=None,
            start_device_name=None,
            end_device_name=None,
            quantity=0,
            data_source="人工录入",
        )
        idx = next(
            (i for i, r in enumerate(rows) if r.source_net_plane_id == source_net_plane_id),
            None,
        )
        if idx is not None:
            insert_pos = idx + 1
            while insert_pos < len(rows) and rows[insert_pos].source_net_plane_id == source_net_plane_id:
                insert_pos += 1
            rows.insert(insert_pos, new_row)
        else:
            rows.append(new_row)
        self._save()
        return new_row

    def update_cluster_device(self, project_id: str, row_id: str, data: dict[str, Any]) -> tuple[ClusterDeviceRow, list[WarningItem]]:
        """CELL 编辑：更新字段，触发 ID/用途/命名/数量校验"""
        rows = self.cluster_device_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")

        if "cluster_type" in data and data["cluster_type"]:
            validate_cluster_type(data["cluster_type"])
            row.cluster_type = data["cluster_type"]

        if "device_purpose" in data:
            validate_device_purpose(data["device_purpose"])
            row.device_purpose = data["device_purpose"]

        for field in ("cluster_id", "super_pod_id", "storage_cluster_id",
                       "zone_id", "ccae_cluster_id", "dme_cluster_id",
                       "device_type"):
            if field in data and data[field] is not None:
                setattr(row, field, data[field])

        if "start_device_name" in data:
            row.start_device_name = data["start_device_name"]
        if "end_device_name" in data:
            row.end_device_name = data["end_device_name"]

        if "quantity" in data and data["quantity"] is not None:
            row.quantity = data["quantity"]

        warnings = validate_device_naming(row.start_device_name, row.end_device_name)

        self._save()
        return row, warnings

    def delete_cluster_device(self, project_id: str, row_id: str, confirm: bool = False) -> None:
        rows = self.cluster_device_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")
        if row.data_source == "自动解析" and not confirm:
            raise ValueError("自动解析行需要 confirm=true 才能删除")
        rows.remove(row)
        self._save()

    # ─── 7.1 机房信息（PoD 机柜分配） ─────────────────────────────────────────

    def list_room_rack(self, project_id: str) -> list[RoomRackRow]:
        if project_id not in self.room_rack_rows:
            self._init_room_rack_from_device_info(project_id)
        return self.room_rack_rows.get(project_id, [])

    def _init_room_rack_from_device_info(self, project_id: str) -> None:
        """首次访问时从 device_info_table mock 提取 PoD 名称初始化"""
        pod_names = self._extract_pod_names_from_device_info()
        rows: list[RoomRackRow] = []
        for pod_name in pod_names:
            rows.append(
                RoomRackRow(
                    row_id=str(uuid.uuid4()),
                    pod_name=pod_name,
                    room_name="",
                    compute="",
                    bus="",
                    param_leaf="",
                    biz_leaf="",
                    mgmt="",
                    sample_leaf="",
                    data_source="自动解析",
                )
            )
        self.room_rack_rows[project_id] = rows

    def _extract_pod_names_from_device_info(self) -> list[str]:
        """从 device_info_table mock 数据中提取 PoD 名称（去重、排序）"""
        import re
        pod_names: set[str] = set()
        for item in self._mock_device_info_table():
            basename = item.get("source_basename", "")
            match = re.search(r"POD(\d+)", basename, re.IGNORECASE)
            if match:
                pod_names.add(f"POD{match.group(1)}")
        return sorted(pod_names, key=lambda x: int(re.search(r"\d+", x).group()) if re.search(r"\d+", x) else 0)

    def _mock_device_info_table(self) -> list[dict[str, Any]]:
        """device_info_table.v0.json mock 数据（后续从数据中心 API 获取）"""
        return [
            {
                "section": "智算服务器",
                "device_model": "Atlas 900 A3",
                "device_role": "智算服务器",
                "device_qty": "48",
                "card_model": "",
                "card_qty": None,
                "source_basename": "JXX项目2025昇腾超节点下单-三期-1-1_0000Hw00478677202512170036_不含价格-POD01",
            },
            {
                "section": "智算服务器",
                "device_model": "Atlas 900 A3",
                "device_role": "智算服务器",
                "device_qty": "48",
                "card_model": "",
                "card_qty": None,
                "source_basename": "JXX项目2025昇腾超节点下单-三期-1-1_0000Hw00478677202512170037_不含价格-POD02",
            },
            {
                "section": "智算服务器",
                "device_model": "Atlas 900 A3",
                "device_role": "智算服务器",
                "device_qty": "48",
                "card_model": "",
                "card_qty": None,
                "source_basename": "JXX项目2025昇腾超节点下单-三期-1-1_0000Hw00478677202512170038_不含价格-POD03",
            },
            {
                "section": "存储设备",
                "device_model": "OceanStor Pacific",
                "device_role": "存储节点",
                "device_qty": "9",
                "card_model": "",
                "card_qty": None,
                "source_basename": "JXX项目2025昇腾超节点下单-三期-1-1_0000Hw00478677202512170039_不含价格-POD04",
            },
        ]

    def get_device_info_table(self) -> list[dict[str, Any]]:
        """获取 device_info_table 数据（mock，后续替换为数据中心 API 调用）"""
        return self._mock_device_info_table()

    def create_room_rack(self, project_id: str, data: dict[str, Any], source_row_id: str | None = None) -> RoomRackRow:
        rows = self.room_rack_rows.setdefault(project_id, [])
        new_row = RoomRackRow(
            row_id=str(uuid.uuid4()),
            pod_name=data.get("pod_name", ""),
            room_name=data.get("room_name", ""),
            compute=data.get("compute", ""),
            bus=data.get("bus", ""),
            param_leaf=data.get("param_leaf", ""),
            biz_leaf=data.get("biz_leaf", ""),
            mgmt=data.get("mgmt", ""),
            sample_leaf=data.get("sample_leaf", ""),
            data_source="人工录入",
        )
        source = next((row for row in rows if row.row_id == source_row_id), None)
        if source:
            rows.insert(rows.index(source) + 1, new_row)
        else:
            rows.append(new_row)
        self._save()
        return new_row

    def update_room_rack(self, project_id: str, row_id: str, data: dict[str, Any]) -> RoomRackRow:
        rows = self.room_rack_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")

        for field in ("pod_name", "room_name", "compute", "bus",
                       "param_leaf", "biz_leaf", "mgmt", "sample_leaf"):
            if field in data and data[field] is not None:
                setattr(row, field, data[field])

        self._save()
        return row

    def delete_room_rack(self, project_id: str, row_id: str, confirm: bool = False) -> None:
        rows = self.room_rack_rows.get(project_id, [])
        row = next((r for r in rows if r.row_id == row_id), None)
        if not row:
            raise ValueError(f"行 {row_id} 不存在")
        if row.data_source == "自动解析" and not confirm:
            raise ValueError("自动解析行需要 confirm=true 才能删除")
        rows.remove(row)
        self._save()
        self._save()
