from __future__ import annotations

import inspect
import json
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from analytics_platform.platform.vector_ready.contracts import (
    VECTOR_READY_CONTRACT_ID,
    VectorReadyContractError,
)
from analytics_platform.platform.vector_ready.governed_metrics import (
    documents_from_governed_metric_contract,
)
from analytics_platform.platform.vector_ready.interfaces import (
    EmbeddingProvider,
    VectorStore,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRIC_CONTRACT_PATH = (
    PROJECT_ROOT / "contracts" / "metrics" / "v1" / "governed_metrics.yml"
)
VECTOR_CONTRACT_PATH = (
    PROJECT_ROOT / "contracts" / "vector_ready" / "v1" / "document.yml"
)


def _load_yaml(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    assert isinstance(value, dict)
    return value


def _documents():
    return documents_from_governed_metric_contract(_load_yaml(METRIC_CONTRACT_PATH))


def test_document_contract_manifest_matches_canonical_record() -> None:
    manifest = _load_yaml(VECTOR_CONTRACT_PATH)
    document = _documents()[0]

    assert manifest["contract_version"] == 1
    assert manifest["contract_id"] == VECTOR_READY_CONTRACT_ID
    assert manifest["status"] == "inactive_extension_boundary"
    assert set(manifest["fields"]) == set(document.as_dict())
    assert manifest["serving"] == {
        "embedding_active": False,
        "vector_store_active": False,
        "vendor": None,
    }


def test_governed_documents_have_stable_ids_and_serialization() -> None:
    first = _documents()
    second = _documents()

    assert len(first) == 8
    assert [item.document_id for item in first] == [item.document_id for item in second]
    assert [item.canonical_json() for item in first] == [
        item.canonical_json() for item in second
    ]
    for document in first:
        assert document.document_id.startswith("document_")
        assert json.loads(document.canonical_json()) == document.as_dict()
        assert list(document.metadata) == sorted(document.metadata)
        with pytest.raises(TypeError):
            document.metadata["mutated"] = True


def test_people_metric_contract_adapts_without_changing_semantics() -> None:
    document = next(
        item for item in _documents() if item.metadata["metric_id"] == "people.attrition_rate"
    )

    assert document.domain == "people"
    assert document.metadata["source_model"] == "metrics_people_monthly"
    assert document.metadata["time_grain"] == "month"
    assert document.reference_context == {
        "reference_period": "synthetic analysis window 2023-01-01 through 2025-12-31",
        "time_grain": "month",
    }
    assert document.lineage.source_contract_id == (
        "analytics-portfolio-governed-metrics-v1"
    )
    assert document.lineage.source_record_id == "people.attrition_rate"
    assert "Numerator: attrition_numerator" in document.content
    assert "Denominator: attrition_denominator" in document.content


def test_wage_metric_contract_adapts_with_source_grain_intact() -> None:
    document = next(
        item
        for item in _documents()
        if item.metadata["metric_id"] == "wage.benchmark_occupation_wage_rate"
    )

    assert document.domain == "wage"
    assert document.metadata["source_model"] == "metrics_wage_published"
    assert document.metadata["reference_year"] == 2024
    assert document.reference_context == {
        "reference_period": "PSA 2024 Occupational Wages Survey",
        "reference_year": 2024,
    }
    assert document.lineage.source_record_id == (
        "wage.benchmark_occupation_wage_rate"
    )
    assert "General Office Clerks" in document.content
    assert "Elementary Occupations" in document.content
    assert "Source filter: wage_measure_id = benchmark_wage_rate" in document.content


def test_contract_rejects_identity_version_and_metadata_drift() -> None:
    document = _documents()[0]

    with pytest.raises(VectorReadyContractError):
        replace(document, document_id="document_" + "0" * 64)
    with pytest.raises(VectorReadyContractError):
        replace(document, contract_version=2)
    with pytest.raises(VectorReadyContractError):
        replace(document, metadata={"nested": {"not": "filter-safe"}})


def test_interfaces_are_vendor_neutral_and_have_no_runtime_adapter() -> None:
    assert tuple(inspect.signature(EmbeddingProvider.embed).parameters) == (
        "self",
        "documents",
    )
    assert tuple(inspect.signature(VectorStore.upsert).parameters) == (
        "self",
        "records",
    )
    assert tuple(inspect.signature(VectorStore.query).parameters) == (
        "self",
        "values",
        "top_k",
        "metadata_filter",
    )
    assert tuple(inspect.signature(VectorStore.delete).parameters) == (
        "self",
        "document_ids",
    )

    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))
    dependencies = " ".join(project["project"]["dependencies"]).lower()
    for vendor in ("pinecone", "openai", "pgvector", "qdrant", "weaviate"):
        assert vendor not in dependencies
