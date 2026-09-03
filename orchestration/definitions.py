"""Loadable Dagster definitions for local portfolio orchestration."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import dagster as dg

from orchestration.assets import (
    ALL_ASSETS,
    governed_analytics,
    people_bigquery_raw,
    people_dbt_models,
    people_source_generation,
    quality_freshness_reconciliation,
    wage_bigquery_raw,
    wage_dbt_models,
    wage_openstat_source,
)
from orchestration.resources import DbtCliResource, PortfolioConfigResource


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _dbt_executable() -> str:
    configured = os.environ.get("DBT_EXECUTABLE")
    if configured:
        return configured
    discovered = shutil.which("dbt")
    if discovered:
        return discovered
    executable_name = "dbt.exe" if os.name == "nt" else "dbt"
    return str(Path(sys.executable).resolve().parent / executable_name)


people_pipeline = dg.define_asset_job(
    "people_pipeline",
    selection=dg.AssetSelection.assets(
        people_source_generation,
        people_bigquery_raw,
        people_dbt_models,
    ),
    description="Generate and ingest People raw data, then build and test People dbt models.",
)

wage_pipeline = dg.define_asset_job(
    "wage_pipeline",
    selection=dg.AssetSelection.assets(
        wage_openstat_source,
        wage_bigquery_raw,
        wage_dbt_models,
    ),
    description="Reuse existing Wage raw data by default, or explicitly retrieve and ingest PSA data.",
)

full_portfolio_pipeline = dg.define_asset_job(
    "full_portfolio_pipeline",
    selection=dg.AssetSelection.assets(*ALL_ASSETS),
    description="Run both domains followed by governed analytics and quality controls.",
)

defs = dg.Definitions(
    assets=ALL_ASSETS,
    jobs=(people_pipeline, wage_pipeline, full_portfolio_pipeline),
    resources={
        "portfolio": PortfolioConfigResource.from_environment(PROJECT_ROOT),
        "dbt": DbtCliResource(
            executable=_dbt_executable(),
            project_dir=str(PROJECT_ROOT / "dbt"),
            profiles_dir=str(PROJECT_ROOT / "dbt"),
            target="bigquery",
        ),
    },
)
