# THREADLINE
## Analytics Engineering Platform

**From source data to governed analytics to traceable executive reporting.**

THREADLINE is an end-to-end analytics engineering platform and technical portfolio demonstrating how raw source data can be acquired, modeled, governed, validated, transformed into analytical products, and ultimately presented as evidence-backed executive insight.

**Live platform:**
https://analytics-engineering-portfolio-two.vercel.app

The platform uses two independent analytical domains:

- **People Analytics** — the primary end-to-end domain, demonstrating temporal workforce modeling, governed metrics, data quality, reconciliation, orchestration, and executive reporting.
- **Wage Analytics** — a secondary domain using authoritative Philippine Statistics Authority OpenSTAT data to demonstrate that the architecture can be reused across a different source, grain, and analytical problem.

---

## Platform Journey

```text
SOURCE → INGEST → MODEL → GOVERN → INSIGHT → PRESENT
```

THREADLINE exposes the complete analytical lifecycle through six permanent lenses.

| Stage | Purpose |
| --- | --- |
| **SOURCE** | Establish where data originates, its scope, reliability, grain, and limitations |
| **INGEST** | Acquire, identify, preserve, and land source data reproducibly |
| **MODEL** | Transform raw data through staging, intermediate models, dimensions, facts, marts, and governed metrics |
| **GOVERN** | Validate quality, freshness, reconciliation, provenance, lineage, and contract conformance |
| **INSIGHT** | Explore governed analytical products through interactive BI-style views |
| **PRESENT** | Distill validated evidence into traceable executive reporting |

The website is not separate from the analytical platform. It is the final consumption layer of the same governed system.

---

## Architecture

```mermaid
flowchart LR
    A[Source Systems] --> B[Ingestion]
    B --> C[Raw Layer]
    C --> D[dbt Staging]
    D --> E[Intermediate Models]
    E --> F[Dimensions and Facts]
    F --> G[Analytical Marts]
    G --> H[Governed Metrics]
    H --> I[Presentation Contract]
    I --> J[Executive Insight Engine]
    J --> K[THREADLINE]
```

### Core Stack

**Analytics Engineering**

- Python
- SQL
- dbt Core
- BigQuery
- DuckDB
- Dagster

**Presentation**

- Next.js
- React
- TypeScript
- Recharts
- Vercel

**Engineering Workflow**

- Git
- GitHub
- GitHub Actions
- deterministic artifact generation
- automated testing
- contract validation

---

## People Analytics

People Analytics is the primary enterprise-style domain.

Its pipeline demonstrates the complete analytical path:

```text
deterministic source generation
→ raw ingestion
→ dbt staging
→ intermediate transformation
→ dimensions and facts
→ analytical marts
→ governed metrics
→ executive insights
```

The workforce model applies effective-date logic when determining whether an employment spell is active on a given snapshot date:

```sql
hire_date <= snapshot_date
AND snapshot_date < termination_date
```

Key modeled products include:

```text
dim_worker
dim_job
dim_org_unit
dim_location
fct_workforce_daily
fct_workforce_events
mart_workforce_monthly
metrics_people_monthly
```

Governed metrics include:

```text
Ending Headcount
Hires
Separations
Attrition Rate
```

The synthetic People source intentionally contains controlled data-quality conditions. This allows governance behavior to be demonstrated rather than merely described.

---

## Wage Analytics

Wage Analytics demonstrates that the analytical architecture is reusable beyond People data.

The source is the **Philippine Statistics Authority OpenSTAT API**, using published 2024 Occupational Wages Survey data.

The platform preserves source identity and source grain through independently governed products for:

```text
Industry wages
Regional wages
Benchmark occupations
Wage measures
Reconciliation
```

Published wage observations are treated as **non-additive source-grain values**.

THREADLINE therefore does not manufacture sums or averages across incompatible wage categories simply to make visualization easier.

The People and Wage domains are also intentionally **not joined**.

The repository does not contain the compatible compensation mappings and shared dimensional grain required to support that relationship responsibly.

That absence is an architectural decision rather than a missing feature.

---

## Governance and Trust

THREADLINE treats analytical trust as part of the product.

