{{ config(enabled=target.type == 'bigquery') }}

with industry_members as (
    select industry_code, industry_name
    from {{ ref('int_wage_industry_measures') }}
    union all
    select industry_code, industry_name
    from {{ ref('int_benchmark_occupation_wages') }}
)

select industry_code
from industry_members
group by industry_code
having count(distinct industry_name) != 1
