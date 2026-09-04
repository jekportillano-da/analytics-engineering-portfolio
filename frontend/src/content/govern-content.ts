import type { TechnicalDetail } from "@/content/journey-content";

export const governDetails = {
  reconciliation: { title: "Reconciliation", summary: "Tests whether governed transformations preserve the expected analytical totals.", detail: "People reconciliation compares monthly opening headcount, hires, separations, and ending headcount. Wage reconciliation accounts for source observations from raw through mart. It is distinct from record-quality rules.", sourceReference: "dbt/models/marts/governance/mart_analytics_governance_summary.sql" },
  freshness: { title: "Operational freshness", summary: "When the platform last loaded or successfully retrieved a source.", detail: "People freshness reads raw.file_manifest.loaded_at. Wage freshness reads successful wage_raw.ows_ingestion_runs.retrieval_completed_at. The analytical reference period remains independent from that operational timestamp.", sourceReference: "contracts/metrics/v1/governed_metrics.yml" },
  lineage: { title: "Governance lineage", summary: "A traceable route from source to governed output and presentation.", detail: "The presentation lineage artifact records the active source, ingestion, BigQuery raw, dbt, governed product, presentation-contract, and insight-engine path. The browser consumes that curated contract, not dbt build artifacts.", sourceReference: "presentation/data/lineage.json" },
  contracts: { title: "Governed contracts", summary: "Versioned boundaries keep definitions and consumption responsibilities explicit.", detail: "The relational metric contract defines governed metrics; the presentation contract defines safe curated frontend artifacts; the Executive Insight Contract defines deterministic, evidence-backed executive observations. V1 does not use a native dbt Semantic Layer.", sourceReference: "contracts/metrics/v1/governed_metrics.yml; contracts/presentation/v1/presentation.yml; contracts/insights/v1/executive_insights.yml" },
} satisfies Record<string, TechnicalDetail>;

export const validationArchitecture = [
  ["Python test suite", "Public CI runs the repository Python tests.", ".github/workflows/ci.yml"],
  ["Presentation contract", "CI regenerates the deterministic artifacts, requires no diff, and validates the presentation contract.", ".github/workflows/ci.yml"],
  ["People local validation", "CI generates and loads People sources, then runs dbt build against DuckDB.", ".github/workflows/ci.yml"],
  ["Dagster definitions", "CI validates loadable Dagster definitions.", ".github/workflows/ci.yml"],
] as const;

export const intentionallyOutOfCi = ["BigQuery builds", "Live PSA acquisition", "Governed snapshot refresh", "Deployment", "Embedding and vector infrastructure"] as const;