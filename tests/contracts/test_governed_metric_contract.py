from pathlib import Path

import yaml


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "metrics"
    / "v1"
    / "governed_metrics.yml"
)

EXPECTED_METRICS = {
    "people.ending_headcount",
    "people.hires",
    "people.separations",
    "people.attrition_rate",
    "wage.basic_pay",
    "wage.allowance",
    "wage.wage_rate",
    "wage.benchmark_occupation_wage_rate",
}


def _load_contract() -> dict[str, object]:
    with CONTRACT_PATH.open(encoding="utf-8") as stream:
        contract = yaml.safe_load(stream)
    assert isinstance(contract, dict)
    return contract


def test_metric_contract_has_versioned_executable_surfaces() -> None:
    contract = _load_contract()
    assert contract["contract_version"] == 1
    assert contract["mechanism"]["type"] == "relational_metric_contract"
    assert contract["mechanism"]["native_dbt_semantic_layer"] is False

    metrics = contract["metrics"]
    assert {metric["metric_id"] for metric in metrics} == EXPECTED_METRICS
    assert {metric["source_model"] for metric in metrics} == {
        "metrics_people_monthly",
        "metrics_wage_published",
    }
    for metric in metrics:
        assert metric["definition"]
        assert metric["value_field"]
        assert metric["aggregation_behavior"]
        assert metric["valid_dimension_sets"]
        assert metric["limitations"]


def test_metric_contract_preserves_ratio_and_wage_semantics() -> None:
    contract = _load_contract()
    metrics = {metric["metric_id"]: metric for metric in contract["metrics"]}

    attrition = metrics["people.attrition_rate"]
    assert attrition["numerator"] == "attrition_numerator"
    assert attrition["denominator"] == "attrition_denominator"
    assert attrition["aggregation_behavior"] == "ratio_not_additive_or_averageable"

    for metric_id in EXPECTED_METRICS:
        if metric_id.startswith("wage."):
            metric = metrics[metric_id]
            assert metric["reference_year"] == 2024
            assert metric["aggregation_behavior"] == "source_value_not_additive"


def test_freshness_contracts_separate_operations_from_reference_periods() -> None:
    freshness = _load_contract()["freshness_contracts"]
    assert freshness["people"]["operational_timestamp"] == "loaded_at"
    assert freshness["wage"]["operational_timestamp"] == "retrieval_completed_at"
    for contract in freshness.values():
        assert contract["warn_after_hours"] == 48
        assert contract["error_after_hours"] == 168
        assert contract["reference_period"]
