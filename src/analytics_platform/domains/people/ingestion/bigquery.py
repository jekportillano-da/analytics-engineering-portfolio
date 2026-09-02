from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from analytics_platform.domains.people.ingestion.raw import (
    RAW_TABLES,
    VERSIONED_RAW_TABLES,
    sha256_file,
)

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_DATASET_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")


@dataclass(frozen=True)
class BigQueryLoadSummary:
    project_id: str
    dataset_id: str
    location: str
    row_counts: dict[str, int]
    manifest_count: int
    dataset_created: bool


@dataclass(frozen=True)
class BigQueryRawVerificationSummary:
    project_id: str
    dataset_id: str
    location: str
    row_counts: dict[str, int]
    manifest_count: int


def _validate_target(project_id: str, dataset_id: str, location: str) -> None:
    if not _PROJECT_ID.fullmatch(project_id):
        raise ValueError(f"Invalid GCP project ID: {project_id!r}")
    if not _DATASET_ID.fullmatch(dataset_id):
        raise ValueError(f"Invalid BigQuery dataset ID: {dataset_id!r}")
    if not location.strip():
        raise ValueError("BigQuery location must not be empty")


def _table_id(project_id: str, dataset_id: str, table_name: str) -> str:
    return f"{project_id}.{dataset_id}.{table_name}"


def _ensure_dataset(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    location: str,
) -> bool:
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        dataset = client.get_dataset(dataset_ref)
        _validate_dataset_location(dataset, project_id, dataset_id, location)
        return False
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = location
        client.create_dataset(dataset)
        return True


def _validate_dataset_location(
    dataset: Any,
    project_id: str,
    dataset_id: str,
    location: str,
) -> None:
    if dataset.location and dataset.location.upper() != location.upper():
        raise ValueError(
            f"BigQuery dataset {project_id}.{dataset_id} is in {dataset.location}, "
            f"not configured location {location}"
        )


def _read_source_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"Source file has no header: {path}")
        fieldnames = list(reader.fieldnames)
        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError(f"Source file contains duplicate columns: {path}")
        if {"_source_file", "_loaded_at"}.intersection(fieldnames):
            raise ValueError(f"Source file contains reserved load metadata columns: {path}")
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _load_json_rows(
    client: bigquery.Client,
    rows: list[dict[str, Any]],
    table_id: str,
    schema: list[bigquery.SchemaField],
    location: str,
    replace: bool,
) -> int:
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        write_disposition=(
            bigquery.WriteDisposition.WRITE_TRUNCATE
            if replace
            else bigquery.WriteDisposition.WRITE_EMPTY
        ),
    )
    client.load_table_from_json(
        rows,
        table_id,
        job_config=job_config,
        location=location,
    ).result()
    return int(client.get_table(table_id).num_rows)


