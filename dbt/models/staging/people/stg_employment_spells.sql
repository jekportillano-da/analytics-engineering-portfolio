with source as (
    select * from {{ source('raw', 'employment_spells') }}
),

ranked as (
    select
        trim(source_record_id) as source_record_id,
        trim(employment_id) as employment_id,
        trim(worker_id) as worker_id,
        {{ portable_try_cast('hire_date', 'date') }} as hire_date,
        {{ portable_try_cast("nullif(trim(termination_date), '')", 'date') }} as termination_date,
        lower(nullif(trim(termination_category), '')) as termination_category,
        lower(nullif(trim(termination_reason), '')) as termination_reason,
        {{ portable_try_cast('source_updated_at', 'timestamp') }} as source_updated_at,
        _source_file,
        _loaded_at,
        count(*) over (partition by trim(employment_id)) as source_version_count,
        row_number() over (
            partition by trim(employment_id)
            order by
                {{ portable_try_cast('source_updated_at', 'timestamp') }} desc,
                source_record_id desc
        ) as source_version_rank
    from source
)

select
    source_record_id,
    employment_id,
    worker_id,
    hire_date,
    termination_date,
    termination_category,
    termination_reason,
    source_updated_at,
    source_version_count,
    _source_file,
    _loaded_at
from ranked
where source_version_rank = 1
