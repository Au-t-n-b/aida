"""Gate sheet and network-plane mappings aligned with LLD_IP/config.py."""

from __future__ import annotations

# instruction -> gate sheet (default "互联" when missing)
INSTRUCTION_NETWORK_TYPE_CONFIG: dict[str, str] = {
    "计算样本面地址规划": "存储面端口互联 | 样本面端口互联",
    "计算管理面地址规划": "计算管理面端口互联",
    "计算管存面地址规划": "计算管存面端口互联",
    "计算业务面地址规划": "计算业务面端口互联",
    "存储业务面地址规划": "存储业务面端口互联",
    "计算参数面地址规划": "参数面端口互联",
    "计算超平面地址规划": "超平面端口互联",
    "存储带外管理地址规划": "存储带外管理面端口互联",
    "计算带外管理地址规划": "计算带外管理面端口互联",
    "网络带外管理地址规划": "网络带外管理面端口互联",
    "灵衢带外管理地址规划": "灵衢带外管理面端口互联",
    "计算样本面互联规划": "存储面端口互联 | 样本面端口互联",
    "计算参数面互联规划": "参数面端口互联",
    "存储样本面地址规划": "样本面端口互联 | 数据面端口互联",
    "存储样本面互联规划": "样本面端口互联 | 数据面端口互联",
    "网络业务地址规划": "网络业务地址规划",
    "交换机MLAG规划": "存储管理面端口互联",
    "网络设备ASN规划": "存储管理面端口互联",
}

# gate sheet -> resource table 网络平面 name
WEB_NETWORK_TYPE_CONFIG: dict[str, str] = {
    "存储面端口互联 | 样本面端口互联": "计算样本面",
    "计算管理面端口互联": "计算管理面",
    "计算业务面端口互联": "计算业务面",
    "计算管存面端口互联": "计算管存面",
    "参数面端口互联": "计算参数面",
    "样本面端口互联 | 数据面端口互联": "存储样本面",
    "存储业务面端口互联": "存储业务面",
    "存储管理面端口互联": "存储管理面",
    "计算带外管理面端口互联": "计算带外管理面",
    "网络带外管理面端口互联": "网络带外管理面",
    "灵衢带外管理面端口互联": "灵衢带外管理面",
    "存储带外管理面端口互联": "存储带外管理面",
    "超平面端口互联": "超平面",
    "网络业务地址规划": "其它",
}

# MLAG skill scans these topology sheet names (skip 超平面)
MLAG_TOPOLOGY_SHEETS: frozenset[str] = frozenset(WEB_NETWORK_TYPE_CONFIG.keys()) - {"超平面端口互联"}

# main_flow.generate_all_lld_file instruction order
INSTRUCTION_SET: list[str] = [
    "交换机MLAG规划",
    "计算带外管理地址规划",
    "存储带外管理地址规划",
    "网络带外管理地址规划",
    "灵衢带外管理地址规划",
    "计算管理面地址规划",
    "存储管理面地址规划",
    "计算管存面地址规划",
    "计算参数面地址规划",
    "计算超平面地址规划",
    "计算业务面地址规划",
    "存储业务面地址规划",
    "计算样本面地址规划",
    "存储样本面地址规划",
    "网络业务地址规划",
    "网络设备ASN规划",
    "计算样本面互联规划",
    "计算参数面互联规划",
    "存储样本面互联规划",
    "CCAE规划",
    "DME规划",
    "NCE规划",
    "融合完整LLD设计",
]

INTEGRATE_EXCLUDE_PLANE_KEYS: frozenset[str] = frozenset({
    "A3LLD设计",
    "A3网络设备接入规划",
})
INTEGRATE_EXCLUDE_FILENAMES: frozenset[str] = frozenset({
    "网络设备接入规划.xlsx",
    "A3网络设备接入规划.xlsx",
})

# CPM 等子 skill 产物名省略 A3 前缀时的融合别名（plane_key → 扫描文件名）
INTEGRATE_PLANE_FILENAME_ALIASES: dict[str, str] = {
    "超平面网络规划.xlsx": "A3超平面网络规划",
}
