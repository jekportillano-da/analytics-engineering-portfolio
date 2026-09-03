"""Persistence-agnostic retrieval, artifact, and extraction provenance records."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal, TypeAlias

from analytics_platform.platform.provenance.artifacts import artifact_storage_key
from analytics_platform.platform.provenance.identifiers import (
    IdentifierVersion,
    artifact_id_for_version,
    extraction_batch_id_v2,
    new_retrieval_run_id,
    validate_retrieval_run_id,
    validate_sha256,
    validate_source_id,
)


RetrievalStatus: TypeAlias = Literal["started", "succeeded", "failed"]
ContentOutcome: TypeAlias = Literal[
    "new_artifact", "known_artifact", "not_modified", "no_artifact"
]
ExtractionStatus: TypeAlias = Literal["started", "succeeded", "partial", "failed"]

_METHOD = re.compile(r"^[A-Z][A-Z0-9_-]{0,15}$")
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ARTIFACT_IDENTIFIER = re.compile(r"^artifact_[0-9a-f]{64}$")


class ProvenanceError(ValueError):
    """Raised when provenance metadata or a lifecycle transition is invalid."""


def utc_now_text() -> str:
    """Return a canonical microsecond UTC timestamp."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _text(value: str, field_name: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or value == ""
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ProvenanceError(f"{field_name} is not canonical text")
    return value


def _optional_text(value: str | None, field_name: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, field_name, maximum)


