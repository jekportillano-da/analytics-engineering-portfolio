with source as (
    select * from {{ source('raw', 'workers') }}
),

ranked as (
    select
        trim(source_record_id) as source_record_id,
        trim(worker_id) as worker_id,
        {{ portable_try_cast('source_created_at', 'timestamp') }} as source_created_at,
        {{ portable_try_cast('source_updated_at', 'timestamp') }} as source_updated_at,
        _source_file,
        _loaded_at,
        count(*) over (partition by trim(worker_id)) as source_version_count,
        row_number() over (
            partition by trim(worker_id)
            order by
                {{ portable_try_cast('source_updated_at', 'timestamp') }} desc,
                source_record_id desc
        ) as source_version_rank
    from source
)

select
    source_record_id,
    worker_id,
    source_created_at,
    source_updated_at,
    source_version_count,
    _source_file,
    _loaded_at
from ranked
where source_version_rank = 1
