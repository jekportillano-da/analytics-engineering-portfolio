# ADR 0002: Defer active vector retrieval while preserving a vector-ready extension boundary

## Status

Accepted. The extension boundary is implemented; embedding and vector serving are
not active.

## Current state

People and Wage are predominantly structured, governed analytical data products.
Their authoritative retrieval path is deterministic warehouse SQL over tested dbt
models and contracts.

## Decision

Continue using SQL/dbt/warehouse retrieval for current analytical workloads. Add
a versioned, vendor-neutral document contract plus embedding-provider and
vector-store protocols, but do not select or operate an embedding model, vector
database, RAG system, or agent.

## Why vector retrieval is not active

- Current use cases do not strongly require semantic similarity search.
- SQL is more deterministic and auditable for exact analytical metrics.
- Another managed service would add dependency, security, and operating surface.
- Recurring infrastructure and embedding API cost is not currently justified.
- Adding technology only to broaden a portfolio is not sufficient business value.

## Why readiness is preserved

Future economic reports, policy documents, market intelligence, financial
guidance, or other substantial text-heavy sources may create a legitimate
semantic-retrieval requirement. The boundary prevents that future choice from
forcing a redesign of ingestion, BigQuery raw storage, dbt, governance, or
orchestration.

## Activation conditions

Implement an adapter only when all relevant conditions are met:

- a meaningful governed unstructured corpus enters the platform;
- measured semantic retrieval materially outperforms deterministic lookup;
- an approved RAG or agent requirement needs contextual retrieval;
- security, deletion, freshness, evaluation, and ownership controls are defined;
- demonstrated business value outweighs infrastructure and operating cost.

## Future path

```text
governed data product
  -> vector-ready document contract
  -> embedding-provider adapter
  -> vector-store adapter
  -> semantic retrieval / RAG consumer
```

Pinecone could be one vector-store adapter. It is not an architectural dependency;
pgvector, Qdrant, Weaviate, or another compatible implementation could satisfy the
same protocol.

## Consequences

The repository contains no embeddings, model integration, vector index, vector
credentials, retrieval consumer, active Dagster asset, or vendor dependency. An
activation checkpoint must choose and evaluate concrete adapters rather than
treating this boundary as an operational capability.
