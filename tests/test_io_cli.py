"""样本加载、输出写入与 CLI 端到端测试。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from plate_layout.cli import main
from plate_layout.config import parse_config
from plate_layout.planner import build_layout
from plate_layout.samples import SampleError, load_samples
from plate_layout.writer import SUMMARY_FILE, plate_filename, write_outputs


def write(path, content):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)


SAMPLE_CSV = (
    "sample_id,group,replicates\n"
    "S2,g2,2\n"
    "S1,g1,3\n"
)


class SampleLoadingTest(unittest.TestCase):
    def test_load_valid_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "samples.csv")
            write(path, SAMPLE_CSV)
            samples = load_samples(path)
            self.assertEqual([s.sample_id for s in samples], ["S2", "S1"])
            self.assertEqual(samples[0].row_number, 2)

    def test_empty_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "samples.csv")
            write(path, "")
            with self.assertRaisesRegex(SampleError, "为空"):
                load_samples(path)

    def test_no_records_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "samples.csv")
            write(path, "sample_id,group,replicates\n\n")
            with self.assertRaisesRegex(SampleError, "没有任何样本"):
                load_samples(path)

    def test_duplicate_id_rejected_with_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "samples.csv")
            write(path, "sample_id,group,replicates\nS1,g,1\nS1,g,2\n")
            with self.assertRaisesRegex(SampleError, "第 3 行"):
                load_samples(path)

    def test_missing_group_rejected_with_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "samples.csv")
            write(path, "sample_id,group,replicates\nS1,,1\n")
            with self.assertRaisesRegex(SampleError, "第 2 行"):
                load_samples(path)

    def test_non_positive_replicates_rejected_with_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "samples.csv")
            write(path, "sample_id,group,replicates\nS1,g,0\n")
            with self.assertRaisesRegex(SampleError, "第 2 行"):
                load_samples(path)


class OutputTest(unittest.TestCase):
    def _build(self):
        config = parse_config(
            {"max_plates": 3, "control_wells": ["A1"], "disabled_wells": ["H12"]}
        )
        return config

    def test_writes_plate_csv_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._build()
            sample_path = os.path.join(tmp, "samples.csv")
            write(sample_path, SAMPLE_CSV)
            samples = load_samples(sample_path)
            result = build_layout(samples, config)
            out_dir = os.path.join(tmp, "out")
            files = write_outputs(result, config, out_dir)
            self.assertEqual(len(files), 2)
            plate_path = os.path.join(out_dir, plate_filename(1))
            with open(plate_path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            self.assertEqual(len(lines), 97)
            self.assertEqual(lines[0], "plate,well,state,sample_id,group,replicate")
            self.assertEqual(lines[1], "1,A1,control,,,")
            self.assertEqual(lines[2], "1,A2,sample,S1,g1,1")
            self.assertEqual(lines[-1], "1,H12,disabled,,,")
            with open(os.path.join(out_dir, SUMMARY_FILE), encoding="utf-8") as handle:
                summary = json.load(handle)
            self.assertEqual(summary["plate_count"], 1)
            self.assertEqual(summary["plates"][0]["counts"]["sample"], 5)
            self.assertEqual(summary["control_wells"], ["A1"])
            s1 = next(s for s in summary["samples"] if s["sample_id"] == "S1")
            self.assertEqual(len(s1["coordinates"]), 3)

    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._build()
            sample_path = os.path.join(tmp, "samples.csv")
            write(sample_path, SAMPLE_CSV)
            result = build_layout(load_samples(sample_path), config)
            write_outputs(result, config, tmp)
            with self.assertRaises(FileExistsError):
                write_outputs(result, config, tmp)

    def test_failure_leaves_no_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            samples_path = os.path.join(tmp, "samples.csv")
            write(samples_path, "sample_id,group,replicates\nS1,g,95\n")
            config_path = os.path.join(tmp, "config.json")
            write(
                config_path,
                json.dumps({"max_plates": 1, "control_wells": ["A1"], "disabled_wells": ["A2"]}),
            )
            out_dir = os.path.join(tmp, "out")
            code = main(["--samples", samples_path, "--config", config_path, "--output-dir", out_dir])
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(out_dir))

    def test_cli_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            samples_path = os.path.join(tmp, "samples.csv")
            write(samples_path, SAMPLE_CSV)
            config_path = os.path.join(tmp, "config.json")
            write(config_path, json.dumps({"max_plates": 2, "control_wells": [], "disabled_wells": []}))
            out_dir = os.path.join(tmp, "out")
            code = main(["--samples", samples_path, "--config", config_path, "--output-dir", out_dir])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(os.path.join(out_dir, plate_filename(1))))
            self.assertTrue(os.path.exists(os.path.join(out_dir, SUMMARY_FILE)))


if __name__ == "__main__":
    unittest.main()
