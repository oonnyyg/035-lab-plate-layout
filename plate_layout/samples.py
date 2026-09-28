"""样本 CSV 的加载与校验。"""

from __future__ import annotations

import csv
from dataclasses import dataclass


class SampleError(ValueError):
    """样本数据非法。"""


REQUIRED_COLUMNS = ("sample_id", "group", "replicates")


@dataclass(frozen=True)
class Sample:
    """一条样本记录。"""

    sample_id: str
    group: str
    replicates: int
    row_number: int


def load_samples(path: str) -> list[Sample]:
    """从 CSV 文件读取并校验样本记录。

    CSV 必须包含表头 ``sample_id,group,replicates``。
    任何坏行都会抛出 :class:`SampleError`，错误信息定位到记录行号。
    """
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
    except FileNotFoundError as exc:
        raise SampleError(f"样本文件不存在: {path}") from exc

    if not rows:
        raise SampleError("样本表为空：缺少表头与记录")

    header = [cell.strip() for cell in rows[0]]
    missing = [name for name in REQUIRED_COLUMNS if name not in header]
    if missing:
        raise SampleError(f"样本表缺少列: {', '.join(missing)}")

    index = {name: header.index(name) for name in REQUIRED_COLUMNS}
    records: list[Sample] = []
    seen_ids: set[str] = set()

    for offset, cells in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in cells):
            continue
        sample_id = cells[index["sample_id"]].strip() if len(cells) > index["sample_id"] else ""
        group = cells[index["group"]].strip() if len(cells) > index["group"] else ""
        replicates_text = cells[index["replicates"]].strip() if len(cells) > index["replicates"] else ""

        if not sample_id:
            raise SampleError(f"第 {offset} 行：样本编号缺失")
        if not group:
            raise SampleError(f"第 {offset} 行（样本 {sample_id}）：分组缺失")
        if sample_id in seen_ids:
            raise SampleError(f"第 {offset} 行（样本 {sample_id}）：样本编号重复")
        try:
            replicates = int(replicates_text)
        except ValueError as exc:
            raise SampleError(
                f"第 {offset} 行（样本 {sample_id}）：重复数必须为正整数，得到 {replicates_text!r}"
            ) from exc
        if replicates <= 0:
            raise SampleError(
                f"第 {offset} 行（样本 {sample_id}）：重复数必须为正整数，得到 {replicates}"
            )

        seen_ids.add(sample_id)
        records.append(Sample(sample_id, group, replicates, offset))

    if not records:
        raise SampleError("样本表为空：没有任何样本记录")

    return records
