"""Reading and validation of the sample CSV and layout config JSON."""

from __future__ import annotations

import csv
import json

from .errors import LayoutError
from .models import PlateConfig, Sample
from .wells import parse_well

SAMPLE_FIELDS = ("sample_id", "group", "replicates")


def load_samples(path: str) -> list[Sample]:
    """Load and validate the sample CSV.

    Required header: ``sample_id,group,replicates`` (extras ignored).
    Every error references the CSV record (data row) number.
    """
    try:
        handle = open(path, "r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise LayoutError(f"cannot read sample CSV {path!r}: {exc}") from exc

    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise LayoutError(f"sample CSV {path!r} is empty")
        missing = [name for name in SAMPLE_FIELDS if name not in reader.fieldnames]
        if missing:
            raise LayoutError(
                f"sample CSV {path!r} missing required columns: "
                + ", ".join(missing)
            )

        samples: list[Sample] = []
        seen: set[str] = set()
        for index, raw in enumerate(reader, start=1):
            where = f"record {index} (CSV line {index + 1})"
            sid = (raw.get("sample_id") or "").strip()
            group = (raw.get("group") or "").strip()
            rep_raw = (raw.get("replicates") or "").strip()

            if not sid:
                raise LayoutError(f"{where}: sample_id is empty")
            if not group:
                raise LayoutError(f"{where} (sample {sid!r}): group is empty")
            if not rep_raw:
                raise LayoutError(f"{where} (sample {sid!r}): replicates is empty")
            if sid in seen:
                raise LayoutError(f"{where}: duplicate sample_id {sid!r}")

            try:
                replicates = int(rep_raw)
            except ValueError:
                raise LayoutError(
                    f"{where} (sample {sid!r}): replicates {rep_raw!r} "
                    "is not an integer"
                ) from None
            if replicates <= 0:
                raise LayoutError(
                    f"{where} (sample {sid!r}): replicates must be a "
                    f"positive integer, got {replicates}"
                )

            seen.add(sid)
            samples.append(Sample(sid, group, replicates, index))

    if not samples:
        raise LayoutError(f"sample CSV {path!r} contains no sample records")
    return samples


def _load_well_list(data: dict, key: str) -> frozenset[str]:
    raw = data.get(key, [])
    if not isinstance(raw, list) or not all(isinstance(w, str) for w in raw):
        raise LayoutError(f"config field {key!r} must be a list of well strings")
    wells: set[str] = set()
    for value in raw:
        try:
            row, col = parse_well(value)
        except ValueError as exc:
            raise LayoutError(f"config {key}: {exc}") from None
        label = f"{chr(ord('A') + row - 1)}{col}"
        if label in wells:
            raise LayoutError(
                f"config {key}: well {label} is listed more than once"
            )
        wells.add(label)
    return frozenset(wells)


def load_config(path: str) -> PlateConfig:
    """Load and validate the layout configuration JSON."""
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise LayoutError(f"cannot read config JSON {path!r}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LayoutError(f"config JSON {path!r} is invalid: {exc}") from exc

    if not isinstance(data, dict):
        raise LayoutError("config JSON root must be an object")

    max_plates = data.get("max_plates")
    if not isinstance(max_plates, int) or isinstance(max_plates, bool) or max_plates <= 0:
        raise LayoutError(
            f"config max_plates must be a positive integer, got {max_plates!r}"
        )

    controls = _load_well_list(data, "control_wells")
    disabled = _load_well_list(data, "disabled_wells")
    overlap = controls & disabled
    if overlap:
        raise LayoutError(
            "wells cannot be both control and disabled: "
            + ", ".join(sorted(overlap))
        )

    return PlateConfig(max_plates, controls, disabled)