The platform includes:

- data-quality controls
- freshness evaluation
- reconciliation
- deterministic identifiers
- lineage
- provenance
- metric definitions
- executable presentation contracts
- CI validation

The presentation application consumes six committed analytical artifacts:

```text
platform.json
people.json
wage.json
quality.json
lineage.json
insights.json
```

These files form the governed boundary between the analytical platform and the frontend.

The browser does **not** query BigQuery directly and receives no GCP credentials.

The artifacts are deterministic, versioned snapshots rather than live warehouse telemetry.

---

## Executive Insight Engine

THREADLINE includes a deterministic executive-insight layer.

Its reporting flow is:

```text
QUESTION
→ FINDING
→ EVIDENCE
→ LIMITATION
→ NEXT QUESTION
```

Executive findings are generated upstream from governed analytical evidence and contain stable identifiers and machine-resolvable evidence references.

This allows the presentation layer to answer:

> **Why does THREADLINE say this?**

without recalculating the underlying analysis in the browser.

The Executive Insight Engine is deliberately not:

```text
an LLM
a recommendation engine
a forecasting system
a causal model
an automated decision maker
```

Its role is evidence-led decision support.

Interpretation, investigation, and business decisions remain human responsibilities.

---

## Presentation Contract

Analytical responsibility remains upstream of the frontend.

```text
Analytics Platform
├── ingestion
├── transformation
├── metric calculation
├── aggregation
├── reconciliation
├── quality
├── provenance
├── executive findings
└── presentation contract

THREADLINE Frontend
├── visualization
├── interaction
├── approved filtering
├── question navigation
├── technical disclosure
├── accessibility
└── formatting
```

This separation prevents the reporting layer from quietly becoming a second analytics engine.

The frontend may filter, sort, select, and format governed values for presentation.

It does not redefine metrics, invent executive findings, calculate unsupported comparisons, or infer causality.

---

## Validation

Public CI validates the platform without requiring production cloud credentials.

```text
Python test suite
        ↓
Presentation artifact regeneration
        ↓
Determinism and contract validation
        ↓
People source generation
        ↓
DuckDB load
        ↓
dbt build and tests
        ↓
Dagster definitions validation
```

Cloud-dependent operations remain intentionally outside public CI.

These include:

```text
BigQuery builds
governed snapshot refreshes
live PSA retrieval
deployment operations
```

This keeps public CI reproducible while avoiding hidden cloud identity, external-source, and cost dependencies.

---

## Engineering Decisions

Several technologies and relationships were deliberately not forced into the architecture.

### No artificial People ↔ Wage join

The required compatible dimensions and compensation mappings do not currently exist.

Creating a join merely for demonstration would misrepresent the data.

### No direct browser → BigQuery connection

THREADLINE consumes governed presentation artifacts rather than exposing warehouse credentials or treating internal warehouse relations as browser APIs.

### No active vector database or RAG layer

Structured analytical questions are better served deterministically through SQL and dbt.

Vendor-neutral vector interfaces exist only as a future-ready boundary for genuine unstructured-data use cases.

### No automated executive recommendations

The platform surfaces observed evidence, limitations, and investigation paths without pretending observational data proves causality.

---

## Repository Structure

```text
analytics-engineering-portfolio/
├── .github/
├── analytics/
├── contracts/
├── dbt/
├── docs/
├── frontend/
├── orchestration/
├── presentation/
├── src/
├── tests/
├── README.md
└── pyproject.toml
```

The repository intentionally separates ingestion, analytical computation, orchestration, contracts, governed presentation artifacts, and frontend concerns.

---

## Explore THREADLINE

**Live application**

https://analytics-engineering-portfolio-two.vercel.app

Start with **SOURCE** and follow the lifecycle through **PRESENT**.

Technical reviewers can progressively move from executive and analytical views into model responsibilities, provenance, governance controls, engineering decisions, and evidence lineage.

---

## Current Status

THREADLINE is implemented and publicly deployed.

The analytical platform, governed data products, Executive Insight Engine, interactive analytics layer, and executive reporting experience are implemented and validated.

The repository is preparing for its first formal public release.
