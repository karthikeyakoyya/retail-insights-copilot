with source as (
    select * from {{ source('raw_olist', 'products') }}
),

cleaned as (
    select
        product_id,
        lower(trim(product_category)) as product_category,
        round(base_price, 2) as base_price,
        weight_g
    from source
    where product_id is not null
)

select * from cleaned
