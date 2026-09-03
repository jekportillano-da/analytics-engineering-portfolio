"""Versioned deterministic identifiers for ingestion provenance."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Sequence
from typing import Literal, TypeAlias


LEGACY_IDENTIFIER_NAMESPACE = "budget-buddy-data-platform"
LEGACY_IDENTIFIER_VERSION = "identifier-v1"
PORTFOLIO_IDENTIFIER_NAMESPACE = "analytics-platform"
PORTFOLIO_IDENTIFIER_VERSION = "identifier-v2"

IdentifierVersion: TypeAlias = Literal["legacy-v1", "portfolio-v2"]

_SOURCE_ID = re.compile(r"^[a-z0-9_]+$")
_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ISSUE_CODE = re.compile(r"^[A-Z0-9_]+$")
_NONEMPTY_FIELDS = {
    "artifact_id",
    "extraction_batch_id",
    "extractor_name",
    "extractor_version",
    "output_contract_version",
    "source_record_locator",
}


class IdentifierError(ValueError):
    """Raised when an identifier input is not canonical."""


def validate_source_id(value: str) -> str:
    """Return a canonical controlled source identifier or raise."""

    if not isinstance(value, str) or _SOURCE_ID.fullmatch(value) is None:
        raise IdentifierError(
            "source_id must contain only lowercase ASCII letters, digits, and underscores"
        )
    return value


def validate_sha256(value: str, *, field_name: str = "sha256") -> str:
    """Return a canonical lowercase SHA-256 hex digest or raise."""

    if not isinstance(value, str) or _LOWERCASE_SHA256.fullmatch(value) is None:
        raise IdentifierError(f"{field_name} must be exactly 64 lowercase hex characters")
    return value


def _validate_type_prefixed_sha256(value: str, prefix: str, field_name: str) -> str:
    expected_prefix = f"{prefix}_"
    if not isinstance(value, str) or not value.startswith(expected_prefix):
        raise IdentifierError(f"{field_name} must start with {expected_prefix!r}")
    validate_sha256(value[len(expected_prefix) :], field_name=field_name)
    return value


def validate_artifact_id(value: str) -> str:
    """Return a canonical artifact identifier or raise."""

    return _validate_type_prefixed_sha256(value, "artifact", "artifact_id")


def validate_extraction_batch_id(value: str) -> str:
    """Return a canonical extraction-batch identifier or raise."""

    return _validate_type_prefixed_sha256(
        value, "extraction", "extraction_batch_id"
    )


def _encode_component(value: str) -> bytes:
    encoded = value.encode("utf-8", errors="strict")
    if len(encoded) > 0xFFFFFFFF:
        raise IdentifierError("canonical identifier component exceeds 4-byte length limit")
    return len(encoded).to_bytes(4, byteorder="big") + encoded


def _canonical_payload(
    namespace: str,
    version: str,
    identifier_kind: str,
    fields: Sequence[tuple[str, str | None]],
) -> bytes:
    """Serialize labeled values without delimiter or null/empty ambiguity."""

    payload = bytearray()
    for component in (namespace, version, identifier_kind):
        payload.extend(_encode_component(component))
    for field_name, value in fields:
        payload.extend(_encode_component(field_name))
        if value is None:
            payload.extend(b"\x00")
            continue
        if not isinstance(value, str):
            raise IdentifierError(f"{field_name} must be text or None")
        if field_name in _NONEMPTY_FIELDS and value == "":
            raise IdentifierError(f"{field_name} must not be empty")
        payload.extend(b"\x01")
        payload.extend(_encode_component(value))
    return bytes(payload)


def _deterministic_id(
    prefix: str,
    identifier_kind: str,
    fields: Sequence[tuple[str, str | None]],
    *,
    namespace: str,
    version: str,
) -> str:
    payload = _canonical_payload(namespace, version, identifier_kind, fields)
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()}"


def new_retrieval_run_id() -> str:
    """Create a unique identifier for one retrieval attempt."""

    return f"retrieval_{uuid.uuid4()}"


def validate_retrieval_run_id(value: str) -> str:
    """Return a canonical type-prefixed UUIDv4 retrieval identifier or raise."""

    prefix = "retrieval_"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise IdentifierError(f"retrieval_run_id must start with {prefix!r}")
    suffix = value[len(prefix) :]
    try:
        parsed = uuid.UUID(suffix)
    except (AttributeError, ValueError) as exc:
        raise IdentifierError("retrieval_run_id must contain a canonical UUIDv4") from exc
    if parsed.version != 4 or parsed.variant != uuid.RFC_4122 or str(parsed) != suffix:
        raise IdentifierError("retrieval_run_id must contain a canonical UUIDv4")
    return value


def _artifact_id(
    source_id: str,
    sha256_checksum: str,
    *,
    namespace: str,
    version: str,
) -> str:
    validate_source_id(source_id)
    validate_sha256(sha256_checksum, field_name="sha256_checksum")
    return _deterministic_id(
        "artifact",
        "artifact",
        (("source_id", source_id), ("sha256_checksum", sha256_checksum)),
        namespace=namespace,
        version=version,
    )


def legacy_artifact_id_v1(source_id: str, sha256_checksum: str) -> str:
    """Reproduce the immutable Budget Buddy v1 artifact identity exactly."""

    return _artifact_id(
        source_id,
        sha256_checksum,
        namespace=LEGACY_IDENTIFIER_NAMESPACE,
        version=LEGACY_IDENTIFIER_VERSION,
    )


def artifact_id_v2(source_id: str, sha256_checksum: str) -> str:
    """Derive a source-neutral v2 artifact identity from exact content bytes."""

    return _artifact_id(
        source_id,
        sha256_checksum,
        namespace=PORTFOLIO_IDENTIFIER_NAMESPACE,
        version=PORTFOLIO_IDENTIFIER_VERSION,
    )


def artifact_id_for_version(
    source_id: str,
    sha256_checksum: str,
    *,
    identifier_version: IdentifierVersion,
) -> str:
    """Derive an artifact identity with an explicit persisted version."""

    if identifier_version == "legacy-v1":
        return legacy_artifact_id_v1(source_id, sha256_checksum)
    if identifier_version == "portfolio-v2":
        return artifact_id_v2(source_id, sha256_checksum)
    raise IdentifierError("identifier_version is not supported")


def _extraction_batch_id(
    artifact_id: str,
    extractor_name: str,
    extractor_version: str,
    output_contract_version: str,
    extraction_config_hash: str,
    *,
    namespace: str,
    version: str,
) -> str:
    _validate_type_prefixed_sha256(artifact_id, "artifact", "artifact_id")
    validate_sha256(extraction_config_hash, field_name="extraction_config_hash")
    return _deterministic_id(
        "extraction",
        "extraction_batch",
        (
            ("artifact_id", artifact_id),
            ("extractor_name", extractor_name),
            ("extractor_version", extractor_version),
            ("output_contract_version", output_contract_version),
            ("extraction_config_hash", extraction_config_hash),
        ),
        namespace=namespace,
        version=version,
    )


def legacy_extraction_batch_id_v1(
    artifact_id: str,
    extractor_name: str,
    extractor_version: str,
    output_contract_version: str,
    extraction_config_hash: str,
) -> str:
    """Reproduce the immutable Budget Buddy v1 extraction identity exactly."""

    return _extraction_batch_id(
        artifact_id,
        extractor_name,
        extractor_version,
        output_contract_version,
        extraction_config_hash,
        namespace=LEGACY_IDENTIFIER_NAMESPACE,
        version=LEGACY_IDENTIFIER_VERSION,
    )


def extraction_batch_id_v2(
    artifact_id: str,
    extractor_name: str,
    extractor_version: str,
    output_contract_version: str,
    extraction_config_hash: str,
) -> str:
    """Derive a source-neutral v2 identity from every output-affecting input."""

    return _extraction_batch_id(
        artifact_id,
        extractor_name,
        extractor_version,
        output_contract_version,
        extraction_config_hash,
        namespace=PORTFOLIO_IDENTIFIER_NAMESPACE,
        version=PORTFOLIO_IDENTIFIER_VERSION,
    )


def _extraction_issue_id(
    extraction_batch_id: str,
    issue_code: str,
    source_record_locator: str | None,
    occurrence_ordinal: int,
    *,
    namespace: str,
    version: str,
) -> str:
    _validate_type_prefixed_sha256(
        extraction_batch_id, "extraction", "extraction_batch_id"
    )
    if not isinstance(issue_code, str) or _ISSUE_CODE.fullmatch(issue_code) is None:
        raise IdentifierError(
            "issue_code must contain only uppercase ASCII letters, digits, and underscores"
        )
    if (
        not isinstance(occurrence_ordinal, int)
        or isinstance(occurrence_ordinal, bool)
        or occurrence_ordinal <= 0
    ):
        raise IdentifierError("occurrence_ordinal must be a positive integer")
    return _deterministic_id(
        "issue",
        "extraction_issue",
        (
            ("extraction_batch_id", extraction_batch_id),
            ("issue_code", issue_code),
            ("source_record_locator", source_record_locator),
            ("occurrence_ordinal", str(occurrence_ordinal)),
        ),
        namespace=namespace,
        version=version,
    )


def legacy_extraction_issue_id_v1(
    extraction_batch_id: str,
    issue_code: str,
    source_record_locator: str | None,
    occurrence_ordinal: int,
) -> str:
    """Reproduce the immutable Budget Buddy v1 issue identity exactly."""

    return _extraction_issue_id(
        extraction_batch_id,
        issue_code,
        source_record_locator,
        occurrence_ordinal,
        namespace=LEGACY_IDENTIFIER_NAMESPACE,
        version=LEGACY_IDENTIFIER_VERSION,
    )


def extraction_issue_id_v2(
    extraction_batch_id: str,
    issue_code: str,
    source_record_locator: str | None,
    occurrence_ordinal: int,
) -> str:
    """Derive a stable v2 identity for one ordered issue occurrence."""

    return _extraction_issue_id(
        extraction_batch_id,
        issue_code,
        source_record_locator,
        occurrence_ordinal,
        namespace=PORTFOLIO_IDENTIFIER_NAMESPACE,
        version=PORTFOLIO_IDENTIFIER_VERSION,
    )


def _raw_record_id(
    extraction_batch_id: str,
    source_record_locator: str,
    *,
    namespace: str,
    version: str,
) -> str:
    _validate_type_prefixed_sha256(
        extraction_batch_id, "extraction", "extraction_batch_id"
    )
    return _deterministic_id(
        "raw",
        "raw_record",
        (
            ("extraction_batch_id", extraction_batch_id),
            ("source_record_locator", source_record_locator),
        ),
        namespace=namespace,
        version=version,
    )


def legacy_raw_record_id_v1(
    extraction_batch_id: str, source_record_locator: str
) -> str:
    """Reproduce the immutable Budget Buddy v1 raw-record identity exactly."""

    return _raw_record_id(
        extraction_batch_id,
        source_record_locator,
        namespace=LEGACY_IDENTIFIER_NAMESPACE,
        version=LEGACY_IDENTIFIER_VERSION,
    )


def raw_record_id_v2(extraction_batch_id: str, source_record_locator: str) -> str:
    """Derive a raw-record v2 identity from a batch and stable locator."""

    return _raw_record_id(
        extraction_batch_id,
        source_record_locator,
        namespace=PORTFOLIO_IDENTIFIER_NAMESPACE,
        version=PORTFOLIO_IDENTIFIER_VERSION,
    )


def vector_document_id_v1(
    domain: str,
    document_type: str,
    source_id: str,
    source_record_id: str,
) -> str:
    """Derive a stable identity for one logical vector-ready document."""

    validate_source_id(domain)
    validate_source_id(document_type)
    validate_source_id(source_id)
    if (
        not isinstance(source_record_id, str)
        or source_record_id == ""
        or source_record_id.strip() != source_record_id
    ):
        raise IdentifierError("source_record_id must be canonical nonempty text")
    return _deterministic_id(
        "document",
        "vector_ready_document",
        (
            ("domain", domain),
            ("document_type", document_type),
            ("source_id", source_id),
            ("source_record_id", source_record_id),
        ),
        namespace=PORTFOLIO_IDENTIFIER_NAMESPACE,
        version="vector-ready-document-identity-v1",
    )
