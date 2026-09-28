"""核心分配规则测试。"""

from __future__ import annotations

import unittest

from plate_layout.config import ConfigError, parse_config
from plate_layout.planner import LayoutError, build_layout
from plate_layout.samples import Sample


def make_config(max_plates=5, control_wells=(), disabled_wells=()):
    return parse_config(
        {
            "max_plates": max_plates,
            "control_wells": list(control_wells),
            "disabled_wells": list(disabled_wells),
        }
    )


def make_sample(sample_id, group, replicates, row=2):
    return Sample(sample_id, group, replicates, row)


class PlannerTest(unittest.TestCase):
    def test_single_plate_row_major_order(self):
        config = make_config()
        samples = [make_sample("S1", "G1", 3)]
        result = build_layout(samples, config)
        self.assertEqual(result.plate_count, 1)
        wells = [w for w in result.plates[0].wells if w.sample_id == "S1"]
        self.assertEqual([w.well for w in wells], ["A1", "A2", "A3"])
        self.assertEqual([w.replicate for w in wells], [1, 2, 3])
        self.assertEqual(result.plates[0].counts["sample"], 3)
        self.assertEqual(result.plates[0].counts["empty"], 93)

    def test_group_then_id_sort_and_input_order_stability(self):
        config = make_config()
        ordered = [
            make_sample("B", "g2", 1),
            make_sample("a", "g1", 1),
            make_sample("C", "g1", 1),
        ]
        shuffled = [ordered[2], ordered[0], ordered[1]]
        r1 = build_layout(ordered, config)
        r2 = build_layout(shuffled, config)
        ids_r1 = [s.sample_id for s in r1.samples]
        ids_r2 = [s.sample_id for s in r2.samples]
        self.assertEqual(ids_r1, ["C", "a", "B"])
        self.assertEqual(ids_r1, ids_r2)
        wells_1 = [w.well for w in r1.plates[0].wells if w.kind == "sample"]
        wells_2 = [w.well for w in r2.plates[0].wells if w.kind == "sample"]
        self.assertEqual(wells_1, ["A1", "A2", "A3"])
        self.assertEqual(wells_1, wells_2)

    def test_replicates_not_split_across_plates(self):
        config = make_config(max_plates=3)
        samples = [
            make_sample("S1", "g", 90),
            make_sample("S2", "g", 10),
        ]
        result = build_layout(samples, config)
        self.assertEqual(result.plate_count, 2)
        s2 = next(s for s in result.samples if s.sample_id == "S2")
        self.assertTrue(all(coord["plate"] == 2 for coord in s2.coordinates))
        self.assertEqual([w.well for w in result.plates[0].wells if w.sample_id == "S2"], [])
        self.assertEqual(
            [coord["well"] for coord in s2.coordinates],
            [f"A{i}" for i in range(1, 11)],
        )

    def test_smallest_fitting_plate_is_chosen(self):
        config = make_config(max_plates=3)
        samples = [
            make_sample("S1", "g", 95),
            make_sample("S2", "g", 5),
            make_sample("S3", "g", 6),
        ]
        result = build_layout(samples, config)
        plates = {s.sample_id: s.coordinates[0]["plate"] for s in result.samples}
        self.assertEqual(plates["S1"], 1)
        self.assertEqual(plates["S2"], 2)
        self.assertEqual(plates["S3"], 2)

    def test_reserved_wells_skipped(self):
        config = make_config(control_wells=["A1"], disabled_wells=["A2"])
        result = build_layout([make_sample("S1", "g", 2)], config)
        plate = result.plates[0]
        self.assertEqual(plate.counts["control"], 1)
        self.assertEqual(plate.counts["disabled"], 1)
        sample_wells = [w.well for w in plate.wells if w.kind == "sample"]
        self.assertEqual(sample_wells, ["A3", "A4"])

    def test_sample_exceeds_single_plate_capacity(self):
        config = make_config(control_wells=["A1"], disabled_wells=["A2"], max_plates=3)
        with self.assertRaisesRegex(LayoutError, "S1"):
            build_layout([make_sample("S1", "g", 95)], config)

    def test_plate_limit_exceeded(self):
        config = make_config(max_plates=2)
        samples = [make_sample(f"S{i}", "g", 90) for i in range(1, 4)]
        with self.assertRaisesRegex(LayoutError, "板数超过上限 2"):
            build_layout(samples, config)

    def test_counts_add_up_to_96(self):
        config = make_config(max_plates=3, control_wells=["H12"], disabled_wells=["A1"])
        samples = [
            make_sample("S1", "g", 90),
            make_sample("S2", "g", 5),
        ]
        result = build_layout(samples, config)
        for plate in result.plates:
            self.assertEqual(sum(plate.counts.values()), 96)
            self.assertEqual(len(plate.wells), 96)
        total = sum(plate.counts["sample"] for plate in result.plates)
        self.assertEqual(total, 95)

    def test_columns_sorted_numerically(self):
        config = make_config()
        result = build_layout([make_sample("S1", "g", 14)], config)
        wells = [w.well for w in result.plates[0].wells if w.sample_id == "S1"]
        self.assertEqual(wells[-2:], ["B1", "B2"])


class ConfigValidationTest(unittest.TestCase):
    def test_invalid_well_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config({"max_plates": 1, "control_wells": ["I1"], "disabled_wells": []})

    def test_duplicate_well_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config({"max_plates": 1, "control_wells": ["A1", "a1"], "disabled_wells": []})

    def test_control_disabled_conflict_rejected(self):
        with self.assertRaisesRegex(ConfigError, "A1"):
            parse_config({"max_plates": 1, "control_wells": ["A1"], "disabled_wells": ["A1"]})

    def test_bad_max_plates_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config({"max_plates": 0, "control_wells": [], "disabled_wells": []})
        with self.assertRaises(ConfigError):
            parse_config({"max_plates": True, "control_wells": [], "disabled_wells": []})


if __name__ == "__main__":
    unittest.main()
