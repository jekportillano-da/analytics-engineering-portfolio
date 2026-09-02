with duplicate_workers as (
    select
        'warning' as severity,
        'duplicate_source_versions' as issue_type,
        'worker' as record_type,
        worker_id as record_id,
        'Latest source_updated_at retained from '
            || source_version_count::varchar || ' source rows.' as issue_detail
    from {{ ref('stg_workers') }}
    where source_version_count > 1
),

duplicate_employment as (
    select
        'warning' as severity,
        'duplicate_source_versions' as issue_type,
        'employment_spell' as record_type,
        employment_id as record_id,
        'Latest source_updated_at retained from '
            || source_version_count::varchar || ' source rows.' as issue_detail
    from {{ ref('stg_employment_spells') }}
    where source_version_count > 1
),

duplicate_job_history as (
    select
        'warning' as severity,
        'duplicate_source_versions' as issue_type,
        'job_history' as record_type,
        job_history_id as record_id,
        'Latest source_updated_at retained from '
            || source_version_count::varchar || ' source rows.' as issue_detail
    from {{ ref('stg_job_history') }}
    where source_version_count > 1
),

invalid_employment_dates as (
    select
        'error' as severity,
        'invalid_employment_date_range' as issue_type,
        'employment_spell' as record_type,
        employment_id as record_id,
        'termination_date must be later than hire_date.' as issue_detail
    from {{ ref('int_employment_spells_validated') }}
    where not has_hire_date or not has_valid_date_range
),

orphan_employment_workers as (
    select
        'error' as severity,
        'missing_worker_reference' as issue_type,
        'employment_spell' as record_type,
        employment_id as record_id,
        'worker_id does not exist in the worker source.' as issue_detail
    from {{ ref('int_employment_spells_validated') }}
    where not has_valid_worker
),

invalid_job_dates as (
    select
        'error' as severity,
        'invalid_job_history_date_range' as issue_type,
        'job_history' as record_type,
        job_history_id as record_id,
        'Job dates are invalid or fall outside the employment spell.' as issue_detail
    from {{ ref('int_job_history_validated') }}
    where
        not has_valid_date_range
        or not starts_within_employment
        or not ends_within_employment
),

orphan_job_employment as (
    select
        'error' as severity,
        'missing_employment_reference' as issue_type,
        'job_history' as record_type,
        job_history_id as record_id,
        'employment_id does not reference a usable employment spell.' as issue_detail
    from {{ ref('int_job_history_validated') }}
    where not has_valid_employment
),

missing_job_dimensions as (
    select
        'warning' as severity,
        'missing_job_reference' as issue_type,
        'job_history' as record_type,
        job_history_id as record_id,
        'job_id mapped to UNKNOWN.' as issue_detail
    from {{ ref('int_job_history_validated') }}
    where not has_valid_job

    union all

    select
        'warning',
        'missing_org_unit_reference',
        'job_history',
        job_history_id,
        'org_unit_id mapped to UNKNOWN.'
    from {{ ref('int_job_history_validated') }}
    where not has_valid_org_unit

    union all

    select
        'warning',
        'missing_location_reference',
        'job_history',
        job_history_id,
        'location_id mapped to UNKNOWN.'
    from {{ ref('int_job_history_validated') }}
    where not has_valid_location

    union all

    select
        'warning',
        'missing_manager_reference',
        'job_history',
        job_history_id,
        'manager_worker_id does not exist in the worker source.'
    from {{ ref('int_job_history_validated') }}
    where not has_valid_manager
),

overlapping_history as (
    select
        'error' as severity,
        'overlapping_job_history' as issue_type,
        'job_history' as record_type,
        job_history_id as record_id,
        'Assignment starts before a prior assignment ends; latest effective start wins.'
            as issue_detail
    from {{ ref('int_job_history_overlaps') }}
)

select * from duplicate_workers
union all select * from duplicate_employment
union all select * from duplicate_job_history
union all select * from invalid_employment_dates
union all select * from orphan_employment_workers
union all select * from invalid_job_dates
union all select * from orphan_job_employment
union all select * from missing_job_dimensions
union all select * from overlapping_history
