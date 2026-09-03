{{ config(enabled=target.type == 'bigquery') }}

with reconciliation as (
    select * from {{ ref('mart_wage_observation_reconciliation') }}
),

summary as (
    select
        count(*) as matrix_count,
        sum(raw_observation_count) as raw_observation_count,
        sum(mart_accounted_observation_count) as mart_accounted_observation_count
    from reconciliation
)

select matrix_id
from reconciliation
where not is_reconciled
    or staging_difference != 0
    or intermediate_difference != 0
    or fact_difference != 0
    or mart_difference != 0

union all

select 'ALL_MATRICES'
from summary
where matrix_count != 4
    or raw_observation_count != 225
    or mart_accounted_observation_count != 225
