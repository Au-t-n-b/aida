# vendored from CPCIA_AGENT deploymentandtest/constant/files.py (feature_new / CloudopsConfigColumns)

class AgentTag:
    INSTALLATION = "installation_agent"
    DESIGN = "design_agent"
    DEPLOYMENT = "deployment_agent"


class FileTagName:
    LLD_DESIGN = "LLD_Design"
    CLOUDOPS_CONFIG_INIT = "CloudOps_Config_Init"
    CLOUDOPS_CONFIG_MANUAL = "CloudOps_Config_Manual"
    CLOUDOPS_CONFIG_FULL = "CloudOps_Config_Full"
    CHECK_LIST = "Device_Checklist"
    PARAMS_CONFIG = "CloudOps_Params_Config"
    LQ_CONFIG_CHECK = "ZTP_CFG"


class DeviceCheckListColumns:
    SERVER_TYPE = "设备大类"
    VENDOR = "厂家"
    DEVICE_MODEL = "设备型号"
    DEVICE_NAME = "设备名称"
    SERIAL_NUMBER = "ESN"


class CloudopsConfigSheets:
    SERVER_INFO = "服务器信息"
    SWITCH_INFO = "交换机信息"
    VERSION_INFO = "版本信息"
    CONNECTION_TABLE = "连线表"
    OS_CONFIG_INFO = "OS配置信息"
    DISK_PARTITION = "磁盘分区"
    ROUTER = "路由"
    NETWORK_PORT_PANEL_DIAGRAM = "网口面板图"
    NPU_MULTI_PLANE_PARTITIONING = "NPU多平面划分"
    NPU_RoCE_UDP_PORT = "NPU RoCE UDP端口"


class CloudopsConfigColumns:
    # 服务器信息（对齐 Agent feature_new）
    HOST_NAME = "主机名称"
    SERIAL_NUMBER = "SN序列号"
    DEVICE_ID = "设备ID*（主键）"
    IBMC_IP_ADDRESS = "IBMC-IP地址"
    IBMC_USERNAME = "IBMC用户名"
    IBMC_PASSWORD = "IBMC密码"
    IBMC_HTTPS_PORT = "IBMC-HTTPS端口"
    MANAGEMENT_IPV4_ADDRESS = "管理网-IPV4地址"
    MANAGEMENT_IPV4_GATEWAY = "管理网-IPV4网关"
    MANAGEMENT_IPV4_SUBNET_MASK = "管理网-IPV4掩码"
    MANAGEMENT_USERNAME = "管理网-用户名"
    MANAGEMENT_PASSWORD = "管理网-密码"
    ROOT_PASSWORD = "ROOT密码"
    SSH_SFTP_PORT = "SSH/SFTP端口(默认22)"
    PARAMETER_IPV4_ADDRESS = "参数网-IPV4地址"
    PARAMETER_IPV4_GATEWAY = "参数网-IPV4网关"
    PARAMETER_IPV4_SUBNET_MASK = "参数网-IPV4掩码"
    VENDOR = "厂家"
    SERVER_TYPE = "服务器类型"
    SERVER_MODEL = "服务器型号"
    DATA_CENTER = "机房"
    CABINET = "柜列"
    COUNTER = "柜位"
    U_POSITION = "U位"
    U_HEIGHT = "U数"
    SUPER_NODE_SET_ID = "超节点集合ID"
    COMPUTING_SUPER_ID_WITH_SUPER_NODE = "超节点内的计算节点编号"
    SUPER_NODE_SCALE = "超节点规模(NPU卡数)"

    # 模板中仍保留的 IBMC v4/v6 列（初配可不填，与 Agent 一致）
    IBMC_IPV4_SUBNET_MASK = "IBMC-IPV4掩码"
    IBMC_IPV4_GATEWAY = "IBMC-IPV4网关"
    IBMC_IPV6_ADDRESS = "IBMC-IPV6地址"
    IBMC_IPV6_SUBNET_MASK = "IBMC-IPV6掩码"
    IBMC_IPV6_GATEWAY = "IBMC-IPV6网关"

    # 旧版 Skill/模板列名（读档兼容）
    IBMC_IPV4_ADDRESS = "IBMC-IPV4地址"
    DEVICE_NAME_LEGACY_SERVER = "设备名称"

    # 交换机信息
    DEVICE_NAME = "设备名称"
    DEVICE_IP = "设备IP"
    MANAGEMENT_USERNAME_SWITCH = "管理网用户名"
    PASSWORD = "密码"
    SSH_PORT = "ssh端口"
    DEVICE_TYPE = "设备类型"

    # 连线表
    SERVER_SWITCH_NAME = "服务器/交换机名称"
    MANAGEMENT_IP = "管理网IP"
    SOURCE_INTERFACE_NAME = "源端接口名称"
    SOURCE_INTERFACE_PHYSICAL_POSITION = "源端接口_物理位置"
    SOURCE_INTERFACE_PANEL_LAYOUT = "源端接口面板图Profile"
    DESTINATION_SWITCH_NAME = "目标端交换机名称"
    DESTINATION_INTERFACE_NAME = "目标端接口名称"
    DESTINATION_INTERFACE_PHYSICAL_POSITION = "目标端接口_物理位置"
    DESTINATION_INTERFACE_PANEL_LAYOUT = "目标端接口面板图Profile"


