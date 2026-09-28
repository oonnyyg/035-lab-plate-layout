"""多板孔位分配规划。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import PlateConfig
from .samples import Sample
from .wells import all_wells


class LayoutError(ValueError):
    """规划失败（容量不足、板数超限等）。"""


@dataclass
class WellAssignment:
    """单个孔位的安排。"""

    plate: int
    well: str
    kind: str  # sample / control / disabled / empty
    sample_id: str | None = None
    group: str | None = None
    replicate: int | None = None


@dataclass
class SamplePlacement:
    """一个样本的全部孔位坐标。"""

    sample_id: str
    group: str
    replicates: int
    coordinates: list[dict[str, object]] = field(default_factory=list)


@dataclass
class PlateLayout:
    """一块板上 96 个孔的完整布局。"""

    plate: int
    wells: list[WellAssignment]
    counts: dict[str, int]


@dataclass
class LayoutResult:
    """整次规划的结果。"""

    plates: list[PlateLayout]
    samples: list[SamplePlacement]

    @property
    def plate_count(self) -> int:
        return len(self.plates)


def build_layout(samples: list[Sample], config: PlateConfig) -> LayoutResult:
    """按规则把样本重复孔安排到若干孔板上。

    顺序：先按分组、再按样本编号字典序排列样本；
    总是选择编号最小、剩余容量足够的已有板；
    已有板都放不下时才开新板（不保证板数最少）。
    任何样本无法安排时抛出 :class:`LayoutError`，不产生部分结果。
    """
    ordered = sorted(samples, key=lambda s: (s.group, s.sample_id))

    for sample in ordered:
        if sample.replicates > config.available_per_plate:
            raise LayoutError(
                f"样本 {sample.sample_id} 需要 {sample.replicates} 个重复孔，"
                f"超过单板可用容量 {config.available_per_plate}"
            )

    plates: list[list[WellAssignment]] = []
    free_counts: list[int] = []
    placements: dict[str, SamplePlacement] = {}

    def open_new_plate() -> int:
        plate_no = len(plates) + 1
        if plate_no > config.max_plates:
            raise LayoutError(f"所需板数超过上限 {config.max_plates}")
        wells: list[WellAssignment] = []
        for well in all_wells():
            if well in config.control_wells:
                kind = "control"
            elif well in config.disabled_wells:
                kind = "disabled"
            else:
                kind = "empty"
            wells.append(WellAssignment(plate=plate_no, well=well, kind=kind))
        plates.append(wells)
        free_counts.append(config.available_per_plate)
        return plate_no

    open_new_plate()

    for sample in ordered:
        target_plate = next(
            (idx for idx, free in enumerate(free_counts) if free >= sample.replicates),
            None,
        )
        if target_plate is None:
            target_plate = open_new_plate() - 1

        placement = SamplePlacement(
            sample_id=sample.sample_id,
            group=sample.group,
            replicates=sample.replicates,
        )
        remaining = sample.replicates
        for assignment in plates[target_plate]:
            if remaining == 0:
                break
            if assignment.kind != "empty":
                continue
            replicate_no = sample.replicates - remaining + 1
            assignment.kind = "sample"
            assignment.sample_id = sample.sample_id
            assignment.group = sample.group
            assignment.replicate = replicate_no
            placement.coordinates.append(
                {"plate": target_plate + 1, "well": assignment.well, "replicate": replicate_no}
            )
            remaining -= 1
        free_counts[target_plate] -= sample.replicates
        placements[sample.sample_id] = placement

    plate_layouts = [_finalize_plate(plate_no, wells) for plate_no, wells in enumerate(plates, start=1)]
    ordered_placements = [placements[sample.sample_id] for sample in ordered]
    return LayoutResult(plates=plate_layouts, samples=ordered_placements)


def _finalize_plate(plate_no: int, wells: list[WellAssignment]) -> PlateLayout:
    counts = {"sample": 0, "control": 0, "disabled": 0, "empty": 0}
    for assignment in wells:
        counts[assignment.kind] += 1
        assignment.plate = plate_no
    return PlateLayout(plate=plate_no, wells=wells, counts=counts)
