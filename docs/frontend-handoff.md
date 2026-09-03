# Frontend handoff: presentation contract V1

## Stable integration boundary

The planned Next.js application must read the five committed JSON files under
`presentation/data/`. Their envelope is defined by
`contracts/presentation/v1/presentation.yml` and identified as
`analytics-portfolio-presentation-v1`.

| Artifact | Purpose |
| --- | --- |
| `platform.json` | Domains, data products, responsibility split, and capability status |
| `people.json` | Governed monthly People metrics, quality summary, and reconciliation |
| `wage.json` | Governed 2024 industry, regional, and benchmark-occupation wage products |
| `quality.json` | Quality, freshness, and reconciliation contracts and evaluated controls |
| `lineage.json` | Portfolio-level architecture graph and compact source provenance |

All artifact IDs are stable (`presentation.<artifact-type>.v1`), every file is
canonical UTF-8 JSON, and arrays are emitted in deterministic order.

## Safe display and filtering

The frontend may filter, sort, group for display, paginate, format numbers, and
select chart dimensions already present in an artifact. Useful approved fields
include People periods and metric values; Wage industry, region, benchmark
occupation, sex, measure, and reference year; governance domain, check type, and
status; and lineage node/edge status.

Metric definitions, aggregation behavior, numerator/denominator fields,
limitations, reference periods, reconciliation results, and quality states are
canonical platform outputs. The frontend must not recalculate or redefine them.
In particular, Wage values are non-additive PSA-published source values and must
not be summed or averaged across categories.

These files are static, versioned snapshots rather than live telemetry. Freshness
and health fields reflect the evaluation recorded in the governed snapshot. The
frontend must display that context and must not present it as a live warehouse
status check.

The artifacts contain no row-level worker or employment records. They must remain
free of credentials and machine-specific paths.

## Responsibility boundary

The analytics platform owns ingestion, metric calculation, aggregation,
reconciliation, quality, provenance, and business definitions. The presentation
application owns visualization, interaction, filtering over approved fields,
layout, accessibility, and formatting.

Browser code must never connect directly to BigQuery or receive GCP credentials.
The committed files are the frontend data boundary; internal dbt relations and
the governed snapshot are not browser APIs.

## Regeneration

Artifact generation is network-free and suitable for CI:

```text
python -m analytics_platform.presentation.cli generate
python -m analytics_platform.presentation.cli validate
```

Refreshing the intermediate governed snapshot is a separate operator action. It
requires an already-built local People DuckDB plus read-only ADC access to the
existing Wage and governance marts:

```powershell
python -m analytics_platform.presentation.cli snapshot `
  --people-database .local/checkpoint/people_analytics.duckdb `
  --project <gcp-project> `
  --marts-dataset <dbt-base-dataset>_marts `
  --wage-raw-dataset <wage-raw-dataset> `
  --location <bigquery-location>
```

The snapshot command reads governed relations only. It does not write BigQuery,
retrieve PSA data, or calculate a metric. After an intentional refresh, regenerate
the five files and review their diff.

## Active, planned, and deferred capabilities

The warehouse/dbt/governed-product/presentation-contract path is active. Next.js
and Vercel are planned presentation targets and are not deployed. The vector-ready
contract is an optional boundary; embeddings, vector storage, RAG, and agent
consumers remain deferred and are not available to the frontend.

## Public CI boundary

Public CI installs the supported Python stack, runs all Python tests, regenerates
and diffs the presentation files from the committed governed snapshot, runs the
People DuckDB/dbt build, and validates Dagster definitions. It uses no GCP, PSA,
embedding, vector-store, or deployment credentials.

BigQuery dbt builds and governed snapshot refreshes remain outside public CI
because they require cloud identity and may create query cost or replace managed
relations. Live PSA acquisition remains an explicit, independently controlled
ingestion operation.
