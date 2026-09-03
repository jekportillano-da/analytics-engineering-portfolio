{{ config(enabled=target.type == 'bigquery') }}

select industry_wage_mart_id as record_id, 'industry' as mart_name
from {{ ref('mart_industry_wages_2024') }}
where source_observation_count != 3
    or average_monthly_basic_pay is null
    or average_monthly_allowance is null
    or average_monthly_wage_rate is null

union all

select regional_wage_mart_id, 'regional'
from {{ ref('mart_regional_wages_2024') }}
where source_observation_count != 3
    or average_monthly_basic_pay is null
    or average_monthly_allowance is null
    or average_monthly_wage_rate is null

union all

select benchmark_wage_mart_id, 'benchmark_occupation'
from {{ ref('mart_benchmark_occupation_wages_2024') }}
where source_observation_count != 1
    or average_monthly_wage_rate is null
