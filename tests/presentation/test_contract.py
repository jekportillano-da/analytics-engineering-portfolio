from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from analytics_platform.presentation.cli import main
from analytics_platform.presentation.contract import (
    ARTIFACT_TYPES,
    PRESENTATION_CONTRACT_ID,
    canonical_json,
    validate_artifact_directory,
)
from analytics_platform.presentation.generator import (
    build_presentation_artifacts,
    load_governed_snapshot,
    load_metric_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "presentation" / "data"
SNAPSHOT_PATH = (
    PROJECT_ROOT / "presentation" / "source" / "v1" / "governed_snapshot.json"
)
METRIC_CONTRACT_PATH = (
    PROJECT_ROOT / "contracts" / "metrics" / "v1" / "governed_metrics.yml"
)
PRESENTATION_CONTRACT_PATH = (
    PROJECT_ROOT / "contracts" / "presentation" / "v1" / "presentation.yml"
)


def _artifacts() -> dict[str, dict[str, object]]:
    return validate_artifact_directory(DATA_DIR)


def test_versioned_contract_and_complete_artifact_set() -> None:
    contract = yaml.safe_load(PRESENTATION_CONTRACT_PATH.read_text("utf-8"))
    artifacts = _artifacts()

    assert contract["contract_version"] == 1
    assert contract["contract_id"] == PRESENTATION_CONTRACT_ID
    assert set(contract["artifacts"]) == {
        f"{artifact_type}.json" for artifact_type in ARTIFACT_TYPES
    }
    assert set(artifacts) == set(ARTIFACT_TYPES)
    assert {artifact["artifact_id"] for artifact in artifacts.values()} == {
        f"presentation.{artifact_type}.v1" for artifact_type in ARTIFACT_TYPES
    }


def test_generation_is_deterministic_and_matches_committed_artifacts(
    tmp_path: Path,
) -> None:
    snapshot = load_governed_snapshot(SNAPSHOT_PATH)
    metric_contract = load_metric_contract(METRIC_CONTRACT_PATH)
    first = build_presentation_artifacts(snapshot, metric_contract)
    second = build_presentation_artifacts(snapshot, metric_contract)

    assert {
        name: canonical_json(artifact) for name, artifact in first.items()
    } == {name: canonical_json(artifact) for name, artifact in second.items()}
    for artifact_type, artifact in first.items():
        assert (DATA_DIR / f"{artifact_type}.json").read_text("utf-8") == (
            canonical_json(artifact)
        )

    output_dir = tmp_path / "presentation"
    assert main(
        [
            "generate",
            "--snapshot",
            str(SNAPSHOT_PATH),
            "--metric-contract",
            str(METRIC_CONTRACT_PATH),
            "--output-dir",
            str(output_dir),
        ]
    ) == 0
    assert main(["validate", "--output-dir", str(output_dir)]) == 0


def test_people_artifact_preserves_governed_metrics_and_golden_summary() -> None:
    people = _artifacts()["people"]["data"]

    assert people["summary"] == {
        "daily_fact_count": 402141,
        "ending_headcount": 448,
        "event_count": 774,
        "monthly_period_count": 36,
        "quality_issue_count": 68,
    }
    assert len(people["monthly"]) == 36
    assert {item["metric_id"] for item in people["definitions"]} == {
        "people.attrition_rate",
        "people.ending_headcount",
        "people.hires",
        "people.separations",
    }
    attrition = next(
        item
        for item in people["definitions"]
        if item["metric_id"] == "people.attrition_rate"
    )
    assert attrition["numerator"] == "attrition_numerator"
    assert attrition["denominator"] == "attrition_denominator"
    assert people["reconciliation"]["summary"] == {
        "maximum_difference": 0,
        "period_count": 36,
        "reconciled_period_count": 36,
    }


def test_wage_artifact_preserves_source_grain_and_nonadditive_semantics() -> None:
    wage = _artifacts()["wage"]["data"]

    assert wage["summary"] == {
        "benchmark_observation_count": 114,
        "industry_category_count": 19,
        "industry_observation_count": 57,
        "ingestion_record_count": 8,
        "matrix_count": 4,
        "observation_count": 225,
        "regional_category_count": 18,
        "regional_observation_count": 54,
    }
    assert (len(wage["industry"]), len(wage["regional"])) == (19, 18)
    assert len(wage["benchmark_occupations"]) == 114
    assert {item["reference_year"] for item in wage["industry"]} == {2024}
    assert {item["reference_year"] for item in wage["regional"]} == {2024}
    assert {item["reference_year"] for item in wage["benchmark_occupations"]} == {
        2024
    }
    assert {
        item["aggregation_behavior"] for item in wage["definitions"]
    } == {"source_value_not_additive"}
    assert wage["reconciliation"]["summary"] == {
        "matrix_count": 4,
        "maximum_difference": 0,
        "reconciled_matrix_count": 4,
    }


def test_platform_lineage_distinguishes_active_planned_and_optional_paths() -> None:
    artifacts = _artifacts()
    platform = artifacts["platform"]["data"]
    lineage = artifacts["lineage"]["data"]

    assert platform["domain_count"] == 2
    assert platform["consumption_policy"] == {
        "browser_bigquery_access": False,
        "canonical_metric_calculation_in_frontend": False,
        "frontend_role": "visualization_filtering_interaction_formatting",
        "platform_role": "metrics_quality_reconciliation_provenance",
    }
    capability_status = {
        item["id"]: item["status"] for item in platform["capabilities"]
    }
    assert capability_status["warehouse_analytics"] == "active"
    assert capability_status["executive_insight_engine"] == "active"
    assert capability_status["nextjs_frontend"] == "planned"
    assert capability_status["vector_ready_contract"] == "optional_boundary"
    assert capability_status["embedding_generation"] == "deferred_optional"
    assert capability_status["vector_database"] == "deferred_optional"
    edge_statuses = {
        edge["status"] for edge in lineage["architecture"]["edges"]
    }
    assert edge_statuses == {"active", "planned", "deferred_optional"}
    assert {
        "from": "presentation_contract",
        "status": "active",
        "to": "insight_engine",
    } in lineage["architecture"]["edges"]
    assert {
        "from": "insight_engine",
        "status": "planned",
        "to": "nextjs",
    } in lineage["architecture"]["edges"]


def test_artifacts_are_frontend_safe_and_do_not_create_cross_domain_data() -> None:
    artifacts = _artifacts()
    serialized = "\n".join(canonical_json(item) for item in artifacts.values())
    serialized += SNAPSHOT_PATH.read_text("utf-8")

    assert not re.search(r'"[A-Za-z]:[\\/]', serialized)
    assert "/Users/" not in serialized
    assert "/home/" not in serialized
    assert "BEGIN PRIVATE KEY" not in serialized
    for forbidden in ('"password"', '"client_secret"', '"refresh_token"', '"api_key"'):
        assert forbidden not in serialized.lower()

    people = artifacts["people"]["data"]
    wage = artifacts["wage"]["data"]
    assert all(
        definition["metric_id"].startswith("people.")
        for definition in people["definitions"]
    )
    assert all(
        definition["metric_id"].startswith("wage.")
        for definition in wage["definitions"]
    )
    assert "worker_id" not in serialized
    assert "employment_id" not in serialized
    assert "people_wage" not in serialized


def test_quality_artifact_uses_existing_governance_controls() -> None:
    quality = _artifacts()["quality"]["data"]

    assert len(quality["governance_checks"]) == 5
    assert {item["check_type"] for item in quality["governance_checks"]} == {
        "freshness",
        "quality",
        "reconciliation",
    }
    assert set(quality["freshness_contracts"]) == {"people", "wage"}
    assert quality["people_quality"]["issue_count"] == 68
    assert quality["wage_reconciliation"]["summary"]["maximum_difference"] == 0


def test_public_ci_uses_only_local_reproducible_validation() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        "utf-8"
    )

    for required in (
        "python -m pytest",
        "analytics_platform.presentation.cli generate",
        "git diff --exit-code -- presentation/data",
        "--target local",
        "dagster definitions validate",
    ):
        assert required in workflow
    for forbidden in (
        "--target bigquery",
        "wage-openstat-ingest",
        "gcloud",
        "pinecone",
        "vercel deploy",
    ):
        assert forbidden not in workflow.lower()
