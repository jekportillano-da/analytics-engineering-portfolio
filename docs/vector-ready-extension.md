# Vector-ready extension boundary

## Architecture status

```text
ACTIVE
sources -> ingestion -> BigQuery raw -> dbt -> governed data products
                                             -> deterministic SQL / BI / application consumption

DEFERRED / OPTIONAL
governed data products -> vector-ready document contract
                       -> embedding-provider adapter
                       -> vector-store adapter
                       -> semantic retrieval / RAG / agent consumer
```

Only the active path executes today. The optional path is a contract and protocol
boundary; it has no Dagster assets, provider adapters, credentials, network calls,
generated embeddings, vector index, RAG system, or agent.

## Contract and adaptation

`contracts/vector_ready/v1/document.yml` declares the versioned portable shape.
`analytics_platform.platform.vector_ready` enforces it with standard-library
types. A document has stable logical identity, canonical content, flat
filter-ready metadata, authoritative upstream lineage pointers, and reference
context. Existing provenance IDs can be carried through when an upstream product
has them; this layer does not regenerate or reinterpret those IDs.

The first adapter reads the existing governed metric contract and produces one
small definition document per real People or Wage metric. It copies metric
definitions, aggregation behavior, allowed dimensional grain, limitations,
source model, and reference period. It does not query the warehouse, change a
metric, add compensation data, infer mappings, or join domains.

## Extension protocols

`EmbeddingProvider` accepts vector-ready documents and returns provider-neutral
embedded records with provider, model, version, and dimension provenance.
`VectorStore` exposes only upsert, filtered query, and delete. No implementation is
selected. A future adapter must own its credentials, retry behavior, batching,
cost controls, deletion semantics, and observability outside the domain logic.

Dagster's active jobs remain unchanged. If the ADR activation conditions are met,
future orchestration may attach after governed data products; no placeholder asset
is registered today.
