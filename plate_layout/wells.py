"""孔板孔位的表示与工具函数。

每块板固定 8 行（A-H）12 列（1-12），共 96 孔，孔位命名如 ``A1``、``H12``。
"""

from __future__ import annotations

import re

ROWS = "ABCDEFGH"
COLS = range(1, 13)
ROW_COUNT = 8
COL_COUNT = 12
WELL_COUNT = ROW_COUNT * COL_COUNT

_WELL_RE = re.compile(r"^([A-H])([1-9]|1[0-2])$")


def parse_well(value: str) -> tuple[str, int]:
    """把 ``A1`` 形式的孔位解析为 ``(行字母, 列号)``。

    非法孔位（大小写不匹配、行列越界、多余空白等）抛出 :class:`ValueError`。
    """
    if not isinstance(value, str):
        raise ValueError(f"非法孔位: {value!r}")
    match = _WELL_RE.match(value)
    if match is None:
        raise ValueError(f"非法孔位: {value!r}")
    row = match.group(1)
    col = int(match.group(2))
    return row, col


def format_well(row: str, col: int) -> str:
    """由行字母与列号生成孔位名称。"""
    return f"{row}{col}"


def well_index(row: str, col: int) -> int:
    """返回先行后列顺序下的 0 基序号（行内列号按数值排序）。"""
    return ROWS.index(row) * COL_COUNT + (col - 1)


def all_wells() -> list[str]:
    """按先行后列、列号数值排序返回全部 96 个孔位。"""
    return [format_well(row, col) for row in ROWS for col in COLS]
