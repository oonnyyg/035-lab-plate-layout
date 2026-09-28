"""Tests for CSV validation, deterministic output and serialization."""

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
    load_samples,
    plan_layout,
    write_outputs,
)
from plate_layout.models import PlateConfig, Sample  # noqa: E402


def write_csv(tmp, rows, header="sample_id,group,replicates\n"):
    path = os.path.join(tmp, "samples.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(header)
        f.writelines(rows)
    return path


class TestCsvValidation(unittest.TestCase):
    def test_empty_file_and_empty_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.csv")
            open(path, "w").close()
            with self.assertRaises(LayoutError):
                load_samples(path)
            path2 = write_csv(tmp, [], )
            with self.assertRaisesRegex(LayoutError, "no sample records"):
                load_samples(path2)

    def test_missing_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(tmp, ["S1,g1,1\n"], header="sample_id,group\n")
            with self.assertRaisesRegex(LayoutError, "replicates"):
                load_samples(path)

    def test_errors_pinpoint_record(self):
        cases = {
            "S1,g1,1\n,g2,2\n": "record 2",
            "S1,,1\n": "record 1",
            "S1,g1,\n": "record 1",
            "S1,g1,0\n": "record 1",
            "S1,g1,-3\n": "record 1",
            "S1,g1,two\n": "record 1",
            "S1,g1,1\nS1,g2,2\n": "record 2",
        }
        for content, needle in cases.items():
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as tmp:
                    path = write_csv(tmp, [content])
                    with self.assertRaisesRegex(LayoutError, needle):
                        load_samples(path)


class TestStabilityAndOutput(unittest.TestCase):
    def setUp(self):
        self.config = PlateConfig(
            4, frozenset({"A1", "H12"}), frozenset({"A2", "G6"})
        )
        rows = [("S7", "zeta", 12), ("S1", "alpha", 3), ("S2", "alpha", 90),
                ("S3", "beta", 40), ("S9", "alpha", 40)]
        self.samples = [Sample(sid, grp, rep, i + 1)
                        for i, (sid, grp, rep) in enumerate(rows)]

    def test_shuffled_input_gives_identical_layout(self):
        first = plan_layout(self.samples, self.config)
        shuffled = [self.samples[i] for i in (4, 0, 2, 1, 3)]
        second = plan_layout(shuffled, self.config)
        self.assertEqual(
            [(c.plate, c.well, c.content_type, c.sample_id, c.replicate)
             for plate in first.plates for c in plate],
            [(c.plate, c.well, c.content_type, c.sample_id, c.replicate)
             for plate in second.plates for c in plate],
        )

    def test_repeated_runs_byte_stable_and_counts_check_out(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            layout1 = plan_layout(self.samples, self.config)
            csv1, json1 = write_outputs(layout1, d1)
            layout2 = plan_layout(self.samples, self.config)
            csv2, json2 = write_outputs(layout2, d2)
            with open(csv1, "rb") as a, open(csv2, "rb") as b:
                self.assertEqual(a.read(), b.read())
            with open(json1, "rb") as a, open(json2, "rb") as b:
                self.assertEqual(a.read(), b.read())

            with open(csv1, encoding="utf-8", newline="") as f:
                records = list(csv.DictReader(f))
            self.assertEqual(len(records), 96 * len(layout1.plates))
            plates = {int(r["plate"]) for r in records}
            self.assertEqual(plates, set(range(1, len(plates) + 1)))
            for plate_no in sorted(plates):
                rows = [r for r in records if int(r["plate"]) == plate_no]
                self.assertEqual(len(rows), 96)
                counts = {k: 0 for k in ("sample", "control", "disabled", "empty")}
                for r in rows:
                    counts[r["content_type"]] += 1
                self.assertEqual(counts["control"], 2)
                self.assertEqual(counts["disabled"], 2)

            with open(json1, encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(summary["plates_used"], len(plates))
            # cross-check summary counts against CSV
            for entry in summary["plates"]:
                rows = [r for r in records if int(r["plate"]) == entry["plate"]]
                for kind in ("sample", "control", "disabled", "empty"):
                    self.assertEqual(entry[kind],
                                     sum(r["content_type"] == kind for r in rows))
                self.assertEqual(
                    sum(entry[k] for k in ("sample", "control", "disabled", "empty")),
                    96,
                )
            # every sample coordinate matches a sample CSV row with seq number
            for sample_entry in summary["samples"]:
                self.assertEqual(
                    len(sample_entry["assigned_wells"]), sample_entry["replicates"])
                coords = {(w["plate"], w["well"])
                          for w in sample_entry["assigned_wells"]}
                self.assertEqual(len(coords), sample_entry["replicates"])
                for plate_no, well in coords:
                    match = [r for r in records
                             if int(r["plate"]) == plate_no and r["well"] == well]
                    self.assertEqual(match[0]["sample_id"], sample_entry["sample_id"])

    def test_failed_planning_does_not_overwrite_existing_results(self):
        with tempfile.TemporaryDirectory() as out_dir:
            good = plan_layout(self.samples, self.config)
            csv_path, json_path = write_outputs(good, out_dir)
            with open(csv_path, "rb") as f:
                before = f.read()
            # oversized sample relative to 4 reserved wells -> 92 usable
            bad_samples = [Sample("BIG", "g", 93, 1)]
            with self.assertRaises(LayoutError):
                plan_layout(bad_samples, self.config)
            with open(csv_path, "rb") as f:
                self.assertEqual(f.read(), before)
            with open(json_path, "rb") as f:
                json_before = f.read()
            # simulate the real CLI flow: plan first, write only on success
            try:
                write_outputs(plan_layout(bad_samples, self.config), out_dir)
            except LayoutError:
                pass
            with open(csv_path, "rb") as f:
                self.assertEqual(f.read(), before)
            with open(json_path, "rb") as f:
                self.assertEqual(f.read(), json_before)


if __name__ == "__main__":
    unittest.main()
