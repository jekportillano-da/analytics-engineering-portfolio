{% macro portable_try_cast(expression, data_type) -%}
    {{ return(adapter.dispatch('portable_try_cast', 'analytics_engineering_portfolio')(expression, data_type)) }}
{%- endmacro %}

{% macro default__portable_try_cast(expression, data_type) -%}
    try_cast({{ expression }} as {{ data_type }})
{%- endmacro %}

{% macro bigquery__portable_try_cast(expression, data_type) -%}
    {%- set target_type = 'int64' if data_type | lower == 'integer' else data_type -%}
    safe_cast({{ expression }} as {{ target_type }})
{%- endmacro %}


{% macro portable_string_type() -%}
    {{ return(adapter.dispatch('portable_string_type', 'analytics_engineering_portfolio')()) }}
{%- endmacro %}

{% macro default__portable_string_type() -%}
    varchar
{%- endmacro %}

{% macro bigquery__portable_string_type() -%}
    string
{%- endmacro %}


{% macro portable_date_spine(start_date, end_date) -%}
    {{ return(adapter.dispatch('portable_date_spine', 'analytics_engineering_portfolio')(start_date, end_date)) }}
{%- endmacro %}

{% macro default__portable_date_spine(start_date, end_date) -%}
select cast(calendar_date as date) as calendar_date
from generate_series(
    date '{{ start_date }}',
    date '{{ end_date }}',
    interval 1 day
) as generated(calendar_date)
{%- endmacro %}

{% macro bigquery__portable_date_spine(start_date, end_date) -%}
select calendar_date
from unnest(generate_date_array(
    date '{{ start_date }}',
    date '{{ end_date }}',
    interval 1 day
)) as calendar_date
{%- endmacro %}


{% macro portable_month_start(expression) -%}
    {{ return(adapter.dispatch('portable_month_start', 'analytics_engineering_portfolio')(expression)) }}
{%- endmacro %}

{% macro default__portable_month_start(expression) -%}
    cast(date_trunc('month', {{ expression }}) as date)
{%- endmacro %}

{% macro bigquery__portable_month_start(expression) -%}
    date_trunc({{ expression }}, month)
{%- endmacro %}


{% macro portable_arg_max(value_expression, order_expression) -%}
    {{ return(adapter.dispatch('portable_arg_max', 'analytics_engineering_portfolio')(value_expression, order_expression)) }}
{%- endmacro %}

{% macro default__portable_arg_max(value_expression, order_expression) -%}
    arg_max({{ value_expression }}, {{ order_expression }})
{%- endmacro %}

{% macro bigquery__portable_arg_max(value_expression, order_expression) -%}
    (array_agg({{ value_expression }} order by {{ order_expression }} desc limit 1))[offset(0)]
{%- endmacro %}


{% macro portable_count_if(condition) -%}
    {{ return(adapter.dispatch('portable_count_if', 'analytics_engineering_portfolio')(condition)) }}
{%- endmacro %}

{% macro default__portable_count_if(condition) -%}
    count(*) filter (where {{ condition }})
{%- endmacro %}

{% macro bigquery__portable_count_if(condition) -%}
    countif({{ condition }})
{%- endmacro %}


{% macro portable_date_diff(date_part, start_expression, end_expression) -%}
    {{ return(adapter.dispatch('portable_date_diff', 'analytics_engineering_portfolio')(date_part, start_expression, end_expression)) }}
{%- endmacro %}

{% macro default__portable_date_diff(date_part, start_expression, end_expression) -%}
    date_diff('{{ date_part }}', {{ start_expression }}, {{ end_expression }})
{%- endmacro %}

{% macro bigquery__portable_date_diff(date_part, start_expression, end_expression) -%}
    date_diff({{ end_expression }}, {{ start_expression }}, {{ date_part | upper }})
{%- endmacro %}
