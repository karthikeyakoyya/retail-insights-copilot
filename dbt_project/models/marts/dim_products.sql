select
    product_id,
    product_category,
    base_price,
    weight_g,
    case
        when weight_g < 1000 then 'light'
        when weight_g < 5000 then 'medium'
        else 'heavy'
    end as weight_class
from {{ ref('stg_products') }}
