#!/usr/bin/env python
# coding: utf-8

import configparser
from pathlib import Path


class Config:
    def __init__(self, conf_dir: Path | None = None):
        self.confElements: dict[str, str] = {}
        self.replaceLabel: dict[str, str] = {}

        if conf_dir is None:
            conf_dir = Path(__file__).resolve().parent.parent / "conf"
        config_file_path = conf_dir / "config.ini"
        if not config_file_path.is_file():
            raise FileNotFoundError(f"配置文件不存在: {config_file_path}")

        config = configparser.ConfigParser()
        config.read(config_file_path, encoding="UTF-8")

        for key in (
            "deviceName",
            "esn",
            "level",
            "methIP",
            "gateway",
            "switchId",
            "bgpAs",
            "roomName",
            "rackNum",
            "rackLocation",
            "loopback0",
            "loopback1",
            "loopback2",
            "loopback3",
            "loopback4",
            "loopback5",
            "loopback6",
        ):
            self.confElements[key] = config.get("confElements", key)

        for key in (
            "deviceName",
            "esn",
            "location",
            "methIP",
            "gateway",
            "subMask",
            "switchId",
            "switchLevel",
            "bgpAs",
            "loopback0",
            "loopback1",
            "loopback2",
            "loopback3",
            "loopback4",
            "loopback5",
            "loopback6",
        ):
            self.replaceLabel[key] = config.get("replaceLabel", key)
