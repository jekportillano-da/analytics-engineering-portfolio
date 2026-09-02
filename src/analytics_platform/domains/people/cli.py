from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from analytics_platform.domains.people.config import load_scenario
from analytics_platform.domains.people.generator import GenerationSummary, generate_dataset
from analytics_platform.domains.people.ingestion.duckdb import (
    LoadSummary,
    RawVerificationSummary,
    load_raw_dataset,
    verify_raw_dataset,
)

DEFAULT_SCENARIO = Path(__file__).resolve().parent / "scenarios" / "baseline.yml"
DEFAULT_RAW_DIR = Path("generated") / "people" / "raw"
DEFAULT_DATABASE = Path("warehouse") / "people_analytics.duckdb"


def _print_generation(summary: GenerationSummary) -> None:
    print(f"Generated scenario '{summary.scenario_name}' in {summary.output_dir}")
    for filename, row_count in sorted(summary.row_counts.items()):
        print(f"  {filename}: {row_count:,} rows")


def _print_load(summary: LoadSummary) -> None:
    print(f"Loaded raw sources into {summary.database_path}")
    for table_name, row_count in sorted(summary.row_counts.items()):
        print(f"  raw.{table_name}: {row_count:,} rows")


def _print_verification(summary: RawVerificationSummary) -> None:
    print(f"Verified raw sources in {summary.database_path}")
    print(f"  raw.file_manifest: {summary.manifest_count:,} files")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="people-local-demo",
        description="Generate, load, and verify the local People Analytics raw layer.",
    )
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    scenario_path = args.scenario.resolve()
    raw_dir = args.raw_dir.resolve()
    database_path = args.database.resolve()

    config = load_scenario(scenario_path)
    _print_generation(generate_dataset(config, raw_dir))
    _print_load(load_raw_dataset(raw_dir, database_path, reset=True))
    _print_verification(verify_raw_dataset(raw_dir, database_path))
    print("People local ingestion demo completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
