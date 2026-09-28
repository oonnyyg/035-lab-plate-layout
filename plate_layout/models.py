"""Dataclasses describing samples, plate configuration and results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Sample:
    """One input sample record."""

    sample_id: str
    group: str
    replicates: int
    line_number: int  # 1-based line within the CSV data section


@dataclass(frozen=True)
class PlateConfig:
    """Shared configuration applied identically to every plate."""

    max_plates: int
    control_wells: frozenset[str]
    disabled_wells: frozenset[str]

    @property
    def usable_per_plate(self) -> int:
        return 96 - len(self.control_wells) - len(self.disabled_wells)


@dataclass
class WellCell:
    """Final content of a single well in the output layout."""

    plate: int
    well: str
    row: str
    column: int
    content_type: str  # sample | control | disabled | empty
    sample_id: str = ""
    group: str = ""
    replicate: int | None = None


@dataclass
class PlannedLayout:
    """Complete planning result ready to be serialized."""

    config: PlateConfig
    samples: list[Sample]
    plates: list[list[WellCell]] = field(default_factory=list)
    # sample_id -> list of (plate_number, well_label)
    coordinates: dict[str, list[tuple[int, str]]] = field(default_factory=dict)
