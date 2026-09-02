"""
load_raw.py
-----------
Loads the CSVs in ../sample_data/ into DuckDB under the raw_olist schema,
matching dbt_project/models/staging/_sources.yml exactly. This stands in
for a real warehouse ingestion job (e.g. `bq load` or a Fivetran/Airbyte
connector) -- same source() contract downstream, different loader.

Run: python3 warehouse/load_raw.py
"""
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "retail_insights.duckdb")
RAW_DIR = os.path.join(HERE, "..", "sample_data")

TABLES = ["customers", "sellers", "products", "orders", "order_items"]

con = duckdb.connect(DB)
con.execute("create schema if not exists raw_olist")
for t in TABLES:
    path = os.path.join(RAW_DIR, f"{t}.csv")
    con.execute(f"create or replace table raw_olist.{t} as select * from read_csv_auto('{path}')")
    n = con.execute(f"select count(*) from raw_olist.{t}").fetchone()[0]
    print(f"loaded raw_olist.{t}: {n:,} rows")
con.close()
