"""Minimal end-to-end command for PSA OpenSTAT Wage raw ingestion."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from analytics_platform.domains.wage.ingestion.bigquery import (
    APPROVED_DATASET_ID,
    APPROVED_LOCATION,
    APPROVED_PROJECT_ID,
    load_wage_raw,
    verify_wage_raw,
)
from analytics_platform.domains.wage.ingestion.openstat import (
    MATRIX_SPECS,
    OpenSTATHTTPClient,
    acquire_matrix,
    validate_representative_values,
)
from analytics_platform.platform.provenance.reconciliation import reconcile_artifacts


DEFAULT_LOCAL_ROOT = Path(".local") / "wage" / "openstat"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wage-openstat-ingest",
        description="Acquire, extract, load, and verify the PSA 2024 OWS raw layer.",
    )
    parser.add_argument(
        "--local-root",
        type=Path,
        default=Path(
            os.environ.get("WAGE_OPENSTAT_LOCAL_ROOT", str(DEFAULT_LOCAL_ROOT))
        ),
    )
    parser.add_argument(
        "--project", default=os.environ.get("BIGQUERY_PROJECT", APPROVED_PROJECT_ID)
    )
    parser.add_argument(
        "--dataset",
        default=os.environ.get("WAGE_BIGQUERY_RAW_DATASET", APPROVED_DATASET_ID),
    )
    parser.add_argument(
        "--location", default=os.environ.get("BIGQUERY_LOCATION", APPROVED_LOCATION)
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    local_root = args.local_root.resolve()
    http_client = OpenSTATHTTPClient()
    acquisitions = tuple(
        acquire_matrix(spec, local_root, client=http_client) for spec in MATRIX_SPECS
    )
    validate_representative_values(acquisitions)
    reconciliation = reconcile_artifacts(
        local_root, [item.artifact for item in acquisitions]
    )
    blocking_findings = [
        item
        for item in reconciliation.findings
        if item.severity == "error" or item.code == "STAGING_FILE_PRESENT"
    ]
    if blocking_findings:
        codes = ", ".join(item.code for item in blocking_findings)
        raise RuntimeError(f"Local immutable artifact reconciliation failed: {codes}")

    for item in acquisitions:
        print(
            f"{item.spec.matrix_id}: {len(item.observations):,} observations; "
            f"sha256={item.artifact.sha256_checksum}; "
            f"artifact={item.artifact_publication.outcome}"
        )
    loaded = load_wage_raw(
        acquisitions, args.project, args.dataset, args.location
    )
    verified = verify_wage_raw(
        acquisitions, args.project, args.dataset, args.location
    )
    for table_name, row_count in sorted(verified.table_row_counts.items()):
        print(f"{loaded.project_id}.{loaded.dataset_id}.{table_name}: {row_count:,} rows")
    print(
        "PSA OpenSTAT Wage raw ingestion completed with unique V2 identities "
        f"for {verified.unique_logical_observation_ids:,} observations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
