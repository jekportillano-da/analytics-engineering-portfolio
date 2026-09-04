import Link from "next/link";
import { sourceProfiles, technicalDetails } from "@/content/journey-content";
import { TechnicalTerm } from "@/components/ui/technical-disclosure";

export function SourcePanel() {
  return (
    <main className="journey-panel source-panel" id="main-content" tabIndex={-1}>
      <p className="panel-stage-number">STAGE 01</p>
      <h1 className="panel-title">SOURCE</h1>
      <p className="journey-lede">Source = origin, not truth.</p>
      <p className="journey-intro">Raw does not mean bad. It means unprocessed: authority, grain, scope, privacy context, and limitations are visible before downstream systems assign analytical meaning.</p>

      <section aria-label="Source families" className="source-profiles">
        {sourceProfiles.map((profile) => (
          <article className="source-profile" key={profile.title}>
            <p className="eyebrow">SOURCE FAMILY</p>
            <h2>{profile.title}</h2>
            <p className="profile-descriptor">{profile.descriptor}</p>
            <dl className="metadata-list">
              <div><dt>Nature</dt><dd>{profile.nature}</dd></div>
              <div><dt>Raw structures</dt><dd className="metadata-tags">{profile.fields.map((field) => <span key={field}>{field}</span>)}</dd></div>
              <div><dt>Why acceptable</dt><dd>{profile.reliability}</dd></div>
              <div><dt>Limitation</dt><dd>{profile.limitation}</dd></div>
            </dl>
            <p className="source-reference">Repository reference: {profile.sourceReference}</p>
          </article>
        ))}
      </section>

      <section className="source-notes" aria-labelledby="source-notes-title">
        <p className="eyebrow" id="source-notes-title">SOURCE DISCIPLINE</p>
        <div className="source-note-grid">
          <p><strong>People privacy.</strong> The controlled synthetic workforce is privacy-safe and suitable for reproducible workforce analytics validation. <TechnicalTerm detail={technicalDetails.deterministicSource}>Deterministic source</TechnicalTerm></p>
          <p><strong>Wage semantics.</strong> PSA OWS is official published establishment-level material, not individual salary data. <TechnicalTerm detail={technicalDetails.openstat}>PSA OpenSTAT</TechnicalTerm></p>
          <p><strong>Grain remains explicit.</strong> A <TechnicalTerm detail={technicalDetails.sourceGrain}>source grain</TechnicalTerm> is not an analytical metric definition.</p>
        </div>
        <p className="source-caution">What we do not assume yet: credibility does not imply clean records, valid business metrics, or the absence of limitations. Known People imperfections are intentionally preserved for downstream governance validation.</p>
      </section>

      <footer className="journey-handoff">
        <p>We know what the sources are and what they mean. The next problem is acquiring them without losing provenance or source meaning.</p>
        <Link className="journey-link" href="/ingest">Explore ingestion <span aria-hidden="true">→</span></Link>
      </footer>
    </main>
  );
}