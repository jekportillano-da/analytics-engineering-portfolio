import Link from "next/link";
import { governDetails, intentionallyOutOfCi, validationArchitecture } from "@/content/govern-content";
import { TechnicalTerm } from "@/components/ui/technical-disclosure";
import { loadGovernedHealthSnapshot, type GovernanceCheck } from "@/lib/presentation/contract-loader";

function statusLabel(status: string) {
  return status.replaceAll("_", " ").toUpperCase();
}

function statusClass(status: string) {
  return status === "passed" ? "status-pass" : status === "review_required" || status === "warn" ? "status-review" : "status-failed";
}

function checkById(checks: GovernanceCheck[], id: string) {
  const check = checks.find((item) => item.governance_check_id === id);
  if (!check) throw new Error(`Governed health payload missing ${id}.`);
  return check;
}

export async function GovernPanel() {
  const health = await loadGovernedHealthSnapshot();
  const peopleReconciliation = checkById(health.governance_checks, "people.headcount_reconciliation");
  const wageReconciliation = checkById(health.governance_checks, "wage.raw_to_mart_reconciliation");
  const peopleQuality = checkById(health.governance_checks, "people.quality_issues");
  const peopleFreshness = checkById(health.governance_checks, "people.operational_freshness");
  const wageFreshness = checkById(health.governance_checks, "wage.operational_freshness");
  const evaluatedAt = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(peopleReconciliation.evaluated_at));

  return <main className="journey-panel govern-panel" id="main-content" tabIndex={-1}>
    <p className="panel-stage-number">STAGE 04</p>
    <h1 className="panel-title">GOVERN</h1>
    <p className="journey-lede">Latest validated platform health.</p>
    <p className="journey-intro">This is a point-in-time governed snapshot evaluated {evaluatedAt} UTC. It is not live monitoring.</p>

    <section className="govern-principles" aria-label="Trust dimensions"><span>TEST</span><span>RECONCILE</span><span>MONITOR</span><span>TRACE</span><span>CONTRACT-CONFORMANT</span></section>
    <section className="health-summary" aria-label="Governed health summary"><article><small>PEOPLE RECONCILIATION</small><strong>{peopleReconciliation.observed_value}</strong><span className={statusClass(peopleReconciliation.status)}>{statusLabel(peopleReconciliation.status)}</span></article><article><small>WAGE RECONCILIATION</small><strong>{wageReconciliation.observed_value}</strong><span className={statusClass(wageReconciliation.status)}>{statusLabel(wageReconciliation.status)}</span></article><article><small>MAXIMUM DIFFERENCE</small><strong>{health.people_reconciliation.summary.maximum_difference}</strong><span>RECONCILED</span></article><article><small>PEOPLE QUALITY FINDINGS</small><strong>{health.people_quality.issue_count}</strong><span className="status-review">REVIEW CONTEXT</span></article></section>

    <section className="control-section" aria-labelledby="controls-title"><p className="eyebrow" id="controls-title">GOVERNANCE CONTROLS</p><div className="control-grid">
      {[peopleReconciliation, wageReconciliation, peopleFreshness, wageFreshness, peopleQuality].map((check) => <article className="control-row" key={check.governance_check_id}><div><p>{check.domain} / {check.check_type}</p><strong>{check.governance_check_id}</strong><span>{check.expected_value}</span></div><div><b>{check.observed_value}</b><em className={statusClass(check.status)}>{statusLabel(check.status)}</em></div></article>)}
    </div></section>

    <section className="quality-context" aria-labelledby="quality-title"><div><p className="eyebrow" id="quality-title">QUALITY IS A SEPARATE QUESTION</p><h2>{health.people_quality.issue_count} findings, intentionally visible</h2><p>Reconciliation asks whether transformation preserved expected totals. Quality rules ask whether individual records satisfy defined expectations. These synthetic fixtures demonstrate detection; they are not a production outage.</p></div><div className="quality-counts"><span>{peopleQuality.detail}</span><small>INTENTIONAL SYNTHETIC GOVERNANCE FIXTURES</small></div></section>

    <section className="freshness-section" aria-labelledby="freshness-title"><p className="eyebrow" id="freshness-title">OPERATIONAL FRESHNESS</p><p><TechnicalTerm detail={governDetails.freshness}>Freshness</TechnicalTerm> is based on load/retrieval timing, not the data reference period. Both contracts warn after 48 hours and error after 168 hours.</p><div className="freshness-grid"><article><small>PEOPLE REFERENCE PERIOD</small><strong>{health.freshness_contracts.people.reference_period}</strong><span>Load timing: {peopleFreshness.latest_operational_at ?? "not recorded"}</span></article><article><small>WAGE REFERENCE PERIOD</small><strong>{health.freshness_contracts.wage.reference_period}</strong><span>Retrieval timing: {wageFreshness.latest_operational_at ?? "not recorded"}</span></article></div></section>

    <section className="traceability-section" aria-labelledby="traceability-title"><p className="eyebrow" id="traceability-title">TRACEABILITY AND CONTRACTS</p><div className="govern-lineage"><span>SOURCE</span><i>→</i><span>RAW</span><i>→</i><span>MODEL</span><i>→</i><span>GOVERNED METRIC</span><i>→</i><span>PRESENTATION CONTRACT</span><i>→</i><span>EXECUTIVE INSIGHT</span></div><div className="contract-grid"><p><TechnicalTerm detail={governDetails.reconciliation}>Reconciliation</TechnicalTerm><br />Defined totals remain traceable through governed marts.</p><p><TechnicalTerm detail={governDetails.lineage}>Lineage</TechnicalTerm><br />The presentation artifact records the curated active path.</p><p><TechnicalTerm detail={governDetails.contracts}>Contracts</TechnicalTerm><br />Metrics, frontend consumption, and insight evidence remain versioned boundaries.</p></div></section>

    <section className="validation-section" aria-labelledby="validation-title"><p className="eyebrow" id="validation-title">VALIDATION ARCHITECTURE</p><p>Repository validation evidence, not browser-session telemetry.</p><div className="validation-feed">{validationArchitecture.map(([title, detail, reference]) => <article key={title}><span>VALIDATED CHECKPOINT</span><strong>{title}</strong><p>{detail}</p><small>{reference}</small></article>)}</div><p className="out-of-ci">Deliberately outside public CI: {intentionallyOutOfCi.join(" · ")}. Historical run telemetry is intentionally outside the current presentation contract.</p></section>
    <footer className="journey-handoff"><p>The data product is now modeled, validated, reconciled, and traceable. The next question is what the governed analytical data actually shows.</p><Link className="journey-link" href="/insight">Explore insights <span aria-hidden="true">→</span></Link></footer>
  </main>;
}