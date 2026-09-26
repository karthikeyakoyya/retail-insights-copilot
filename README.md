# Retail Insights Copilot

A self-service analytics platform on a Brazilian e-commerce marketplace: a
dbt-modeled warehouse, three Tableau-ready dashboards, and a small
GenAI layer that answers plain-English business questions in real SQL.
Everything in this zip actually runs — the dbt build is tested (41/41
green), the dashboard is populated from live queries, and the NL-to-SQL
copilot is a real Python service, not a mock.

## Why this project

Built specifically to answer a Data Analyst / Tableau Developer JD that
asked for: Tableau dashboard development, SQL & data validation,
ETL/data-transformation (dbt preferred), database/warehousing concepts, and
Python with Generative AI / LLM integration. Rather than five disconnected
toy scripts, this is one coherent pipeline — raw data → dbt warehouse →
Tableau dashboards + a natural-language query layer over the same marts.

| JD requirement | Where it's answered |
|---|---|
| Tableau dashboard development, calculated fields, performance | `tableau/` — 3 extracts + tested calculated-field formulas + a performance note on extracts vs. live connections |
| SQL & data validation | `dbt_project/models/` — every mart has schema tests (unique, not_null, accepted_values, relationships, a custom range test) |
| ETL / data transformation, dbt preferred | `dbt_project/` — full staging → marts dbt project, builds clean |
| Database / warehousing, joins, data models | 4 dimension tables + 3 fact tables, proper dimensional modeling |
| Python with Generative AI, LLM integration | `nl_to_sql/` — a real NL→SQL engine, with an optional live OpenAI hook |

## What's in here

```
data/            synthetic data generator (Faker + numpy, offline, reproducible)
sample_data/     the CSVs it produces — the "raw warehouse export"
warehouse/       DuckDB loader + the live-query export scripts
dbt_project/     the actual dbt project: staging -> marts, with tests
dashboard/       the standalone HTML dashboard (open it directly, no server needed)
nl_to_sql/       the NL-to-SQL copilot: CLI, and a FastAPI server
tableau/         per-dashboard CSV extracts + setup guide with calc-field formulas
docs/            what changes to point this at BigQuery instead of DuckDB
```

## Quickstart (re-running the whole pipeline)

Everything below already ran once to produce what's in this zip — you don't
need to re-run anything just to look at it. Run this if you want to
regenerate fresh data, or verify the pipeline yourself end to end.

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv

# 1. Generate synthetic raw data (offline, no downloads)
python3 data/generate_data.py --orders 5000

# 2. Load it into DuckDB
python3 warehouse/load_raw.py

# 3. Point dbt at the local DuckDB file
mkdir -p ~/.dbt
cat > ~/.dbt/profiles.yml << 'EOF'
retail_insights_copilot:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: '<absolute-path-to-this-folder>/warehouse/retail_insights.duckdb'
      threads: 4
EOF

# 4. Build the warehouse (staging views + mart tables + 29 tests)
cd dbt_project && dbt build && cd ..

# 5. Export the results
python3 warehouse/export_for_dashboard.py     # -> dashboard/dashboard_data.json
python3 tableau/export_extracts.py            # -> tableau/*.csv

# 6. Rebuild the standalone dashboard HTML with the fresh data baked in
python3 -c "
data = open('dashboard/dashboard_data.json').read()
tpl = open('dashboard/index_template.html').read()
open('dashboard/index.html', 'w').write(tpl.replace('__DASHBOARD_DATA__', data))
"
```

Then just open `dashboard/index.html` in a browser — it's fully
self-contained (data is inlined, no server required).

## Try the live NL-to-SQL copilot

The dashboard's "Ask the Manifest" panel replays canned answers client-side
so it works with zero setup. To ask it *for real* against the warehouse:

```bash
cd nl_to_sql
python3 query_copilot.py "which state has the worst delivery delay?"

# or serve it over HTTP:
uvicorn app:app --reload --port 8008
curl -X POST http://localhost:8008/ask -H "Content-Type: application/json" \
     -d '{"question": "what is the average order value?"}'
```

It understands questions about delivery delay, best revenue month, top
category, at-risk/churning customers, on-time rate, average order value,
top sellers, and champion customers — all matched against a template bank
and executed as real SQL. Set `OPENAI_API_KEY` in your environment and it
switches to asking GPT-4o-mini to write the SQL itself (still validated —
read-only, known tables only — before it's ever run).

## Tableau

See `tableau/README_tableau_setup.md` for the three dashboards (Sales &
Revenue, Delivery Performance, Customer Segmentation), the exact calculated
fields for each, and a note on extracts vs. live connections for
performance — since that's explicitly what the JD asks about.

## Honesty about scope

- **Synthetic data, real schema.** The dataset is generated locally, not
  downloaded — it mirrors the shape of the real public Olist dataset
  (customers, sellers, products, orders, order items) rather than being a
  copy of it. Point `warehouse/load_raw.py` at a real export and nothing
  else changes.
- **No `.twbx` file.** Tableau's workbook format isn't reliably hand-buildable
  outside Tableau itself. What's here instead: exact extracts + every
  calculated field, tested and ready to paste in — 10 minutes of clicking,
  not guesswork.
- **DuckDB by default, BigQuery-ready.** `docs/BIGQUERY_MIGRATION.md` lists
  the handful of dialect-specific lines (date functions mostly) that change
  to point the same dbt project at BigQuery.
## Checkout A/B Test Analysis

Extended the warehouse with an experimentation module to close a gap most
BI-focused projects skip: statistical testing. Simulates a checkout
redesign test (control vs. a free-shipping threshold banner) across
roughly 19,500 synthetic visitors, then runs a two-proportion z-test on
conversion rate and a Welch's t-test on order value, with 95% confidence
intervals, effect sizes (Cohen's h and d), and a pre-test sample size
calculator. Renders results as a self-contained animated HTML report.

Result from the reference run: conversion lifted from 11.48% to 13.40%
(p = 0.00005), order value from R$221.19 to R$244.24 (p = 0.0006). All
numbers are computed live from the data, not hand-typed.

