"""Coarse Dagster assets around the platform's existing domain and dbt APIs."""

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import dagster as dg
from google.cloud import bigquery

from analytics_platform.domains.people.config import load_scenario
from analytics_platform.domains.people.generator import GenerationSummary, generate_dataset
from analytics_platform.domains.people.ingestion.bigquery import (
    BigQueryRawVerificationSummary,
    load_raw_dataset,
    verify_raw_dataset,
)
from analytics_platform.domains.wage.ingestion.bigquery import (
    TABLE_CONTRACTS,
    load_wage_raw,
    verify_wage_raw,
)
from analytics_platform.domains.wage.ingestion.openstat import (
    MATRIX_SPECS,
    AcquiredMatrix,
    OpenSTATHTTPClient,
    acquire_matrix,
    validate_representative_values,
)
from analytics_platform.platform.provenance.reconciliation import reconcile_artifacts
from orchestration.resources import (
    DbtCliResource,
    DbtCommandResult,
    PortfolioConfigResource,
)


@dataclass(frozen=True)
class WageSourceBatch:
    mode: str
    acquisitions: tuple[AcquiredMatrix, ...]


@dataclass(frozen=True)
class WageRawState:
    mode: str
    table_row_counts: dict[str, int]


class PeopleRawConfig(dg.Config):
    replace_existing: bool = False


class WageSourceConfig(dg.Config):
    retrieve_live: bool = False


def _run_dbt(
    context,
    dbt: DbtCliResource,
    portfolio: PortfolioConfigResource,
    arguments: Sequence[str],
) -> DbtCommandResult:
    result = dbt.run(arguments, portfolio.dbt_environment())
    if result.output.strip():
        context.log.info(result.output.rstrip())
    context.add_output_metadata(
        {
            "target": dbt.target,
            "command": " ".join(result.command),
        }
    )
    return result


@dg.asset(
    group_name="people",
    kinds={"python"},
    owners=["team:analytics-engineering"],
    description="Generate the deterministic People baseline source files.",
)
def people_source_generation(
    context,
    portfolio: PortfolioConfigResource,
) -> GenerationSummary:
    scenario = load_scenario(Path(portfolio.people_scenario_path).resolve())
    summary = generate_dataset(scenario, Path(portfolio.people_raw_dir).resolve())
    context.add_output_metadata(
        {
            "scenario": scenario.name,
            "seed": scenario.seed,
            "source_files": len(summary.row_counts),
            "source_rows": sum(summary.row_counts.values()),
            "output_dir": str(summary.output_dir),
        }
    )
    return summary


@dg.asset(
    group_name="people",
    kinds={"bigquery"},
    owners=["team:analytics-engineering"],
    description="Load and verify generated People files in the configured BigQuery raw dataset.",
)
def people_bigquery_raw(
    context,
    people_source_generation: GenerationSummary,
    portfolio: PortfolioConfigResource,
    config: PeopleRawConfig,
) -> BigQueryRawVerificationSummary:
    portfolio.validate_cloud()
    load_raw_dataset(
        people_source_generation.output_dir,
        portfolio.project_id,
        portfolio.people_raw_dataset,
        portfolio.location,
        replace=config.replace_existing,
    )
    verification = verify_raw_dataset(
        people_source_generation.output_dir,
        portfolio.project_id,
        portfolio.people_raw_dataset,
        portfolio.location,
    )
    context.add_output_metadata(
        {
            "dataset": f"{verification.project_id}.{verification.dataset_id}",
            "manifest_files": verification.manifest_count,
            "raw_rows": sum(verification.row_counts.values()),
            "replace_existing": config.replace_existing,
        }
    )
    return verification


@dg.asset(
    group_name="wage",
    kinds={"python"},
    owners=["team:analytics-engineering"],
    description="Use existing Wage raw data by default or explicitly retrieve PSA OpenSTAT matrices.",
)
def wage_openstat_source(
    context,
    portfolio: PortfolioConfigResource,
    config: WageSourceConfig,
) -> WageSourceBatch:
    if not config.retrieve_live:
        context.log.info(
            "Live PSA retrieval disabled; the Wage raw asset will verify existing BigQuery tables."
        )
        context.add_output_metadata({"mode": "existing_bigquery_raw", "live_http": False})
        return WageSourceBatch(mode="existing_bigquery_raw", acquisitions=())

    local_root = Path(portfolio.wage_local_root).resolve()
    client = OpenSTATHTTPClient()
    acquisitions = tuple(
        acquire_matrix(spec, local_root, client=client) for spec in MATRIX_SPECS
    )
    validate_representative_values(acquisitions)
    reconciliation = reconcile_artifacts(
        local_root, [item.artifact for item in acquisitions]
    )
    blocking = [
        finding
        for finding in reconciliation.findings
        if finding.severity == "error" or finding.code == "STAGING_FILE_PRESENT"
    ]
    if blocking:
        codes = ", ".join(finding.code for finding in blocking)
        raise RuntimeError(f"Local immutable artifact reconciliation failed: {codes}")
    context.add_output_metadata(
        {
            "mode": "live_openstat",
            "live_http": True,
            "matrices": len(acquisitions),
            "observations": sum(len(item.observations) for item in acquisitions),
        }
    )
    return WageSourceBatch(mode="live_openstat", acquisitions=acquisitions)


