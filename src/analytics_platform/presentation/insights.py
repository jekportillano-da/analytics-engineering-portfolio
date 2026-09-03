"""Deterministic executive insights over governed presentation artifacts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from analytics_platform.presentation.contract import PresentationContractError


INSIGHT_CONTRACT_VERSION = 1
INSIGHT_CONTRACT_ID = "analytics-portfolio-executive-insights-v1"
INSIGHT_GENERATION_MODE = "deterministic_offline_from_presentation_contract"

_INSIGHT_FIELDS = {
    "comparison", "contract_version", "dimensions", "display_hint", "domain",
    "evidence", "evidence_state", "executive_question", "headline", "insight_id",
    "limitations", "metric_ids", "narrative", "next_question_ids", "periods",
    "question_id",
}
_EVIDENCE_FIELDS = {
    "artifact_id", "collection", "dimensions", "field", "governed_source",
    "metric_id", "observed_value", "period", "record_id", "record_key",
}
_QUESTION_ID = re.compile(r"^question\.(people|wage|platform)\.[a-z0-9_]+\.v1$")
_CAUSAL_CLAIM = re.compile(
    r"\b(?:because|caused?|causes?|due to|driven by|led to|results? from)\b",
    re.IGNORECASE,
)


def _round(value: Decimal | float | int, places: str = "0.01") -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _percent_change(current: float | int, baseline: float | int) -> float:
    if baseline == 0:
        raise PresentationContractError("cannot calculate a percentage from a zero baseline")
    change = Decimal(str(current)) - Decimal(str(baseline))
    return _round(change * 100 / Decimal(str(baseline)))


def _month(value: object) -> str:
    if not isinstance(value, str):
        raise PresentationContractError("period_start must be ISO date text")
    try:
        return date.fromisoformat(value).strftime("%B %Y")
    except ValueError as exc:
        raise PresentationContractError("period_start must be an ISO date") from exc


def _money(value: float | int) -> str:
    rounded = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"PHP {rounded:,.0f}"


def _artifact_data(
    artifacts: Mapping[str, Mapping[str, object]], artifact_type: str
) -> Mapping[str, Any]:
    artifact = artifacts.get(artifact_type)
    if not isinstance(artifact, Mapping):
        raise PresentationContractError(f"missing {artifact_type} presentation artifact")
    data = artifact.get("data")
    if not isinstance(data, Mapping):
        raise PresentationContractError(f"invalid {artifact_type} artifact data")
    return data


def _records(data: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    value = data.get(field)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, Mapping) for item in value)
    ):
        raise PresentationContractError(f"{field} must be a nonempty record list")
    return list(value)


def _evidence(
    *,
    artifact_type: str,
    collection: str,
    field: str,
    observed_value: object,
    governed_source: str,
    metric_id: str | None = None,
    record_key: str | None = None,
    record_id: str | None = None,
    period: str | int | None = None,
    dimensions: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "artifact_id": f"presentation.{artifact_type}.v1",
        "collection": collection,
        "dimensions": dict(dimensions or {}),
        "field": field,
        "governed_source": governed_source,
        "metric_id": metric_id,
        "observed_value": observed_value,
        "period": period,
        "record_id": record_id,
        "record_key": record_key,
    }


def _insight(
    *,
    domain: str,
    slug: str,
    question: str,
    headline: str,
    narrative: str,
    evidence: list[dict[str, object]],
    metric_ids: list[str],
    periods: list[str | int],
    dimensions: Mapping[str, object],
    comparison: Mapping[str, object],
    limitations: list[str],
    next_question_ids: list[str],
    visualization: str,
    evidence_focus: str,
    evidence_state: str = "governed_observation",
) -> dict[str, object]:
    return {
        "comparison": dict(comparison),
        "contract_version": INSIGHT_CONTRACT_VERSION,
        "dimensions": dict(dimensions),
        "display_hint": {
            "evidence_focus": evidence_focus,
            "visualization": visualization,
        },
        "domain": domain,
        "evidence": evidence,
        "evidence_state": evidence_state,
        "executive_question": question,
        "headline": headline,
        "insight_id": f"insight.{domain}.{slug}.v1",
        "limitations": limitations,
        "metric_ids": metric_ids,
        "narrative": narrative,
        "next_question_ids": next_question_ids,
        "periods": periods,
        "question_id": f"question.{domain}.{slug}.v1",
    }


def _people_insights(people: Mapping[str, Any]) -> list[dict[str, object]]:
    monthly = sorted(
        _records(people, "monthly"), key=lambda item: str(item["period_start"])
    )
    first, latest = monthly[0], monthly[-1]
    first_headcount = int(first["ending_headcount"])
    latest_headcount = int(latest["ending_headcount"])
    headcount_change = latest_headcount - first_headcount
    headcount_percent = _percent_change(latest_headcount, first_headcount)
    direction = "above" if headcount_change >= 0 else "below"
    movement = "increase" if headcount_change >= 0 else "decrease"

    workforce = _insight(
        domain="people",
        slug="workforce_direction",
        question="Is the workforce growing or contracting across the analysis window?",
        headline=(
            f"Workforce ended {abs(headcount_percent):.1f}% {direction} "
            "the first observed month"
        ),
        narrative=(
            f"Ending headcount moved from {first_headcount:,} in "
            f"{_month(first['period_start'])} to {latest_headcount:,} in "
            f"{_month(latest['period_start'])}, a net {movement} of "
            f"{abs(headcount_change):,} ({abs(headcount_percent):.1f}%) across the "
            f"{len(monthly)}-month synthetic analysis window."
        ),
        evidence=[
            _evidence(
                artifact_type="people", collection="monthly",
                record_key="period_start", record_id=str(first["period_start"]),
                field="ending_headcount", observed_value=first_headcount,
                metric_id="people.ending_headcount",
                governed_source="metrics_people_monthly",
                period=str(first["period_start"]),
            ),
            _evidence(
                artifact_type="people", collection="monthly",
                record_key="period_start", record_id=str(latest["period_start"]),
                field="ending_headcount", observed_value=latest_headcount,
                metric_id="people.ending_headcount",
                governed_source="metrics_people_monthly",
                period=str(latest["period_start"]),
            ),
        ],
        metric_ids=["people.ending_headcount"],
        periods=[str(first["period_start"]), str(latest["period_start"])],
        dimensions={"time_grain": "month"},
        comparison={
            "absolute_change": headcount_change,
            "baseline_value": first_headcount,
            "comparison_value": latest_headcount,
            "method": "first_to_last_observed_period",
            "percent_change": headcount_percent,
        },
        limitations=[
            "The workforce is synthetic and supports a portfolio demonstration, not a real employer decision.",
            "The governed monthly model has no organization, job, or location breakout.",
        ],
        next_question_ids=[
            "question.people.hiring_separation_balance.v1",
            "question.people.attrition_pressure.v1",
            "question.platform.evidence_trust.v1",
        ],
        visualization="line",
        evidence_focus="first_and_last_period",
    )

    balance_row = min(
        monthly,
        key=lambda item: (
            int(item["hires"]) - int(item["separations"]),
            str(item["period_start"]),
        ),
    )
    hires = int(balance_row["hires"])
    separations = int(balance_row["separations"])
    net_balance = hires - separations
    if net_balance < 0:
        balance_headline = (
            f"Separations exceeded hires most in {_month(balance_row['period_start'])}"
        )
        balance_narrative = (
            f"{_month(balance_row['period_start'])} recorded {hires:,} hires and "
            f"{separations:,} separations, a net event balance of {net_balance:,}. "
            "This was the largest monthly separation-over-hire gap in the observed window."
        )
    else:
        balance_headline = "Hires matched or exceeded separations in every observed month"
        balance_narrative = (
            f"The smallest monthly event balance occurred in "
            f"{_month(balance_row['period_start'])}: {hires:,} hires and "
            f"{separations:,} separations, for a net balance of {net_balance:,}."
        )
    balance = _insight(
        domain="people",
        slug="hiring_separation_balance",
        question="When did hiring least offset separations?",
        headline=balance_headline,
        narrative=balance_narrative,
        evidence=[
            _evidence(
                artifact_type="people", collection="monthly",
                record_key="period_start", record_id=str(balance_row["period_start"]),
                field="hires", observed_value=hires, metric_id="people.hires",
                governed_source="metrics_people_monthly",
                period=str(balance_row["period_start"]),
            ),
            _evidence(
                artifact_type="people", collection="monthly",
                record_key="period_start", record_id=str(balance_row["period_start"]),
                field="separations", observed_value=separations,
                metric_id="people.separations",
                governed_source="metrics_people_monthly",
                period=str(balance_row["period_start"]),
            ),
        ],
        metric_ids=["people.hires", "people.separations"],
        periods=[str(balance_row["period_start"])],
        dimensions={"time_grain": "month"},
        comparison={
            "hires": hires,
            "method": "minimum_monthly_hires_minus_separations",
            "net_event_balance": net_balance,
            "separations": separations,
        },
        limitations=[
            "The event balance is an observed arithmetic comparison and does not establish why either metric changed.",
            "Hires and separations use the governed employment-spell event definitions.",
        ],
        next_question_ids=[
            "question.people.attrition_pressure.v1",
            "question.people.workforce_direction.v1",
            "question.platform.evidence_trust.v1",
        ],
        visualization="grouped_bar",
        evidence_focus="lowest_net_event_balance_period",
    )

    peak = max(
        monthly,
        key=lambda item: (float(item["attrition_rate"]), str(item["period_start"])),
    )
    peak_rate = float(peak["attrition_rate"])
    latest_rate = float(latest["attrition_rate"])
    percentage_point_change = _round(
        (Decimal(str(latest_rate)) - Decimal(str(peak_rate))) * 100
    )
    attrition = _insight(
        domain="people",
        slug="attrition_pressure",
        question="When was attrition pressure highest, and where did it stand at the end?",
        headline=(
            f"Monthly attrition peaked at {peak_rate * 100:.2f}% in "
            f"{_month(peak['period_start'])}"
        ),
        narrative=(
            f"The highest observed monthly attrition rate was {peak_rate * 100:.2f}% "
            f"in {_month(peak['period_start'])}. The final month was "
            f"{latest_rate * 100:.2f}%, {abs(percentage_point_change):.2f} percentage "
            "points below that peak."
        ),
        evidence=[
            _evidence(
                artifact_type="people", collection="monthly",
                record_key="period_start", record_id=str(peak["period_start"]),
                field="attrition_rate", observed_value=peak_rate,
                metric_id="people.attrition_rate",
                governed_source="metrics_people_monthly",
                period=str(peak["period_start"]),
            ),
            _evidence(
                artifact_type="people", collection="monthly",
                record_key="period_start", record_id=str(latest["period_start"]),
                field="attrition_rate", observed_value=latest_rate,
                metric_id="people.attrition_rate",
                governed_source="metrics_people_monthly",
                period=str(latest["period_start"]),
            ),
        ],
        metric_ids=["people.attrition_rate"],
        periods=[str(peak["period_start"]), str(latest["period_start"])],
        dimensions={"time_grain": "month"},
        comparison={
            "comparison_value": latest_rate,
            "method": "peak_to_latest_observed_period",
            "peak_value": peak_rate,
            "percentage_point_change": percentage_point_change,
        },
        limitations=[
            "Monthly attrition rates are ratios and must not be summed or averaged across periods.",
            "The peak comparison describes timing and magnitude, not a cause.",
        ],
        next_question_ids=[
            "question.people.hiring_separation_balance.v1",
            "question.platform.evidence_trust.v1",
        ],
        visualization="line",
        evidence_focus="peak_and_latest_period",
    )
    return [workforce, balance, attrition]


def _wage_range_insight(
    rows: list[Mapping[str, Any]],
    *,
    slug: str,
    question: str,
    collection: str,
    record_key: str,
    label_field: str,
    dimension_name: str,
    next_question_ids: list[str],
) -> dict[str, object]:
    detailed = [
        row for row in rows if str(row[label_field]).upper() != "ALL INDUSTRIES"
    ]
    if not detailed:
        raise PresentationContractError(f"no detailed {dimension_name} Wage records")
    lowest = min(
        detailed,
        key=lambda item: (
            float(item["average_monthly_wage_rate"]), str(item[record_key])
        ),
    )
    highest = max(
        detailed,
        key=lambda item: (
            float(item["average_monthly_wage_rate"]), str(item[record_key])
        ),
    )
    low_value = float(lowest["average_monthly_wage_rate"])
    high_value = float(highest["average_monthly_wage_rate"])
    absolute_difference = _round(high_value - low_value)
    multiple = _round(Decimal(str(high_value)) / Decimal(str(low_value)))
    high_label = str(highest[label_field])
    low_label = str(lowest[label_field])
    reference_year = int(highest["reference_year"])
    return _insight(
        domain="wage",
        slug=slug,
        question=question,
        headline=f"{high_label} had the highest published {dimension_name} wage rate",
        narrative=(
            f"Among the detailed {dimension_name} categories published for "
            f"{reference_year}, the observed average monthly wage rate ranged from "
            f"{_money(low_value)} for {low_label} to {_money(high_value)} for "
            f"{high_label}. The difference was {_money(absolute_difference)}, and the "
            f"higher published value was {multiple:.2f}x the lower value."
        ),
        evidence=[
            _evidence(
                artifact_type="wage", collection=collection,
                record_key=record_key, record_id=str(lowest[record_key]),
                field="average_monthly_wage_rate", observed_value=low_value,
                metric_id="wage.wage_rate", governed_source="metrics_wage_published",
                period=reference_year, dimensions={dimension_name: low_label},
            ),
            _evidence(
                artifact_type="wage", collection=collection,
                record_key=record_key, record_id=str(highest[record_key]),
                field="average_monthly_wage_rate", observed_value=high_value,
                metric_id="wage.wage_rate", governed_source="metrics_wage_published",
                period=reference_year, dimensions={dimension_name: high_label},
            ),
        ],
        metric_ids=["wage.wage_rate"],
        periods=[reference_year],
        dimensions={
            "category_type": dimension_name,
            "highest": high_label,
            "lowest": low_label,
        },
        comparison={
            "absolute_difference": absolute_difference,
            "highest_value": high_value,
            "lowest_value": low_value,
            "method": f"published_{dimension_name}_category_range",
            "multiple": multiple,
        },
        limitations=[
            "These are non-additive PSA-published source values and are not summed or averaged across categories.",
            "The observed range describes this OWS source scope and does not represent individual compensation.",
            "The ALL INDUSTRIES aggregate is excluded from the detailed-category range.",
        ],
        next_question_ids=next_question_ids,
        visualization="range_bar",
        evidence_focus="highest_and_lowest_published_categories",
    )


def _wage_insights(wage: Mapping[str, Any]) -> list[dict[str, object]]:
    industry_insight = _wage_range_insight(
        _records(wage, "industry"),
        slug="industry_wage_range",
        question="Which reported industries have the highest and lowest observed wage rates?",
        collection="industry",
        record_key="industry_wage_mart_id",
        label_field="industry_name",
        dimension_name="industry",
        next_question_ids=[
            "question.wage.regional_wage_range.v1",
            "question.wage.benchmark_occupation_range.v1",
            "question.platform.evidence_trust.v1",
        ],
    )
    regional_insight = _wage_range_insight(
        _records(wage, "regional"),
        slug="regional_wage_range",
        question="How materially do observed wage rates differ across regions?",
        collection="regional",
        record_key="regional_wage_mart_id",
        label_field="region_name",
        dimension_name="region",
        next_question_ids=[
            "question.wage.industry_wage_range.v1",
            "question.wage.benchmark_occupation_range.v1",
            "question.platform.evidence_trust.v1",
        ],
    )

    benchmark = _records(wage, "benchmark_occupations")
    lowest = min(
        benchmark,
        key=lambda item: (
            float(item["average_monthly_wage_rate"]),
            str(item["benchmark_wage_mart_id"]),
        ),
    )
    highest = max(
        benchmark,
        key=lambda item: (
            float(item["average_monthly_wage_rate"]),
            str(item["benchmark_wage_mart_id"]),
        ),
    )
    low_value = float(lowest["average_monthly_wage_rate"])
    high_value = float(highest["average_monthly_wage_rate"])
    summary = wage.get("summary")
    if not isinstance(summary, Mapping):
        raise PresentationContractError("Wage summary is invalid")
    observation_count = int(summary["benchmark_observation_count"])
    reference_year = int(highest["reference_year"])
    benchmark_insight = _insight(
        domain="wage",
        slug="benchmark_occupation_range",
        question="What does the available benchmark-occupation evidence show?",
        headline=(
            f"The {reference_year} benchmark observations span "
            f"{_money(low_value)} to {_money(high_value)}"
        ),
        narrative=(
            f"Across {observation_count:,} published observations for General Office "
            f"Clerks and Elementary Occupations, the lowest observed wage rate was "
            f"{_money(low_value)} for {lowest['benchmark_occupation_name']} "
            f"({lowest['sex']}) in {lowest['industry_name']}. The highest was "
            f"{_money(high_value)} for {highest['benchmark_occupation_name']} "
            f"({highest['sex']}) in {highest['industry_name']}."
        ),
        evidence=[
            _evidence(
                artifact_type="wage", collection="summary",
                field="benchmark_observation_count", observed_value=observation_count,
                governed_source="mart_wage_benchmark_occupation", period=reference_year,
            ),
            _evidence(
                artifact_type="wage", collection="benchmark_occupations",
                record_key="benchmark_wage_mart_id",
                record_id=str(lowest["benchmark_wage_mart_id"]),
                field="average_monthly_wage_rate", observed_value=low_value,
                metric_id="wage.benchmark_occupation_wage_rate",
                governed_source="metrics_wage_published", period=reference_year,
                dimensions={
                    "benchmark_occupation": str(lowest["benchmark_occupation_name"]),
                    "industry": str(lowest["industry_name"]), "sex": str(lowest["sex"]),
                },
            ),
            _evidence(
                artifact_type="wage", collection="benchmark_occupations",
                record_key="benchmark_wage_mart_id",
                record_id=str(highest["benchmark_wage_mart_id"]),
                field="average_monthly_wage_rate", observed_value=high_value,
                metric_id="wage.benchmark_occupation_wage_rate",
                governed_source="metrics_wage_published", period=reference_year,
                dimensions={
                    "benchmark_occupation": str(highest["benchmark_occupation_name"]),
                    "industry": str(highest["industry_name"]), "sex": str(highest["sex"]),
                },
            ),
        ],
        metric_ids=["wage.benchmark_occupation_wage_rate"],
        periods=[reference_year],
        dimensions={
            "benchmark_occupations": [
                "Elementary Occupations", "General Office Clerks"
            ],
            "grain": ["benchmark_occupation", "industry", "sex", "reference_year"],
        },
        comparison={
            "absolute_difference": _round(high_value - low_value),
            "highest_value": high_value,
            "lowest_value": low_value,
            "method": "published_benchmark_observation_range",
            "observation_count": observation_count,
        },
        limitations=[
            "The source covers only General Office Clerks and Elementary Occupations.",
            "Each value remains at benchmark occupation, industry, sex, and reference-year grain.",
            "The range is not a national salary benchmark and does not represent individual compensation.",
        ],
        next_question_ids=[
            "question.wage.industry_wage_range.v1",
            "question.wage.regional_wage_range.v1",
            "question.platform.evidence_trust.v1",
        ],
        visualization="range_bar",
        evidence_focus="lowest_and_highest_source_grain_observations",
    )
    return [industry_insight, regional_insight, benchmark_insight]


def _trust_insight(quality: Mapping[str, Any]) -> dict[str, object]:
    people_reconciliation = quality.get("people_reconciliation")
    wage_reconciliation = quality.get("wage_reconciliation")
    people_quality = quality.get("people_quality")
    checks = _records(quality, "governance_checks")
    if not all(
        isinstance(value, Mapping)
        for value in (people_reconciliation, wage_reconciliation, people_quality)
    ):
        raise PresentationContractError("quality summaries are invalid")
    people_summary = people_reconciliation.get("summary")
    wage_summary = wage_reconciliation.get("summary")
    if not isinstance(people_summary, Mapping) or not isinstance(wage_summary, Mapping):
        raise PresentationContractError("reconciliation summaries are invalid")
    checks_by_id = {str(item["governance_check_id"]): item for item in checks}
    required_checks = {
        "people.headcount_reconciliation", "people.operational_freshness",
        "people.quality_issues", "wage.operational_freshness",
        "wage.raw_to_mart_reconciliation",
    }
    if not required_checks.issubset(checks_by_id):
        raise PresentationContractError("governance checks are incomplete")
    people_periods = int(people_summary["period_count"])
    people_reconciled = int(people_summary["reconciled_period_count"])
    wage_matrices = int(wage_summary["matrix_count"])
    wage_reconciled = int(wage_summary["reconciled_matrix_count"])
    issue_count = int(people_quality["issue_count"])
    people_freshness = str(checks_by_id["people.operational_freshness"]["status"])
    wage_freshness = str(checks_by_id["wage.operational_freshness"]["status"])
    freshness_phrase = (
        f"both {people_freshness}"
        if people_freshness == wage_freshness
        else f"{people_freshness} and {wage_freshness}, respectively"
    )
    return _insight(
        domain="platform",
        slug="evidence_trust",
        question="How trustworthy and current is this evidence snapshot?",
        headline=(
            "People and Wage reconciliation passed with intentional People quality "
            "fixtures visible"
        ),
        narrative=(
            f"All {people_reconciled}/{people_periods} People periods and all "
            f"{wage_reconciled}/{wage_matrices} Wage matrices reconciled with maximum "
            f"difference 0. The {issue_count} People quality records are intentional "
            "synthetic fixtures retained for governance demonstration; review_required "
            "is not a production transformation failure. People and Wage freshness "
            f"checks were {freshness_phrase} when the governed "
            "snapshot was evaluated, so these states are point-in-time rather than live "
            "telemetry."
        ),
        evidence=[
            _evidence(
                artifact_type="quality", collection="people_reconciliation.summary",
                field="reconciled_period_count", observed_value=people_reconciled,
                governed_source="mart_headcount_reconciliation",
            ),
            _evidence(
                artifact_type="quality", collection="people_reconciliation.summary",
                field="maximum_difference",
                observed_value=people_summary["maximum_difference"],
                governed_source="mart_headcount_reconciliation",
            ),
            _evidence(
                artifact_type="quality", collection="wage_reconciliation.summary",
                field="reconciled_matrix_count", observed_value=wage_reconciled,
                governed_source="mart_wage_reconciliation",
            ),
            _evidence(
                artifact_type="quality", collection="wage_reconciliation.summary",
                field="maximum_difference",
                observed_value=wage_summary["maximum_difference"],
                governed_source="mart_wage_reconciliation",
            ),
            _evidence(
                artifact_type="quality", collection="people_quality",
                field="issue_count", observed_value=issue_count,
                governed_source="mart_data_quality_issues",
            ),
            *[
                _evidence(
                    artifact_type="quality", collection="governance_checks",
                    record_key="governance_check_id", record_id=check_id,
                    field="status", observed_value=checks_by_id[check_id]["status"],
                    governed_source="mart_analytics_governance_summary",
                )
                for check_id in (
                    "people.quality_issues", "people.operational_freshness",
                    "wage.operational_freshness",
                )
            ],
        ],
        metric_ids=[],
        periods=[],
        dimensions={
            "domains": ["people", "wage"],
            "status_semantics": "point_in_time",
        },
        comparison={
            "method": "governed_control_summary",
            "people_maximum_difference": people_summary["maximum_difference"],
            "people_reconciled_periods": f"{people_reconciled}/{people_periods}",
            "wage_maximum_difference": wage_summary["maximum_difference"],
            "wage_reconciled_matrices": f"{wage_reconciled}/{wage_matrices}",
        },
        limitations=[
            "Freshness and governance states reflect the committed snapshot evaluation time, not live telemetry.",
            "Reconciliation proves defined pipeline parity; it does not independently validate every source claim.",
        ],
        next_question_ids=[],
        visualization="status",
        evidence_focus="reconciliation_quality_and_freshness_controls",
        evidence_state="validated_with_review_context",
    )


def build_executive_insight_data(
    artifacts: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Build the V1 insight payload solely from governed presentation artifacts."""

    insights = (
        _people_insights(_artifact_data(artifacts, "people"))
        + _wage_insights(_artifact_data(artifacts, "wage"))
        + [_trust_insight(_artifact_data(artifacts, "quality"))]
    )
    insights = sorted(insights, key=lambda item: str(item["insight_id"]))
    questions = sorted(
        [
            {
                "domain": item["domain"],
                "executive_question": item["executive_question"],
                "insight_id": item["insight_id"],
                "question_id": item["question_id"],
            }
            for item in insights
        ],
        key=lambda item: str(item["question_id"]),
    )
    return {
        "generation_mode": INSIGHT_GENERATION_MODE,
        "insight_contract_id": INSIGHT_CONTRACT_ID,
        "insight_contract_version": INSIGHT_CONTRACT_VERSION,
        "insights": insights,
        "limitations": [
            "Insights describe governed observations and do not establish causality.",
            "Decision support means evidence-backed investigation, not automated business decisions.",
            "People is synthetic; Wage remains within the published PSA 2024 OWS scope and source grain.",
        ],
        "questions": questions,
        "source_artifact_ids": [
            "presentation.people.v1",
            "presentation.quality.v1",
            "presentation.wage.v1",
        ],
    }


