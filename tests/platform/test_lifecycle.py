from __future__ import annotations

import hashlib

import pytest

from analytics_platform.platform.provenance.artifacts import artifact_storage_key
from analytics_platform.platform.provenance.identifiers import (
    artifact_id_v2,
    new_retrieval_run_id,
)
from analytics_platform.platform.provenance.lifecycle import (
    ArtifactProvenance,
    ProvenanceError,
    RetrievalResponse,
    complete_retrieval,
    fail_retrieval,
    finish_extraction,
    start_extraction,
    start_retrieval,
)


STARTED = "2026-08-10T01:02:03.000000Z"
COMPLETED = "2026-08-10T01:02:04.000000Z"
SOURCE_ID = "public_example_source"
CHECKSUM = hashlib.sha256(b"artifact").hexdigest()
ARTIFACT_ID = artifact_id_v2(SOURCE_ID, CHECKSUM)


def test_retrieval_retains_source_and_response_metadata() -> None:
    retrieval_id = new_retrieval_run_id()
    started = start_retrieval(
        SOURCE_ID,
        "https://example.org/source.csv",
        retrieval_run_id=retrieval_id,
        retrieval_started_at=STARTED,
    )
    response = RetrievalResponse(
        resolved_location="https://cdn.example.org/source.csv",
        status_code=200,
        content_type="text/csv",
        content_length=8,
        bytes_received=8,
        etag='"abc"',
        last_modified="Mon, 10 Aug 2026 01:00:00 GMT",
    )
    completed = complete_retrieval(
        started,
        content_outcome="new_artifact",
        response=response,
        retrieval_completed_at=COMPLETED,
        artifact_id=ARTIFACT_ID,
    )
    assert completed.source_id == SOURCE_ID
    assert completed.requested_location == "https://example.org/source.csv"
    assert completed.response == response
    assert completed.artifact_id == ARTIFACT_ID
    assert started.retrieval_status == "started"


def test_retrieval_failure_requires_redacted_terminal_metadata() -> None:
    started = start_retrieval(
        SOURCE_ID,
        "https://example.org/source.csv",
        retrieval_started_at=STARTED,
    )
    failed = fail_retrieval(
        started,
        error_code="SOURCE_TIMEOUT",
        redacted_error_message="Approved source timed out",
        retrieval_completed_at=COMPLETED,
    )
    assert failed.retrieval_status == "failed"
    assert failed.content_outcome == "no_artifact"
    with pytest.raises(ProvenanceError):
        fail_retrieval(
            failed,
            error_code="SOURCE_TIMEOUT",
            redacted_error_message="retry",
            retrieval_completed_at=COMPLETED,
        )


def test_artifact_provenance_validates_identity_storage_and_version() -> None:
    retrieval_id = new_retrieval_run_id()
    record = ArtifactProvenance(
        artifact_id=ARTIFACT_ID,
        source_id=SOURCE_ID,
        sha256_checksum=CHECKSUM,
        byte_size=8,
        storage_key=artifact_storage_key(SOURCE_ID, CHECKSUM),
        first_retrieval_run_id=retrieval_id,
        first_retrieved_at=COMPLETED,
        content_type="text/csv",
    )
    assert record.identifier_version == "portfolio-v2"
    with pytest.raises(ProvenanceError):
        ArtifactProvenance(
            artifact_id="artifact_" + "0" * 64,
            source_id=SOURCE_ID,
            sha256_checksum=CHECKSUM,
            byte_size=8,
            storage_key=artifact_storage_key(SOURCE_ID, CHECKSUM),
            first_retrieval_run_id=retrieval_id,
            first_retrieved_at=COMPLETED,
        )


def test_extraction_lifecycle_is_payload_and_persistence_agnostic() -> None:
    started = start_extraction(
        SOURCE_ID,
        ARTIFACT_ID,
        "csv_rows",
        "1.0.0",
        "records-v1",
        "b" * 64,
        extraction_started_at=STARTED,
    )
    completed = finish_extraction(
        started,
        status="partial",
        extraction_completed_at=COMPLETED,
        records_emitted=10,
        issues_emitted=2,
    )
    assert completed.extraction_status == "partial"
    assert completed.records_emitted == 10
    assert started.extraction_status == "started"
    with pytest.raises(ProvenanceError):
        finish_extraction(
            completed,
            status="succeeded",
            extraction_completed_at=COMPLETED,
            records_emitted=10,
            issues_emitted=0,
        )
