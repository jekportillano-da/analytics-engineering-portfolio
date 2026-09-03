"""Adapt the existing governed metric contract to the vector-ready boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from analytics_platform.platform.vector_ready.contracts import (
    SourceLineage,
    VectorReadyContractError,
    VectorReadyDocument,
)


GOVERNED_METRIC_SOURCE_ID = "governed_metrics"
GOVERNED_METRIC_DOCUMENT_TYPE = "governed_metric_definition"


def _required_text(values: Mapping[str, Any], field: str) -> str:
    value = values.get(field)
    if not isinstance(value, str) or not value.strip():
        raise VectorReadyContractError(f"governed metric {field} must be nonempty text")
    return value


def _semantic_content(metric: Mapping[str, Any]) -> str:
    dimensions = metric.get("valid_dimension_sets")
    if not isinstance(dimensions, list) or not dimensions:
        raise VectorReadyContractError(
            "governed metric valid_dimension_sets must be a nonempty list"
        )
    lines = [
        f"Metric: {_required_text(metric, 'metric_id')}",
        f"Definition: {_required_text(metric, 'definition')}",
        f"Aggregation behavior: {_required_text(metric, 'aggregation_behavior')}",
        "Valid dimensions: "
        + json.dumps(dimensions, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        f"Limitations: {_required_text(metric, 'limitations')}",
    ]
    for field, label in (
        ("filter", "Source filter"),
        ("numerator", "Numerator"),
        ("denominator", "Denominator"),
    ):
        value = metric.get(field)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise VectorReadyContractError(f"governed metric {field} is invalid")
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def documents_from_governed_metric_contract(
    contract: Mapping[str, Any],
    *,
    source_path: str = "contracts/metrics/v1/governed_metrics.yml",
) -> tuple[VectorReadyDocument, ...]:
    """Create one canonical document per existing governed metric definition."""

    if contract.get("contract_version") != 1:
        raise VectorReadyContractError("unsupported governed metric contract version")
    contract_id = _required_text(contract, "contract_id")
    metrics = contract.get("metrics")
    freshness = contract.get("freshness_contracts")
    if not isinstance(metrics, list) or not isinstance(freshness, Mapping):
        raise VectorReadyContractError("governed metric contract structure is invalid")

    documents: list[VectorReadyDocument] = []
    seen_metric_ids: set[str] = set()
    for raw_metric in metrics:
        if not isinstance(raw_metric, Mapping):
            raise VectorReadyContractError("governed metric entries must be mappings")
        metric_id = _required_text(raw_metric, "metric_id")
        if metric_id in seen_metric_ids:
            raise VectorReadyContractError("governed metric IDs must be unique")
        seen_metric_ids.add(metric_id)
        domain = _required_text(raw_metric, "domain")
        source_model = _required_text(raw_metric, "source_model")
        domain_freshness = freshness.get(domain)
        if not isinstance(domain_freshness, Mapping):
            raise VectorReadyContractError(
                f"governed metric domain {domain!r} lacks reference context"
            )
        reference_period = _required_text(domain_freshness, "reference_period")

        metadata: dict[str, str | int | float | bool | None] = {
            "aggregation_behavior": _required_text(
                raw_metric, "aggregation_behavior"
            ),
            "contract_id": contract_id,
            "contract_version": 1,
            "domain": domain,
            "document_type": GOVERNED_METRIC_DOCUMENT_TYPE,
            "metric_id": metric_id,
            "source_model": source_model,
            "value_field": _required_text(raw_metric, "value_field"),
        }
        reference_context: dict[str, str | int | float | bool | None] = {
            "reference_period": reference_period
        }
        for field in ("reference_year", "time_grain"):
            value = raw_metric.get(field)
            if value is not None:
                if not isinstance(value, (str, int)) or isinstance(value, bool):
                    raise VectorReadyContractError(
                        f"governed metric {field} must be text or an integer"
                    )
                metadata[field] = value
                reference_context[field] = value

        lineage = SourceLineage(
            source_id=GOVERNED_METRIC_SOURCE_ID,
            source_locator=f"{source_path}#{metric_id}",
            source_record_id=metric_id,
            source_contract_id=contract_id,
            source_relation=source_model,
        )
        documents.append(
            VectorReadyDocument.create(
                domain=domain,
                document_type=GOVERNED_METRIC_DOCUMENT_TYPE,
                content=_semantic_content(raw_metric),
                metadata=metadata,
                lineage=lineage,
                reference_context=reference_context,
            )
        )
    return tuple(sorted(documents, key=lambda document: document.document_id))
