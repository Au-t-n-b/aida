#!/usr/bin/env python
# coding: utf-8
# 对齐 ztp_cfg_processor/src/data_struct.py

import sys


class CfgData:
    def __init__(
        self,
        deviceName,
        esn,
        location,
        level,
        methIP,
        gateway,
        subMask,
        switchId,
        bgpAs,
        loopback0,
        loopback1,
        loopback2,
        loopback3="",
        loopback4="",
        loopback5="",
        loopback6="",
    ):
        self.deviceName = deviceName
        self.esn = esn
        self.location = location
        self.methIP = methIP
        self.gateway = gateway
        self.subMask = subMask
        self.switchId = switchId
        self.bgpAs = bgpAs
        self.loopback0 = loopback0
        self.loopback1 = loopback1
        self.loopback2 = loopback2
        self.loopback3 = loopback3
        self.loopback4 = loopback4
        self.loopback5 = loopback5
        self.loopback6 = loopback6
        self.level = self.getLevel(level, deviceName)

    def getLevel(self, level, deviceName):
        if int(level) == 1:
            return "1"
        if int(level) == 2:
            return "2"
        if deviceName.find("LQ312-A-INT") != -1:
            return "1"
        if deviceName.find("LQ630-D-INT") != -1:
            return "2"
        if deviceName.find("LQJHB") != -1:
            return "1"
        if deviceName.find("LQLEAF-HW630") != -1:
            return "2"
        sys.stderr.write("[Error] 设备名不合法: %s\n" % deviceName)
        sys.exit(1)


class ElementInfo:
    def __init__(self, element="", elementNameInExcel=""):
        self.element = element
        self.elementNameInExcel = elementNameInExcel
        self.rowNum = 0
        self.columnNum = 0

    def setPos(self, rowNum=0, columnNum=0):
        self.rowNum = rowNum
        self.columnNum = columnNum
