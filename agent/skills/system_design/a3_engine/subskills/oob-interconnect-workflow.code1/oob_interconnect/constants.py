"""通用常量与默认平面配置。

平面配置把「用户输入的互联规划名称」映射到：

- ``sheet_name`` : 端口连线表中的 sheet 名。
- ``keyword``  : 用于在连线表「leaf 列」上做包含匹配的关键字（大小写不敏感）。
- ``peer_keyword`` : 用于在连线表「spine/对端列」上做包含匹配的关键字（缺省 ``spine``）。
- ``network_type`` : 资源表「网络平面」列中对应的取值（用于查 VLAN / 互连地址段），同时是输出表「网络平面」列写入值。

默认配置覆盖常用网络平面：

- 端口连线表：``建模仿真输出文档007-端口连线表.xlsx``
- 资源信息表：``项目信息收集表.xlsx``

可在运行时通过 CLI ``--plane-config FILE`` 传入自定义 JSON 完全覆盖。
"""

from __future__ import annotations

DEFAULT_PLANE_CONFIG: dict[str, dict[str, str]] = {
    "计算带外管理互联规划": {
        "sheet_name": "计算带外管理面端口互联",
        "keyword": "DWGL-LEAF",
        "network_type": "计算带外管理面",
    },
    "存储带外管理互联规划": {
        "sheet_name": "存储带外管理面端口互联",
        "keyword": "DWGL-LEAF",
        "network_type": "存储带外管理面",
    },
    "网络带外管理互联规划": {
        "sheet_name": "网络带外管理面端口互联",
        "keyword": "DWGL-LEAF",
        "network_type": "网络带外管理面",
    },
    "灵衢带外管理互联规划": {
        "sheet_name": "灵衢带外管理面端口互联",
        "keyword": "DWGL-LEAF",
        "network_type": "灵衢带外管理面",
    },
    "计算管理面互联规划": {
        "sheet_name": "计算管理面端口互联",
        "keyword": "GLM-LEAF",
        "network_type": "计算管理面",
    },
    "计算管存面互联规划": {
        "sheet_name": "计算管存面端口互联",
        "keyword": "GCM-LEAF",
        "network_type": "计算管存面",
    },
    "计算业务面互联规划": {
        "sheet_name": "计算业务面端口互联",
        "keyword": "YWM-LEAF",
        "network_type": "计算业务面",
    },
    "计算样本面互联规划": {
        "sheet_name": "存储面端口互联 | 样本面端口互联",
        "keyword": "ZSYBM-LEAF",
        "network_type": "计算样本面",
    },
    "计算参数面互联规划": {
        "sheet_name": "参数面端口互联",
        "keyword": "LEAF",
        "network_type": "计算参数面",
    },
    "存储管理面互联规划": {
        "sheet_name": "存储管理面端口互联",
        "keyword": "CCGLM-LEAF",
        "network_type": "存储管理面",
    },
    "存储业务面互联规划": {
        "sheet_name": "存储业务面端口互联",
        "keyword": "CCYWM-LEAF",
        "network_type": "存储业务面",
    },
    "存储样本面互联规划": {
        "sheet_name": "样本面端口互联 | 数据面端口互联",
        "keyword": "CCYBM-LEAF",
        "network_type": "存储样本面",
    },
    "SPINE上行互联规划": {
        "sheet_name": "超平面端口互联",
        "keyword": "SP1-JHB",
        "peer_keyword": "SP1-LQS",
        "network_type": "网络互联地址",
    },
    "SPINE上行端口互联": {
        "sheet_name": "SPINE上行端口互联",
        "keyword": "FW-",
        "network_type": "防火墙互联地址",
    },
}

RESOURCE_SHEET = "资源表"
RESOURCE_PLANE_COLUMN = "网络平面"
RESOURCE_VLAN_COLUMN = "VLAN"
RESOURCE_IP_POOL_COLUMN = "互连地址段"
RESOURCE_GATEWAY_LOCATION_COLUMN = "网关位置"
OUTPUT_SHEET = "网络互联规划"
DEFAULT_OUTPUT_FILENAME = "A3网络互联规划.xlsx"
HEADER_TOKEN = "设备命名"
SPINE_TOKEN = "spine"
INTER_LINK_LABEL = "INTER_LINK"
TRUNK_PORT_TYPE = "trunk"
DEFAULT_TRUNK_START = 2
P30_MASK = 30
