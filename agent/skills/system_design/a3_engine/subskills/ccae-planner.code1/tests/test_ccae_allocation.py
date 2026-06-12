"""CCAE 分配规则单元测试（无真实项目 xlsx 依赖）。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from ipaddress import IPv4Address
from pathlib import Path

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ccae_ip_rules import (  # noqa: E402
    allocate_plane,
    container_dest_network,
    enumerate_usable_ips,
    parse_ip_pool_bounds,
    resolve_gateway,
)
from ccae_planner import PlannerInputs, run_planner, write_ccae_excel  # noqa: E402
from ccae_resource_parser import parse_plane_resources  # noqa: E402


class TestCcaeIpRules(unittest.TestCase):
    def test_parse_ip_pool(self):
        start, end = parse_ip_pool_bounds("192.168.0.1-192.168.0.20")
        self.assertEqual(str(start), "192.168.0.1")
        self.assertEqual(str(end), "192.168.0.20")

    def test_container_dest_network(self):
        self.assertIn("FULL-MESH", container_dest_network(2))
        self.assertIn("SPINE-LEAF", container_dest_network(4))

    def test_gateway_start_position(self):
        net = __import__("ipaddress").IPv4Network("192.168.0.0/24")
        gw = resolve_gateway(
            net,
            gateway_position="网段起始位",
            gateway_address="",
            allow_empty=False,
            plane_hint="test",
        )
        self.assertEqual(gw, IPv4Address("192.168.0.1"))

    def test_allocate_north_with_vip(self):
        spec = next(s for s in __import__("ccae_ip_rules").PLANE_SPECS if s.is_north)
        rows = allocate_plane(
            spec=spec,
            devices=["ccae-node1", "ccae-node2"],
            ip_pool="192.168.0.1-192.168.0.20",
            mask="24",
            vlan_raw="101",
            gateway_position="网段起始位",
            gateway_address="",
            occupied_ips=set(),
            reserved_ips=set(),
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].ip, "192.168.0.2")
        self.assertEqual(rows[2].is_vip, True)
        self.assertEqual(rows[2].device_or_usage, "北向网络浮动IP")
        self.assertEqual(rows[0].dest_net, "0.0.0.0")

    def test_oob_does_not_treat_available_as_reserved(self):
        """occupied 避让；available 列表不应在本实现中并入 reserved。"""
        reserved = {IPv4Address("192.168.1.10")}
        usable = enumerate_usable_ips(
            "192.168.1.1-192.168.1.15",
            24,
            lambda n: resolve_gateway(
                n,
                gateway_position="网段起始位",
                gateway_address="",
                allow_empty=False,
                plane_hint="oob",
            ),
            reserved,
        )
        self.assertIn(IPv4Address("192.168.1.2"), usable)
        self.assertNotIn(IPv4Address("192.168.1.10"), usable)


class TestCcaePlannerIntegration(unittest.TestCase):
    def _write_fixtures(self, tmp: Path) -> PlannerInputs:
        topo = tmp / "007.xlsx"
        res = tmp / "resource.xlsx"

        topo_df = pd.DataFrame(
            {
                "设备命名": ["CCAE-01", "CCAE-02", "LEAF-1"],
                "接入交换机": ["LEAF-1", "LEAF-1", "SPINE-1"],
            }
        )
        topo_df.to_excel(topo, sheet_name="计算带外管理面端口互联", index=False)

        res_df = pd.DataFrame(
            [
                {
                    "网络平面": "CCAE容器内部通信网络",
                    "地址池*": "172.17.0.1-172.17.0.30",
                    "最小规划掩码*": "24",
                    "VLAN*": "",
                    "网关位置*": "",
                },
                {
                    "网络平面": "CCAE北向网络",
                    "地址池*": "192.168.0.1-192.168.0.30",
                    "最小规划掩码*": "24",
                    "VLAN*": "100",
                    "网关位置*": "网段起始位",
                },
            ]
        )
        res_df.to_excel(res, index=False)

        return PlannerInputs(
            topology_path=str(topo),
            resource_path=str(res),
        )

    def test_end_to_end_minimal(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            inputs = self._write_fixtures(tmp)
            result = run_planner(inputs)
            self.assertEqual(len(result.module1), 4)
            self.assertEqual(len(result.module2), 3)
            out = write_ccae_excel(result, str(tmp / "out.xlsx"))
            self.assertTrue(out.is_file())

    def test_parse_plane_resources(self):
        with tempfile.TemporaryDirectory() as td:
            inputs = self._write_fixtures(Path(td))
            df = pd.read_excel(inputs.resource_path)
            planes = parse_plane_resources(df)
            self.assertIn("ccae_container_internal", planes)
            self.assertIn("ccae_northbound", planes)


if __name__ == "__main__":
    unittest.main()
