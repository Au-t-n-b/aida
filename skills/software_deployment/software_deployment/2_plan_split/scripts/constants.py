"""部署调测业务常量（源自 CPCIA deploymentandtest，随 skill 发布，不依赖外部仓库路径）。"""

from __future__ import annotations

# 项目场景（与 CPCIA ProjectScene 一致）
LIQUID_COOLING = "liquid_cooling"
TRAIN = "train"
INFER = "infer"
TRAIN_INFER = "train_infer"
SINGLE_POD = "single_pod"
MULTI_PODS = "multi_pods"

# 二级活动名（generate_task_map 用，须与 data/rules/second_to_third.json 的 key 一致）
SERVER_DEVICE_HARDWARE_INIT = "设备硬装初始化-智算服务器"
COMPUTE_SUBSYSTEM_TEST_SERVER = "计算子系统验证-智算服务器"
CLUSTER_SYSTEM_INTEGRATION_TEST = "集群系统集成测试"

# 场景叠加的三级活动名
RM211_UPDATE = "升级RM211固件"
SINGLE_TRAIN_TEST = "单机训练测试"
SINGLE_INFER = "单机推理测试"
CLUSTER_MODELS_TEST = "集群训练测试"
CLUSTER_INFER = "集群推理测试"
HCCL_TEST_SINGLE_POD = "集群通信配置测试-单Pod"
CLUSTER_MODELS_TEST_SINGLE_POD = "集群训练测试-单Pod"
CLUSTER_INFER_SINGLE_POD = "集群推理测试-单Pod"

server_liquid_cooling = [RM211_UPDATE]

SERVER_SINGLE_TRAIN = [SINGLE_TRAIN_TEST]
SERVER_SINGLE_INFER = [SINGLE_INFER]
SERVER_SINGLE_TRAIN_INFER = [SINGLE_TRAIN_TEST, SINGLE_INFER]
SERVER_CLUSTER_TRAIN = [CLUSTER_MODELS_TEST]
SERVER_CLUSTER_INFER = [CLUSTER_INFER]
SERVER_CLUSTER_TRAIN_INFER = [CLUSTER_MODELS_TEST, CLUSTER_INFER]

# 不区分设备类型的二级活动（CPCIA SecondActivity.NO_BELONG_DEVICE_TASKS）
NO_BELONG_DEVICE_TASKS = [
    "线序及光链路质量排查",
    "综合布线整改",
    "集群性能调优",
    "客户集群验收",
    "输出验收报告",
    "验收报告沟通",
    "移交",
    "验收测试",
]

# 远程工程师任务（与 CPCIA AGENT_ACTIVITIES 一致，用于责任人判定）
AGENT_ACTIVITIES = [
    "生成CloudOps初始配置文件",
    "补充CloudOps初始配置文件信息",
    "生成CloudOps完整配置文件",
    "计算服务器BMC IP地址配置",
    "计算服务器初始化",
    "计算硬件压测",
    "OS安装",
    "昇腾软件安装",
    "连线检查",
    "弱光检查",
    "灵衢配置检查",
    "灵衢连线检查",
    "灵衢光链路检查",
    "灵衢健康检查",
    "灵衢PRBS压测",
    "单机综合测试",
    "AI核压测",
    "单机训练测试",
    "单机推理测试",
    "集群健康检查",
    "集群训练测试",
    "集群推理测试",
    "集群通信配置测试",
    "集群通信配置测试-单Pod",
    "集群训练测试-单Pod",
    "集群推理测试-单Pod",
    "灵衢总线打流测试",
]

TASK_STATUS_PENDING_DISPATCHED = "待派发"
TASK_STATUS_UN_INIT = "UN_INIT"

# LLD 页签/列（CPCIA LldSheets / LldColumns / CloudopsConfigColumns）
SHEET_SERVER_OOB = "计算带外管理地址"
SHEET_LQ_OOB = "灵衢带外管理地址"
SHEET_STORAGE_OOB = "存储带外管理地址"
SHEET_HYPERPLANE = "超平面网络规划"
SHEET_DEVICE_LOCATION = "设备位置信息"

COL_DEVICE_NAME = "设备名称"
COL_MGMT_IP = "带外管理地址"
COL_SUPER_NODE = "超节点ID"
COL_SN_ESN = "ESN"
COL_DEVICE_ID = "设备ID*（主键）"

CC_DEVICE_NAME = "设备名称"
CC_SERIAL_NUMBER = "SN序列号"

DEVICE_SERVER = "智算"
DEVICE_LQ_SWITCH = "灵衢"
DEVICE_STORAGE = "存储"
DEVICE_SWITCH = "网络"
DEVICE_U_SERVER = "通算"
DEVICE_ALL = (DEVICE_U_SERVER, DEVICE_SERVER, DEVICE_LQ_SWITCH, DEVICE_SWITCH, DEVICE_STORAGE)
