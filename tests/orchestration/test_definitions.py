from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import dagster as dg
import pytest

from orchestration.assets import WageSourceConfig
from orchestration.definitions import PROJECT_ROOT, defs
from orchestration.resources import (
    DbtCliResource,
    PortfolioConfigResource,
)


def _portfolio_resource(tmp_path: Path) -> PortfolioConfigResource:
    return PortfolioConfigResource(
        project_id="example-project",
        people_raw_dataset="people_raw",
        wage_raw_dataset="wage_raw",
        dbt_base_dataset="analytics_dev",
        location="US",
        people_scenario_path=str(tmp_path / "scenario.yml"),
        people_raw_dir=str(tmp_path / "people"),
        wage_local_root=str(tmp_path / "wage"),
    )


def test_definitions_and_jobs_load() -> None:
    dg.Definitions.validate_loadable(defs)
    assert {job.name for job in defs.resolve_all_job_defs()} >= {
        "people_pipeline",
        "wage_pipeline",
        "full_portfolio_pipeline",
    }


def test_asset_dependencies_resolve() -> None:
    graph = defs.resolve_asset_graph()

    def parent_keys(name: str) -> set[str]:
        node = graph.get(dg.AssetKey(name))
        return {parent.key.to_user_string() for parent in graph.get_parents(node)}

    assert parent_keys("people_bigquery_raw") == {"people_source_generation"}
    assert parent_keys("people_dbt_models") == {"people_bigquery_raw"}
    assert parent_keys("wage_bigquery_raw") == {"wage_openstat_source"}
    assert parent_keys("wage_dbt_models") == {"wage_bigquery_raw"}
    assert parent_keys("governed_analytics") == {
        "people_dbt_models",
        "wage_dbt_models",
    }
    assert parent_keys("quality_freshness_reconciliation") == {"governed_analytics"}


def test_resources_resolve_existing_dbt_project(tmp_path: Path) -> None:
    portfolio = _portfolio_resource(tmp_path)
    assert portfolio.dbt_environment() == {
        "BIGQUERY_PROJECT": "example-project",
        "PEOPLE_BIGQUERY_RAW_DATASET": "people_raw",
        "WAGE_BIGQUERY_RAW_DATASET": "wage_raw",
        "DBT_BIGQUERY_DATASET": "analytics_dev",
        "BIGQUERY_LOCATION": "US",
    }

    dbt = defs.resources["dbt"]
    _, project_dir, profiles_dir = dbt.validate_project()
    assert project_dir == PROJECT_ROOT / "dbt"
    assert profiles_dir == PROJECT_ROOT / "dbt"


def test_wage_source_defaults_to_existing_raw() -> None:
    assert WageSourceConfig().retrieve_live is False


def test_dbt_failure_surfaces_as_failed_orchestration_step(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dbt = defs.resources["dbt"]

    def fail_dbt(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=2, stdout="controlled dbt failure")

    monkeypatch.setattr(subprocess, "run", fail_dbt)

    @dg.asset
    def failing_dbt_asset(dbt: DbtCliResource) -> None:
        dbt.run(("build",), _portfolio_resource(tmp_path).dbt_environment())

    result = dg.materialize(
        [failing_dbt_asset],
        resources={"dbt": dbt},
        raise_on_error=False,
    )
    assert result.success is False
    assert any(event.is_step_failure for event in result.all_events)
