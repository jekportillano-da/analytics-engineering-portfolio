{{ config(enabled=target.type == 'bigquery') }}

select
    cast(reference_year as string) || '|' || geography_code as regional_wage_mart_id,
    reference_year,
    matrix_id as source_matrix_id,
    geography_code as wage_region_id,
    geography_code as region_code,
    geography_name as region_name,
    max(case when wage_measure_id = 'basic_pay' then observation_value end)
        as average_monthly_basic_pay,
    max(case when wage_measure_id = 'allowance' then observation_value end)
        as average_monthly_allowance,
    max(case when wage_measure_id = 'wage_rate' then observation_value end)
        as average_monthly_wage_rate,
    count(*) as source_observation_count
from {{ ref('fct_wage_observations') }}
where matrix_scope = 'regional_wage_measures'
group by reference_year, matrix_id, geography_code, geography_name
