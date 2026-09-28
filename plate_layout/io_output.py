"""Serialization of the planned layout to CSV and summary JSON."""

from __future__ import annotations

import csv
import json
import os

from .errors import LayoutError

LAYOUT_FILENAME = "plate_layout.csv"
SUMMARY_FILENAME = "plate_summary.json"


def _atomic_write(path: str, write_body) -> None:
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
            write_body(handle)
        os.replace(tmp_path, path)
    except OSError as exc:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise LayoutError(f"cannot write {path!r}: {exc}") from exc


def write_outputs(layout, output_dir: str) -> tuple[str, str]:
    """Write layout CSV and summary JSON; return their full paths.

    Files are written atomically (temp file + replace) only after planning
    succeeded, so a failed planning run never touches existing results.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        raise LayoutError(f"cannot create output dir {output_dir!r}: {exc}") from exc

    csv_path = os.path.join(output_dir, LAYOUT_FILENAME)
    json_path = os.path.join(output_dir, SUMMARY_FILENAME)

    def write_csv(handle) -> None:
        writer = csv.writer(handle)
        writer.writerow(
            ["plate", "well", "row", "column", "content_type",
             "sample_id", "group", "replicate"]
        )
        for cells in layout.plates:
            for cell in cells:
                writer.writerow([
                    cell.plate,
                    cell.well,
                    cell.row,
                    cell.column,
                    cell.content_type,
                    cell.sample_id,
                    cell.group,
                    "" if cell.replicate is None else cell.replicate,
                ])

    def write_json(handle) -> None:
        plates_summary = []
        for cells in layout.plates:
            counts = {"sample": 0, "control": 0, "disabled": 0, "empty": 0}
            for cell in cells:
                counts[cell.content_type] += 1
            plates_summary.append(
                {"plate": cells[0].plate, "total_wells": len(cells), **counts}
            )

        samples_summary = []
        for sample in layout.samples:
            coords = layout.coordinates[sample.sample_id]
            samples_summary.append({
                "sample_id": sample.sample_id,
                "group": sample.group,
                "replicates": sample.replicates,
                "assigned_wells": [
                    {"plate": plate, "well": well} for plate, well in coords
                ],
            })

        payload = {
            "max_plates": layout.config.max_plates,
            "plates_used": len(layout.plates),
            "control_wells": sorted(layout.config.control_wells),
            "disabled_wells": sorted(layout.config.disabled_wells),
            "plates": plates_summary,
            "samples": samples_summary,
        }
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    _atomic_write(csv_path, write_csv)
    try:
        _atomic_write(json_path, write_json)
    except LayoutError:
        raise
    return csv_path, json_path