def load_raw_dataset(
    raw_dir: Path,
    project_id: str,
    dataset_id: str,
    location: str,
    *,
    replace: bool = False,
    client: bigquery.Client | None = None,
) -> BigQueryLoadSummary:
    _validate_target(project_id, dataset_id, location)
    missing = [filename for filename in RAW_TABLES if not (raw_dir / filename).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing generated source files: {', '.join(missing)}")

    bq_client = client or bigquery.Client(project=project_id, location=location)
    if bq_client.project != project_id:
        raise ValueError(
            f"BigQuery client project {bq_client.project!r} does not match {project_id!r}"
        )

    dataset_created = _ensure_dataset(bq_client, project_id, dataset_id, location)
    loaded_at = datetime.now(UTC).isoformat()
    row_counts: dict[str, int] = {}
    manifest_rows: list[dict[str, Any]] = []

    for filename, table_name in RAW_TABLES.items():
        source_path = (raw_dir / filename).resolve()
        fieldnames, source_rows = _read_source_rows(source_path)
        rows = [
            {**row, "_source_file": filename, "_loaded_at": loaded_at}
            for row in source_rows
        ]
        schema = [bigquery.SchemaField(name, "STRING") for name in fieldnames]
        schema.extend(
            (
                bigquery.SchemaField("_source_file", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("_loaded_at", "TIMESTAMP", mode="REQUIRED"),
            )
        )
        table_id = _table_id(project_id, dataset_id, table_name)
        row_count = _load_json_rows(
            bq_client,
            rows,
            table_id,
            schema,
            location,
            replace,
        )
        if row_count != len(source_rows):
            raise ValueError(f"Row-count mismatch after loading {filename}")
        row_counts[table_name] = row_count
        manifest_rows.append(
            {
                "file_name": filename,
                "sha256": sha256_file(source_path),
                "row_count": row_count,
                "loaded_at": loaded_at,
            }
        )

    manifest_schema = [
        bigquery.SchemaField("file_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("sha256", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("row_count", "INT64", mode="REQUIRED"),
        bigquery.SchemaField("loaded_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    manifest_count = _load_json_rows(
        bq_client,
        manifest_rows,
        _table_id(project_id, dataset_id, "file_manifest"),
        manifest_schema,
        location,
        replace,
    )
    if manifest_count != len(RAW_TABLES):
        raise ValueError("Raw manifest row count does not match the source file set")

    return BigQueryLoadSummary(
        project_id=project_id,
        dataset_id=dataset_id,
        location=location,
        row_counts=row_counts,
        manifest_count=manifest_count,
        dataset_created=dataset_created,
    )


def _query_rows(
    client: bigquery.Client,
    sql: str,
    location: str,
    job_config: bigquery.QueryJobConfig | None = None,
) -> list[Any]:
    return list(client.query(sql, location=location, job_config=job_config).result())


def verify_raw_dataset(
    raw_dir: Path,
    project_id: str,
    dataset_id: str,
    location: str,
    *,
    client: bigquery.Client | None = None,
) -> BigQueryRawVerificationSummary:
    _validate_target(project_id, dataset_id, location)
    bq_client = client or bigquery.Client(project=project_id, location=location)
    if bq_client.project != project_id:
        raise ValueError(
            f"BigQuery client project {bq_client.project!r} does not match {project_id!r}"
        )
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        dataset = bq_client.get_dataset(dataset_ref)
    except NotFound as error:
        raise ValueError(
            f"BigQuery dataset {project_id}.{dataset_id} does not exist"
        ) from error
    _validate_dataset_location(dataset, project_id, dataset_id, location)

    manifest_table = _table_id(project_id, dataset_id, "file_manifest")
    manifest_rows = _query_rows(
        bq_client,
        f"""
        select file_name, sha256, row_count, loaded_at
        from `{manifest_table}`
        order by file_name
        """,
        location,
    )
    manifest = {row["file_name"]: row for row in manifest_rows}
    if len(manifest) != len(manifest_rows) or set(manifest) != set(RAW_TABLES):
        raise ValueError("Raw file manifest does not match the expected source files")

    row_counts: dict[str, int] = {}
    for filename, table_name in RAW_TABLES.items():
        source_path = (raw_dir / filename).resolve()
        manifest_row = manifest[filename]
        table_id = _table_id(project_id, dataset_id, table_name)
        versioned_check = (
            "countif(coalesce(source_record_id, '') = '' "
            "or coalesce(source_updated_at, '') = '')"
            if table_name in VERSIONED_RAW_TABLES
            else "0"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source_file", "STRING", filename)
            ]
        )
        validation_rows = _query_rows(
            bq_client,
            f"""
            select
                count(*) as row_count,
                countif(
                    _source_file is null
                    or _source_file != @source_file
                    or _loaded_at is null
                ) as invalid_load_metadata,
                {versioned_check} as missing_source_metadata
            from `{table_id}`
            """,
            location,
            job_config,
        )
        validation = validation_rows[0]
        row_count = int(validation["row_count"])
        if manifest_row["sha256"] != sha256_file(source_path):
            raise ValueError(f"SHA-256 mismatch for {filename}")
        if int(manifest_row["row_count"]) != row_count:
            raise ValueError(f"Row-count mismatch for {filename}")
        if manifest_row["loaded_at"] is None or validation["invalid_load_metadata"]:
            raise ValueError(f"Incomplete load metadata for {filename}")
        if validation["missing_source_metadata"]:
            raise ValueError(f"Incomplete source metadata for {filename}")
        row_counts[table_name] = row_count

    return BigQueryRawVerificationSummary(
        project_id=project_id,
        dataset_id=dataset_id,
        location=location,
        row_counts=row_counts,
        manifest_count=len(manifest_rows),
    )
