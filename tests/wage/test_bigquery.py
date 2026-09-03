from __future__ import annotations

import copy

import pytest

from analytics_platform.domains.wage.ingestion.bigquery import (
    APPROVED_DATASET_ID,
    APPROVED_LOCATION,
    APPROVED_PROJECT_ID,
    INGESTION_RUN_SCHEMA,
    _load_idempotent_rows,
    _validate_target,
)


class QueryJob:
    def __init__(self, rows=()) -> None:
        self._rows = rows

    def result(self):
        return iter(self._rows)


class LoadJob:
    def result(self) -> None:
        return None


class FakeClient:
    def __init__(self, persisted=()) -> None:
        self.persisted = [copy.deepcopy(row) for row in persisted]
        self.loaded = []
        self.sql = []

    def load_table_from_json(self, rows, table_id, **kwargs):
        self.loaded.append((rows, table_id, kwargs))
        self.persisted.extend(copy.deepcopy(rows))
        return LoadJob()

    def query(self, sql, **kwargs):
        self.sql.append((sql, kwargs))
        return QueryJob(copy.deepcopy(self.persisted))


def _run_row(retrieval_id: str) -> dict[str, object]:
    strings = {
        "retrieval_id": retrieval_id,
        "semantic_dataset_id": "semantic_" + "f" * 64,
        "matrix_id": "0011B3E2001.px",
        "source_id": "psa_openstat_ows_0011b3e2001",
        "request_id": "request_" + "a" * 64,
        "canonical_endpoint": "https://openstat.psa.gov.ph/example",
        "canonical_request": "{}",
        "requested_format": "json-stat",
        "request_method": "POST",
        "retrieval_status": "succeeded",
        "content_outcome": "new_artifact",
        "retrieval_started_at": "2026-09-03T00:00:00.000000Z",
        "retrieval_completed_at": "2026-09-03T00:00:01.000000Z",
        "response_content_type": "application/json",
        "source_artifact_id": "artifact_" + "b" * 64,
        "sha256_checksum": "c" * 64,
        "extraction_id": "extraction_" + "d" * 64,
        "extraction_status": "succeeded",
        "identifier_version": "portfolio-v2",
        "loaded_at": "2026-09-03T00:00:02.000000Z",
    }
    integers = {
        "http_status_code": 200,
        "response_content_length": 10,
        "response_bytes_received": 10,
        "records_emitted": 1,
        "issues_emitted": 0,
    }
    nullable = {"response_etag": None, "response_last_modified": None}
    row = {**strings, **integers, **nullable}
    assert set(row) == {field.name for field in INGESTION_RUN_SCHEMA}
    return row


def _load(client: FakeClient, row: dict[str, object]) -> int:
    return _load_idempotent_rows(
        client,
        project_id=APPROVED_PROJECT_ID,
        dataset_id=APPROVED_DATASET_ID,
        location=APPROVED_LOCATION,
        table_name="ows_ingestion_runs",
        key_column="retrieval_id",
        rows=[row],
    )


def test_bigquery_target_is_fail_closed() -> None:
    _validate_target(APPROVED_PROJECT_ID, APPROVED_DATASET_ID, APPROVED_LOCATION)
    with pytest.raises(ValueError, match="portfolio GCP project"):
        _validate_target("budget-buddy-project", APPROVED_DATASET_ID, APPROVED_LOCATION)


def test_load_is_idempotent_and_uses_sandbox_compatible_append() -> None:
    client = FakeClient()
    row = _run_row("retrieval_00000000-0000-4000-8000-000000000001")

    assert _load(client, row) == 1
    assert _load(client, row) == 0
    assert len(client.loaded) == 1
    assert client.loaded[0][2]["job_config"].write_disposition == "WRITE_APPEND"
    assert all("select *" in sql.lower() for sql, _ in client.sql)


def test_load_rejects_immutable_conflicts_without_appending() -> None:
    row = _run_row("retrieval_00000000-0000-4000-8000-000000000001")
    conflicting = copy.deepcopy(row)
    conflicting["records_emitted"] = 2
    client = FakeClient([conflicting])

    with pytest.raises(ValueError, match="Immutable row conflict"):
        _load(client, row)
    assert not client.loaded
