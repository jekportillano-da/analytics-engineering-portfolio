"""Inactive, vendor-neutral extension contracts for future semantic retrieval."""

from analytics_platform.platform.vector_ready.contracts import (
    VECTOR_READY_CONTRACT_ID,
    VECTOR_READY_CONTRACT_VERSION,
    SourceLineage,
    VectorReadyDocument,
)
from analytics_platform.platform.vector_ready.interfaces import (
    EmbeddedDocument,
    EmbeddingModelProvenance,
    EmbeddingProvider,
    VectorMatch,
    VectorStore,
)

__all__ = (
    "EmbeddedDocument",
    "EmbeddingModelProvenance",
    "EmbeddingProvider",
    "SourceLineage",
    "VECTOR_READY_CONTRACT_ID",
    "VECTOR_READY_CONTRACT_VERSION",
    "VectorMatch",
    "VectorReadyDocument",
    "VectorStore",
)
