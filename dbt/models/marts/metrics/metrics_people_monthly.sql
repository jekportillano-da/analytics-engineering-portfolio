{{ config(materialized='view') }}

select
    'v1' as metric_contract_version,
    period_start,
    period_end,
    calendar_days,
    ending_headcount,
    hires,
    separations,
    period_attrition_rate as attrition_rate,
    separations as attrition_numerator,
    average_daily_headcount as attrition_denominator
from {{ ref('mart_workforce_monthly') }}
