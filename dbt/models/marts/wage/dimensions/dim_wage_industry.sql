{{ config(enabled=target.type == 'bigquery') }}

with industry_members as (
    select industry_code, industry_name
    from {{ ref('int_wage_industry_measures') }}

    union all

    select industry_code, industry_name
    from {{ ref('int_benchmark_occupation_wages') }}
)

select
    industry_code as wage_industry_id,
    industry_code,
    max(industry_name) as industry_name
from industry_members
group by industry_code