def _existing_wage_table_counts(portfolio: PortfolioConfigResource) -> dict[str, int]:
    client = bigquery.Client(project=portfolio.project_id, location=portfolio.location)
    if client.project != portfolio.project_id:
        raise ValueError("BigQuery client project does not match orchestration configuration")
    dataset = client.get_dataset(
        bigquery.DatasetReference(portfolio.project_id, portfolio.wage_raw_dataset)
    )
    if dataset.location and dataset.location.upper() != portfolio.location.upper():
        raise ValueError("Existing Wage raw dataset is in the wrong location")
    counts = {
        table_name: int(
            client.get_table(
                f"{portfolio.project_id}.{portfolio.wage_raw_dataset}.{table_name}"
            ).num_rows
        )
        for table_name in TABLE_CONTRACTS
    }
    if any(row_count <= 0 for row_count in counts.values()):
        raise ValueError("Existing Wage raw tables must be non-empty")
    return counts


@dg.asset(
    group_name="wage",
    kinds={"bigquery"},
    owners=["team:analytics-engineering"],
    description="Load a live Wage acquisition idempotently or verify the existing raw tables.",
)
def wage_bigquery_raw(
    context,
    wage_openstat_source: WageSourceBatch,
    portfolio: PortfolioConfigResource,
) -> WageRawState:
    portfolio.validate_cloud()
    if wage_openstat_source.acquisitions:
        load_wage_raw(
            wage_openstat_source.acquisitions,
            portfolio.project_id,
            portfolio.wage_raw_dataset,
            portfolio.location,
        )
        verification = verify_wage_raw(
            wage_openstat_source.acquisitions,
            portfolio.project_id,
            portfolio.wage_raw_dataset,
            portfolio.location,
        )
        counts = verification.table_row_counts
    else:
        counts = _existing_wage_table_counts(portfolio)
    context.add_output_metadata(
        {
            "mode": wage_openstat_source.mode,
            "dataset": f"{portfolio.project_id}.{portfolio.wage_raw_dataset}",
            "observations": counts["ows_observations"],
            "matrix_metadata": counts["ows_matrix_metadata"],
            "ingestion_runs": counts["ows_ingestion_runs"],
        }
    )
    return WageRawState(mode=wage_openstat_source.mode, table_row_counts=counts)


@dg.asset(
    deps=[people_bigquery_raw],
    group_name="people",
    kinds={"dbt"},
    owners=["team:analytics-engineering"],
    description="Build and test the existing People dbt lineage and governed metrics.",
)
def people_dbt_models(
    context,
    portfolio: PortfolioConfigResource,
    dbt: DbtCliResource,
) -> DbtCommandResult:
    return _run_dbt(
        context,
        dbt,
        portfolio,
        (
            "build",
            "--select",
            "+metrics_people_monthly",
            "+mart_data_quality_issues",
            "+mart_headcount_reconciliation",
        ),
    )


@dg.asset(
    deps=[wage_bigquery_raw],
    group_name="wage",
    kinds={"dbt"},
    owners=["team:analytics-engineering"],
    description="Build and test the existing Wage dbt lineage, marts, and governed measures.",
)
def wage_dbt_models(
    context,
    portfolio: PortfolioConfigResource,
    dbt: DbtCliResource,
) -> DbtCommandResult:
    return _run_dbt(
        context,
        dbt,
        portfolio,
        (
            "build",
            "--select",
            "+metrics_wage_published",
            "+mart_wage_observation_reconciliation",
        ),
    )


@dg.asset(
    deps=[people_dbt_models, wage_dbt_models],
    group_name="governance",
    kinds={"dbt"},
    owners=["team:analytics-engineering"],
    description="Build the existing cross-domain governed analytics summary.",
)
def governed_analytics(
    context,
    portfolio: PortfolioConfigResource,
    dbt: DbtCliResource,
) -> DbtCommandResult:
    return _run_dbt(
        context,
        dbt,
        portfolio,
        ("run", "--select", "mart_analytics_governance_summary"),
    )


@dg.asset(
    deps=[governed_analytics],
    group_name="governance",
    kinds={"dbt"},
    owners=["team:analytics-engineering"],
    description="Run source freshness and governance tests as an explicit failure boundary.",
)
def quality_freshness_reconciliation(
    context,
    portfolio: PortfolioConfigResource,
    dbt: DbtCliResource,
) -> None:
    _run_dbt(context, dbt, portfolio, ("source", "freshness"))
    _run_dbt(
        context,
        dbt,
        portfolio,
        ("test", "--select", "mart_analytics_governance_summary"),
    )


ALL_ASSETS = (
    people_source_generation,
    people_bigquery_raw,
    people_dbt_models,
    wage_openstat_source,
    wage_bigquery_raw,
    wage_dbt_models,
    governed_analytics,
    quality_freshness_reconciliation,
)
