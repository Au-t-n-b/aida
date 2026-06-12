"""LEAF–SPINE 互联规划（独立离线包）。"""
from oob_interconnect.pipeline import run_l2, run_l2_multi, run_l3, run_l3_multi

__all__ = ["run_l2", "run_l3", "run_l2_multi", "run_l3_multi", "__version__"]
__version__ = "1.2.0"
