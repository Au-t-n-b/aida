"""NCE planner tests without real project dependencies."""

from __future__ import annotations

import sys
import tempfile
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from nce_ip_rules import (  # noqa: E402
    allocate_floating_row,
    allocate_node_rows,
    enumerate_available_ips,
    parse_ip_pool_bounds,
    resolve_gateway,
)
from nce_planner import PlannerInputs, run_planner, write_nce_excel  # noqa: E402
from nce_resource_parser import parse_nce_resources  # noqa: E402


class TestNceIpRules(unittest.TestCase):
    def test_parse_ip_pool_bounds(self):
        start, end = parse_ip_pool_bounds("10.0.0.1-10.0.0.10")
        self.assertEqual(str(start), "10.0.0.1")
        self.assertEqual(str(end), "10.0.0.10")

    def test_gateway_start_position(self):
        gw = resolve_gateway(
            IPv4Network("10.0.0.0/24"),
            plane_name="NCEFB北向网络",
            gateway_position="网段起始位",
            gateway_address="",
        )
        self.assertEqual(gw, IPv4Address("10.0.0.1"))

    def test_internal_network_has_no_gateway(self):
        gw = resolve_gateway(
            IPv4Network("172.16.0.0/24"),
            plane_name="NCEFB内部通信网络",
            gateway_position="",
            gateway_address="",
        )
        self.assertIsNone(gw)

    def test_enumerate_ips_skips_gateway(self):
        usable = enumerate_available_ips(
            "10.0.0.1-10.0.0.5",
            24,
            lambda n: resolve_gateway(
                n,
                plane_name="NCEFB北向网络",
                gateway_position="网段起始位",
                gateway_address="",
            ),
        )
        self.assertEqual(usable[0], ("10.0.0.2", "10.0.0.1"))

    def test_allocate_nodes_increments_vlan(self):
        rows = allocate_node_rows(
            devices=["NCEFB-01", "NCEFB-02"],
            plane_name="NCEFB北向网络",
            ip_pool="10.0.0.1-10.0.0.10",
            mask="24",
            vlan_raw="100-101",
            gateway_position="网段起始位",
            gateway_address="",
            bond_name="bond0",
            bond_mode="mode1",
        )
        self.assertEqual([row.vlan for row in rows], ["100", "101"])
        self.assertEqual(rows[0].dest_net, "0.0.0.0")

    def test_allocate_floating_after_devices(self):
        row = allocate_floating_row(
            devices=["NCEFB-01", "NCEFB-02"],
            usage_name="北向浮动IP",
            display_plane_name="北向通信网络",
            source_plane_name="NCEFB北向网络",
            ip_pool="10.0.0.1-10.0.0.10",
            mask="24",
            vlan_raw="100-101",
            gateway_position="网段起始位",
            gateway_address="",
            bond_name="bond0",
            bond_mode="mode1",
        )
        self.assertEqual(row.ip, "10.0.0.4")
        self.assertEqual(row.vlan, "100")


class TestNcePlannerIntegration(unittest.TestCase):
    def _write_fixtures(self, tmp: Path) -> PlannerInputs:
        topology = tmp / "007.xlsx"
        resource = tmp / "resource.xlsx"
        topology_df = pd.DataFrame(
            {
                "设备命名": ["NCEFB-01", "NCEFB-02", "NCEFI-01", "LEAF-1"],
                "接入交换机": ["LEAF-1", "LEAF-1", "LEAF-2", "SPINE-1"],
            }
        )
        topology_df.to_excel(topology, sheet_name="计算带外管理面端口互联", index=False)

        resource_df = pd.DataFrame(
            [
                {
                    "网络平面": "NCEFB内部通信网络",
                    "地址池*": "172.16.0.1-172.16.0.20",
                    "最小规划掩码*": "24",
                    "VLAN*": "",
                    "网关位置*": "",
                },
                {
                    "网络平面": "NCEFB北向网络",
                    "地址池*": "10.0.0.1-10.0.0.20",
                    "最小规划掩码*": "24",
                    "VLAN*": "100-110",
                    "网关位置*": "网段起始位",
                },
                {
                    "网络平面": "NCEFI北向网络",
                    "地址池*": "10.0.1.1-10.0.1.20",
                    "最小规划掩码*": "24",
                    "VLAN*": "200-210",
                    "网关位置*": "网段起始位",
                },
            ]
        )
        resource_df.to_excel(resource, index=False)
        return PlannerInputs(topology_path=str(topology), resource_path=str(resource))

    def test_parse_resources(self):
        with tempfile.TemporaryDirectory() as td:
            inputs = self._write_fixtures(Path(td))
            planes = parse_nce_resources(pd.read_excel(inputs.resource_path))
            self.assertIn("NCEFB北向网络", planes)
            self.assertIn("NCEFI北向网络", planes)

    def test_end_to_end_minimal(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            inputs = self._write_fixtures(tmp)
            result = run_planner(inputs)
            self.assertEqual(result.fb_node_rows, 4)
            self.assertEqual(result.fb_floating_rows, 1)
            self.assertEqual(result.fi_node_rows, 1)
            self.assertEqual(result.fi_floating_rows, 1)
            out = write_nce_excel(result, str(tmp / "A3NCE部署规划.xlsx"))
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
