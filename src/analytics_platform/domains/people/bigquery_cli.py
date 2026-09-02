from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from analytics_platform.domains.people.config import load_scenario
from analytics_platform.domains.people.generator import generate_dataset
from analytics_platform.domains.people.ingestion.bigquery import (
    load_raw_dataset,
    verify_raw_dataset,
)

DEFAULT_SCENARIO = Path(__file__).resolve().parent / "scenarios" / "baseline.yml"
DEFAULT_RAW_DIR = Path("generated") / "people" / "raw"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="people-bigquery-demo",
        description="Generate, load, and verify the People Analytics BigQuery raw layer.",
    )
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--project", default=os.environ.get("BIGQUERY_PROJECT"))
    parser.add_argument(
        "--dataset", default=os.environ.get("PEOPLE_BIGQUERY_RAW_DATASET")
    )
    parser.add_argument("--location", default=os.environ.get("BIGQUERY_LOCATION"))
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace only the seven tables in the configured People raw dataset.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    missing = [
        name
        for name, value in (
            ("BIGQUERY_PROJECT/--project", args.project),
            ("PEOPLE_BIGQUERY_RAW_DATASET/--dataset", args.dataset),
            ("BIGQUERY_LOCATION/--location", args.location),
        )
        if not value
    ]
    if missing:
        parser.error(f"Missing required configuration: {', '.join(missing)}")

    scenario = load_scenario(args.scenario.resolve())
    generation = generate_dataset(scenario, args.raw_dir.resolve())
    print(f"Generated scenario '{scenario.name}' with seed {scenario.seed}")
    for filename, row_count in sorted(generation.row_counts.items()):
        print(f"  {filename}: {row_count:,} rows")

    loaded = load_raw_dataset(
        args.raw_dir.resolve(),
        args.project,
        args.dataset,
        args.location,
        replace=args.replace,
    )
    for table_name, row_count in sorted(loaded.row_counts.items()):
        print(f"  {loaded.project_id}.{loaded.dataset_id}.{table_name}: {row_count:,} rows")

    verified = verify_raw_dataset(
        args.raw_dir.resolve(),
        args.project,
        args.dataset,
        args.location,
    )
    print(
        f"Verified {verified.manifest_count} source files in "
        f"{verified.project_id}.{verified.dataset_id} ({verified.location})"
    )
    print("People BigQuery raw ingestion completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
