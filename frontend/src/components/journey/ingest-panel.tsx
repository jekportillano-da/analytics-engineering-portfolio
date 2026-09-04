import Link from "next/link";
import { ingestionDecisions, technicalDetails } from "@/content/journey-content";
import { TechnicalTerm } from "@/components/ui/technical-disclosure";

const responsibilities = [
  ["ACQUIRE", "Retrieve sources reproducibly with explicit requests and controlled source access."],
  ["PRESERVE", "Retain source identity, provenance, and source meaning before interpretation."],
  ["LAND", "Load raw structures without silently repairing what the source expressed."],
] as const;

export function IngestPanel() {
  return (
    <main className="journey-panel ingest-panel" id="main-content" tabIndex={-1}>
      <p className="panel-stage-number">STAGE 02</p>
      <h1 className="panel-title">INGEST</h1>
      <p className="journey-lede">Preserve first. Transform later.</p>
      <p className="journey-intro">Ingestion acquires and lands source material while retaining the context needed to understand where it came from. It does not silently repair source meaning.</p>

      <section aria-label="Ingestion responsibilities" className="ingest-responsibilities">
        {responsibilities.map(([title, description], index) => <article key={title}><span>{`0${index + 1}`}</span><h2>{title}</h2><p>{description}</p></article>)}
      </section>

      <section aria-labelledby="ingestion-flows-title" className="ingestion-flows">
        <p className="eyebrow" id="ingestion-flows-title">TWO INGESTION BOUNDARIES</p>
        <article className="flow-record">
          <div><p className="flow-label">PEOPLE</p><h2>Controlled source landing</h2></div>
          <ol className="flow-line"><li>Deterministic People generator</li><li>raw source files</li><li>manifest metadata</li><li>raw analytical landing</li></ol>
          <p>Configured seed and source rules reproduce the source output. Intentional imperfections remain present; later modeling and governance own their interpretation.</p>
        </article>
        <article className="flow-record">
          <div><p className="flow-label">WAGE</p><h2>Official source acquisition</h2></div>
          <ol className="flow-line"><li>PSA OpenSTAT</li><li>explicit request</li><li>immutable source artifact</li><li>observation extraction</li><li>BigQuery raw landing</li></ol>
          <p>Each acquisition retains a traceable route from official source through request, artifact, retrieval, extraction, and normalized observation.</p>
        </article>
      </section>

      <section className="provenance-section" aria-labelledby="provenance-title">
        <p className="eyebrow" id="provenance-title">PROVENANCE AND REPEATABILITY</p>
        <p className="provenance-lede"><TechnicalTerm detail={technicalDetails.provenance}>Provenance</TechnicalTerm> makes the source trail inspectable. <TechnicalTerm detail={technicalDetails.idempotency}>Idempotent by design</TechnicalTerm> prevents repeated acquisition from blindly creating duplicate analytical observations.</p>
        <div className="identity-grid"><span>REQUEST IDENTITY<small>What was requested</small></span><span>ARTIFACT IDENTITY<small>Exact response bytes</small></span><span>SEMANTIC IDENTITY<small>Normalized analytical payload</small></span><span>LOGICAL OBSERVATION IDENTITY<small>Source-grain business observation</small></span></div>
      </section>

      <section className="decision-section" aria-labelledby="decision-title">
        <p className="eyebrow" id="decision-title">ENGINEERING DECISIONS</p>
        <div className="decision-grid">
          {ingestionDecisions.map((decision) => <article className="decision-record" key={decision.blocker}><p><strong>BLOCKER</strong>{decision.blocker}</p><p><strong>DECISION</strong>{decision.decision}</p><p><strong>RATIONALE</strong>{decision.rationale}</p><p><strong>RESULT</strong>{decision.result}</p><span>{decision.sourceReference}</span></article>)}
        </div>
      </section>

      <footer className="journey-handoff">
        <p>At this point, the data can be acquired reproducibly and its origin preserved. But raw source structures are still not analytical models.</p>
        <Link className="journey-link" href="/model">Explore modeling <span aria-hidden="true">→</span></Link>
      </footer>
    </main>
  );
}