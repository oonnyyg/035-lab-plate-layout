"""布局 CSV 与汇总 JSON 的输出。"""

from __future__ import annotations

import csv
import io
import json
import os

from .config import PlateConfig
from .planner import LayoutResult, WellAssignment

PLATE_FILE_TEMPLATE = "plate_{plate:02d}.csv"
SUMMARY_FILE = "summary.json"


def plate_filename(plate: int) -> str:
    return PLATE_FILE_TEMPLATE.format(plate=plate)


def _render_plate_csv(wells: list[WellAssignment]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["plate", "well", "state", "sample_id", "group", "replicate"])
    for item in wells:
        if item.kind == "sample":
            state = "sample"
            values = [item.sample_id, item.group, item.replicate]
        elif item.kind == "control":
            state = "control"
            values = ["", "", ""]
        elif item.kind == "disabled":
            state = "disabled"
            values = ["", "", ""]
        else:
            state = "empty"
            values = ["", "", ""]
        writer.writerow([item.plate, item.well, state, *values])
    return buffer.getvalue()


def _render_summary(result: LayoutResult, config: PlateConfig) -> str:
    summary = {
        "plate_count": result.plate_count,
        "max_plates": config.max_plates,
        "control_wells": sorted(config.control_wells),
        "disabled_wells": sorted(config.disabled_wells),
        "plates": [
            {
                "plate": plate.plate,
                "file": plate_filename(plate.plate),
                "counts": plate.counts,
            }
            for plate in result.plates
        ],
        "samples": [
            {
                "sample_id": placement.sample_id,
                "group": placement.group,
                "replicates": placement.replicates,
                "coordinates": placement.coordinates,
            }
            for placement in result.samples
        ],
    }
    return json.dumps(summary, ensure_ascii=False, indent=2) + "\n"


def write_outputs(result: LayoutResult, config: PlateConfig, output_dir: str) -> list[str]:
    """把规划结果写入 ``output_dir``。

    失败时不写入任何文件、不覆盖已有结果：先在内存中生成全部内容，
    再确认目标文件均不存在后统一落盘。
    返回写入的文件路径列表。
    """
    contents: list[tuple[str, str]] = [
        (
            os.path.join(output_dir, plate_filename(plate.plate)),
            _render_plate_csv(plate.wells),
        )
        for plate in result.plates
    ]
    contents.append((os.path.join(output_dir, SUMMARY_FILE), _render_summary(result, config)))

    existing = [path for path, _ in contents if os.path.exists(path)]
    if existing:
        raise FileExistsError(f"输出文件已存在，拒绝覆盖: {', '.join(existing)}")

    os.makedirs(output_dir, exist_ok=True)
    written: list[str] = []
    try:
        for path, text in contents:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            written.append(path)
    except OSError:
        for path in written:
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    return written
