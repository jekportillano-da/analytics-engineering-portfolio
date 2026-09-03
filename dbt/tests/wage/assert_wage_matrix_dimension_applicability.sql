{{ config(enabled=target.type == 'bigquery') }}

select logical_observation_id, matrix_id
from {{ ref('stg_wage_ows_observations') }}
where not (
    (
        matrix_id = '0011B3E2001.px'
        and industry_code is not null
        and industry_name is not null
        and geography_type is null
        and geography_code is null
        and geography_name is null
        and occupation_code is null
        and occupation_name is null
        and sex_code is null
        and sex is null
        and measure_code in ('0', '1', '2')
    )
    or (
        matrix_id = '0021B3E2002.px'
        and industry_code is null
        and industry_name is null
        and geography_type = 'region'
        and geography_code is not null
        and geography_name is not null
        and occupation_code is null
        and occupation_name is null
        and sex_code is null
        and sex is null
        and measure_code in ('0', '1', '2')
    )
    or (
        matrix_id in ('0051B3E2005.px', '0071B3E2007.px')
        and industry_code is not null
        and industry_name is not null
        and geography_type is null
        and geography_code is null
        and geography_name is null
        and occupation_code is null
        and occupation_name is not null
        and sex_code in ('0', '1', '2')
        and sex in ('Both Sexes', 'Male', 'Female')
        and measure_code is null
    )
)
