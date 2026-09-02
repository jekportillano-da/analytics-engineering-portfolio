with valid_employment as (
    select
        *,
        row_number() over (
            partition by worker_id
            order by hire_date, employment_id
        ) as employment_spell_number
    from {{ ref('int_employment_spells_validated') }}
    where is_usable
),

hire_events as (
    select
        employment_id || '-HIRE' as workforce_event_id,
        employment_id,
        worker_id,
        hire_date as event_date,
        case
            when employment_spell_number = 1 then 'first_hire'
            else 'rehire'
        end as event_type,
        cast(null as {{ portable_string_type() }}) as separation_category,
        cast(null as {{ portable_string_type() }}) as separation_reason
    from valid_employment
),

separation_events as (
    select
        employment_id || '-SEPARATION' as workforce_event_id,
        employment_id,
        worker_id,
        termination_date as event_date,
        'separation' as event_type,
        termination_category as separation_category,
        termination_reason as separation_reason
    from valid_employment
    where termination_date is not null
)

select * from hire_events
union all
select * from separation_events
