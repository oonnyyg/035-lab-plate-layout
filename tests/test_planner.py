"""Unit tests for plate_layout (run with ``python -m unittest``)."""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plate_layout import (  # noqa: E402
    LayoutError,
    load_config,
    load_samples,
    plan_layout,
    write_outputs,
)
from plate_layout.models import PlateConfig, Sample  # noqa: E402


def make_config(max_plates=5, controls=(), disabled=()) -> PlateConfig:
    return PlateConfig(max_plates, frozenset(controls), frozenset(disabled))


def make_samples(specs) -> list[Sample]:
    # specs: list of (id, group, replicates); CSV line numbers start at 1
    return [Sample(sid, group, reps, i + 1) for i, (sid, group, reps) in enumerate(specs)]


def sample_cells(layout, plate_index, sample_id):
    return [c for c in layout.plates[plate_index]
            if c.content_type == "sample" and c.sample_id == sample_id]


class TestBasicPlacement(unittest.TestCase):
    def test_single_plate_row_major_and_replicate_numbers(self):
        layout = plan_layout(
            make_samples([("S2", "g2", 2), ("S1", "g1", 3)]),
            make_config(),
        )
        self.assertEqual(len(layout.plates), 1)
        s1 = sample_cells(layout, 0, "S1")
        s2 = sample_cells(layout, 0, "S2")
        # group order: g1 before g2
        self.assertEqual([c.well for c in s1], ["A1", "A2", "A3"])
        self.assertEqual([c.replicate for c in s1], [1, 2, 3])
        self.assertEqual([c.well for c in s2], ["A4", "A5"])

    def test_columns_sort_numerically(self):
        # fill first 11 columns of row A, then A12, then B1 ...
        layout = plan_layout(make_samples([("X", "g", 14)]), make_config())
        wells = [c.well for c in sample_cells(layout, 0, "X")]
        self.assertEqual(wells[:14], [f"A{i}" for i in range(1, 13)] + ["B1", "B2"])

    def test_each_plate_has_96_rows_and_reserved_wells(self):
        layout = plan_layout(
            make_samples([("X", "g", 5)]),
            make_config(controls=["A1"], disabled=["H12", "H11"]),
        )
        cells = layout.plates[0]
        self.assertEqual(len(cells), 96)
        by_well = {c.well: c for c in cells}
        self.assertEqual(by_well["A1"].content_type, "control")
        self.assertEqual(by_well["H12"].content_type, "disabled")
        self.assertEqual(by_well["H11"].content_type, "disabled")
        # samples must skip the reserved wells
        self.assertEqual(
            [c.well for c in sample_cells(layout, 0, "X")],
            ["A2", "A3", "A4", "A5", "A6"],
        )


class TestMultiPlate(unittest.TestCase):
    def test_opens_new_plate_only_when_needed_and_picks_smallest(self):
        # 2 control wells -> 94 usable per plate
        config = make_config(controls=["A1", "A2"])
        layout = plan_layout(
            make_samples([("A", "g", 88), ("B", "g", 5), ("C", "g", 87)]),
            config,
        )
        # A -> plate1 (6 left); B fits plate1 (1 left); C needs 87 -> plate2.
        self.assertEqual(len(layout.plates), 2)
        plates_of = {sid: [p for p, _ in layout.coordinates[sid]]
                     for sid in "ABC"}
        self.assertEqual(plates_of["A"], [1] * 88)
        self.assertEqual(plates_of["B"], [1] * 5)
        self.assertEqual(plates_of["C"], [2] * 87)

    def test_backfills_smallest_fitting_plate(self):
        config = make_config()
        layout = plan_layout(
            make_samples([("A", "g", 90), ("B", "g", 5), ("C", "g", 6)]),
            config,
        )
        # A -> plate1 (6 free); B needs 5, plate1 fits -> plate1
        # C needs 6, plate1 has 1 -> plate2
        plates_of = {sid: sorted({p for p, _ in layout.coordinates[sid]})
                     for sid in "ABC"}
        self.assertEqual(plates_of, {"A": [1], "B": [1], "C": [2]})

    def test_replicates_never_split_across_plates(self):
        layout = plan_layout(
            make_samples([("A", "g", 50), ("B", "g", 50), ("C", "g", 50)]),
            make_config(),
        )
        self.assertEqual(len(layout.plates), 3)
        for sid in ("A", "B", "C"):
            plate_numbers = {p for p, _ in layout.coordinates[sid]}
            self.assertEqual(len(plate_numbers), 1)
            self.assertEqual(len(layout.coordinates[sid]), 50)

    def test_new_plate_retains_reserved_wells(self):
        config = make_config(controls=["A1"], disabled=["B1"])
        layout = plan_layout(make_samples([("A", "g", 94), ("B", "g", 1)]), config)
        self.assertEqual(len(layout.plates), 2)
        p2 = {c.well: c for c in layout.plates[1]}
        self.assertEqual(p2["A1"].content_type, "control")
        self.assertEqual(p2["B1"].content_type, "disabled")
        self.assertEqual(p2["A2"].sample_id, "B")


class TestFailures(unittest.TestCase):
    def test_sample_exceeds_single_plate_capacity(self):
        with self.assertRaisesRegex(LayoutError, "S9"):
            plan_layout(make_samples([("S9", "g", 95)]),
                        make_config(controls=["A1", "A2"]))

    def test_too_many_plates_needed(self):
        with self.assertRaisesRegex(LayoutError, "max_plates is 1"):
            plan_layout(make_samples([("A", "g", 50), ("B", "g", 50)]),
                        make_config(max_plates=1))

    def test_invalid_config_wells_rejected(self):
        cfg = {"max_plates": 1, "control_wells": ["Z1"], "disabled_wells": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            with self.assertRaisesRegex(LayoutError, "invalid well"):
                load_config(path)

    def test_control_disabled_conflict_rejected(self):
        cfg = {"max_plates": 1, "control_wells": ["A1"],
               "disabled_wells": ["a1", "B2"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            with self.assertRaisesRegex(LayoutError, "both control and disabled"):
                load_config(path)

    def test_duplicate_well_in_one_list_rejected(self):
        cfg = {"max_plates": 1, "control_wells": ["A1", "a1"],
               "disabled_wells": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            with self.assertRaisesRegex(LayoutError, "more than once"):
                load_config(path)

    def test_bad_max_plates(self):
        for bad in (0, -1, "2", True, None):
            cfg = {"max_plates": bad, "control_wells": [], "disabled_wells": []}
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "c.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f)
                with self.assertRaises(LayoutError):
                    load_config(path)
