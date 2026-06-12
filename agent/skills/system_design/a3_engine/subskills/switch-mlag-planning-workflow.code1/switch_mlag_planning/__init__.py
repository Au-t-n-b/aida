#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Standalone switch MLAG planning package."""

from .planner import (
    DEFAULT_OUTPUT_FILE,
    DEFAULT_RESOURCE_FILE,
    DEFAULT_TOPOLOGY_FILE,
    DEFAULT_TEMP_FILE,
    NetResourceInfo,
    PlanningResult,
    allocate_connection,
    available_mlag_sheets,
    build_project_output_paths,
    find_consecutive_pair_in_pool,
    generate_switch_mlag,
    get_net_ni_resource_info,
    get_switch_data,
    resolve_config_sheet,
    switch_connect,
)

__all__ = [
    "DEFAULT_OUTPUT_FILE",
    "DEFAULT_RESOURCE_FILE",
    "DEFAULT_TOPOLOGY_FILE",
    "DEFAULT_TEMP_FILE",
    "NetResourceInfo",
    "PlanningResult",
    "allocate_connection",
    "available_mlag_sheets",
    "build_project_output_paths",
    "find_consecutive_pair_in_pool",
    "generate_switch_mlag",
    "get_net_ni_resource_info",
    "get_switch_data",
    "resolve_config_sheet",
    "switch_connect",
]
