{{ config(enabled=target.type == 'bigquery') }}

with measures as (
    select
        wage_measure_id,
        governed_measure_name,
        source_measure_code,
        case
            when wage_measure_id = 'benchmark_wage_rate'
                then 'benchmark_occupation'
            else 'industry_and_region'
        end as source_scope
    from {{ ref('int_wage_industry_measures') }}

    union all

    select
        wage_measure_id,
        governed_measure_name,
        source_measure_code,
        'industry_and_region' as source_scope
    from {{ ref('int_wage_regional_measures') }}

    union all

    select
        wage_measure_id,
        governed_measure_name,
        source_measure_code,
        'benchmark_occupation' as source_scope
    from {{ ref('int_benchmark_occupation_wages') }}
)

select
    wage_measure_id,
    max(governed_measure_name) as wage_measure_name,
    max(source_measure_code) as source_measure_code,
    max(source_scope) as source_scope
from measures
group by wage_measure_id
