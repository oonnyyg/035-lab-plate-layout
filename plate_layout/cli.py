"""Command-line entry: ``python -m plate_layout ...``."""

from __future__ import annotations

import argparse
import sys

from .errors import LayoutError
from .io_input import load_config, load_samples
from .io_output import LAYOUT_FILENAME, SUMMARY_FILENAME
from .planner import plan_layout, write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plate_layout",
        description=(
            "Assign sample replicates onto 8x12 lab plates while avoiding "
            "control and disabled wells."
        ),
    )
    parser.add_argument("--samples", required=True, help="path to sample CSV")
    parser.add_argument("--config", required=True, help="path to layout config JSON")
    parser.add_argument("--output-dir", required=True, help="directory for results")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        samples = load_samples(args.samples)
        config = load_config(args.config)
        layout = plan_layout(samples, config)
        csv_path, json_path = write_outputs(layout, args.output_dir)
    except LayoutError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"plates used: {len(layout.plates)}")
    print(f"layout CSV : {csv_path}")
    print(f"summary    : {json_path}")
    print(f"({LAYOUT_FILENAME}, {SUMMARY_FILENAME})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
