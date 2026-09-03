from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from analytics_platform.presentation.contract import (
    PresentationContractError,
    canonical_json,
    validate_artifact_directory,
)
from analytics_platform.presentation.generator import (
    build_presentation_artifacts,
    load_governed_snapshot,
    load_metric_contract,
)
from analytics_platform.presentation.insights import (
    INSIGHT_CONTRACT_ID,
    INSIGHT_CONTRACT_VERSION,
    validate_insight_artifact,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "presentation" / "data"
SNAPSHOT_PATH = (
    PROJECT_ROOT / "presentation" / "source" / "v1" / "governed_snapshot.json"
)
METRIC_CONTRACT_PATH = (
    PROJECT_ROOT / "contracts" / "metrics" / "v1" / "governed_metrics.yml"
)
INSIGHT_CONTRACT_PATH = (
    PROJECT_ROOT / "contracts" / "insights" / "v1" / "executive_insights.yml"
)


def _artifacts() -> dict[str, dict[str, object]]:
    return validate_artifact_directory(DATA_DIR)


def _insights() -> dict[str, dict[str, object]]:
    records = _artifacts()["insights"]["data"]["insights"]
    return {record["insight_id"]: record for record in records}


def test_versioned_insight_contract_and_stable_question_registry() -> None:
    contract = yaml.safe_load(INSIGHT_CONTRACT_PATH.read_text("utf-8"))
    data = _artifacts()["insights"]["data"]

    assert contract["contract_version"] == INSIGHT_CONTRACT_VERSION == 1
    assert contract["contract_id"] == INSIGHT_CONTRACT_ID
    assert contract["artifact"]["artifact_id"] == "presentation.insights.v1"
    assert data["insight_contract_id"] == INSIGHT_CONTRACT_ID
    assert data["insight_contract_version"] == INSIGHT_CONTRACT_VERSION
    assert len(data["questions"]) == len(data["insights"]) == 7
    assert {question["insight_id"] for question in data["questions"]} == {
        insight["insight_id"] for insight in data["insights"]
    }
    for insight in data["insights"]:
        assert insight["insight_id"] == insight["question_id"].replace(
            "question.", "insight.", 1
        )


def test_people_insights_use_governed_values_and_correct_arithmetic() -> None:
    insights = _insights()
    workforce = insights["insight.people.workforce_direction.v1"]
    balance = insights["insight.people.hiring_separation_balance.v1"]
    attrition = insights["insight.people.attrition_pressure.v1"]

    assert workforce["comparison"] == {
        "absolute_change": 199,
        "baseline_value": 249,
        "comparison_value": 448,
        "method": "first_to_last_observed_period",
        "percent_change": 79.92,
    }
    assert balance["comparison"] == {
        "hires": 0,
        "method": "minimum_monthly_hires_minus_separations",
        "net_event_balance": -11,
        "separations": 11,
    }
    assert attrition["comparison"] == {
        "comparison_value": 0.024448,
        "method": "peak_to_latest_observed_period",
        "peak_value": 0.028364,
        "percentage_point_change": -0.39,
    }
    assert workforce["comparison"]["absolute_change"] == (
        workforce["comparison"]["comparison_value"]
        - workforce["comparison"]["baseline_value"]
    )
    assert all(
        metric_id.startswith("people.")
        for insight in (workforce, balance, attrition)
        for metric_id in insight["metric_ids"]
    )


def test_wage_insights_preserve_source_grain_and_nonadditive_scope() -> None:
    artifacts = _artifacts()
    insights = {
        item["insight_id"]: item
        for item in artifacts["insights"]["data"]["insights"]
    }
    industry = insights["insight.wage.industry_wage_range.v1"]
    regional = insights["insight.wage.regional_wage_range.v1"]
    benchmark = insights["insight.wage.benchmark_occupation_range.v1"]

    assert industry["dimensions"] == {
        "category_type": "industry",
        "highest": "Information and Communications",
        "lowest": "Agriculture, Forestry, and Fishing",
    }
    assert industry["comparison"]["absolute_difference"] == 29060.91
    assert regional["dimensions"]["highest"] == "National Capital Region"
    assert regional["dimensions"]["lowest"] == (
        "Bangsamoro Autonomous Region in Muslim Mindanao"
    )
    assert regional["comparison"]["absolute_difference"] == 17814.82
    assert benchmark["comparison"]["observation_count"] == 114
    assert benchmark["comparison"]["absolute_difference"] == 18856.98
    assert benchmark["dimensions"]["grain"] == [
        "benchmark_occupation",
        "industry",
        "sex",
        "reference_year",
    ]
    assert {
        definition["aggregation_behavior"]
        for definition in artifacts["wage"]["data"]["definitions"]
    } == {"source_value_not_additive"}
    assert all(
        metric_id.startswith("wage.")
        for insight in (industry, regional, benchmark)
        for metric_id in insight["metric_ids"]
    )


def test_every_evidence_reference_resolves_to_its_governed_artifact() -> None:
    artifacts = _artifacts()
    validate_insight_artifact(artifacts["insights"], artifacts)

    invalid = deepcopy(artifacts)
    invalid["insights"]["data"]["insights"][0]["evidence"][0][
        "observed_value"
    ] = "not-the-governed-value"
    with pytest.raises(PresentationContractError, match="evidence value differs"):
        validate_insight_artifact(invalid["insights"], invalid)


def test_question_navigation_is_closed_and_does_not_mix_domain_metrics() -> None:
    insights = list(_insights().values())
    question_ids = {insight["question_id"] for insight in insights}

    for insight in insights:
        assert set(insight["next_question_ids"]).issubset(question_ids)
        assert insight["question_id"] not in insight["next_question_ids"]
        prefixes = {metric_id.split(".", 1)[0] for metric_id in insight["metric_ids"]}
        assert prefixes != {"people", "wage"}


def test_trust_insight_distinguishes_validation_from_intentional_fixtures() -> None:
    trust = _insights()["insight.platform.evidence_trust.v1"]

    assert trust["evidence_state"] == "validated_with_review_context"
    assert trust["comparison"]["people_reconciled_periods"] == "36/36"
    assert trust["comparison"]["wage_reconciled_matrices"] == "4/4"
    assert trust["comparison"]["people_maximum_difference"] == 0
    assert trust["comparison"]["wage_maximum_difference"] == 0
    assert "68 People quality records are intentional synthetic fixtures" in trust[
        "narrative"
    ]
    assert "not a production transformation failure" in trust["narrative"]
    assert "point-in-time rather than live telemetry" in trust["narrative"]


def test_defined_narratives_do_not_assert_causality() -> None:
    forbidden = re.compile(
        r"\b(?:because|caused?|causes?|due to|driven by|led to|results? from)\b",
        re.IGNORECASE,
    )
    for insight in _insights().values():
        assert not forbidden.search(insight["headline"])
        assert not forbidden.search(insight["narrative"])

    artifacts = _artifacts()
    invalid = deepcopy(artifacts)
    invalid["insights"]["data"]["insights"][0]["narrative"] = (
        "The observed metric changed because morale deteriorated."
    )
    with pytest.raises(PresentationContractError, match="causal language"):
        validate_insight_artifact(invalid["insights"], invalid)


def test_insight_generation_is_byte_deterministic_and_offline_by_contract() -> None:
    snapshot = load_governed_snapshot(SNAPSHOT_PATH)
    metric_contract = load_metric_contract(METRIC_CONTRACT_PATH)
    first = build_presentation_artifacts(snapshot, metric_contract)["insights"]
    second = build_presentation_artifacts(snapshot, metric_contract)["insights"]

    assert canonical_json(first) == canonical_json(second)
    assert first["data"]["generation_mode"] == (
        "deterministic_offline_from_presentation_contract"
    )
    assert first["data"]["source_artifact_ids"] == [
        "presentation.people.v1",
        "presentation.quality.v1",
        "presentation.wage.v1",
    ]
