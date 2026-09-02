-- One row per line item; adds price + freight together as the item's total charge.
with source as (
    select * from {{ source('raw_olist', 'order_items') }}
),

cleaned as (
    select
        order_item_id,
        order_id,
        product_id,
        seller_id,
        round(price, 2) as price,
        round(freight_value, 2) as freight_value,
        round(price + freight_value, 2) as item_total_value
    from source
    where order_item_id is not null
)

select * from cleaned
