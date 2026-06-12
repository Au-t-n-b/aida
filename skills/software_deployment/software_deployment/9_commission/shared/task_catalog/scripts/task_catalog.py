# -*- coding: utf-8 -*-
"""下发调测 · 命令注册表（命令名 → 规格）。三模块所有命令在此唯一登记。

加新命令 = 在 TASKS 增加一条（声明），无需改 driver / task_runner。
字段：
    task_type     结果存储与 results/index 的类型键
    work_stage    Toolkit X-WORKSTAGE
    module        所属模块：init_install | subsystem_test | cluster_test
    device_kind   server（设备底表）| switch（完整配置《交换机信息》）
    device_field  设备 IP 放进 execute body 的哪个字段
    labels        语义识别用：命令同义词（LLM/路由匹配）
    config_dir    命令目录名（commands/<module>/<config_dir>/config）
    query_step    query body 的 stepName（部分命令需要）
    omit_task_name  True=下发不传 taskName（os_install/ascend_install）
    poll_mode     轮询模式：""=默认 dict；"ascend_multi_step"=昇腾多阶段
    poll_finished_rule  轮询完成规则（lq_config_check / report_end_only）
    create_mode   下发模式：json | multipart_ztp
    export_format / export_suffix  报告扩展名（xlsx/zip）
    post_poll_hook / post_export_hook / report_parser  灵衢命令扩展
    require_cloudops_params / params_sheet  xlsx 门禁与 templateId
    implemented   False=留位（仅声明，未接模板/未测）
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TaskSpec:
    task_type: str
    work_stage: str
    module: str
    labels: tuple[str, ...]
    config_dir: str
    device_field: str = "serviceDeviceIds"
    device_kind: str = "server"
    execute_template: str = "execute.json"
    query_template: str = "query.json"
    poll_max: int = 60
    poll_interval_s: int = 5
    report_wait_s: int = 60
    omit_task_name: bool = False
    poll_mode: str = ""  # ascend_multi_step | prbs_multi_step | traffic_array | hccl_count | cluster_train
    export_mode: str = ""  # ""=标准 ReportExport；health_report_list=先 ReportQuery 再带 reportList
    export_suffix: str = ""  # 非空时报告扩展名（如 xlsx）
    implemented: bool = False
    post_poll_hook: str = ""
    post_export_hook: str = ""
    report_parser: str = ""
    result_message: str = ""
    poll_finished_rule: str = ""
    create_mode: str = "json"
    skip_env_prep: bool = False
    export_format: str = "zip"
    require_cloudops_params: bool = False
    params_sheet: str = ""


def _spec(**kw) -> TaskSpec:
    return TaskSpec(**kw)


TASKS: dict[str, TaskSpec] = {
    # ── 9 初始化与软件安装（init_install）────────────────────────────
    "connection": _spec(
        task_type="connection", work_stage="connectionCheck", module="init_install",
        labels=("服务器连线检查", "连线检查", "connection"),
        config_dir="connection", device_kind="server", device_field="serviceDeviceIds",
        implemented=True,
    ),
    "lq_connection": _spec(
        task_type="lq_connection", work_stage="lqConnectionCheck", module="init_install",
        labels=("灵衢连线检查", "灵衢连线", "灵衢链路检查", "lq连线检查", "lq_connection"),
        config_dir="lq_connection", device_kind="switch", device_field="switchesDeviceIds",
        implemented=True,
    ),
    "lq_config_check": _spec(
        task_type="lq_config_check", work_stage="lqConfigCheck", module="init_install",
        labels=("灵衢配置检查", "灵衢配置", "ZTP配置检查", "lq_config_check"),
        config_dir="lq_config_check",
        device_kind="switch", device_field="deviceIds",
        create_mode="multipart_ztp",
        poll_finished_rule="lq_config_check",
        skip_env_prep=True,
        export_format="xlsx",
        report_parser="lq_config_check_report",
        post_poll_hook="paginate_node_results",
        result_message="markdown",
        poll_max=250,
        poll_interval_s=30,
        implemented=True,
    ),
    "lq_health_check": _spec(
        task_type="lq_health_check",
        work_stage="lqClusterHealthCheck",
        module="init_install",
        labels=("灵衢健康检查", "灵衢交换机健康检查", "lq_health_check"),
        config_dir="lq_health_check",
        device_kind="switch",
        device_field="deviceIds",
        poll_max=250,
        poll_interval_s=30,
        poll_finished_rule="report_end_only",
        require_cloudops_params=True,
        params_sheet="灵衢健康检查",
        post_poll_hook="check_all_devices_failed",
        report_parser="lq_health_check_report",
        result_message="markdown",
        implemented=True,
    ),
    "hccs_weak_light": _spec(
        task_type="hccs_weak_light", work_stage="lqWeakLightCheck", module="init_install",
        labels=(
            "灵衢光链路检查", "灵衢光链路", "灵衢弱光",
            "hccs光链路", "hccs_weak_light",
        ),
        config_dir="hccs_weak_light",
        device_kind="switch", device_field="switchesDeviceIds",
        post_poll_hook="collect_switch_info",
        post_export_hook="merge_collect_xlsx",
        report_parser="hccs_weak_light_report",
        result_message="dual",
        implemented=True,
    ),
    "os_install": _spec(
        task_type="os_install", work_stage="osInstall", module="init_install",
        labels=("服务器OS安装", "OS安装", "os_install"),
        config_dir="os_install", device_field="deviceIds", omit_task_name=True,
        implemented=True,
    ),
    "ascend_install": _spec(
        task_type="ascend_install", work_stage="ascendInstall", module="init_install",
        labels=("服务器昇腾软件安装", "昇腾软件安装", "昇腾安装", "ascend_install"),
        config_dir="ascend_install", device_field="deviceIds", omit_task_name=True,
        poll_mode="ascend_multi_step", poll_max=120, poll_interval_s=30,
        implemented=True,
    ),
    # CloudOps 图1「服务器健康检查」；Agent 无 handler/params（见 server_health_check/SKILL.md）
    "server_health_check": _spec(
        task_type="server_health_check", work_stage="", module="init_install",
        labels=("服务器健康检查", "执行健康检查", "server_health_check"),
        config_dir="server_health_check", device_field="deviceIds",
    ),
    "cluster_health_check": _spec(
        task_type="cluster_health_check", work_stage="clusterHealthCheck", module="init_install",
        labels=("集群健康检查", "cluster_health_check"),
        config_dir="cluster_health_check", device_field="serviceDeviceIds",
        export_mode="health_report_list",
        implemented=True,
    ),
    "weak_light": _spec(
        task_type="weak_light", work_stage="weakLightCheck", module="init_install",
        labels=("服务器弱光检查", "弱光检查", "weak_light"),
        config_dir="weak_light", device_field="serverDeviceIds",
        implemented=True,
    ),
    # ── 10 子系统测试（subsystem_test）──────────────────────────────
    "lq_prbs_test": _spec(
        task_type="lq_prbs_test", work_stage="prbsStressTest", module="subsystem_test",
        labels=("灵衢PRBS测试", "灵衢PRBS压测", "PRBS测试", "lq_prbs_test"),
        config_dir="lq_prbs_test", device_kind="switch", device_field="deviceIds",
        poll_mode="prbs_multi_step", poll_max=3000, poll_interval_s=60,
        implemented=True,
    ),
    "burn_test": _spec(
        task_type="burn_test", work_stage="burnTest", module="subsystem_test",
        labels=("计算硬件压测", "硬件压测", "SP压测", "burn_test"),
        config_dir="burn_test", device_field="nodeList",
        poll_max=120, poll_interval_s=30,
        implemented=True,
    ),
    "single_comprehensive": _spec(
        task_type="single_comprehensive", work_stage="singleComprehensiveDetection",
        module="subsystem_test",
        labels=("单机综合测试", "单机综合检测", "single_comprehensive"),
        config_dir="single_comprehensive", device_field="deviceIds",
        implemented=True,
    ),
    "single_model_test": _spec(
        task_type="single_model_test", work_stage="singleTrainingTask", module="subsystem_test",
        labels=("单机模型测试", "单机训练测试", "single_model_test"),
        config_dir="single_model_test", device_field="nodeList",
        implemented=True,
    ),
    "traffic_test": _spec(
        task_type="traffic_test", work_stage="trafficTest", module="subsystem_test",
        labels=("打流测试", "灵衢总线打流测试", "traffic_test"),
        config_dir="traffic_test", device_field="deviceIds",
        poll_mode="traffic_array", export_suffix="xlsx",
        implemented=True,
    ),
    "hccl_test_single_pod": _spec(
        task_type="hccl_test_single_pod", work_stage="hcclTestTask", module="subsystem_test",
        labels=("集群通信配置测试-单POD", "集群通信配置测试-单Pod", "HCCL单POD", "hccl_test_single_pod"),
        config_dir="hccl_test_single_pod", device_field="nodeList",
        poll_mode="hccl_count", report_wait_s=120,
        implemented=True,
    ),
    "cluster_train_single_pod": _spec(
        task_type="cluster_train_single_pod", work_stage="clusterTrainingTask", module="subsystem_test",
        labels=("集群训练测试-单POD", "集群训练测试-单Pod", "集群系统集成测试-单POD", "cluster_train_single_pod"),
        config_dir="cluster_train_single_pod", device_field="nodeList",
        poll_mode="cluster_train", report_wait_s=120,
        implemented=True,
    ),
    "cluster_infer_single_pod": _spec(
        task_type="cluster_infer_single_pod", work_stage="clusterInferTask", module="subsystem_test",
        labels=("集群推理测试-单POD", "集群推理测试-单Pod", "cluster_infer_single_pod"),
        config_dir="cluster_infer_single_pod", device_field="nodeList",
        poll_mode="cluster_train", report_wait_s=120,
        implemented=True,
    ),
    # Agent 仅有计划活动名 STORAGE_SUBSYSTEM_TEST，无 handler/params → 留位
    "storage_subsystem_test": _spec(
        task_type="storage_subsystem_test", work_stage="", module="subsystem_test",
        labels=("存储子系统测试", "存储子系统验证", "storage_subsystem_test"),
        config_dir="storage_subsystem_test", device_kind="storage", device_field="deviceIds",
    ),
    # Agent 仅有计划活动名 NETWORK_SUBSYSTEM_TEST，无 handler/params → 留位
    "network_subsystem_test": _spec(
        task_type="network_subsystem_test", work_stage="", module="subsystem_test",
        labels=("网络子系统测试", "网络子系统验证", "network_subsystem_test"),
        config_dir="network_subsystem_test", device_kind="switch", device_field="switchesDeviceIds",
    ),
    # ── 11 集群系统测试（cluster_test）──────────────────────────────
    "hccl_test": _spec(
        task_type="hccl_test", work_stage="hcclTestTask", module="cluster_test",
        labels=("集合通信测试",), config_dir="hccl_test", device_field="nodeList",
        poll_mode="hccl_count", report_wait_s=120,
        implemented=True,
    ),
    "cluster_model_test": _spec(
        task_type="cluster_model_test", work_stage="clusterTrainingTask", module="cluster_test",
        labels=("集群模型测试",), config_dir="cluster_model_test", device_field="nodeList",
        poll_mode="cluster_train", report_wait_s=120,
        implemented=True,
    ),
}

MODULES = ("init_install", "subsystem_test", "cluster_test")
MODULE_TITLES = {
    "init_install": "初始化与软件安装",
    "subsystem_test": "子系统测试",
    "cluster_test": "集群系统测试",
}


def resolve_task(name_or_type: str) -> TaskSpec | None:
    key = str(name_or_type or "").strip()
    if not key:
        return None
    if key in TASKS:
        return TASKS[key]
    for spec in TASKS.values():
        if key in spec.labels:
            return spec
    # 宽松匹配：命令文本包含某 label（取最长 label 命中，避免“连线检查”误吞“灵衢连线检查”）
    best: TaskSpec | None = None
    best_len = 0
    for spec in TASKS.values():
        for label in spec.labels:
            if label and label in key and len(label) > best_len:
                best, best_len = spec, len(label)
    return best


def tasks_by_module(module: str) -> list[TaskSpec]:
    return [s for s in TASKS.values() if s.module == module]
