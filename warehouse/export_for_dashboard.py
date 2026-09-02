"""
export_for_dashboard.py
------------------------
Queries the dbt-built marts (already materialized in DuckDB by `dbt build`)
and writes dashboard/dashboard_data.json — the single data file the static
dashboard reads. Nothing here is invented: every number is a live aggregation
over main_marts.fct_orders / fct_delivery_performance / fct_customer_rfm /
dim_products / dim_customers / dim_sellers.

Run after `dbt build`:
    python3 warehouse/export_for_dashboard.py
"""
import json
import os

import duckdb

DB = os.path.join(os.path.dirname(__file__), "retail_insights.duckdb")
OUT = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dashboard_data.json")

con = duckdb.connect(DB, read_only=True)


def q(sql):
    return con.execute(sql).fetchdf()


# ---------- summary ----------
total_orders = int(q("select count(distinct order_id) as n from main_marts.fct_orders")["n"][0])
total_revenue = float(q("select sum(item_total_value) as v from main_marts.fct_orders")["v"][0])
n_customers = int(q("select count(*) as n from main_marts.dim_customers")["n"][0])
n_sellers = int(q("select count(*) as n from main_marts.dim_sellers")["n"][0])
n_states = int(q("select count(distinct customer_state) as n from main_marts.dim_customers")["n"][0])
on_time_rate = float(q(
    "select round(100.0 * sum(case when delivery_outcome='on_time' then 1 else 0 end) / count(*), 1) as r "
    "from main_marts.fct_delivery_performance"
)["r"][0])

summary = {
    "total_orders": total_orders,
    "total_revenue": round(total_revenue, 2),
    "avg_order_value": round(total_revenue / total_orders, 2),
    "on_time_rate": on_time_rate,
    "n_customers": n_customers,
    "n_sellers": n_sellers,
    "n_states": n_states,
    "dim_tables": 4,
    "fact_tables": 3,
}

# ---------- monthly trend ----------
trend_df = q("""
    select
        strftime(purchase_date, '%Y-%m') as month,
        sum(item_total_value) as revenue,
        count(distinct order_id) as orders
    from main_marts.fct_orders
    group by 1
    order by 1
""")
monthly_trend = [
    {"month": r.month, "revenue": round(float(r.revenue), 2), "orders": int(r.orders)}
    for r in trend_df.itertuples()
]

# ---------- state delivery performance ----------
state_df = q("""
    select
        customer_state as state,
        round(avg(delivery_delay_days), 1) as avg_delay_days,
        round(100.0 * sum(case when delivery_outcome='on_time' then 1 else 0 end) / count(*), 1) as on_time_rate,
        count(*) as order_count
    from main_marts.fct_delivery_performance
    group by 1
    having count(*) >= 5
    order by avg_delay_days desc
""")
state_performance = [
    {
        "state": r.state,
        "avg_delay_days": float(r.avg_delay_days),
        "on_time_rate": float(r.on_time_rate),
        "order_count": int(r.order_count),
    }
    for r in state_df.itertuples()
]

# ---------- category revenue ----------
cat_df = q("""
    select
        p.product_category as category,
        sum(o.item_total_value) as revenue,
        count(distinct o.order_id) as orders
    from main_marts.fct_orders o
    join main_marts.dim_products p using (product_id)
    group by 1
    order by revenue desc
    limit 10
""")
category_revenue = [
    {"category": r.category, "revenue": round(float(r.revenue), 2), "orders": int(r.orders)}
    for r in cat_df.itertuples()
]

# ---------- RFM ----------
rfm_df = q("""
    select recency_days, frequency, monetary_value, segment
    from main_marts.fct_customer_rfm
""")
rfm_points = [
    {
        "recency_days": int(r.recency_days),
        "frequency": int(r.frequency),
        "monetary_value": round(float(r.monetary_value), 2),
        "segment": r.segment,
    }
    for r in rfm_df.itertuples()
]

seg_df = q("select segment, count(*) as n from main_marts.fct_customer_rfm group by 1")
segment_counts = {r.segment: int(r.n) for r in seg_df.itertuples()}

data = {
    "summary": summary,
    "monthly_trend": monthly_trend,
    "state_performance": state_performance,
    "category_revenue": category_revenue,
    "rfm_points": rfm_points,
    "segment_counts": segment_counts,
}

with open(OUT, "w") as f:
    json.dump(data, f, indent=None, separators=(",", ":"))

print(f"wrote {OUT}")
print(f"  total_orders={total_orders}  total_revenue={total_revenue:,.2f}  "
      f"n_customers={n_customers}  n_states={n_states}  on_time_rate={on_time_rate}%")
print(f"  monthly_trend rows: {len(monthly_trend)}")
print(f"  state_performance rows: {len(state_performance)}")
print(f"  category_revenue rows: {len(category_revenue)}")
print(f"  rfm_points rows: {len(rfm_points)}  segments: {segment_counts}")

con.close()
