"""Protocols for future embedding and vector-store adapters; no adapters are active."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from analytics_platform.platform.vector_ready.contracts import (
    MetadataScalar,
    VectorReadyDocument,
)


@dataclass(frozen=True)
class EmbeddingModelProvenance:
    """Identity of the provider/model that produced an embedding vector."""

    provider_id: str
    model_id: str
    model_version: str
    dimensions: int


@dataclass(frozen=True)
class EmbeddedDocument:
    """Provider-independent result passed from embedding to vector storage."""

    document_id: str
    values: tuple[float, ...]
    metadata: Mapping[str, MetadataScalar]
    model: EmbeddingModelProvenance


@dataclass(frozen=True)
class VectorMatch:
    """Provider-independent semantic query result."""

    document_id: str
    score: float
    metadata: Mapping[str, MetadataScalar]


class EmbeddingProvider(Protocol):
    """Extension point for a future embedding implementation."""

    @property
    def model_provenance(self) -> EmbeddingModelProvenance: ...

    def embed(
        self, documents: Sequence[VectorReadyDocument]
    ) -> Sequence[EmbeddedDocument]: ...


class VectorStore(Protocol):
    """Smallest storage boundary needed for indexing and semantic retrieval."""

    def upsert(self, records: Sequence[EmbeddedDocument]) -> None: ...

    def query(
        self,
        values: Sequence[float],
        *,
        top_k: int,
        metadata_filter: Mapping[str, MetadataScalar] | None = None,
    ) -> Sequence[VectorMatch]: ...

    def delete(self, document_ids: Sequence[str]) -> None: ...
