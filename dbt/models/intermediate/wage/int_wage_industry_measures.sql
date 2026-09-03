{{ config(enabled=target.type == 'bigquery') }}

select
    logical_observation_id,
    source_record_id,
    semantic_dataset_id,
    matrix_id,
    matrix_title,
    'industry_wage_measures' as matrix_scope,
    reference_year,
    industry_code,
    regexp_replace(industry_name, r'^\.\.', '') as industry_name,
    industry_name as source_industry_name,
    cast(null as string) as geography_type,
    cast(null as string) as geography_code,
    cast(null as string) as geography_name,
    cast(null as string) as benchmark_occupation_id,
    cast(null as string) as occupation_name,
    cast(null as string) as sex_code,
    cast(null as string) as sex,
    measure_code as source_measure_code,
    source_measure_name,
    case measure_code
        when '0' then 'basic_pay'
        when '1' then 'allowance'
        when '2' then 'wage_rate'
    end as wage_measure_id,
    case measure_code
        when '0' then 'Basic Pay'
        when '1' then 'Allowance'
        when '2' then 'Wage Rate'
    end as governed_measure_name,
    observation_value,
    observation_status,
    source_unit,
    source_publisher,
    source_updated_at,
    source_artifact_id,
    retrieval_id,
    extraction_id,
    request_id,
    source_record_locator,
    identifier_version,
    matrix_metadata_id,
    canonical_endpoint,
    requested_format,
    sha256_checksum,
    storage_key,
    first_retrieved_at,
    retrieval_started_at,
    retrieval_completed_at,
    loaded_at
from {{ ref('stg_wage_ows_observations') }}
where matrix_id = '0011B3E2001.px'
