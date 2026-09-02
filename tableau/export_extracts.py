"""
export_extracts.py
-------------------
Exports the dbt marts (live from DuckDB) as flat CSVs sized and shaped for
Tableau to connect to directly -- one extract per dashboard, at the grain
each dashboard actually needs, rather than dumping raw fact tables and
making Tableau join everything on load.

Run after `dbt build`:
    python3 tableau/export_extracts.py
"""
import os
import duckdb

DB = os.path.join(os.path.dirname(__file__), "..", "warehouse", "retail_insights.duckdb")
OUT_DIR = os.path.dirname(__file__)

con = duckdb.connect(DB, read_only=True)

# ---- Sales & Revenue dashboard: order-line grain, denormalized for one-connection use ----
con.execute(f"""
    copy (
        select
            o.order_item_id, o.order_id, o.customer_id, o.seller_id, o.product_id,
            o.order_status, o.purchase_date,
            strftime(o.purchase_date, '%Y-%m') as year_month,
            o.price, o.freight_value, o.item_total_value,
            p.product_category, p.weight_class,
            c.customer_state, c.customer_city,
            s.seller_state
        from main_marts.fct_orders o
        join main_marts.dim_products p using (product_id)
        join main_marts.dim_customers c using (customer_id)
        join main_marts.dim_sellers s using (seller_id)
    ) to '{OUT_DIR}/tableau_extract_fct_orders.csv' (header, delimiter ',')
""")

# ---- Logistics / Delivery Performance dashboard ----
con.execute(f"""
    copy (
        select * from main_marts.fct_delivery_performance
    ) to '{OUT_DIR}/tableau_extract_delivery_performance.csv' (header, delimiter ',')
""")

# ---- Customer RFM Segmentation dashboard ----
con.execute(f"""
    copy (
        select r.*, c.customer_state, c.customer_city
        from main_marts.fct_customer_rfm r
        join main_marts.dim_customers c using (customer_id)
    ) to '{OUT_DIR}/tableau_extract_customer_rfm.csv' (header, delimiter ',')
""")

con.close()
for f in ["tableau_extract_fct_orders.csv", "tableau_extract_delivery_performance.csv",
          "tableau_extract_customer_rfm.csv"]:
    path = os.path.join(OUT_DIR, f)
    n = sum(1 for _ in open(path)) - 1
    print(f"{f}: {n:,} rows")