def _timestamp(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ProvenanceError(f"{field_name} must be a canonical UTC timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ProvenanceError(
            f"{field_name} must use YYYY-MM-DDTHH:MM:SS.ffffffZ"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
        raise ProvenanceError(
            f"{field_name} must use YYYY-MM-DDTHH:MM:SS.ffffffZ"
        )
    return value


def _nonnegative(value: int | None, field_name: str) -> None:
    if value is not None and (
        not isinstance(value, int) or isinstance(value, bool) or value < 0
    ):
        raise ProvenanceError(f"{field_name} must be a nonnegative integer or None")


@dataclass(frozen=True)
class RetrievalResponse:
    """Bounded protocol metadata retained without response-body content."""

    resolved_location: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    content_length: int | None = None
    bytes_received: int | None = None
    etag: str | None = None
    last_modified: str | None = None

    def __post_init__(self) -> None:
        _optional_text(self.resolved_location, "resolved_location", 8192)
        _optional_text(self.content_type, "content_type", 255)
        _optional_text(self.etag, "etag", 2048)
        _optional_text(self.last_modified, "last_modified", 2048)
        if self.status_code is not None and (
            not isinstance(self.status_code, int)
            or isinstance(self.status_code, bool)
            or not 100 <= self.status_code <= 599
        ):
            raise ProvenanceError("status_code must be an HTTP status or None")
        _nonnegative(self.content_length, "content_length")
        _nonnegative(self.bytes_received, "bytes_received")


@dataclass(frozen=True)
class ArtifactProvenance:
    """Immutable metadata for one exact source-scoped byte sequence."""

    artifact_id: str
    source_id: str
    sha256_checksum: str
    byte_size: int
    storage_key: str
    first_retrieval_run_id: str
    first_retrieved_at: str
    identifier_version: IdentifierVersion = "portfolio-v2"
    content_type: str | None = None

    def __post_init__(self) -> None:
        validate_source_id(self.source_id)
        validate_sha256(self.sha256_checksum, field_name="sha256_checksum")
        _nonnegative(self.byte_size, "byte_size")
        if self.byte_size == 0:
            raise ProvenanceError("byte_size must be positive for an artifact")
        validate_retrieval_run_id(self.first_retrieval_run_id)
        _timestamp(self.first_retrieved_at, "first_retrieved_at")
        _optional_text(self.content_type, "content_type", 255)
        expected_id = artifact_id_for_version(
            self.source_id,
            self.sha256_checksum,
            identifier_version=self.identifier_version,
        )
        if self.artifact_id != expected_id:
            raise ProvenanceError("artifact_id is inconsistent with its versioned inputs")
        if self.storage_key != artifact_storage_key(
            self.source_id, self.sha256_checksum
        ):
            raise ProvenanceError("storage_key is inconsistent with artifact content")


@dataclass(frozen=True)
class RetrievalRun:
    """One source retrieval attempt, independent of its persistence adapter."""

    retrieval_run_id: str
    source_id: str
    requested_location: str
    retrieval_started_at: str
    request_method: str
    retrieval_status: RetrievalStatus = "started"
    content_outcome: ContentOutcome | None = None
    response: RetrievalResponse = RetrievalResponse()
    retrieval_completed_at: str | None = None
    artifact_id: str | None = None
    error_code: str | None = None
    redacted_error_message: str | None = None

    def __post_init__(self) -> None:
        validate_retrieval_run_id(self.retrieval_run_id)
        validate_source_id(self.source_id)
        _text(self.requested_location, "requested_location", 8192)
        _timestamp(self.retrieval_started_at, "retrieval_started_at")
        if _METHOD.fullmatch(self.request_method) is None:
            raise ProvenanceError("request_method is invalid")
        if not isinstance(self.response, RetrievalResponse):
            raise ProvenanceError("response must be RetrievalResponse")
        if self.retrieval_completed_at is not None:
            _timestamp(self.retrieval_completed_at, "retrieval_completed_at")
            if self.retrieval_completed_at < self.retrieval_started_at:
                raise ProvenanceError("retrieval completion precedes retrieval start")
        if self.artifact_id is not None and re.fullmatch(
            r"artifact_[0-9a-f]{64}", self.artifact_id
        ) is None:
            raise ProvenanceError("artifact_id format is invalid")
        if self.error_code is not None and _ERROR_CODE.fullmatch(self.error_code) is None:
            raise ProvenanceError("error_code is invalid")
        _optional_text(
            self.redacted_error_message, "redacted_error_message", 1024
        )
        if self.retrieval_status == "started":
            if any(
                value is not None
                for value in (
                    self.content_outcome,
                    self.retrieval_completed_at,
                    self.artifact_id,
                    self.error_code,
                    self.redacted_error_message,
                )
            ):
                raise ProvenanceError("started retrieval contains terminal metadata")
        elif self.retrieval_status == "succeeded":
            if self.retrieval_completed_at is None or self.content_outcome not in (
                "new_artifact",
                "known_artifact",
                "not_modified",
            ):
                raise ProvenanceError("succeeded retrieval lacks terminal metadata")
            if (
                self.content_outcome in ("new_artifact", "known_artifact")
                and self.artifact_id is None
            ) or (
                self.content_outcome == "not_modified" and self.artifact_id is not None
            ):
                raise ProvenanceError("succeeded retrieval artifact metadata is inconsistent")
            if self.error_code is not None or self.redacted_error_message is not None:
                raise ProvenanceError("succeeded retrieval contains failure metadata")
        elif self.retrieval_status == "failed":
            if (
                self.retrieval_completed_at is None
                or self.content_outcome != "no_artifact"
                or self.artifact_id is not None
                or self.error_code is None
                or self.redacted_error_message is None
            ):
                raise ProvenanceError("failed retrieval metadata is inconsistent")
        else:
            raise ProvenanceError("retrieval_status is invalid")


def start_retrieval(
    source_id: str,
    requested_location: str,
    *,
    retrieval_run_id: str | None = None,
    retrieval_started_at: str | None = None,
    request_method: str = "GET",
) -> RetrievalRun:
    return RetrievalRun(
        retrieval_run_id=retrieval_run_id or new_retrieval_run_id(),
        source_id=source_id,
        requested_location=requested_location,
        retrieval_started_at=retrieval_started_at or utc_now_text(),
        request_method=request_method,
    )


def complete_retrieval(
    run: RetrievalRun,
    *,
    content_outcome: Literal["new_artifact", "known_artifact", "not_modified"],
    response: RetrievalResponse,
    retrieval_completed_at: str,
    artifact_id: str | None = None,
) -> RetrievalRun:
    if run.retrieval_status != "started":
        raise ProvenanceError("only a started retrieval can complete")
    if content_outcome in ("new_artifact", "known_artifact") and artifact_id is None:
        raise ProvenanceError("artifact outcome requires artifact_id")
    if content_outcome == "not_modified" and artifact_id is not None:
        raise ProvenanceError("not_modified must not assign a new artifact")
    return replace(
        run,
        retrieval_status="succeeded",
        content_outcome=content_outcome,
        response=response,
        retrieval_completed_at=retrieval_completed_at,
        artifact_id=artifact_id,
    )


def fail_retrieval(
    run: RetrievalRun,
    *,
    error_code: str,
    redacted_error_message: str,
    retrieval_completed_at: str,
    response: RetrievalResponse | None = None,
) -> RetrievalRun:
    if run.retrieval_status != "started":
        raise ProvenanceError("only a started retrieval can fail")
    return replace(
        run,
        retrieval_status="failed",
        content_outcome="no_artifact",
        response=response or RetrievalResponse(),
        retrieval_completed_at=retrieval_completed_at,
        error_code=error_code,
        redacted_error_message=redacted_error_message,
    )


@dataclass(frozen=True)
class ExtractionRun:
    """Source-neutral extraction lifecycle metadata; payloads remain domain-owned."""

    extraction_batch_id: str
    source_id: str
    artifact_id: str
    extractor_name: str
    extractor_version: str
    output_contract_version: str
    extraction_config_hash: str
    extraction_started_at: str
    extraction_status: ExtractionStatus = "started"
    extraction_completed_at: str | None = None
    records_emitted: int = 0
    issues_emitted: int = 0

    def __post_init__(self) -> None:
        validate_source_id(self.source_id)
        if _ARTIFACT_IDENTIFIER.fullmatch(self.artifact_id) is None:
            raise ProvenanceError("artifact_id format is invalid")
        validate_sha256(
            self.extraction_config_hash, field_name="extraction_config_hash"
        )
        for field_name in (
            "extractor_name",
            "extractor_version",
            "output_contract_version",
        ):
            _text(getattr(self, field_name), field_name, 128)
        _timestamp(self.extraction_started_at, "extraction_started_at")
        expected = extraction_batch_id_v2(
            self.artifact_id,
            self.extractor_name,
            self.extractor_version,
            self.output_contract_version,
            self.extraction_config_hash,
        )
        if self.extraction_batch_id != expected:
            raise ProvenanceError("extraction_batch_id is inconsistent")
        _nonnegative(self.records_emitted, "records_emitted")
        _nonnegative(self.issues_emitted, "issues_emitted")
        if self.extraction_status == "started":
            if (
                self.extraction_completed_at is not None
                or self.records_emitted != 0
                or self.issues_emitted != 0
            ):
                raise ProvenanceError("started extraction contains terminal metadata")
        elif self.extraction_status in ("succeeded", "partial", "failed"):
            if self.extraction_completed_at is None:
                raise ProvenanceError("terminal extraction lacks completion timestamp")
            _timestamp(self.extraction_completed_at, "extraction_completed_at")
            if self.extraction_completed_at < self.extraction_started_at:
                raise ProvenanceError("extraction completion precedes extraction start")
            if self.extraction_status == "failed" and self.records_emitted != 0:
                raise ProvenanceError("failed extraction cannot emit records")
        else:
            raise ProvenanceError("extraction_status is invalid")


def start_extraction(
    source_id: str,
    artifact_id: str,
    extractor_name: str,
    extractor_version: str,
    output_contract_version: str,
    extraction_config_hash: str,
    *,
    extraction_started_at: str | None = None,
) -> ExtractionRun:
    batch_id = extraction_batch_id_v2(
        artifact_id,
        extractor_name,
        extractor_version,
        output_contract_version,
        extraction_config_hash,
    )
    return ExtractionRun(
        extraction_batch_id=batch_id,
        source_id=source_id,
        artifact_id=artifact_id,
        extractor_name=extractor_name,
        extractor_version=extractor_version,
        output_contract_version=output_contract_version,
        extraction_config_hash=extraction_config_hash,
        extraction_started_at=extraction_started_at or utc_now_text(),
    )


def finish_extraction(
    run: ExtractionRun,
    *,
    status: Literal["succeeded", "partial", "failed"],
    extraction_completed_at: str,
    records_emitted: int,
    issues_emitted: int,
) -> ExtractionRun:
    if run.extraction_status != "started":
        raise ProvenanceError("only a started extraction can finish")
    return replace(
        run,
        extraction_status=status,
        extraction_completed_at=extraction_completed_at,
        records_emitted=records_emitted,
        issues_emitted=issues_emitted,
    )
