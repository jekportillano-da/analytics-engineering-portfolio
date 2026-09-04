import type { TechnicalDetail } from "@/content/journey-content";

export type MetricTrace = {
  id: string;
  label: string;
  inputGrain: string;
  transform: string;
  outputGrain: string;
  destination: string;
  path: string[];
  excerpt?: string;
  sourceReference: string;
};

export const modelDetails = {
  temporalModel: { title: "Temporal workforce model", summary: "Workforce state is evaluated against a date, not inferred from one employee count.", detail: "People active employment is resolved by joining valid employment spells to the date spine. A spell is active when hire_date is on or before the snapshot date and termination_date is absent or after that date. The daily fact then resolves the current usable job assignment for each active spell.", sourceReference: "dbt/models/intermediate/people/int_active_employment_daily.sql" },
  grain: { title: "Model grain", summary: "What one modeled row represents.", detail: "People daily workforce records are scoped to a snapshot date and employment spell. Wage facts retain a logical source observation, including its matrix scope and applicable dimension context. Preserving these grains prevents invalid aggregation or comparison.", sourceReference: "dbt/models/marts/people/facts/fct_workforce_daily.sql; dbt/models/marts/wage/facts/fct_wage_observations.sql" },
  dbt: { title: "dbt transformation authority", summary: "dbt owns the transformation graph and analytical modeling semantics.", detail: "The project materializes staging and intermediate models as views, and marts as tables. Dagster invokes dbt at coarse domain and governance boundaries; it does not duplicate model-level lineage.", sourceReference: "dbt/dbt_project.yml; docs/orchestration.md" },
  portability: { title: "Adapter-aware SQL", summary: "Shared People business logic is expressed through dbt adapter dispatch.", detail: "Portability macros provide engine-specific implementations for casts, date spines, month start, arg-max, conditional counts, and date differences. DuckDB supports local People validation; BigQuery is the cloud execution target. Wage models are explicitly BigQuery-only.", sourceReference: "dbt/macros/portability.sql; dbt/models/marts/metrics/metrics_wage_published.sql" },
  dagster: { title: "Dagster boundary", summary: "Dagster orchestrates execution boundaries; dbt remains the model graph.", detail: "dagster-dbt is intentionally absent because the compatible release would require dbt-core below the validated 1.12.3 stack. The platform keeps one authoritative dbt transformation graph.", sourceReference: "docs/orchestration.md" },
} satisfies Record<string, TechnicalDetail>;

export const peopleTraces: MetricTrace[] = [
  { id: "headcount", label: "Ending Headcount", inputGrain: "daily employment state", transform: "end-of-month daily headcount", outputGrain: "month", destination: "metrics_people_monthly", path: ["raw employment_spells", "stg_employment_spells", "int_active_employment_daily", "fct_workforce_daily", "mart_workforce_monthly", "metrics_people_monthly"], excerpt: "hire_date <= snapshot_date < termination_date", sourceReference: "dbt/models/intermediate/people/int_active_employment_daily.sql" },
  { id: "hires", label: "Hires", inputGrain: "employment event", transform: "monthly first-hire and rehire count", outputGrain: "month", destination: "metrics_people_monthly", path: ["raw employment_spells", "stg_employment_spells", "int_employment_spells_validated", "fct_workforce_events", "mart_workforce_monthly", "metrics_people_monthly"], sourceReference: "dbt/models/marts/people/reporting/mart_workforce_monthly.sql" },
  { id: "separations", label: "Separations", inputGrain: "employment event", transform: "monthly separation count", outputGrain: "month", destination: "metrics_people_monthly", path: ["raw employment_spells", "stg_employment_spells", "int_employment_spells_validated", "fct_workforce_events", "mart_workforce_monthly", "metrics_people_monthly"], sourceReference: "dbt/models/marts/people/reporting/mart_workforce_monthly.sql" },
  { id: "attrition", label: "Attrition Rate", inputGrain: "monthly events and daily state", transform: "separations / average daily headcount", outputGrain: "month ratio", destination: "metrics_people_monthly", path: ["fct_workforce_daily + fct_workforce_events", "mart_workforce_monthly", "metrics_people_monthly"], sourceReference: "dbt/models/marts/metrics/metrics_people_monthly.sql" },
];

export const wageTraces: MetricTrace[] = [
  { id: "wage-rate", label: "Published Wage Rate", inputGrain: "logical source observation", transform: "matrix-specific normalization retaining dimensional context", outputGrain: "published source observation", destination: "metrics_wage_published", path: ["ows_observations", "stg_wage_ows_observations", "int_wage_industry_measures / int_wage_regional_measures / int_benchmark_occupation_wages", "fct_wage_observations", "metrics_wage_published"], sourceReference: "dbt/models/marts/metrics/metrics_wage_published.sql" },
];

export const modelDecisions = [
  ["Layered dbt models", "Staging normalizes source structure, intermediate models hold reusable logic, and marts expose consumption-ready relations.", "dbt/dbt_project.yml"],
  ["Temporal workforce state", "Point-in-time workforce measures require effective-date-aware daily state, rather than a simple employee count.", "dbt/models/intermediate/people/int_active_employment_daily.sql"],
  ["Preserve Wage source grain", "PSA published values retain matrix-specific dimensional context and are not universally additive.", "contracts/metrics/v1/governed_metrics.yml"],
  ["No People-to-Wage mart", "Required compensation, occupation, industry, region, and reference-period semantics do not exist.", "docs/adr/0001-defer-cross-domain-compensation-benchmark.md"],
] as const;