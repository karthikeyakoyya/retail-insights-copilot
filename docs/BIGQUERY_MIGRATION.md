# Running this against BigQuery instead of DuckDB

This project defaults to DuckDB so the whole pipeline builds and runs with
zero cloud account, zero credentials, and zero cost — you can `dbt build`
it the moment you unzip the folder. The dbt models are written in plain,
portable SQL wherever possible, but a handful of lines are genuinely
dialect-specific. Here's the complete, honest list of what changes to point
the same project at BigQuery:

## 1. Profile

Copy `dbt_project/profiles.yml.example` to `~/.dbt/profiles.yml`, fill in
your GCP project/dataset, and `pip install dbt-bigquery` instead of
`dbt-duckdb`.

## 2. Load raw data into BigQuery instead of DuckDB

Replace `warehouse_load_raw.py` with a `bq load` call (or the
`google-cloud-bigquery` Python client) pointing at the same five CSVs in
`sample_data/` — the table names and column names are unchanged, so nothing
downstream needs to know the difference.

## 3. Three SQL functions need dialect swaps

**`dim_date.sql`** — the date spine generation:
```sql
-- DuckDB (current):
select unnest(generate_series(date '2024-01-01', date '2024-01-01' + interval '900 day', interval '1 day')) as calendar_date

-- BigQuery:
select calendar_date
from unnest(generate_date_array('2024-01-01', '2026-06-19')) as calendar_date
```
And `strftime(calendar_date, '%Y-%m')` becomes `format_date('%Y-%m', calendar_date)`.

**`fct_customer_rfm.sql` and `fct_delivery_performance.sql`** — `date_diff`
argument order is reversed between the two engines:
```sql
-- DuckDB (current): part first, then start, then end
date_diff('day', start_date, end_date)

-- BigQuery: end, then start, then part
date_diff(end_date, start_date, day)
```
Every `date_diff('day', a, b)` call in those two models becomes
`date_diff(b, a, day)`.

**`stg_customers.sql`** — this project uses `trim(customer_city)` because
DuckDB has no `initcap()`. BigQuery does have `initcap()`, so you can
restore `initcap(trim(customer_city))` if you want title-cased city names.

## 4. Re-enable dbt_utils (optional)

This project replaced `dbt_utils.accepted_range` with a small local generic
test (`tests/generic/test_accepted_range.sql`) purely because the sandbox
this was built in has no network access to `hub.getdbt.com` — not because
of any BigQuery/DuckDB difference. With normal internet access,
`dbt deps` will work with a `packages.yml` declaring
`dbt-labs/dbt_utils`, and you can swap the test back to
`dbt_utils.accepted_range` if you prefer the maintained version.

## 5. Tableau and the NL-to-SQL API

Neither needs to change. `tableau/export_extracts.py` and
`nl_to_sql/query_copilot.py` both connect through DuckDB's Python API
(`duckdb.connect(...)`) — swap that one line for
`google.cloud.bigquery.Client()` and a `client.query(sql).to_dataframe()`
call, and everything downstream (the extracts, the API, the dashboard)
is unchanged, because they only depend on the marts' column names, not on
which warehouse produced them.
