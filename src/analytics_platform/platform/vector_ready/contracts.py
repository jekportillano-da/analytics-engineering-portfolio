"""Versioned, vendor-neutral contracts for content eligible for future embedding."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias

from analytics_platform.platform.provenance.identifiers import (
    validate_artifact_id,
    validate_extraction_batch_id,
    validate_retrieval_run_id,
    validate_source_id,
    vector_document_id_v1,
)


VECTOR_READY_CONTRACT_VERSION = 1
VECTOR_READY_CONTRACT_ID = "analytics-portfolio-vector-ready-document-v1"

MetadataScalar: TypeAlias = str | int | float | bool | None

_METADATA_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class VectorReadyContractError(ValueError):
    """Raised when a vector-ready document is not canonical or version-compatible."""


def _canonical_text(value: str, field_name: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or value == ""
        or value.strip() != value
        or len(value) > maximum
        or "\r" in value
        or any(ord(character) < 32 and character not in "\n\t" for character in value)
        or any(ord(character) == 127 for character in value)
    ):
        raise VectorReadyContractError(f"{field_name} is not canonical text")
    return value


def _optional_text(value: str | None, field_name: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _canonical_text(value, field_name, maximum)


def _frozen_scalar_mapping(
    values: Mapping[str, MetadataScalar], field_name: str
) -> Mapping[str, MetadataScalar]:
    if not isinstance(values, Mapping):
        raise VectorReadyContractError(f"{field_name} must be a mapping")
    canonical: dict[str, MetadataScalar] = {}
    for key, value in values.items():
        if not isinstance(key, str) or _METADATA_KEY.fullmatch(key) is None:
            raise VectorReadyContractError(
                f"{field_name} keys must be lowercase filter-safe identifiers"
            )
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise VectorReadyContractError(
                f"{field_name} values must be scalar JSON values"
            )
        if isinstance(value, str):
            _canonical_text(value, f"{field_name}.{key}", 4096)
        if isinstance(value, float) and not math.isfinite(value):
            raise VectorReadyContractError(
                f"{field_name}.{key} must be a finite number"
            )
        canonical[key] = value
    return MappingProxyType(dict(sorted(canonical.items())))


@dataclass(frozen=True)
class SourceLineage:
    """Pointers to authoritative upstream lineage; identifiers are never regenerated here."""

    source_id: str
    source_locator: str
    source_record_id: str
    source_contract_id: str | None = None
    source_relation: str | None = None
    source_artifact_id: str | None = None
    retrieval_id: str | None = None
    extraction_id: str | None = None
    identifier_version: str | None = None

    def __post_init__(self) -> None:
        validate_source_id(self.source_id)
        _canonical_text(self.source_locator, "source_locator", 8192)
        _canonical_text(self.source_record_id, "source_record_id", 2048)
        _optional_text(self.source_contract_id, "source_contract_id", 256)
        _optional_text(self.source_relation, "source_relation", 1024)
        _optional_text(self.identifier_version, "identifier_version", 128)
        if self.source_artifact_id is not None:
            validate_artifact_id(self.source_artifact_id)
        if self.retrieval_id is not None:
            validate_retrieval_run_id(self.retrieval_id)
        if self.extraction_id is not None:
            validate_extraction_batch_id(self.extraction_id)

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class VectorReadyDocument:
    """Canonical governed content before any embedding or vector-store operation."""

    document_id: str
    domain: str
    document_type: str
    content: str
    metadata: Mapping[str, MetadataScalar]
    lineage: SourceLineage
    reference_context: Mapping[str, MetadataScalar]
    contract_version: int = VECTOR_READY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != VECTOR_READY_CONTRACT_VERSION:
            raise VectorReadyContractError("unsupported vector-ready contract version")
        validate_source_id(self.domain)
        validate_source_id(self.document_type)
        _canonical_text(self.content, "content", 100_000)
        if not isinstance(self.lineage, SourceLineage):
            raise VectorReadyContractError("lineage must be SourceLineage")
        expected_id = vector_document_id_v1(
            self.domain,
            self.document_type,
            self.lineage.source_id,
            self.lineage.source_record_id,
        )
        if self.document_id != expected_id:
            raise VectorReadyContractError(
                "document_id is inconsistent with its stable lineage inputs"
            )
        object.__setattr__(
            self, "metadata", _frozen_scalar_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "reference_context",
            _frozen_scalar_mapping(self.reference_context, "reference_context"),
        )

    @classmethod
    def create(
        cls,
        *,
        domain: str,
        document_type: str,
        content: str,
        metadata: Mapping[str, MetadataScalar],
        lineage: SourceLineage,
        reference_context: Mapping[str, MetadataScalar],
    ) -> "VectorReadyDocument":
        return cls(
            document_id=vector_document_id_v1(
                domain,
                document_type,
                lineage.source_id,
                lineage.source_record_id,
            ),
            domain=domain,
            document_type=document_type,
            content=content,
            metadata=metadata,
            lineage=lineage,
            reference_context=reference_context,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "document_id": self.document_id,
            "domain": self.domain,
            "document_type": self.document_type,
            "content": self.content,
            "metadata": dict(self.metadata),
            "lineage": self.lineage.as_dict(),
            "reference_context": dict(self.reference_context),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
