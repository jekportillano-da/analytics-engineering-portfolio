# Frontend handoff: presentation contract V1

## Stable integration boundary

The planned Next.js application must read the six committed JSON files under
`presentation/data/`. Their envelope is defined by
`contracts/presentation/v1/presentation.yml` and identified as
`analytics-portfolio-presentation-v1`.

| Artifact | Purpose |
| --- | --- |
| `insights.json` | Authoritative executive questions, findings, evidence references, limitations, and investigation paths |
| `platform.json` | Domains, data products, responsibility split, and capability status |
| `people.json` | Governed monthly People metrics, quality summary, and reconciliation |
| `wage.json` | Governed 2024 industry, regional, and benchmark-occupation wage products |
| `quality.json` | Quality, freshness, and reconciliation contracts and evaluated controls |
| `lineage.json` | Portfolio-level architecture graph and compact source provenance |

All artifact IDs are stable (`presentation.<artifact-type>.v1`), every file is
canonical UTF-8 JSON, and arrays are emitted in deterministic order.

`insights.json` additionally conforms to
`contracts/insights/v1/executive_insights.yml`, identified as
`analytics-portfolio-executive-insights-v1`. Each insight has a stable
`insight_id`, a stable `question_id`, declared governed `metric_ids`, and
machine-resolvable evidence references. An evidence reference names the source
presentation artifact, collection, record identity when applicable, field,
observed value, governed source, period, and dimensions. This is the audit path
for answering, "Why does the product say this?"

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

The executive finding, narrative, comparison arithmetic, evidence state, and
limitations in `insights.json` are also authoritative platform outputs. The
frontend must not invent findings, reinterpret comparison methods or thresholds,
or add causal explanations. It may visualize the referenced evidence, format
values, filter approved presentation dimensions, navigate `next_question_ids`,
animate transitions, provide drill-down interactions, and surface limitations or
provenance.

## Responsibility boundary

The analytics platform owns ingestion, metric calculation, aggregation,
reconciliation, quality, provenance, business definitions, deterministic
comparison logic, and executive findings. The presentation application owns
visualization, interaction, filtering over approved fields, question navigation,
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
the six files and review their diff.

## Executive insight and decision-support semantics

The active analytical flow is:

```text
Governed Data Products
  -> Presentation Contract
  -> Executive Insight Engine
  -> planned Executive Reporting Frontend
  -> evidence-led Decision Support / Investigation
```

The insight engine is deterministic and offline. It identifies observable
comparisons, extrema, and governance states from the presentation contract; it is
not an LLM, recommendation engine, causal model, forecasting system, or automated
decision maker. "Decision support" means giving an executive a traceable finding
and a structured next question. Business decisions and causal investigation
remain human responsibilities.

## Active, planned, and deferred capabilities

The warehouse/dbt/governed-product/presentation-contract/insight-engine path is
active. Next.js and Vercel are planned presentation targets and are not deployed.
The vector-ready contract is an optional boundary; embeddings, vector storage,
RAG, and agent consumers remain deferred and are not available to the frontend.

## Public CI boundary

Public CI installs the supported Python stack, runs all Python tests, regenerates
and diffs the presentation files from the committed governed snapshot, runs the
People DuckDB/dbt build, and validates Dagster definitions. It uses no GCP, PSA,
embedding, vector-store, or deployment credentials.

BigQuery dbt builds and governed snapshot refreshes remain outside public CI
because they require cloud identity and may create query cost or replace managed
relations. Live PSA acquisition remains an explicit, independently controlled
ingestion operation.
