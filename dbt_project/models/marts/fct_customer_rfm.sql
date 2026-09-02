-- Recency / Frequency / Monetary scoring per customer, quintile-banded 1-5 (5 = best),
-- so Tableau can plot a segmentation quadrant without recomputing anything.
-- date_diff arg order below is DuckDB's (part, start, end); see docs/BIGQUERY_MIGRATION.md
-- for the equivalent BigQuery call (part comes last, args reversed).
with orders as (
    select * from {{ ref('stg_orders') }}
    where order_status = 'delivered'
),

per_customer as (
    select
        customer_id,
        date_diff('day', max(purchase_date), current_date()) as recency_days,
        count(distinct order_id) as frequency,
        sum(order_total_value) as monetary_value
    from orders
    group by customer_id
),

scored as (
    select
        *,
        ntile(5) over (order by recency_days desc) as recency_score,
        ntile(5) over (order by frequency asc) as frequency_score,
        ntile(5) over (order by monetary_value asc) as monetary_score
    from per_customer
)

select
    customer_id,
    recency_days,
    frequency,
    monetary_value,
    recency_score,
    frequency_score,
    monetary_score,
    (recency_score + frequency_score + monetary_score) as rfm_total,
    case
        when recency_score >= 4 and frequency_score >= 4 then 'champions'
        when recency_score >= 4 and frequency_score < 4 then 'new_and_promising'
        when recency_score < 3 and frequency_score >= 4 then 'at_risk_loyal'
        when recency_score < 3 and frequency_score < 3 then 'lost'
        else 'needs_attention'
    end as segment
from scored
