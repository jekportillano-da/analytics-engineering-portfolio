"""Explicit local/cloud readers for creating a governed presentation snapshot."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from google.cloud import bigquery

from analytics_platform.presentation.generator import GOVERNED_SNAPSHOT_VERSION


_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_DATASET_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")


def _json_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _duckdb_rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, object]]:
    cursor = connection.execute(sql)
    columns = [item[0] for item in cursor.description]
    return [
        {column: _json_value(value) for column, value in zip(columns, row, strict=True)}
        for row in cursor.fetchall()
    ]


def _bigquery_rows(
    client: bigquery.Client, sql: str, location: str
) -> list[dict[str, object]]:
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in client.query(sql, location=location).result()
    ]


def _single(rows: list[dict[str, object]], description: str) -> dict[str, object]:
    if len(rows) != 1:
        raise ValueError(f"expected one {description} row, received {len(rows)}")
    return rows[0]


def _people_snapshot(database: Path) -> dict[str, object]:
    connection = duckdb.connect(str(database.resolve()), read_only=True)
    try:
        summary = _single(
            _duckdb_rows(
                connection,
                """
                select
                    (select count(*) from marts.fct_workforce_daily) as daily_fact_count,
                    (select count(*) from marts.fct_workforce_events) as event_count,
                    count(*) as monthly_period_count,
                    arg_max(ending_headcount, period_start) as ending_headcount,
                    (select count(*) from marts.mart_data_quality_issues) as quality_issue_count
                from marts.metrics_people_monthly
                """,
            ),
            "People summary",
        )
        monthly = _duckdb_rows(
            connection,
            """
            select
                metric_contract_version, period_start, period_end, calendar_days,
                ending_headcount, hires, separations, attrition_rate,
                attrition_numerator, attrition_denominator
            from marts.metrics_people_monthly
            order by period_start
            """,
        )
        quality_by_type = _duckdb_rows(
            connection,
            """
            select severity, issue_type, count(*) as issue_count
            from marts.mart_data_quality_issues
            group by severity, issue_type
            order by severity, issue_type
            """,
        )
        reconciliation_rows = _duckdb_rows(
            connection,
            """
            select
                period_start, opening_headcount, hires, separations,
                expected_ending_headcount, actual_ending_headcount,
                difference, is_reconciled
            from marts.mart_headcount_reconciliation
            order by period_start
            """,
        )
        reconciliation_summary = _single(
            _duckdb_rows(
                connection,
                """
                select
                    count(*) as period_count,
                    count(*) filter (where is_reconciled) as reconciled_period_count,
                    max(abs(difference)) as maximum_difference
                from marts.mart_headcount_reconciliation
                """,
            ),
            "People reconciliation summary",
        )
    finally:
        connection.close()
    return {
        "monthly": monthly,
        "quality": {
            "by_type": quality_by_type,
            "issue_count": summary["quality_issue_count"],
        },
        "reconciliation": {
            "periods": reconciliation_rows,
            "summary": reconciliation_summary,
        },
        "summary": summary,
    }


def _validate_cloud_target(project: str, marts_dataset: str, raw_dataset: str, location: str) -> None:
    if _PROJECT_ID.fullmatch(project) is None:
        raise ValueError("invalid BigQuery project ID")
    for value in (marts_dataset, raw_dataset):
        if _DATASET_ID.fullmatch(value) is None:
            raise ValueError("invalid BigQuery dataset ID")
    if not location.strip():
        raise ValueError("BigQuery location is required")


def _wage_snapshot(
    project: str, marts_dataset: str, raw_dataset: str, location: str
) -> tuple[dict[str, object], list[dict[str, object]]]:
    _validate_cloud_target(project, marts_dataset, raw_dataset, location)
    client = bigquery.Client(project=project, location=location)
    if client.project != project:
        raise ValueError("BigQuery client project differs from requested project")
    marts = f"`{project}.{marts_dataset}"
    raw = f"`{project}.{raw_dataset}"

    summary = _single(
        _bigquery_rows(
            client,
            f"""
            select
                (select count(*) from {marts}.fct_wage_observations`) as observation_count,
                (select count(*) from {marts}.mart_wage_observation_reconciliation`) as matrix_count,
                (select count(*) from {marts}.mart_industry_wages_2024`) as industry_category_count,
                (select sum(source_observation_count) from {marts}.mart_industry_wages_2024`) as industry_observation_count,
                (select count(*) from {marts}.mart_regional_wages_2024`) as regional_category_count,
                (select sum(source_observation_count) from {marts}.mart_regional_wages_2024`) as regional_observation_count,
                (select count(*) from {marts}.mart_benchmark_occupation_wages_2024`) as benchmark_observation_count,
                (select count(*) from {raw}.ows_ingestion_runs`) as ingestion_record_count
            """,
            location,
        ),
        "Wage summary",
    )
    industry = _bigquery_rows(
        client,
        f"""
        select
            industry_wage_mart_id, reference_year, source_matrix_id,
            wage_industry_id, industry_code, industry_name,
            average_monthly_basic_pay, average_monthly_allowance,
            average_monthly_wage_rate, source_observation_count
        from {marts}.mart_industry_wages_2024`
        order by industry_code
        """,
        location,
    )
    regional = _bigquery_rows(
        client,
        f"""
        select
            regional_wage_mart_id, reference_year, source_matrix_id,
            wage_region_id, region_code, region_name,
            average_monthly_basic_pay, average_monthly_allowance,
            average_monthly_wage_rate, source_observation_count
        from {marts}.mart_regional_wages_2024`
        order by region_code
        """,
        location,
    )
    benchmark = _bigquery_rows(
        client,
        f"""
        select
            benchmark_wage_mart_id, reference_year, source_matrix_id,
            benchmark_occupation_id, benchmark_occupation_name,
            wage_industry_id, industry_code, industry_name, sex_code, sex,
            average_monthly_wage_rate, source_measure_name,
            source_observation_count
        from {marts}.mart_benchmark_occupation_wages_2024`
        order by benchmark_occupation_id, industry_code, sex_code
        """,
        location,
    )
    reconciliation = _bigquery_rows(
        client,
        f"""
        select
            matrix_id, raw_observation_count, staging_observation_count,
            intermediate_observation_count, fact_observation_count,
            mart_accounted_observation_count, staging_difference,
            intermediate_difference, fact_difference, mart_difference,
            is_reconciled
        from {marts}.mart_wage_observation_reconciliation`
        order by matrix_id
        """,
        location,
    )
    provenance = _bigquery_rows(
        client,
        f"""
        select
            matrix_id, matrix_title, source_publisher, reference_year,
            canonical_endpoint, source_artifact_id, first_retrieval_id,
            first_retrieved_at, extraction_id, identifier_version
        from {raw}.ows_matrix_metadata`
        qualify row_number() over (
            partition by matrix_id order by loaded_at desc, source_artifact_id desc
        ) = 1
        order by matrix_id
        """,
        location,
    )
    governance = _bigquery_rows(
        client,
        f"""
        select
            governance_check_id, domain, check_type, status, observed_value,
            expected_value, latest_operational_at, latest_ingestion_id,
            source_reference_period, detail, evaluated_at
        from {marts}.mart_analytics_governance_summary`
        order by governance_check_id
        """,
        location,
    )
    return (
        {
            "benchmark_occupations": benchmark,
            "industry": industry,
            "provenance": provenance,
            "reconciliation": {
                "matrices": reconciliation,
                "summary": {
                    "matrix_count": len(reconciliation),
                    "maximum_difference": max(
                        abs(int(row["mart_difference"])) for row in reconciliation
                    ),
                    "reconciled_matrix_count": sum(
                        1 for row in reconciliation if row["is_reconciled"]
                    ),
                },
            },
            "regional": regional,
            "summary": summary,
        },
        governance,
    )


def export_governed_snapshot(
    *,
    people_database: Path,
    project: str,
    marts_dataset: str,
    wage_raw_dataset: str,
    location: str,
) -> dict[str, object]:
    """Read only governed outputs; never retrieve a source or write to a warehouse."""

    people = _people_snapshot(people_database)
    wage, governance = _wage_snapshot(
        project, marts_dataset, wage_raw_dataset, location
    )
    return {
        "governance": governance,
        "people": people,
        "snapshot_version": GOVERNED_SNAPSHOT_VERSION,
        "source_contracts": {
            "metrics": "analytics-portfolio-governed-metrics-v1",
            "presentation": "analytics-portfolio-presentation-v1",
        },
        "source_relations": {
            "people": [
                "metrics_people_monthly",
                "mart_data_quality_issues",
                "mart_headcount_reconciliation",
            ],
            "platform": ["mart_analytics_governance_summary"],
            "wage": [
                "mart_industry_wages_2024",
                "mart_regional_wages_2024",
                "mart_benchmark_occupation_wages_2024",
                "mart_wage_observation_reconciliation",
                "ows_matrix_metadata",
            ],
        },
        "wage": wage,
    }