# CPCIA ChecklistToCloudOpsConfig 写回完整配置时的列顺序（与 Agent 一致）
SERVER_EXPORT_COLUMNS: tuple[str, ...] = (
    CloudopsConfigColumns.DEVICE_ID,
    CloudopsConfigColumns.IBMC_IP_ADDRESS,
    CloudopsConfigColumns.IBMC_USERNAME,
    CloudopsConfigColumns.IBMC_PASSWORD,
    CloudopsConfigColumns.IBMC_HTTPS_PORT,
    CloudopsConfigColumns.HOST_NAME,
    CloudopsConfigColumns.MANAGEMENT_IPV4_ADDRESS,
    CloudopsConfigColumns.MANAGEMENT_USERNAME,
    CloudopsConfigColumns.MANAGEMENT_PASSWORD,
    CloudopsConfigColumns.ROOT_PASSWORD,
    CloudopsConfigColumns.SSH_SFTP_PORT,
    CloudopsConfigColumns.MANAGEMENT_IPV4_GATEWAY,
    CloudopsConfigColumns.MANAGEMENT_IPV4_SUBNET_MASK,
    CloudopsConfigColumns.VENDOR,
    CloudopsConfigColumns.SERVER_TYPE,
    CloudopsConfigColumns.SERVER_MODEL,
    CloudopsConfigColumns.PARAMETER_IPV4_ADDRESS,
    CloudopsConfigColumns.PARAMETER_IPV4_SUBNET_MASK,
    CloudopsConfigColumns.PARAMETER_IPV4_GATEWAY,
    CloudopsConfigColumns.DATA_CENTER,
    CloudopsConfigColumns.CABINET,
    CloudopsConfigColumns.COUNTER,
    CloudopsConfigColumns.U_POSITION,
    CloudopsConfigColumns.U_HEIGHT,
    CloudopsConfigColumns.SERIAL_NUMBER,
    CloudopsConfigColumns.SUPER_NODE_SET_ID,
    CloudopsConfigColumns.COMPUTING_SUPER_ID_WITH_SUPER_NODE,
    CloudopsConfigColumns.SUPER_NODE_SCALE,
)

SWITCH_EXPORT_COLUMNS: tuple[str, ...] = (
    CloudopsConfigColumns.DEVICE_ID,
    CloudopsConfigColumns.DEVICE_NAME,
    CloudopsConfigColumns.DEVICE_IP,
    CloudopsConfigColumns.MANAGEMENT_USERNAME_SWITCH,
    CloudopsConfigColumns.PASSWORD,
    CloudopsConfigColumns.SSH_PORT,
    CloudopsConfigColumns.VENDOR,
    CloudopsConfigColumns.DEVICE_TYPE,
    CloudopsConfigColumns.DATA_CENTER,
    CloudopsConfigColumns.CABINET,
    CloudopsConfigColumns.COUNTER,
    CloudopsConfigColumns.U_POSITION,
    CloudopsConfigColumns.U_HEIGHT,
    CloudopsConfigColumns.SERIAL_NUMBER,
)


