"""Pure transformation from governed snapshots and contracts to presentation JSON."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from analytics_platform.presentation.contract import (
    ARTIFACT_TYPES,
    PRESENTATION_CONTRACT_ID,
    PRESENTATION_CONTRACT_VERSION,
    PresentationContractError,
    load_json,
)
from analytics_platform.presentation.insights import (
    build_executive_insight_data,
    validate_insight_artifact,
)


GOVERNED_SNAPSHOT_VERSION = 1


def load_metric_contract(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise PresentationContractError(f"cannot load governed metric contract: {path}") from exc
    if not isinstance(value, dict) or value.get("contract_version") != 1:
        raise PresentationContractError("unsupported governed metric contract")
    return value


def load_governed_snapshot(path: Path) -> dict[str, object]:
    snapshot = load_json(path)
    if snapshot.get("snapshot_version") != GOVERNED_SNAPSHOT_VERSION:
        raise PresentationContractError("unsupported governed snapshot version")
    required = {
        "governance",
        "people",
        "snapshot_version",
        "source_contracts",
        "source_relations",
        "wage",
    }
    if set(snapshot) != required:
        raise PresentationContractError("governed snapshot has an invalid envelope")
    for field in ("people", "wage"):
        if not isinstance(snapshot[field], dict):
            raise PresentationContractError(f"snapshot {field} data must be an object")
    if not isinstance(snapshot["governance"], list):
        raise PresentationContractError("snapshot governance data must be a list")
    return snapshot


def _metric_definitions(
    contract: Mapping[str, Any], domain: str
) -> list[dict[str, object]]:
    metrics = contract.get("metrics")
    if not isinstance(metrics, list):
        raise PresentationContractError("governed metric list is invalid")
    fields = (
        "aggregation_behavior",
        "definition",
        "denominator",
        "filter",
        "limitations",
        "metric_id",
        "numerator",
        "reference_year",
        "source_model",
        "time_field",
        "time_grain",
        "valid_dimension_sets",
        "value_field",
    )
    definitions: list[dict[str, object]] = []
    for metric in metrics:
        if not isinstance(metric, dict) or metric.get("domain") != domain:
            continue
        definition = {field: metric[field] for field in fields if field in metric}
        definition["domain"] = domain
        definitions.append(definition)
    if not definitions:
        raise PresentationContractError(f"no governed metrics found for {domain}")
    return sorted(definitions, key=lambda item: str(item["metric_id"]))


def _artifact(artifact_type: str, data: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_id": f"presentation.{artifact_type}.v1",
        "artifact_type": artifact_type,
        "contract_id": PRESENTATION_CONTRACT_ID,
        "contract_version": PRESENTATION_CONTRACT_VERSION,
        "data": data,
    }


def _architecture() -> dict[str, object]:
    nodes = [
        {"id": "sources", "label": "Domain sources", "status": "active"},
        {"id": "ingestion", "label": "Validated ingestion", "status": "active"},
        {"id": "bigquery_raw", "label": "BigQuery raw", "status": "active"},
        {"id": "dbt", "label": "dbt staging / intermediate / marts", "status": "active"},
        {"id": "governed_products", "label": "Governed data products", "status": "active"},
        {"id": "presentation_contract", "label": "Presentation contract", "status": "active"},
        {"id": "insight_engine", "label": "Executive insight engine", "status": "active"},
        {"id": "nextjs", "label": "THREADLINE Next.js frontend", "status": "active"},
        {"id": "vercel", "label": "Vercel deployment", "status": "active"},
        {"id": "vector_ready", "label": "Vector-ready contract", "status": "optional_boundary"},
        {"id": "embedding", "label": "Embedding provider", "status": "deferred_optional"},
        {"id": "vector_store", "label": "Vector store", "status": "deferred_optional"},
        {"id": "semantic_consumer", "label": "Semantic / RAG / agent consumer", "status": "deferred_optional"},
    ]
    active_edges = [
        ("sources", "ingestion"),
        ("ingestion", "bigquery_raw"),
        ("bigquery_raw", "dbt"),
        ("dbt", "governed_products"),
        ("governed_products", "presentation_contract"),
        ("presentation_contract", "insight_engine"),
        ("insight_engine", "nextjs"),
        ("nextjs", "vercel"),
    ]
    optional_edges = [
        ("governed_products", "vector_ready"),
        ("vector_ready", "embedding"),
        ("embedding", "vector_store"),
        ("vector_store", "semantic_consumer"),
    ]
    edges = [
        {"from": source, "status": "active", "to": target}
        for source, target in active_edges
    ] + [
        {"from": source, "status": "deferred_optional", "to": target}
        for source, target in optional_edges
    ]
    return {"edges": edges, "nodes": nodes}


def build_presentation_artifacts(
    snapshot: Mapping[str, Any], metric_contract: Mapping[str, Any]
) -> dict[str, dict[str, object]]:
    """Build all artifacts without querying a source or recalculating a metric."""

    if snapshot.get("snapshot_version") != GOVERNED_SNAPSHOT_VERSION:
        raise PresentationContractError("unsupported governed snapshot version")
    people = snapshot.get("people")
    wage = snapshot.get("wage")
    governance = snapshot.get("governance")
    if not isinstance(people, dict) or not isinstance(wage, dict):
        raise PresentationContractError("governed domain snapshot is invalid")
    if not isinstance(governance, list):
        raise PresentationContractError("governance snapshot is invalid")
    source_contracts = snapshot.get("source_contracts")
    source_relations = snapshot.get("source_relations")
    if not isinstance(source_contracts, dict) or not isinstance(source_relations, dict):
        raise PresentationContractError("snapshot lineage metadata is invalid")

    people_definitions = _metric_definitions(metric_contract, "people")
    wage_definitions = _metric_definitions(metric_contract, "wage")
    freshness = metric_contract.get("freshness_contracts")
    if not isinstance(freshness, dict):
        raise PresentationContractError("freshness contract is invalid")

    capabilities = [
        {"id": "warehouse_analytics", "status": "active"},
        {"id": "dagster_orchestration", "status": "active"},
        {"id": "presentation_contract", "status": "active"},
        {"id": "executive_insight_engine", "status": "active"},
        {"id": "nextjs_frontend", "status": "active"},
        {"id": "vercel_deployment", "status": "active"},
        {"id": "vector_ready_contract", "status": "optional_boundary"},
        {"id": "embedding_generation", "status": "deferred_optional"},
        {"id": "vector_database", "status": "deferred_optional"},
        {"id": "rag_agent", "status": "deferred_optional"},
    ]
    artifacts = {
        "platform": _artifact(
            "platform",
            {
                "artifact_inventory": [f"presentation.{name}.v1" for name in ARTIFACT_TYPES],
                "capabilities": capabilities,
                "consumption_policy": {
                    "browser_bigquery_access": False,
                    "canonical_metric_calculation_in_frontend": False,
                    "frontend_role": "visualization_filtering_interaction_formatting",
                    "platform_role": "metrics_quality_reconciliation_provenance",
                },
                "data_products": [
                    {
                        "domain": "people",
                        "metric_count": len(people_definitions),
                        "source_relation": "metrics_people_monthly",
                    },
                    {
                        "domain": "wage",
                        "metric_count": len(wage_definitions),
                        "source_relation": "metrics_wage_published",
                    },
                ],
                "domain_count": 2,
                "snapshot_semantics": {
                    "live_data": False,
                    "refresh_mode": "explicit_governed_snapshot",
                },
            },
        ),
        "people": _artifact(
            "people",
            {
                "definitions": people_definitions,
                "limitations": [item["limitations"] for item in people_definitions],
                **people,
            },
        ),
        "wage": _artifact(
            "wage",
            {
                "definitions": wage_definitions,
                "limitations": [item["limitations"] for item in wage_definitions],
                **wage,
            },
        ),
        "quality": _artifact(
            "quality",
            {
                "freshness_contracts": freshness,
                "governance_checks": governance,
                "health_semantics": "point_in_time_from_governed_snapshot",
                "people_quality": people.get("quality"),
                "people_reconciliation": people.get("reconciliation"),
                "wage_reconciliation": wage.get("reconciliation"),
            },
        ),
        "lineage": _artifact(
            "lineage",
            {
                "architecture": _architecture(),
                "provenance": wage.get("provenance"),
                "source_contracts": source_contracts,
                "source_relations": source_relations,
            },
        ),
    }
    artifacts["insights"] = _artifact(
        "insights", build_executive_insight_data(artifacts)
    )
    validate_insight_artifact(artifacts["insights"], artifacts)
    if set(artifacts) != set(ARTIFACT_TYPES):
        raise PresentationContractError("incomplete presentation artifact set")
    return artifacts
