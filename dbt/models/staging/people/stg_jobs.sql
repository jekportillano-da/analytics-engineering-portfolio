with source as (
    select
        trim(job_id) as job_id,
        trim(job_name) as job_name,
        trim(job_family) as job_family,
        {{ portable_try_cast('job_level', 'integer') }} as job_level
    from {{ source('raw', 'jobs') }}
),

with_unknown as (
    select * from source
    union all
    select 'UNKNOWN', 'Unknown job', 'Unknown', null
)

select * from with_unknown
