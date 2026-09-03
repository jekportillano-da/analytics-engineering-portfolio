# Wage Analytics: PSA OpenSTAT source

The authoritative source for the Wage Analytics V1 raw layer is the Philippine
Statistics Authority (PSA) OpenSTAT API. The source is the 2024 Occupational
Wages Survey (OWS) for formal establishments employing 10 or more workers, under
the survey's applicable coverage and exclusions.

Canonical catalog:

`https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB/1B/OWS/O10/`

V1 includes four matrices:

- `0011B3E2001.px`: pay, allowance, and wage rates by major industry group;
- `0021B3E2002.px`: pay, allowance, and wage rates by region;
- `0051B3E2005.px`: General Office Clerks by sex and major industry group; and
- `0071B3E2007.px`: Elementary Occupations by sex and major industry group.

Acquisition first retrieves matrix metadata, discovers every source category
code, and then posts explicit selections for `json-stat`. The canonical endpoint
and serialized request are retained with the response SHA-256, V2 artifact,
retrieval, extraction, and raw-record identities. Exact response bytes are stored
through the shared immutable, content-addressed artifact mechanism beneath the
ignored `.local` root.

PSA's `json-stat2` response was evaluated and rejected for this implementation:
the live renderer declared 54-57-cell datasets but returned only `[1.0]`, including
for a known single-cell value. Cardinality validation remains fail-closed through
a regression fixture. PSA CSV is requested automatically as an independent
full-dataset cross-check; its published whole-peso values are compared with the
source's higher-precision `json-stat` values using explicit half-up rounding.
JSON and CSV remain validation or fallback formats, not canonical raw artifacts.

The static PSA XLSX endpoints are not the canonical automated route because they
are Cloudflare-protected from this execution environment. No HTML scraping or
anti-bot circumvention is used.

Request identity is deterministic over the matrix, endpoint, explicit selections,
format, and contract. Artifact identity is the SHA-256 of exact response bytes and
therefore changes honestly when bytes change. Semantic dataset identity hashes
only normalized source observations, excluding retrieval timestamps and volatile
response metadata. Logical observation identity uses that semantic identity plus
the source dimension locator, allowing idempotent warehouse loading while every
raw artifact and retrieval run remains traceable.

## Scope and limitations

OWS describes establishment-level occupational wage statistics. It is not
individual salary data and does not represent every Philippine worker, every
establishment, or every occupation. The V1 occupation slice contains only the
two PSA benchmark identities listed above. Those occupations are represented by
separate matrices rather than a general occupation dimension or source-supplied
occupation code. Industry tables expose major groups; region appears only in the
selected regional pay matrix. Null observations and source status markers are
retained rather than imputed.

Acquisition is fully automated through OpenSTAT; no manual XLSX step is required.

Source references:

- PSA OpenSTAT API documentation: `https://openstat.psa.gov.ph/API-Documentation`
- PSA 2024 OWS technical notes: `https://psa.gov.ph/content/2024-occupational-wages-survey`