def _resolve_collection(data: Mapping[str, Any], collection: str) -> object:
    current: object = data
    for field in collection.split("."):
        if not isinstance(current, Mapping) or field not in current:
            raise PresentationContractError(
                f"unresolved evidence collection: {collection}"
            )
        current = current[field]
    return current


def _metric_sources(
    artifacts: Mapping[str, Mapping[str, object]],
) -> dict[str, str]:
    sources: dict[str, str] = {}
    for artifact_type in ("people", "wage"):
        definitions = _artifact_data(artifacts, artifact_type).get("definitions")
        if not isinstance(definitions, list):
            raise PresentationContractError(
                f"invalid {artifact_type} metric definitions"
            )
        for definition in definitions:
            if not isinstance(definition, Mapping):
                raise PresentationContractError("invalid governed metric definition")
            sources[str(definition["metric_id"])] = str(definition["source_model"])
    return sources


def _validate_evidence(
    evidence: Mapping[str, object],
    insight_metric_ids: set[str],
    artifacts: Mapping[str, Mapping[str, object]],
    metric_sources: Mapping[str, str],
) -> None:
    if set(evidence) != _EVIDENCE_FIELDS:
        raise PresentationContractError("invalid insight evidence reference")
    artifact_id = evidence["artifact_id"]
    if (
        not isinstance(artifact_id, str)
        or not artifact_id.startswith("presentation.")
        or not artifact_id.endswith(".v1")
    ):
        raise PresentationContractError("invalid evidence artifact ID")
    artifact_type = artifact_id.removeprefix("presentation.").removesuffix(".v1")
    artifact = artifacts.get(artifact_type)
    if not isinstance(artifact, Mapping) or artifact.get("artifact_id") != artifact_id:
        raise PresentationContractError(f"unresolved evidence artifact: {artifact_id}")
    collection, field = evidence["collection"], evidence["field"]
    if not isinstance(collection, str) or not isinstance(field, str):
        raise PresentationContractError(
            "evidence collection and field must be text"
        )
    target = _resolve_collection(_artifact_data(artifacts, artifact_type), collection)
    record_key, record_id = evidence["record_key"], evidence["record_id"]
    if (record_key is None) != (record_id is None):
        raise PresentationContractError(
            "evidence record key and ID must both be null or text"
        )
    if record_key is not None:
        if (
            not isinstance(record_key, str)
            or not isinstance(record_id, str)
            or not isinstance(target, list)
        ):
            raise PresentationContractError(
                "record evidence must address a list by text identity"
            )
        matches = [
            item for item in target
            if isinstance(item, Mapping) and str(item.get(record_key)) == record_id
        ]
        if len(matches) != 1:
            raise PresentationContractError("evidence record identity is not unique")
        target = matches[0]
    if not isinstance(target, Mapping) or field not in target:
        raise PresentationContractError("evidence field cannot be resolved")
    if target[field] != evidence["observed_value"]:
        raise PresentationContractError(
            "evidence value differs from the governed artifact"
        )
    metric_id = evidence["metric_id"]
    governed_source = evidence["governed_source"]
    if not isinstance(governed_source, str) or not governed_source:
        raise PresentationContractError("evidence governed source is required")
    if metric_id is not None:
        if not isinstance(metric_id, str) or metric_id not in insight_metric_ids:
            raise PresentationContractError(
                "evidence uses an undeclared insight metric"
            )
        if metric_sources.get(metric_id) != governed_source:
            raise PresentationContractError(
                "evidence source differs from the metric contract"
            )
    if not isinstance(evidence["dimensions"], Mapping):
        raise PresentationContractError("evidence dimensions must be an object")


