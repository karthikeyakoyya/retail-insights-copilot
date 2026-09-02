-- Grain: one row per order line item. This is the base fact Tableau connects to for
-- revenue, order-volume, and category analysis.
with items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

joined as (
    select
        items.order_item_id,
        orders.order_id,
        orders.customer_id,
        items.seller_id,
        items.product_id,
        orders.order_status,
        orders.purchase_date,
        items.price,
        items.freight_value,
        items.item_total_value
    from items
    inner join orders on items.order_id = orders.order_id
)

select * from joined
