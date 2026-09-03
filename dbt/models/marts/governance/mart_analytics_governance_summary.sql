{{ config(enabled=target.type == 'bigquery') }}

with people_quality as (
    select
        count(*) as issue_count,
        countif(severity = 'error') as error_count,
        countif(severity = 'warning') as warning_count
    from {{ ref('mart_data_quality_issues') }}
),

people_reconciliation as (
    select
        count(*) as period_count,
        countif(is_reconciled) as reconciled_period_count,
        max(abs(coalesce(difference, 0))) as maximum_difference
    from {{ ref('mart_headcount_reconciliation') }}
),

people_freshness as (
    select max(loaded_at) as latest_operational_at
    from {{ source('raw', 'file_manifest') }}
),

wage_reconciliation as (
    select
        count(*) as matrix_count,
        countif(is_reconciled) as reconciled_matrix_count,
        sum(raw_observation_count) as raw_observation_count,
        sum(mart_accounted_observation_count) as mart_observation_count,
        max(abs(mart_difference)) as maximum_difference
    from {{ ref('mart_wage_observation_reconciliation') }}
),

wage_latest_success as (
    select
        retrieval_id,
        retrieval_completed_at as latest_operational_at,
        source_artifact_id,
        extraction_id
    from {{ source('wage_raw', 'ows_ingestion_runs') }}
    where retrieval_status = 'succeeded'
        and extraction_status = 'succeeded'
    qualify row_number() over (
        order by retrieval_completed_at desc, retrieval_id desc
    ) = 1
),

governance_checks as (
    select
        'people.quality_issues' as governance_check_id,
        'people' as domain,
        'quality' as check_type,
        case when issue_count = 0 then 'passed' else 'review_required' end as status,
        cast(issue_count as string) as observed_value,
        'All intentionally surfaced issues remain reviewable' as expected_value,
        cast(null as timestamp) as latest_operational_at,
        cast(null as string) as latest_ingestion_id,
        '2023-01-01 through 2025-12-31 analysis window' as source_reference_period,
        concat(
            cast(error_count as string), ' errors; ',
            cast(warning_count as string), ' warnings'
        ) as detail
    from people_quality

    union all

    select
        'people.headcount_reconciliation',
        'people',
        'reconciliation',
        case
            when reconciled_period_count = period_count and maximum_difference = 0
                then 'passed'
            else 'failed'
        end,
        concat(cast(reconciled_period_count as string), '/', cast(period_count as string)),
        'Every monthly period reconciles with maximum difference 0',
        cast(null as timestamp),
        cast(null as string),
        '2023-01-01 through 2025-12-31 analysis window',
        concat('maximum difference ', cast(maximum_difference as string))
    from people_reconciliation

    union all

    select
        'people.operational_freshness',
        'people',
        'freshness',
        case
            when latest_operational_at is null then 'failed'
            when timestamp_diff(current_timestamp(), latest_operational_at, hour) > 168
                then 'failed'
            when timestamp_diff(current_timestamp(), latest_operational_at, hour) > 48
                then 'warn'
            else 'passed'
        end,
        cast(timestamp_diff(current_timestamp(), latest_operational_at, hour) as string),
        'Hours since load: warn after 48; error after 168',
        latest_operational_at,
        cast(null as string),
        'Synthetic workforce analysis window 2023-01-01 through 2025-12-31',
        'Operational load time is distinct from the synthetic analysis dates'
    from people_freshness

    union all

    select
        'wage.raw_to_mart_reconciliation',
        'wage',
        'reconciliation',
        case
            when reconciled_matrix_count = matrix_count
                and raw_observation_count = mart_observation_count
                and maximum_difference = 0
                then 'passed'
            else 'failed'
        end,
        concat(
            cast(reconciled_matrix_count as string), '/', cast(matrix_count as string),
            ' matrices; ', cast(mart_observation_count as string), ' observations'
        ),
        '4/4 matrices and 225 observations reconcile with difference 0',
        cast(null as timestamp),
        cast(null as string),
        'PSA 2024 Occupational Wages Survey',
        concat('maximum difference ', cast(maximum_difference as string))
    from wage_reconciliation

    union all

    select
        'wage.operational_freshness',
        'wage',
        'freshness',
        case
            when latest_operational_at is null then 'failed'
            when timestamp_diff(current_timestamp(), latest_operational_at, hour) > 168
                then 'failed'
            when timestamp_diff(current_timestamp(), latest_operational_at, hour) > 48
                then 'warn'
            else 'passed'
        end,
        cast(timestamp_diff(current_timestamp(), latest_operational_at, hour) as string),
        'Hours since successful retrieval: warn after 48; error after 168',
        latest_operational_at,
        retrieval_id,
        'PSA 2024 Occupational Wages Survey',
        concat('artifact ', source_artifact_id, '; extraction ', extraction_id)
    from wage_latest_success
)

select
    governance_check_id,
    domain,
    check_type,
    status,
    observed_value,
    expected_value,
    latest_operational_at,
    latest_ingestion_id,
    source_reference_period,
    detail,
    current_timestamp() as evaluated_at
from governance_checks
