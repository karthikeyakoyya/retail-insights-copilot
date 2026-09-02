select
    customer_id,
    customer_state,
    customer_city
from {{ ref('stg_customers') }}
