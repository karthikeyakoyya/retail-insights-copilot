-- Cleans and standardizes the raw orders feed: typed dates, trimmed status, one row per order.
with source as (
    select * from {{ source('raw_olist', 'orders') }}
),

cleaned as (
    select
        order_id,
        customer_id,
        lower(trim(order_status)) as order_status,
        date(order_purchase_date) as purchase_date,
        date(order_estimated_delivery_date) as estimated_delivery_date,
        date(order_delivered_date) as delivered_date,
        round(order_total_value, 2) as order_total_value
    from source
    where order_id is not null
)

select * from cleaned
