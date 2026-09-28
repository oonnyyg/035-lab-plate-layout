"""Deterministic greedy placement of sample replicates onto plates."""

from __future__ import annotations

from .errors import LayoutError
from .models import PlannedLayout, Sample, WellCell
from .wells import all_wells


def plan_layout(samples: list[Sample], config) -> PlannedLayout:
    """Assign every replicate to wells and return the full layout.

    Samples are processed ordered by (group, sample_id) lexicographically.
    All replicates of one sample stay on the same plate. The plate with the
    smallest number that has enough free wells is chosen; a new plate is
    opened only when none of the existing plates can hold the sample.
    Wells are consumed row-major with numerically ordered columns.
    """
    ordered = sorted(samples, key=lambda s: (s.group, s.sample_id))

    usable = config.usable_per_plate
    for sample in ordered:
        if sample.replicates > usable:
            raise LayoutError(
                f"sample {sample.sample_id!r} (group {sample.group!r}) needs "
                f"{sample.replicates} wells but a plate only has {usable} "
                "usable wells"
            )

    # Each plate tracks reserved (control/disabled) and used (sample) wells.
    reserved: list[set[str]] = []
    used: list[set[str]] = []
    assignments: list[tuple[Sample, int, list[str]]] = []

    free_sequence = [w for w in all_wells()]

    def open_plate(owner: Sample) -> int:
        number = len(reserved) + 1
        if number > config.max_plates:
            raise LayoutError(
                f"sample {owner.sample_id!r} requires plate {number} but "
                f"max_plates is {config.max_plates}; planning failed"
            )
        reserved.append(set(config.control_wells) | set(config.disabled_wells))
        used.append(set())
        return number - 1

    for sample in ordered:
        target = None
        for index in range(len(used)):
            if usable - len(used[index]) >= sample.replicates:
                target = index
                break
        if target is None:
            target = open_plate(sample)

        occupied = reserved[target] | used[target]
        chosen = [w for w in free_sequence if w not in occupied][: sample.replicates]
        if len(chosen) < sample.replicates:
            raise LayoutError(
                f"internal error: plate {target + 1} could not provide "
                f"{sample.replicates} wells for sample {sample.sample_id!r}"
            )
        used[target].update(chosen)
        assignments.append((sample, target, chosen))

    return _build_result(config, ordered, reserved, used, assignments)


def _build_result(config, ordered, reserved, used, assignments) -> PlannedLayout:
    # sample_id -> (plate, wells)
    placement: dict[str, tuple[int, list[str]]] = {
        sample.sample_id: (plate_index, wells)
        for sample, plate_index, wells in assignments
    }

    plates: list[list[WellCell]] = []
    for plate_index, res_set in enumerate(reserved):
        cells: list[WellCell] = []
        used_set = used[plate_index]
        for well in all_wells():
            row_letter, col_text = well[0], well[1:]
            if well in config.control_wells:
                cells.append(
                    WellCell(plate_index + 1, well, row_letter, int(col_text),
                             "control")
                )
            elif well in config.disabled_wells:
                cells.append(
                    WellCell(plate_index + 1, well, row_letter, int(col_text),
                             "disabled")
                )
            elif well in used_set:
                owner = next(
                    sample
                    for sample, idx, wells in assignments
                    if idx == plate_index and well in wells
                )
                rep_index = placement[owner.sample_id][1].index(well) + 1
                cells.append(
                    WellCell(plate_index + 1, well, row_letter, int(col_text),
                             "sample", owner.sample_id, owner.group, rep_index)
                )
            else:
                cells.append(
                    WellCell(plate_index + 1, well, row_letter, int(col_text),
                             "empty")
                )
        plates.append(cells)

    coordinates = {
        sample.sample_id: [
            (placement[sample.sample_id][0] + 1, well)
            for well in placement[sample.sample_id][1]
        ]
        for sample in ordered
    }
    return PlannedLayout(config, ordered, plates, coordinates)


# Re-exported for callers using ``from plate_layout import write_outputs``.
from .io_output import write_outputs  # noqa: E402,F401
from .io_input import load_config, load_samples  # noqa: E402,F401