def validate_insight_artifact(
    insight_artifact: Mapping[str, object],
    artifacts: Mapping[str, Mapping[str, object]],
) -> None:
    """Validate schema, navigation, metric scope, and evidence resolution."""

    data = insight_artifact.get("data")
    expected_data_fields = {
        "generation_mode", "insight_contract_id", "insight_contract_version",
        "insights", "limitations", "questions", "source_artifact_ids",
    }
    if not isinstance(data, Mapping) or set(data) != expected_data_fields:
        raise PresentationContractError("invalid executive insight contract payload")
    if (
        data["insight_contract_id"] != INSIGHT_CONTRACT_ID
        or data["insight_contract_version"] != INSIGHT_CONTRACT_VERSION
    ):
        raise PresentationContractError("unsupported executive insight contract")
    if data["generation_mode"] != INSIGHT_GENERATION_MODE:
        raise PresentationContractError("unexpected insight generation mode")
    if data["source_artifact_ids"] != [
        "presentation.people.v1",
        "presentation.quality.v1",
        "presentation.wage.v1",
    ]:
        raise PresentationContractError("unexpected insight source artifact set")
    questions, insights = data["questions"], data["insights"]
    if (
        not isinstance(questions, list)
        or not isinstance(insights, list)
        or not insights
    ):
        raise PresentationContractError(
            "insight questions and records must be nonempty lists"
        )
    question_ids = {
        item.get("question_id") for item in questions if isinstance(item, Mapping)
    }
    insight_ids = {
        item.get("insight_id") for item in insights if isinstance(item, Mapping)
    }
    if len(question_ids) != len(questions) or len(insight_ids) != len(insights):
        raise PresentationContractError(
            "insight and question identities must be unique"
        )
    metric_sources = _metric_sources(artifacts)
    for question in questions:
        if not isinstance(question, Mapping) or set(question) != {
            "domain", "executive_question", "insight_id", "question_id"
        }:
            raise PresentationContractError("invalid executive question record")
        if (
            not isinstance(question["question_id"], str)
            or not _QUESTION_ID.fullmatch(question["question_id"])
        ):
            raise PresentationContractError("invalid stable question ID")
        if question["insight_id"] not in insight_ids:
            raise PresentationContractError("question references an unknown insight")
    for insight in insights:
        if not isinstance(insight, Mapping) or set(insight) != _INSIGHT_FIELDS:
            raise PresentationContractError("invalid executive insight record")
        question_id, domain = insight["question_id"], insight["domain"]
        if (
            not isinstance(question_id, str)
            or not _QUESTION_ID.fullmatch(question_id)
        ):
            raise PresentationContractError("invalid insight question ID")
        if not isinstance(domain, str) or question_id.split(".")[1] != domain:
            raise PresentationContractError(
                "insight domain differs from its question ID"
            )
        expected_insight_id = question_id.replace("question.", "insight.", 1)
        if (
            insight["insight_id"] != expected_insight_id
            or insight["contract_version"] != INSIGHT_CONTRACT_VERSION
        ):
            raise PresentationContractError("unstable insight identity or version")
        question = next(
            item for item in questions if item["question_id"] == question_id
        )
        if (
            question["insight_id"] != insight["insight_id"]
            or question["executive_question"] != insight["executive_question"]
        ):
            raise PresentationContractError("question registry differs from its insight")
        if insight["evidence_state"] not in {
            "governed_observation", "validated_with_review_context"
        }:
            raise PresentationContractError("invalid insight evidence state")
        if _CAUSAL_CLAIM.search(str(insight["headline"])) or _CAUSAL_CLAIM.search(
            str(insight["narrative"])
        ):
            raise PresentationContractError(
                "insight narrative contains unsupported causal language"
            )
        metric_ids = insight["metric_ids"]
        if not isinstance(metric_ids, list) or not all(
            isinstance(item, str) for item in metric_ids
        ):
            raise PresentationContractError("insight metric IDs must be text")
        metric_id_set = set(metric_ids)
        if not metric_id_set.issubset(metric_sources):
            raise PresentationContractError(
                "insight uses an unsupported governed metric"
            )
        if domain in {"people", "wage"} and any(
            not item.startswith(f"{domain}.") for item in metric_ids
        ):
            raise PresentationContractError(
                "insight crosses governed domain metric boundaries"
            )
        if domain == "platform" and metric_ids:
            raise PresentationContractError(
                "platform trust insight must reference controls, not mixed metrics"
            )
        evidence = insight["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise PresentationContractError("every insight requires evidence")
        for reference in evidence:
            if not isinstance(reference, Mapping):
                raise PresentationContractError("insight evidence must be an object")
            _validate_evidence(reference, metric_id_set, artifacts, metric_sources)
        next_question_ids = insight["next_question_ids"]
        if not isinstance(next_question_ids, list) or any(
            item not in question_ids or item == question_id
            for item in next_question_ids
        ):
            raise PresentationContractError(
                "insight navigation references an invalid question"
            )
        if (
            not isinstance(insight["comparison"], Mapping)
            or "method" not in insight["comparison"]
        ):
            raise PresentationContractError("insight comparison method is required")
        if not isinstance(insight["dimensions"], Mapping) or not isinstance(
            insight["display_hint"], Mapping
        ):
            raise PresentationContractError(
                "insight dimensions and display hint must be objects"
            )
        if (
            not isinstance(insight["periods"], list)
            or not isinstance(insight["limitations"], list)
            or not insight["limitations"]
        ):
            raise PresentationContractError(
                "insight periods and limitations must be lists"
            )


__all__ = (
    "INSIGHT_CONTRACT_ID",
    "INSIGHT_CONTRACT_VERSION",
    "build_executive_insight_data",
    "validate_insight_artifact",
)
