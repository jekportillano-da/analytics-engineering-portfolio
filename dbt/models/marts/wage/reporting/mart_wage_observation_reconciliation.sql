{{ config(enabled=target.type == 'bigquery') }}

with raw_counts as (
    select matrix_id, count(*) as observation_count
    from {{ source('wage_raw', 'ows_observations') }}
    group by matrix_id
),

staging_counts as (
    select matrix_id, count(*) as observation_count
    from {{ ref('stg_wage_ows_observations') }}
    group by matrix_id
),

intermediate_counts as (
    select matrix_id, count(*) as observation_count
    from (
        select matrix_id from {{ ref('int_wage_industry_measures') }}
        union all
        select matrix_id from {{ ref('int_wage_regional_measures') }}
        union all
        select matrix_id from {{ ref('int_benchmark_occupation_wages') }}
    )
    group by matrix_id
),

fact_counts as (
    select matrix_id, count(*) as observation_count
    from {{ ref('fct_wage_observations') }}
    group by matrix_id
),

mart_counts as (
    select source_matrix_id as matrix_id, sum(source_observation_count) as observation_count
    from {{ ref('mart_industry_wages_2024') }}
    group by source_matrix_id

    union all

    select source_matrix_id as matrix_id, sum(source_observation_count) as observation_count
    from {{ ref('mart_regional_wages_2024') }}
    group by source_matrix_id

    union all

    select source_matrix_id as matrix_id, sum(source_observation_count) as observation_count
    from {{ ref('mart_benchmark_occupation_wages_2024') }}
    group by source_matrix_id
)

select
    raw_counts.matrix_id,
    raw_counts.observation_count as raw_observation_count,
    staging_counts.observation_count as staging_observation_count,
    intermediate_counts.observation_count as intermediate_observation_count,
    fact_counts.observation_count as fact_observation_count,
    mart_counts.observation_count as mart_accounted_observation_count,
    staging_counts.observation_count - raw_counts.observation_count
        as staging_difference,
    intermediate_counts.observation_count - raw_counts.observation_count
        as intermediate_difference,
    fact_counts.observation_count - raw_counts.observation_count
        as fact_difference,
    mart_counts.observation_count - raw_counts.observation_count
        as mart_difference,
    staging_counts.observation_count = raw_counts.observation_count
        and intermediate_counts.observation_count = raw_counts.observation_count
        and fact_counts.observation_count = raw_counts.observation_count
        and mart_counts.observation_count = raw_counts.observation_count
        as is_reconciled
from raw_counts
left join staging_counts using (matrix_id)
left join intermediate_counts using (matrix_id)
left join fact_counts using (matrix_id)
left join mart_counts using (matrix_id)
