{{ config(enabled=target.type == 'bigquery') }}

with expected as (
    select 'people.quality_issues' as governance_check_id
    union all select 'people.headcount_reconciliation'
    union all select 'people.operational_freshness'
    union all select 'wage.raw_to_mart_reconciliation'
    union all select 'wage.operational_freshness'
),

actual as (
    select governance_check_id
    from {{ ref('mart_analytics_governance_summary') }}
),

missing_controls as (
    select * from expected
    except distinct
    select * from actual
),

unexpected_controls as (
    select * from actual
    except distinct
    select * from expected
)

select * from missing_controls
union all
select * from unexpected_controls
