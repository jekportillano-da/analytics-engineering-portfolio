"""Local commands for governed snapshot refresh, artifact generation, and validation."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from analytics_platform.presentation.contract import (
    canonical_json,
    validate_artifact_directory,
    write_artifacts,
)
from analytics_platform.presentation.generator import (
    build_presentation_artifacts,
    load_governed_snapshot,
    load_metric_contract,
)
from analytics_platform.presentation.sources import export_governed_snapshot


DEFAULT_SNAPSHOT = Path("presentation/source/v1/governed_snapshot.json")
DEFAULT_OUTPUT_DIR = Path("presentation/data")
DEFAULT_METRIC_CONTRACT = Path("contracts/metrics/v1/governed_metrics.yml")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portfolio-presentation")
    commands = parser.add_subparsers(dest="command", required=True)

    snapshot = commands.add_parser(
        "snapshot", description="Read governed local/cloud outputs into a safe snapshot."
    )
    snapshot.add_argument("--people-database", type=Path, required=True)
    snapshot.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT)
    snapshot.add_argument("--project", default=os.environ.get("BIGQUERY_PROJECT", ""))
    snapshot.add_argument(
        "--marts-dataset",
        default=(
            f"{os.environ['DBT_BIGQUERY_DATASET']}_marts"
            if os.environ.get("DBT_BIGQUERY_DATASET")
            else ""
        ),
    )
    snapshot.add_argument(
        "--wage-raw-dataset", default=os.environ.get("WAGE_BIGQUERY_RAW_DATASET", "")
    )
    snapshot.add_argument("--location", default=os.environ.get("BIGQUERY_LOCATION", ""))

    generate = commands.add_parser(
        "generate", description="Generate presentation artifacts without network access."
    )
    generate.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    generate.add_argument("--metric-contract", type=Path, default=DEFAULT_METRIC_CONTRACT)
    generate.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    validate = commands.add_parser(
        "validate", description="Validate the complete canonical presentation artifact set."
    )
    validate.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "snapshot":
        governed_snapshot = export_governed_snapshot(
            people_database=args.people_database,
            project=args.project,
            marts_dataset=args.marts_dataset,
            wage_raw_dataset=args.wage_raw_dataset,
            location=args.location,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(canonical_json(governed_snapshot), encoding="utf-8")
        print(f"Wrote governed presentation snapshot: {args.output.resolve()}")
        return 0
    if args.command == "generate":
        governed_snapshot = load_governed_snapshot(args.snapshot)
        metric_contract = load_metric_contract(args.metric_contract)
        artifacts = build_presentation_artifacts(governed_snapshot, metric_contract)
        write_artifacts(args.output_dir, artifacts)
        print(f"Generated {len(artifacts)} presentation artifacts in {args.output_dir.resolve()}")
        return 0
    artifacts = validate_artifact_directory(args.output_dir)
    print(f"Validated {len(artifacts)} presentation artifacts in {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
