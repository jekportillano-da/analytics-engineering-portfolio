{{ config(enabled=target.type == 'bigquery') }}

with metric_contract as (
    select
        wage_observation_id,
        reference_year,
        matrix_id,
        matrix_scope,
        wage_measure_id,
        wage_measure_name,
        measure_value
    from {{ ref('metrics_wage_published') }}
),

validated_fact as (
    select
        wage_observation_id,
        reference_year,
        matrix_id,
        matrix_scope,
        wage_measure_id,
        governed_measure_name as wage_measure_name,
        observation_value as measure_value
    from {{ ref('fct_wage_observations') }}
),

contract_minus_fact as (
    select * from metric_contract
    except distinct
    select * from validated_fact
),

fact_minus_contract as (
    select * from validated_fact
    except distinct
    select * from metric_contract
)

select * from contract_minus_fact
union all
select * from fact_minus_contract
