{{ config(enabled=target.type == 'bigquery') }}

select wage_observation_id, matrix_id, source_measure_code, wage_measure_id
from {{ ref('fct_wage_observations') }}
where not (
    (
        matrix_id in ('0011B3E2001.px', '0021B3E2002.px')
        and (
            (source_measure_code = '0' and wage_measure_id = 'basic_pay'
                and source_measure_name = 'Basic Pay')
            or (source_measure_code = '1' and wage_measure_id = 'allowance'
                and source_measure_name = 'Allowance')
            or (source_measure_code = '2' and wage_measure_id = 'wage_rate'
                and source_measure_name = 'Wage Rate')
        )
    )
    or (
        matrix_id in ('0051B3E2005.px', '0071B3E2007.px')
        and source_measure_code is null
        and wage_measure_id = 'benchmark_wage_rate'
        and governed_measure_name = 'Benchmark Occupation Wage Rate'
    )
)
