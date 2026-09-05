# Governed analytics layer

## Metric mechanism

V1 uses executable relational metric contracts, not the dbt Semantic Layer. The
installed dbt Core stack includes semantic-interface and MetricFlow libraries as
internal dependencies, but exposes no supported MetricFlow query CLI or semantic
service. Adding another runtime solely for branding would increase compatibility
risk without improving the platform.

The machine-readable contract is
`contracts/metrics/v1/governed_metrics.yml`. dbt builds its governed query
surfaces as `metrics_people_monthly` and `metrics_wage_published`. Schema and
singular tests prove that these relations reproduce the validated source marts
and fact exactly. People metrics retain their existing formulas. Wage measures
remain one PSA-published value per valid source grain and have no default SUM or
AVG behavior.

## Freshness and reference periods

Operational freshness answers when the platform last loaded or successfully
retrieved a source. It does not change the dates represented by the data.

- People uses `raw.file_manifest.loaded_at`.
- Wage uses `wage_raw.ows_ingestion_runs.retrieval_completed_at`, filtered to
  successful retrievals with successful extraction.
- Both use demo thresholds of 48 hours for warning and 168 hours for error.
- People metrics represent the configured synthetic 2023-2025 analysis window.
- Wage measures remain PSA 2024 OWS data even after a later successful retrieval.

Run the operational checks with:

```text
dbt source freshness --project-dir dbt --profiles-dir dbt --target bigquery
```

No recurring schedule is currently configured.

## Quality and catalog

`mart_analytics_governance_summary` exposes five concise controls: People quality
issues, People reconciliation, People operational freshness, Wage reconciliation,
and Wage operational freshness. It reuses existing governed marts and raw load
metadata. `review_required` on the People issue control means intentional quality
fixtures remain visible; it is not a hidden transformation failure.

The combined lineage and catalog are generated with:

```text
dbt docs generate --project-dir dbt --profiles-dir dbt --target bigquery
```

`manifest.json`, `catalog.json`, and `index.html` remain ignored under `dbt/target`.
The manifest contains source-to-staging-to-intermediate-to-mart dependencies,
relationship tests, grains, and People/Wage ownership metadata.

## Presentation boundary

Governed outputs feed a versioned presentation contract before frontend
consumption:

```text
Governed Data Products
  -> Presentation Contract
  -> Executive Insight Engine
  -> THREADLINE Executive Reporting Frontend
  -> Decision Support / Investigation
       active          active              active               active
```

The presentation generator copies already-calculated metrics, quality states,
reconciliation, and compact provenance into deterministic JSON. The executive
insight engine then derives a small set of deterministic observations, comparison
arithmetic, evidence references, limitations, and related questions solely from
those presentation artifacts. It does not query the warehouse, claim causality,
forecast, recommend actions, or move analytical formulas into frontend code.

Decision support means surfacing evidence-backed observations and questions for
human investigation; it does not mean automated business decisions. The THREADLINE
Next.js presentation application is deployed on Vercel as the public consumption
layer of the governed platform. See `docs/presentation-layer.md` for the V1
consumer rules and `contracts/insights/v1/executive_insights.yml` for the insight
contract.
