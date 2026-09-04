export type TechnicalDetail = {
  title: string;
  summary: string;
  detail: string;
  sourceReference: string;
};

export const technicalDetails = {
  deterministicSource: {
    title: "Deterministic source",
    summary: "The same configured scenario and seed reproduce the same synthetic source shape.",
    detail: "The People generator initializes a seeded random source from the configured scenario before producing the raw workforce files. This makes the demonstration repeatable while retaining realistic source conditions for downstream validation.",
    sourceReference: "src/analytics_platform/domains/people/generator.py",
  },
  sourceGrain: {
    title: "Source grain",
    summary: "What one raw record represents before transformation.",
    detail: "The People source preserves distinct workforce structures such as worker versions, employment spells, job history, jobs, organization units, and locations. Grain is established at the source boundary before models add analytical meaning.",
    sourceReference: "src/analytics_platform/domains/people/ingestion/raw.py",
  },
  openstat: {
    title: "PSA OpenSTAT",
    summary: "The official API used as the canonical automated acquisition path.",
    detail: "The Wage source uses PSA OpenSTAT for the 2024 Occupational Wages Survey. Acquisition first reads matrix metadata, then sends explicit selections for the validated json-stat representation.",
    sourceReference: "docs/wage-psa-openstat-source.md",
  },
  provenance: {
    title: "Provenance",
    summary: "The retained trail from request through artifact, extraction, and observation.",
    detail: "The Wage flow keeps versioned identifiers for requests, artifacts, retrievals, extractions, and raw records. Exact response bytes receive SHA-256 content-addressed identity; normalized content and logical observations retain separate identities for traceability and idempotent loading.",
    sourceReference: "docs/wage-psa-openstat-source.md",
  },
  idempotency: {
    title: "Idempotent by design",
    summary: "Repeated acquisition does not blindly create duplicate analytical observations.",
    detail: "Request identity captures the matrix, endpoint, explicit selections, format, and contract. Artifact identity identifies exact bytes. Semantic identity normalizes content independent of retrieval time, while logical observation identity joins semantic identity to a source dimension locator for warehouse loading.",
    sourceReference: "docs/wage-psa-openstat-source.md",
  },
} satisfies Record<string, TechnicalDetail>;

export const sourceProfiles = [
  {
    title: "People Analytics",
    descriptor: "Synthetic enterprise-style workforce data",
    nature: "Controlled, deterministic source",
    fields: ["workers", "employment spells", "job history", "jobs", "organizational units", "locations", "manifest"],
    reliability: "Deterministic generation, reproducibility, controlled source design, and privacy safety.",
    limitation: "Synthetic workforce data; it is not representative of an actual employer.",
    sourceReference: "src/analytics_platform/domains/people/generator.py",
  },
  {
    title: "Wage Analytics",
    descriptor: "Official public establishment-level wage statistics",
    nature: "Philippine Statistics Authority, PSA OpenSTAT, 2024 OWS",
    fields: ["4 source matrices", "19 industry categories", "18 regions", "benchmark occupation observations", "225 governed observations"],
    reliability: "Authoritative publisher, official API, explicit survey scope, and retained source provenance.",
    limitation: "Not individual salary data. Coverage follows the survey scope and the benchmark occupation slice is limited.",
    sourceReference: "docs/wage-psa-openstat-source.md",
  },
] as const;

export const ingestionDecisions = [
  {
    blocker: "Static PSA XLSX endpoints were Cloudflare-protected in this execution environment.",
    decision: "Use the official PSA OpenSTAT API as the canonical automated route.",
    rationale: "Avoid a manual-download dependency while preserving reproducibility and automation.",
    result: "No HTML scraping or anti-bot circumvention is used.",
    sourceReference: "docs/wage-psa-openstat-source.md",
  },
  {
    blocker: "The live json-stat2 renderer declared 54-57 cells but returned only [1.0].",
    decision: "Use the validated json-stat representation and independently cross-check against CSV.",
    rationale: "Cardinality validation fails closed; CSV validates published whole-peso values against higher-precision json-stat values.",
    result: "JSON and CSV remain validation or fallback formats, not canonical raw artifacts.",
    sourceReference: "docs/wage-psa-openstat-source.md",
  },
] as const;