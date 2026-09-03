"""Faithful normalized raw contracts for PSA OWS observations and provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OWSObservation:
    source_record_id: str
    logical_observation_id: str
    semantic_dataset_id: str
    matrix_id: str
    matrix_title: str
    reference_year: int
    geography_type: str | None
    geography_code: str | None
    geography_name: str | None
    industry_code: str | None
    industry_name: str | None
    occupation_code: str | None
    occupation_name: str | None
    sex_code: str | None
    sex: str | None
    measure_code: str | None
    measure: str
    observation_value: float | None
    observation_status: str | None
    source_unit: str | None
    source_publisher: str
    source_updated_at: str | None
    source_artifact_id: str
    retrieval_id: str
    extraction_id: str
    request_id: str
    source_record_locator: str
    identifier_version: str
    loaded_at: str

    def as_row(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OWSMatrixMetadataRecord:
    matrix_metadata_id: str
    semantic_dataset_id: str
    matrix_id: str
    matrix_title: str
    canonical_endpoint: str
    canonical_request: str
    request_id: str
    requested_format: str
    source_id: str
    source_publisher: str
    reference_year: int
    dimension_ids_json: str
    source_metadata_json: str
    source_artifact_id: str
    sha256_checksum: str
    byte_size: int
    storage_key: str
    first_retrieval_id: str
    first_retrieved_at: str
    extraction_id: str
    identifier_version: str
    source_updated_at: str | None
    loaded_at: str

    def as_row(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OWSIngestionRunRecord:
    retrieval_id: str
    semantic_dataset_id: str
    matrix_id: str
    source_id: str
    request_id: str
    canonical_endpoint: str
    canonical_request: str
    requested_format: str
    request_method: str
    retrieval_status: str
    content_outcome: str
    retrieval_started_at: str
    retrieval_completed_at: str
    http_status_code: int
    response_content_type: str | None
    response_content_length: int | None
    response_bytes_received: int
    response_etag: str | None
    response_last_modified: str | None
    source_artifact_id: str
    sha256_checksum: str
    extraction_id: str
    extraction_status: str
    records_emitted: int
    issues_emitted: int
    identifier_version: str
    loaded_at: str

    def as_row(self) -> dict[str, object]:
        return asdict(self)
