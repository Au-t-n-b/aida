"""主建设流水线步骤顺序（sdui / go_back 共用，避免循环 import）。"""

DI_STEP_NAMES: dict[str, str] = {
    "preflight":     "环境预检",
    "plan_receive":  "接收实施计划",
    "task_dispatch": "计划下发",
    "sn_generate":   "SN扫码表生成",
    "esn_fill":      "ESN信息填写",
}
DI_STEP_ORDER = list(DI_STEP_NAMES.keys())
