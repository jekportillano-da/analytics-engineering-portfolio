# Dagster OSS orchestration

## Architecture

Dagster exposes the platform's existing execution boundaries without moving
business logic into the orchestrator:

```text
people_source_generation -> people_bigquery_raw -> people_dbt_models --+
                                                                    +-> governed_analytics -> quality_freshness_reconciliation
wage_openstat_source ----> wage_bigquery_raw ----> wage_dbt_models --+
```

`people_pipeline`, `wage_pipeline`, and `full_portfolio_pipeline` select those
assets. Source integrity, ingestion, dbt, and governance are separate failure
boundaries; exceptions and non-zero dbt results fail their Dagster step.

People assets call the existing generator and BigQuery adapter directly. Wage
assets call the existing OpenSTAT, immutable-artifact reconciliation, and
idempotent BigQuery APIs when live retrieval is explicitly enabled. The default
Wage configuration verifies and reuses the already-loaded raw tables, so routine
local runs do not create redundant PSA retrievals.

## dbt integration

dbt remains the only transformation graph and its tests remain authoritative.
The orchestration layer invokes the pinned dbt CLI at coarse People, Wage, and
governance boundaries. `dagster-dbt` is intentionally not installed: the current
release requires `dbt-core <1.12` and would downgrade the validated dbt Core
1.12.3 environment. No parallel model-level Dagster graph is maintained.

## Local launch

From the repository root, supply the non-secret BigQuery variables shown in
`.env.example`, then run:

```powershell
$env:DAGSTER_HOME = "$PWD\.local\dagster"
New-Item -ItemType Directory -Force $env:DAGSTER_HOME | Out-Null
.\.venv\Scripts\dagster.exe dev -m orchestration.definitions
```

The UI exposes assets, the three jobs, dependencies, run history, execution
status, and coarse dbt execution boundaries. dbt's generated documentation
remains the authoritative model-level lineage catalog.

`wage_openstat_source` defaults to `retrieve_live: false`. Set it to `true` in
Dagster run configuration only when a deliberate new PSA retrieval is required.
`people_bigquery_raw` defaults to `replace_existing: false`; replacement of the
configured People raw tables must be explicitly enabled for a rerun.

Configuration is read from the existing `BIGQUERY_PROJECT`,
`PEOPLE_BIGQUERY_RAW_DATASET`, `WAGE_BIGQUERY_RAW_DATASET`,
`DBT_BIGQUERY_DATASET`, `BIGQUERY_LOCATION`, and `WAGE_OPENSTAT_LOCAL_ROOT`
environment variables. Optional `PEOPLE_SCENARIO_PATH`,
`PEOPLE_ORCHESTRATION_RAW_DIR`, and `DBT_EXECUTABLE` overrides are also supported.
Credentials continue to come from Application Default Credentials and are never
stored by Dagster.

No schedules, sensors, daemon, or hosted deployment are configured. Scheduling
is deferred until operational cadence, ownership, and cost controls are defined.
