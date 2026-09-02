with monthly as (
    select * from {{ ref('mart_workforce_monthly') }}
),

with_opening as (
    select
        *,
        lag(ending_headcount) over (order by period_start) as opening_headcount
    from monthly
)

select
    period_start,
    opening_headcount,
    hires,
    separations,
    opening_headcount + hires - separations as expected_ending_headcount,
    ending_headcount as actual_ending_headcount,
    ending_headcount - (opening_headcount + hires - separations) as difference,
    case
        when opening_headcount is null then true
        else ending_headcount = opening_headcount + hires - separations
    end as is_reconciled
from with_opening
