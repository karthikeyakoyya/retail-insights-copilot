select
    seller_id,
    seller_state
from {{ ref('stg_sellers') }}
