-- Grain: one row per delivered order. Powers the Tableau delivery-performance dashboard
-- and the "which states run late" analysis.
-- date_diff arg order below is DuckDB's (part, start, end); see docs/BIGQUERY_MIGRATION.md
-- for the equivalent BigQuery call (part comes last, args reversed).
with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

delivered as (
    select
        orders.order_id,
        orders.customer_id,
        customers.customer_state,
        orders.purchase_date,
        orders.estimated_delivery_date,
        orders.delivered_date,
        date_diff('day', orders.purchase_date, orders.delivered_date) as actual_delivery_days,
        date_diff('day', orders.purchase_date, orders.estimated_delivery_date) as estimated_delivery_days,
        date_diff('day', orders.estimated_delivery_date, orders.delivered_date) as delivery_delay_days,
        case
            when orders.delivered_date <= orders.estimated_delivery_date then 'on_time'
            else 'late'
        end as delivery_outcome
    from orders
    inner join customers on orders.customer_id = customers.customer_id
    where orders.order_status = 'delivered'
      and orders.delivered_date is not null
)

select * from delivered
