{{ config(enabled=target.type == 'bigquery') }}

with expected as (
    select '0011B3E2001.px' as matrix_id, 57 as expected_count
    union all select '0021B3E2002.px', 54
    union all select '0051B3E2005.px', 57
    union all select '0071B3E2007.px', 57
),

normalized as (
    select matrix_id, logical_observation_id from {{ ref('int_wage_industry_measures') }}
    union all
    select matrix_id, logical_observation_id from {{ ref('int_wage_regional_measures') }}
    union all
    select matrix_id, logical_observation_id from {{ ref('int_benchmark_occupation_wages') }}
),

actual as (
    select
        matrix_id,
        count(*) as actual_count,
        count(distinct logical_observation_id) as distinct_count
    from normalized
    group by matrix_id
)

select
    expected.matrix_id,
    expected.expected_count,
    actual.actual_count,
    actual.distinct_count
from expected
left join actual using (matrix_id)
where actual.actual_count != expected.expected_count
    or actual.distinct_count != expected.expected_count

union all

select
    'ALL_MATRICES',
    225,
    count(*),
    count(distinct logical_observation_id)
from normalized
having count(*) != 225 or count(distinct logical_observation_id) != 225
