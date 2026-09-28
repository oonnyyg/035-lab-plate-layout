"""实验孔板排布工具。

读取样本 CSV 与布局配置 JSON，将样本重复孔安排到多块 8x12 孔板上，
避开对照孔与禁用孔，输出逐孔布局 CSV 与汇总 JSON。
"""

from .planner import LayoutError, build_layout

__all__ = ["LayoutError", "build_layout"]
__version__ = "0.1.0"
