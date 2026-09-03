"""Idempotent BigQuery raw persistence for PSA OWS acquisitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Sequence

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from analytics_platform.domains.wage.ingestion.openstat import AcquiredMatrix


APPROVED_PROJECT_ID = "analytics-portfolio-101416"
APPROVED_DATASET_ID = "analytics_portfolio_wage_raw"
APPROVED_LOCATION = "US"

OBSERVATION_SCHEMA = (
    bigquery.SchemaField("source_record_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("logical_observation_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("semantic_dataset_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("matrix_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("matrix_title", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("reference_year", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("geography_type", "STRING"),
    bigquery.SchemaField("geography_code", "STRING"),
    bigquery.SchemaField("geography_name", "STRING"),
    bigquery.SchemaField("industry_code", "STRING"),
    bigquery.SchemaField("industry_name", "STRING"),
    bigquery.SchemaField("occupation_code", "STRING"),
    bigquery.SchemaField("occupation_name", "STRING"),
    bigquery.SchemaField("sex_code", "STRING"),
    bigquery.SchemaField("sex", "STRING"),
    bigquery.SchemaField("measure_code", "STRING"),
    bigquery.SchemaField("measure", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("observation_value", "FLOAT64"),
    bigquery.SchemaField("observation_status", "STRING"),
    bigquery.SchemaField("source_unit", "STRING"),
    bigquery.SchemaField("source_publisher", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_updated_at", "STRING"),
    bigquery.SchemaField("source_artifact_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("retrieval_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("extraction_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_record_locator", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("identifier_version", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP", mode="REQUIRED"),
)

MATRIX_METADATA_SCHEMA = (
    bigquery.SchemaField("matrix_metadata_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("semantic_dataset_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("matrix_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("matrix_title", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("canonical_endpoint", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("canonical_request", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("requested_format", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_publisher", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("reference_year", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("dimension_ids_json", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_metadata_json", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_artifact_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("sha256_checksum", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("byte_size", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("storage_key", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("first_retrieval_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("first_retrieved_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("extraction_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("identifier_version", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_updated_at", "STRING"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP", mode="REQUIRED"),
)

INGESTION_RUN_SCHEMA = (
    bigquery.SchemaField("retrieval_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("semantic_dataset_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("matrix_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("canonical_endpoint", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("canonical_request", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("requested_format", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("request_method", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("retrieval_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("content_outcome", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("retrieval_started_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("retrieval_completed_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("http_status_code", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("response_content_type", "STRING"),
    bigquery.SchemaField("response_content_length", "INT64"),
    bigquery.SchemaField("response_bytes_received", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("response_etag", "STRING"),
    bigquery.SchemaField("response_last_modified", "STRING"),
    bigquery.SchemaField("source_artifact_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("sha256_checksum", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("extraction_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("extraction_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("records_emitted", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("issues_emitted", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("identifier_version", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP", mode="REQUIRED"),
)

TABLE_CONTRACTS = {
    "ows_observations": OBSERVATION_SCHEMA,
    "ows_matrix_metadata": MATRIX_METADATA_SCHEMA,
    "ows_ingestion_runs": INGESTION_RUN_SCHEMA,
}


@dataclass(frozen=True)
class WageRawLoadSummary:
    project_id: str
    dataset_id: str
    location: str
    dataset_created: bool
    inserted_rows: dict[str, int]
    table_row_counts: dict[str, int]


@dataclass(frozen=True)
class WageRawVerificationSummary:
    project_id: str
    dataset_id: str
    location: str
    extraction_row_counts: dict[str, int]
    table_row_counts: dict[str, int]
    unique_logical_observation_ids: int


def _validate_target(project_id: str, dataset_id: str, location: str) -> None:
    if project_id != APPROVED_PROJECT_ID:
        raise ValueError("Wage ingestion is restricted to the portfolio GCP project")
    if dataset_id != APPROVED_DATASET_ID:
        raise ValueError("Wage ingestion is restricted to the approved raw dataset")
    if location.upper() != APPROVED_LOCATION:
        raise ValueError("Wage ingestion is restricted to the US location")


def _table_id(project_id: str, dataset_id: str, table_name: str) -> str:
    return f"{project_id}.{dataset_id}.{table_name}"


def _normalize_type(value: str) -> str:
    return {
        "INTEGER": "INT64",
        "FLOAT": "FLOAT64",
        "BOOLEAN": "BOOL",
    }.get(value.upper(), value.upper())


def _schema_signature(schema: Iterable[bigquery.SchemaField]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (field.name, _normalize_type(field.field_type), field.mode.upper())
        for field in schema
    )


def _ensure_dataset(
    client: bigquery.Client, project_id: str, dataset_id: str, location: str
) -> bool:
    reference = bigquery.DatasetReference(project_id, dataset_id)
    try:
        dataset = client.get_dataset(reference)
    except NotFound:
        dataset = bigquery.Dataset(reference)
        dataset.location = location
        dataset.friendly_name = "Analytics Portfolio Wage Raw"
        dataset.description = "Immutable PSA OpenSTAT OWS raw observations and provenance."
        dataset.labels = {
            "domain": "wage",
            "layer": "raw",
            "source": "psa_openstat",
            "classification": "public",
        }
        client.create_dataset(dataset)
        return True
    if dataset.location and dataset.location.upper() != location.upper():
        raise ValueError("Existing Wage raw dataset is in the wrong location")
    return False


def _ensure_tables(
    client: bigquery.Client, project_id: str, dataset_id: str
) -> None:
    descriptions = {
        "ows_observations": "Normalized source-faithful PSA OWS observations.",
        "ows_matrix_metadata": "OpenSTAT matrix, request, artifact, and extraction metadata.",
        "ows_ingestion_runs": "One row for each PSA OpenSTAT retrieval attempt loaded.",
    }
    for table_name, schema in TABLE_CONTRACTS.items():
        table_id = _table_id(project_id, dataset_id, table_name)
        try:
            existing = client.get_table(table_id)
        except NotFound:
            table = bigquery.Table(table_id, schema=list(schema))
            table.description = descriptions[table_name]
            table.labels = {
                "domain": "wage",
                "layer": "raw",
                "source": "psa_openstat",
                "classification": "public",
            }
            client.create_table(table)
            continue
        if _schema_signature(existing.schema) != _schema_signature(schema):
            raise ValueError(f"BigQuery schema drift detected for {table_id}")


def _query_rows(
    client: bigquery.Client,
    sql: str,
    location: str,
    job_config: bigquery.QueryJobConfig | None = None,
) -> list[Any]:
    return list(client.query(sql, location=location, job_config=job_config).result())


def _normalized_value(value: object, field: bigquery.SchemaField) -> object:
    if value is None or field.field_type.upper() != "TIMESTAMP":
        return value
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid timestamp in {field.name}") from exc
    else:
        raise ValueError(f"Invalid timestamp in {field.name}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_idempotent_rows(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset_id: str,
    location: str,
    table_name: str,
    key_column: str,
    rows: Sequence[dict[str, object]],
    ignored_conflict_columns: Sequence[str] = (),
) -> int:
    if not rows:
        return 0
    keys = [row[key_column] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate {key_column} values in the local load batch")
    schema = TABLE_CONTRACTS[table_name]
    columns = [field.name for field in schema]
    if any(set(row) != set(columns) for row in rows):
        raise ValueError(f"Rows do not match the {table_name} contract")
    target = _table_id(project_id, dataset_id, table_name)
    excluded = tuple(dict.fromkeys(ignored_conflict_columns))
    invalid_excluded = set(excluded) - set(columns)
    if invalid_excluded:
        raise ValueError("Conflict comparison excludes unknown columns")
    existing_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("keys", "STRING", keys)]
    )
    existing_rows = _query_rows(
        client,
        f"select * from `{target}` where {key_column} in unnest(@keys)",
        location,
        existing_config,
    )
    existing_by_key: dict[object, dict[str, object]] = {}
    for existing in existing_rows:
        existing_row = dict(existing.items())
        key = existing_row[key_column]
        if key in existing_by_key:
            raise ValueError(f"Duplicate persisted {key_column} in {table_name}")
        existing_by_key[key] = existing_row
    fields = {field.name: field for field in schema}
    for row in rows:
        existing = existing_by_key.get(row[key_column])
        if existing is None:
            continue
        for column in columns:
            if column in excluded:
                continue
            if _normalized_value(existing[column], fields[column]) != _normalized_value(
                row[column], fields[column]
            ):
                raise ValueError(f"Immutable row conflict detected in {table_name}")
    missing_rows = [row for row in rows if row[key_column] not in existing_by_key]
    if not missing_rows:
        return 0
    load_config = bigquery.LoadJobConfig(
        schema=list(schema),
        create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    client.load_table_from_json(
        missing_rows, target, job_config=load_config, location=location
    ).result()
    return len(missing_rows)


def load_wage_raw(
    acquisitions: Sequence[AcquiredMatrix],
    project_id: str,
    dataset_id: str,
    location: str,
    *,
    client: bigquery.Client | None = None,
) -> WageRawLoadSummary:
    _validate_target(project_id, dataset_id, location)
    if not acquisitions:
        raise ValueError("At least one acquisition is required")
    matrix_ids = [item.spec.matrix_id for item in acquisitions]
    if len(matrix_ids) != len(set(matrix_ids)):
        raise ValueError("Each matrix may appear only once in a load batch")
    bq_client = client or bigquery.Client(project=project_id, location=location)
    if bq_client.project != project_id:
        raise ValueError("BigQuery client project does not match the approved project")
    dataset_created = _ensure_dataset(bq_client, project_id, dataset_id, location)
    _ensure_tables(bq_client, project_id, dataset_id)
    observation_rows = [
        observation.as_row()
        for acquisition in acquisitions
        for observation in acquisition.observations
    ]
    matrix_rows = [item.matrix_metadata.as_row() for item in acquisitions]
    run_rows = [item.ingestion_run.as_row() for item in acquisitions]
    inserted = {
        "ows_observations": _load_idempotent_rows(
            bq_client,
            project_id=project_id,
            dataset_id=dataset_id,
            location=location,
            table_name="ows_observations",
            key_column="logical_observation_id",
            rows=observation_rows,
            ignored_conflict_columns=(
                "source_record_id",
                "source_artifact_id",
                "retrieval_id",
                "extraction_id",
                "source_updated_at",
                "loaded_at",
            ),
        ),
        "ows_matrix_metadata": _load_idempotent_rows(
            bq_client,
            project_id=project_id,
            dataset_id=dataset_id,
            location=location,
            table_name="ows_matrix_metadata",
            key_column="matrix_metadata_id",
            rows=matrix_rows,
            ignored_conflict_columns=(
                "first_retrieval_id",
                "first_retrieved_at",
                "loaded_at",
            ),
        ),
        "ows_ingestion_runs": _load_idempotent_rows(
            bq_client,
            project_id=project_id,
            dataset_id=dataset_id,
            location=location,
            table_name="ows_ingestion_runs",
            key_column="retrieval_id",
            rows=run_rows,
        ),
    }
    table_counts = {
        table_name: int(bq_client.get_table(_table_id(project_id, dataset_id, table_name)).num_rows)
        for table_name in TABLE_CONTRACTS
    }
    return WageRawLoadSummary(
        project_id, dataset_id, location, dataset_created, inserted, table_counts
    )


def verify_wage_raw(
    acquisitions: Sequence[AcquiredMatrix],
    project_id: str,
    dataset_id: str,
    location: str,
    *,
    client: bigquery.Client | None = None,
) -> WageRawVerificationSummary:
    _validate_target(project_id, dataset_id, location)
    if not acquisitions:
        raise ValueError("At least one acquisition is required")
    bq_client = client or bigquery.Client(project=project_id, location=location)
    if bq_client.project != project_id:
        raise ValueError("BigQuery client project does not match the approved project")
    reference = bigquery.DatasetReference(project_id, dataset_id)
    try:
        dataset = bq_client.get_dataset(reference)
    except NotFound as exc:
        raise ValueError("The approved Wage raw dataset does not exist") from exc
    if dataset.location and dataset.location.upper() != location.upper():
        raise ValueError("Existing Wage raw dataset is in the wrong location")
    _ensure_tables(bq_client, project_id, dataset_id)

    observation_table = _table_id(project_id, dataset_id, "ows_observations")
    semantic_ids = [item.observations[0].semantic_dataset_id for item in acquisitions]
    semantic_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("semantic_ids", "STRING", semantic_ids)
        ]
    )
    extraction_rows = _query_rows(
        bq_client,
        f"""
        select
          matrix_id,
          count(*) as row_count,
          count(distinct logical_observation_id) as distinct_record_count,
          countif(
            source_artifact_id is null
            or extraction_id is null
            or request_id is null
            or identifier_version != 'portfolio-v2'
          ) as invalid_provenance_count
        from `{observation_table}`
        where semantic_dataset_id in unnest(@semantic_ids)
        group by matrix_id
        order by matrix_id
        """,
        location,
        semantic_config,
    )
    observed_counts = {row["matrix_id"]: int(row["row_count"]) for row in extraction_rows}
    expected_counts = {
        item.spec.matrix_id: len(item.observations) for item in acquisitions
    }
    if observed_counts != expected_counts:
        raise ValueError("BigQuery extraction row counts do not match local extraction")
    if any(
        int(row["distinct_record_count"]) != int(row["row_count"])
        or int(row["invalid_provenance_count"])
        for row in extraction_rows
    ):
        raise ValueError("BigQuery observations failed identity/provenance validation")

    identity_rows = _query_rows(
        bq_client,
        f"""
        select
          count(*) as row_count,
          count(distinct logical_observation_id) as distinct_record_count
        from `{observation_table}`
        """,
        location,
    )
    total_rows = int(identity_rows[0]["row_count"])
    unique_ids = int(identity_rows[0]["distinct_record_count"])
    if total_rows != unique_ids:
        raise ValueError("BigQuery raw observations contain duplicate logical identities")

    artifact_ids = [item.artifact.artifact_id for item in acquisitions]
    retrieval_ids = [item.retrieval.retrieval_run_id for item in acquisitions]
    metadata_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("artifact_ids", "STRING", artifact_ids),
            bigquery.ArrayQueryParameter("retrieval_ids", "STRING", retrieval_ids),
        ]
    )
    provenance_rows = _query_rows(
        bq_client,
        f"""
        select
          (select count(distinct source_artifact_id)
             from `{_table_id(project_id, dataset_id, 'ows_matrix_metadata')}`
            where source_artifact_id in unnest(@artifact_ids)) as artifact_count,
          (select count(distinct retrieval_id)
             from `{_table_id(project_id, dataset_id, 'ows_ingestion_runs')}`
            where retrieval_id in unnest(@retrieval_ids)) as retrieval_count
        """,
        location,
        metadata_config,
    )
    if (
        int(provenance_rows[0]["artifact_count"]) != len(set(artifact_ids))
        or int(provenance_rows[0]["retrieval_count"]) != len(set(retrieval_ids))
    ):
        raise ValueError("BigQuery artifact or retrieval provenance is incomplete")

    table_counts = {
        table_name: int(bq_client.get_table(_table_id(project_id, dataset_id, table_name)).num_rows)
        for table_name in TABLE_CONTRACTS
    }
    return WageRawVerificationSummary(
        project_id,
        dataset_id,
        location,
        expected_counts,
        table_counts,
        unique_ids,
    )
