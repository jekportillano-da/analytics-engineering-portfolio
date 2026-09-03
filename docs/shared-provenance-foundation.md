# Shared provenance foundation

This checkpoint establishes a source-neutral boundary below domain ingestion. It
does not connect the People adapter to the shared code and does not migrate a Wage
source.

The shared platform owns:

- deterministic, versioned identities for artifacts, extraction batches, issues,
  and raw records;
- retrieval, source-artifact, and extraction lifecycle metadata that is independent
  of a database;
- SHA-256 content-addressed local storage keys, explicit-root path validation, and
  immutable no-overwrite publication;
- read-only reconciliation primitives;
- destination validation for resolved and connected IP addresses; and
- bounded HTTP response header/body validation.

Domains continue to own source URL allowlists and redirect rules, request headers,
accepted media semantics, parsing/extraction payloads, persistence adapters, and
warehouse destinations. The shared layer therefore contains no DA-AMAS classes,
PDF rules, financial terminology, Budget Buddy environment variables, `bb_*`
datasets, or repository-root assumptions.

## Identifier compatibility

Budget Buddy's existing identifiers are durable data. The explicit
`legacy_*_v1` functions retain the exact namespace
`budget-buddy-data-platform`, version `identifier-v1`, binary encoding, and golden
outputs.

New shared-platform records use explicit `*_v2` functions with namespace
`analytics-platform` and version `identifier-v2`. V2 intentionally produces
different identifiers; it is a versioned successor, not a relabeling of V1.
Persisted provenance must retain its identifier version so reconciliation can use
the correct derivation.

## Storage and adoption

Artifact storage requires an explicit local root supplied by the caller. The root
is operational configuration and never part of durable identity. Publication uses
same-filesystem exclusive hard links, verifies existing content, and never falls
back to an overwriting copy.

Future domain adoption should happen only after a domain adapter can map its own
source policy and persistence model onto these contracts without changing current
behavior. No current People or Budget Buddy adapter is implicitly migrated by the
presence of this foundation.
