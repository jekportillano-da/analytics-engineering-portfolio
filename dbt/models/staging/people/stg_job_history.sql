with source as (
    select * from {{ source('raw', 'job_history') }}
),

ranked as (
    select
        trim(source_record_id) as source_record_id,
        trim(job_history_id) as job_history_id,
        trim(employment_id) as employment_id,
        {{ portable_try_cast('effective_start_date', 'date') }} as effective_start_date,
        {{ portable_try_cast("nullif(trim(effective_end_date), '')", 'date') }}
            as effective_end_date,
        trim(job_id) as job_id,
        trim(org_unit_id) as org_unit_id,
        trim(location_id) as location_id,
        nullif(trim(manager_worker_id), '') as manager_worker_id,
        lower(trim(employment_type)) as employment_type,
        {{ portable_try_cast('source_updated_at', 'timestamp') }} as source_updated_at,
        _source_file,
        _loaded_at,
        count(*) over (partition by trim(job_history_id)) as source_version_count,
        row_number() over (
            partition by trim(job_history_id)
            order by
                {{ portable_try_cast('source_updated_at', 'timestamp') }} desc,
                source_record_id desc
        ) as source_version_rank
    from source
)

select
    source_record_id,
    job_history_id,
    employment_id,
    effective_start_date,
    effective_end_date,
    job_id,
    org_unit_id,
    location_id,
    manager_worker_id,
    employment_type,
    source_updated_at,
    source_version_count,
    _source_file,
    _loaded_at
from ranked
where source_version_rank = 1