# Phase 2b 在线编辑：按 Sheet 限定可编辑列（editable=None 表示全部列）
MANUAL_EDIT_SPEC: dict[str, dict[str, object]] = {
    CloudopsConfigSheets.SERVER_INFO: {
        "primary_key": CloudopsConfigColumns.DEVICE_ID,
        "display": [
            CloudopsConfigColumns.DEVICE_ID,
            CloudopsConfigColumns.IBMC_IP_ADDRESS,
            CloudopsConfigColumns.HOST_NAME,
        ],
        "editable": [
            CloudopsConfigColumns.IBMC_USERNAME,
            CloudopsConfigColumns.IBMC_PASSWORD,
        ],
    },
    CloudopsConfigSheets.SWITCH_INFO: {
        "primary_key": CloudopsConfigColumns.DEVICE_ID,
        "display": [
            CloudopsConfigColumns.DEVICE_ID,
            CloudopsConfigColumns.DEVICE_NAME,
            CloudopsConfigColumns.DEVICE_IP,
        ],
        "editable": [
            CloudopsConfigColumns.MANAGEMENT_USERNAME_SWITCH,
            CloudopsConfigColumns.PASSWORD,
        ],
    },
    CloudopsConfigSheets.OS_CONFIG_INFO: {
        "primary_key": None,
        "display": None,
        "editable": None,
    },
}


class LldSheets:
    DEVICE_LOCATION_INFO = "设备位置信息"
    SERVER_OUT_OF_BAND_MANAGEMENT_ADDRESS = "计算带外管理地址"
    LQ_OUT_OF_BAND_MANAGEMENT_ADDRESS = "灵衢带外管理地址"
    COMPUTE_NODE_PARAMETER_PLANE_ADDRESS = "计算参数面地址_{}"
    COMPUTE_NODE_SERVICE_PLANE_ADDRESS = "计算业务面地址规划"
    SERVER_MANAGEMENT_ADDRESS = "计算管理面地址规划"
    SERVER_MANAGEMENT_CONTROL_ADDRESS = "计算管存面地址规划"


class LldColumns:
    DEVICE_NAME = "设备名称"
    DATA_CENTER = "所属机房"
    RACK = "所属机柜"
    PARAMETER_GATEWAY_A2 = "参数面IP网关"
    PARAMETER_SUBNET_MASK = "参数面掩码"
    PARAMETER_ID_A2 = "参数面NPU{}"
    PARAMETER_GATEWAY_A3 = "参数面网关"
    PARAMETER_ID_A3 = "参数面地址"
    MANAGEMENT_IP = "带外管理地址"
    MANAGEMENT_SUBNET_MASK = "带外管理掩码"
    MANAGEMENT_GATEWAY = "带外管理网关"
    START_U = "安装起始U位"
    SUPER_NODE_ID = "超节点ID"
    SWITCH_ID = "计算节点ID"
    SUPER_NODE_SCALE = "超节点规模"
    START_INFO = "起始端信息"
    END_INFO = "目的端信息"
    DEVICE_NAME_CONNECTION = "设备命名"
    INTERFACE_INFO = "接口信息"
    SERVICE_GATEWAY = "计算业务面网关"
    SERVICE_ADDRESS = "计算业务面地址"
    SERVICE_SUBNET_MASK = "计算业务面掩码"
    SERVER_MANAGEMENT_GATEWAY = "计算管理面网关"
    SERVER_MANAGEMENT_ADDRESS = "计算管理面地址"
    SERVER_MANAGEMENT_SUBNET_MASK = "计算管理面掩码"
    MANAGEMENT_CONTROL_GATEWAY = "计算管存面网关"
    MANAGEMENT_CONTROL_ADDRESS = "计算管存面地址"
    MANAGEMENT_CONTROL_SUBNET_MASK = "计算管存面掩码"
