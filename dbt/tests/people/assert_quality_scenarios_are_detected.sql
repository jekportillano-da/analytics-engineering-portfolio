{% set expected_issue_types = var('expected_quality_issue_types', []) %}

with expected as (
    {% if expected_issue_types %}
        {% for issue_type in expected_issue_types %}
            select '{{ issue_type }}' as issue_type
            {% if not loop.last %}union all{% endif %}
        {% endfor %}
    {% else %}
        select cast(null as varchar) as issue_type where false
    {% endif %}
),

actual as (
    select distinct issue_type
    from {{ ref('mart_data_quality_issues') }}
)

select expected.issue_type
from expected
left join actual using (issue_type)
where actual.issue_type is null
