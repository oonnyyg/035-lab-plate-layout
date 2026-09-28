"""``python -m plate_layout`` 命令行入口。"""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_config
from .planner import LayoutError, build_layout
from .samples import SampleError, load_samples
from .writer import write_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="plate_layout",
        description="把样本及重复测量需求安排到多块 8x12 孔板并输出布局文件。",
    )
    parser.add_argument("--samples", required=True, help="样本 CSV 文件路径")
    parser.add_argument("--config", required=True, help="布局配置 JSON 文件路径")
    parser.add_argument("--output-dir", required=True, help="布局输出目录")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        samples = load_samples(args.samples)
        result = build_layout(samples, config)
        written = write_outputs(result, config, args.output_dir)
    except (ConfigError, SampleError, LayoutError, FileExistsError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(f"已生成 {result.plate_count} 块板的布局：")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
