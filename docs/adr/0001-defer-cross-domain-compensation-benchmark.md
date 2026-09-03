# ADR 0001: Defer a People-to-Wage benchmark model

## Decision

Do not create a cross-domain analytical model from the currently implemented
People and Wage marts.

## Evidence

People contains employment dates, synthetic workers, internal job IDs, job names,
job families, levels, organization units, and city/country locations. It does not
contain compensation, employer-industry classification, PSA region codes, or a
standard occupation classification. Its internal families such as Engineering,
Finance, and Customer Support describe company functions, not PSA OWS industries.
They also cannot be equated defensibly with the two OWS benchmark occupations.

Wage contains establishment-level 2024 PSA OWS summaries by major industry,
region, and two matrix-scoped benchmark occupations. It is not individual salary
data.

## Required future contract

A defensible comparison requires effective-dated internal compensation facts
(base pay, allowance, total cash, currency, pay frequency, and applicable period),
a governed mapping from internal jobs to a compatible occupation classification
such as PSOC, an employer-industry code compatible with the OWS industry scope,
PSA-compatible region codes, and explicit reference-period and survey-population
alignment. Any crosswalk also needs version, provenance, review status, and known
coverage gaps.

Joining current internal job-family labels or city names to OWS categories would
manufacture comparability and produce analytically misleading benchmarks.
