{% test accepted_range(model, column_name, min_value=none, max_value=none, inclusive=true) %}
-- Hand-rolled stand-in for dbt_utils.accepted_range, so this project has zero
-- external package dependencies and builds fully offline.
with validation as (
    select {{ column_name }} as value_to_check
    from {{ model }}
),
validation_errors as (
    select value_to_check
    from validation
    where
        {% if min_value is not none %}
            {% if inclusive %} value_to_check < {{ min_value }}
            {% else %} value_to_check <= {{ min_value }} {% endif %}
        {% else %} false {% endif %}
        or
        {% if max_value is not none %}
            {% if inclusive %} value_to_check > {{ max_value }}
            {% else %} value_to_check >= {{ max_value }} {% endif %}
        {% else %} false {% endif %}
)
select * from validation_errors
{% endtest %}
