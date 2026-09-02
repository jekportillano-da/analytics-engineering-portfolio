with daily_headcount as (
    select
        dates.calendar_date as snapshot_date,
        count(distinct workforce.employment_id) as daily_headcount
    from {{ ref('int_date_spine') }} as dates
    left join {{ ref('fct_workforce_daily') }} as workforce
        on dates.calendar_date = workforce.snapshot_date
    group by dates.calendar_date
),

monthly_daily as (
    select
        {{ portable_month_start('snapshot_date') }} as period_start,
        max(snapshot_date) as period_end,
        count(*) as calendar_days,
        avg(daily_headcount) as average_daily_headcount,
        {{ portable_arg_max('daily_headcount', 'snapshot_date') }} as ending_headcount
    from daily_headcount
    group by 1
),

monthly_events as (
    select
        {{ portable_month_start('event_date') }} as period_start,
        {{ portable_count_if("event_type in ('first_hire', 'rehire')") }} as hires,
        {{ portable_count_if("event_type = 'first_hire'") }} as first_hires,
        {{ portable_count_if("event_type = 'rehire'") }} as rehires,
        {{ portable_count_if("event_type = 'separation'") }} as separations,
        {{ portable_count_if(
            "event_type = 'separation' and separation_category = 'voluntary'"
        ) }} as voluntary_separations,
        {{ portable_count_if(
            "event_type = 'separation' and separation_category = 'involuntary'"
        ) }} as involuntary_separations
    from {{ ref('fct_workforce_events') }}
    where event_date between
        date '{{ var("analysis_start_date") }}'
        and date '{{ var("analysis_end_date") }}'
    group by 1
)

select
    monthly_daily.period_start,
    monthly_daily.period_end,
    monthly_daily.calendar_days,
    round(monthly_daily.average_daily_headcount, 2) as average_daily_headcount,
    monthly_daily.ending_headcount,
    coalesce(monthly_events.hires, 0) as hires,
    coalesce(monthly_events.first_hires, 0) as first_hires,
    coalesce(monthly_events.rehires, 0) as rehires,
    coalesce(monthly_events.separations, 0) as separations,
    coalesce(monthly_events.voluntary_separations, 0) as voluntary_separations,
    coalesce(monthly_events.involuntary_separations, 0) as involuntary_separations,
    round(
        coalesce(monthly_events.separations, 0)
            / nullif(monthly_daily.average_daily_headcount, 0),
        6
    ) as period_attrition_rate,
    round(
        (
            coalesce(monthly_events.separations, 0)
                / nullif(monthly_daily.average_daily_headcount, 0)
        ) * (365.0 / monthly_daily.calendar_days),
        6
    ) as annualized_attrition_rate
from monthly_daily
left join monthly_events using (period_start)
order by monthly_daily.period_start
