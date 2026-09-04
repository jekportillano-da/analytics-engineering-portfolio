"use client";

import Link from "next/link";
import { useState } from "react";
import { modelDecisions, modelDetails, peopleTraces, wageTraces, type MetricTrace } from "@/content/model-content";
import { TechnicalTerm } from "@/components/ui/technical-disclosure";

type Domain = "people" | "wage";

function TraceMetric({ traces }: { traces: MetricTrace[] }) {
  const [selectedId, setSelectedId] = useState(traces[0].id);
  const selected = traces.find((trace) => trace.id === selectedId) ?? traces[0];

  return <section className="trace-section" aria-labelledby="trace-title">
    <p className="eyebrow" id="trace-title">TRACE A METRIC</p>
    <div className="metric-tabs" role="tablist" aria-label="Metric trace">
      {traces.map((trace) => <button aria-selected={selected.id === trace.id} className="metric-tab" key={trace.id} onClick={() => setSelectedId(trace.id)} role="tab" type="button">{trace.label}</button>)}
    </div>
    <div className="trace-detail" role="tabpanel">
      <dl className="trace-metadata"><div><dt>Input grain</dt><dd>{selected.inputGrain}</dd></div><div><dt>Transformation</dt><dd>{selected.transform}</dd></div><div><dt>Output grain</dt><dd>{selected.outputGrain}</dd></div><div><dt>Governed destination</dt><dd>{selected.destination}</dd></div></dl>
      <ol className="trace-path">{selected.path.map((node, index) => <li className={index === selected.path.length - 1 ? "trace-destination" : ""} key={node}>{node}</li>)}</ol>
      {selected.excerpt && <pre className="sql-excerpt"><code>{selected.excerpt}</code></pre>}
      <p className="source-reference">Repository reference: {selected.sourceReference}</p>
    </div>
  </section>;
}

export function ModelPanel() {
  const [domain, setDomain] = useState<Domain>("people");
  const isPeople = domain === "people";
  const traces = isPeople ? peopleTraces : wageTraces;

  return <main className="journey-panel model-panel" id="main-content" tabIndex={-1}>
    <p className="panel-stage-number">STAGE 03</p>
    <h1 className="panel-title">MODEL</h1>
    <p className="journey-lede">Raw data mirrors how sources store information. Analytical models organize it around how the business needs to ask questions.</p>
    <section className="technical-summary" aria-label="Modeling environment"><span>DBT CORE <strong>1.12.3</strong></span><span>MODELS <strong>37</strong></span><span>CLOUD <strong>BIGQUERY / GCP</strong></span><span>LOCAL <strong>DUCKDB / PEOPLE</strong></span></section>

    <section className="model-spine" aria-labelledby="spine-title">
      <p className="eyebrow" id="spine-title">MODELING SPINE</p>
      <ol>{[["RAW", "Preserve source structures and provenance."], ["STAGING", "Standardize source fields, types, naming, and structural conventions."], ["INTERMEDIATE", "Apply reusable business and analytical logic."], ["MARTS", "Expose facts, dimensions, reconciliations, and governed outputs."]].map(([title, description]) => <li key={title}><strong>{title}</strong><span>{description}</span></li>)}</ol>
    </section>

    <section className="domain-explorer" aria-labelledby="domain-title">
      <div className="explorer-heading"><div><p className="eyebrow" id="domain-title">DOMAIN EXPLORER</p><h2>{isPeople ? "Temporal workforce state" : "Published wage context"}</h2></div><div className="domain-tabs" role="tablist" aria-label="Model domain"><button aria-selected={isPeople} onClick={() => setDomain("people")} role="tab" type="button">People</button><button aria-selected={!isPeople} onClick={() => setDomain("wage")} role="tab" type="button">Wage</button></div></div>
      {isPeople ? <div className="domain-story" role="tabpanel"><p>Headcount is not simply a count of employee IDs. <TechnicalTerm detail={modelDetails.temporalModel}>Employment state through time</TechnicalTerm> resolves valid spells against each snapshot date before daily state becomes monthly metrics.</p><ol className="model-flow"><li>employment spell</li><li>effective-date logic</li><li>active employment by date</li><li>fct_workforce_daily</li><li>mart_workforce_monthly</li><li>metrics_people_monthly</li></ol><div className="fact-dimension"><div><p>DIMENSIONS</p><span>dim_worker</span><span>dim_job</span><span>dim_org_unit</span><span>dim_location</span></div><div><p>FACTS</p><span>fct_workforce_daily</span><span>fct_workforce_events</span></div><div><p>GOVERNED</p><span>metrics_people_monthly</span></div></div></div> : <div className="domain-story" role="tabpanel"><p>Wage modeling preserves <TechnicalTerm detail={modelDetails.grain}>explicit source grain</TechnicalTerm> across distinct PSA matrix contexts. Published values are not forced into invalid cross-category aggregation.</p><ol className="model-flow"><li>stg_wage_ows_observations</li><li>industry / regional / benchmark intermediates</li><li>dim_wage_industry / region / measure</li><li>fct_wage_observations</li><li>2024 reporting marts</li><li>metrics_wage_published</li></ol><div className="fact-dimension"><div><p>DIMENSIONS</p><span>dim_wage_industry</span><span>dim_wage_region</span><span>dim_benchmark_occupation</span><span>dim_wage_measure</span></div><div><p>FACT</p><span>fct_wage_observations</span></div><div><p>MARTS</p><span>mart_industry_wages_2024</span><span>mart_regional_wages_2024</span><span>mart_benchmark_occupation_wages_2024</span></div></div></div>}
      <TraceMetric traces={traces} />
    </section>

    <section className="decision-section" aria-labelledby="model-decisions"><p className="eyebrow" id="model-decisions">MODELING DECISIONS</p><div className="decision-grid">{modelDecisions.map(([title, detail, reference]) => <article className="decision-record" key={title}><h3>{title}</h3><p>{detail}</p><span>{reference}</span></article>)}</div></section>
    <section className="portability-section" aria-labelledby="portability-title"><p className="eyebrow" id="portability-title">CLOUD EXECUTION / LOCAL VALIDATION</p><p><TechnicalTerm detail={modelDetails.dbt}>dbt</TechnicalTerm> executes SQL analytical models in BigQuery for cloud execution. DuckDB provides local analytical validation for supported People workflows. <TechnicalTerm detail={modelDetails.portability}>Adapter-aware SQL</TechnicalTerm> keeps key People logic portable across both engines; Wage remains BigQuery-only.</p><div className="engine-branch"><span>SAME PEOPLE BUSINESS LOGIC</span><i>↓</i><span>ADAPTER DISPATCH</span><div><b>DUCKDB</b><b>BIGQUERY</b></div></div><p className="portability-note">Key People golden outputs achieved exact parity across DuckDB and BigQuery validation. <TechnicalTerm detail={modelDetails.dagster}>Dagster boundary</TechnicalTerm></p></section>
    <footer className="journey-handoff"><p>At this point, the data is analytically useful. But a model producing a number does not automatically make that number trustworthy.</p><Link className="journey-link" href="/govern">Explore governance <span aria-hidden="true">→</span></Link></footer>
  </main>;
}