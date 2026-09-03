with metric_contract as (
    select
        period_start,
        period_end,
        ending_headcount,
        hires,
        separations,
        attrition_rate,
        attrition_numerator,
        attrition_denominator
    from {{ ref('metrics_people_monthly') }}
),

validated_source as (
    select
        period_start,
        period_end,
        ending_headcount,
        hires,
        separations,
        period_attrition_rate as attrition_rate,
        separations as attrition_numerator,
        average_daily_headcount as attrition_denominator
    from {{ ref('mart_workforce_monthly') }}
),

contract_minus_source as (
    select * from metric_contract
    except distinct
    select * from validated_source
),

source_minus_contract as (
    select * from validated_source
    except distinct
    select * from metric_contract
)

select * from contract_minus_source
union all
select * from source_minus_contract
