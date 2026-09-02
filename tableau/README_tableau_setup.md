# Tableau setup

This project doesn't ship a `.twbx` file, on purpose: a hand-written Tableau
workbook file is a proprietary binary/XML format that isn't reliably
buildable outside Tableau itself, and a broken one would be worse than none.
What it ships instead is the exact CSV extract for each dashboard, already
shaped at the right grain, plus every calculated field written out and
verified so setup is copy-paste, not guesswork.

## 1. Connect

Open Tableau (Desktop or Public) → **Connect → Text File** → point at each
CSV in this folder. Each file is scoped to one dashboard so you don't have
to build a single mega-model with unrelated joins:

| File | Grain | Powers |
|---|---|---|
| `tableau_extract_fct_orders.csv` | one row per order line item | Sales & Revenue dashboard |
| `tableau_extract_delivery_performance.csv` | one row per delivered order | Logistics dashboard |
| `tableau_extract_customer_rfm.csv` | one row per customer | Customer Segmentation dashboard |

Re-run `python3 tableau/export_extracts.py` any time after `dbt build` to
refresh these from the live warehouse — same command whether the warehouse
is DuckDB (default here) or BigQuery (see `../docs/BIGQUERY_MIGRATION.md`).

## 2. Dashboard 1 — Sales & Revenue (`tableau_extract_fct_orders.csv`)

**Calculated fields to create:**

`Revenue`
```
[price] + [freight_value]
```
(This matches `item_total_value` already in the extract — creating it again
as a calc lets you show the Price/Freight split in a tooltip without an
extra join.)

`Order Month`
```
DATETRUNC('month', [purchase_date])
```

**Sheets:**
- Bar chart: `SUM(Revenue)` by `Order Month` — this is your monthly trend.
- Bar chart: `SUM(Revenue)` by `product_category`, sorted descending, top 10.
- Map: `customer_state` on Detail, `SUM(Revenue)` on Color (needs Tableau's
  built-in Brazil state geocoding, or a state-name lookup if it doesn't
  resolve — see the note at the bottom).

**Performance note** (this is the thing the JD explicitly asks about):
publish this as a Tableau **Extract** (not a live connection) once the CSV
is finalized — with 7,265 rows it won't matter here, but on the real
warehouse (millions of rows) an extract with an extract-refresh schedule
will materially outperform a live connection re-querying DuckDB/BigQuery on
every filter change. Use "Hide Unused Fields" before publishing so the
extract doesn't carry the full schema if you only use a subset.

## 3. Dashboard 2 — Delivery Performance (`tableau_extract_delivery_performance.csv`)

**Calculated fields:**

`On-Time Flag`
```
IF [delivery_outcome] = "on_time" THEN 1 ELSE 0 END
```

`On-Time Rate` (aggregate calc, drop this directly on a shelf)
```
SUM([On-Time Flag]) / COUNT([order_id])
```

`Delay Bucket`
```
IF [delivery_delay_days] <= 0 THEN "On time or early"
ELSEIF [delivery_delay_days] <= 3 THEN "1-3 days late"
ELSEIF [delivery_delay_days] <= 7 THEN "4-7 days late"
ELSE "8+ days late"
END
```

**Sheets:**
- Bar chart: `AVG([delivery_delay_days])` by `customer_state`, sorted
  descending — this is the "which states run late" view from the live
  dashboard's ledger, in Tableau form.
- Stacked bar: count of orders by `Delay Bucket`, colored by bucket.
- KPI card: `[On-Time Rate]` formatted as a percentage.

## 4. Dashboard 3 — Customer Segmentation (`tableau_extract_customer_rfm.csv`)

**Calculated fields:**

`Segment Display Name`
```
CASE [segment]
WHEN "champions" THEN "Champions"
WHEN "new_and_promising" THEN "New & Promising"
WHEN "at_risk_loyal" THEN "At-Risk Loyal"
WHEN "lost" THEN "Lost"
ELSE "Needs Attention"
END
```

`High Value Flag`
```
IF [monetary_score] >= 4 THEN "High value" ELSE "Standard" END
```

**Sheets:**
- Scatter plot: `recency_days` (x) vs `frequency` (y), size by
  `monetary_value`, color by `Segment Display Name` — this is the same
  chart the live HTML dashboard draws by hand in SVG; in Tableau it's a
  three-click scatter plot with the calc fields above driving color/size.
- Bar chart: count of customers by `Segment Display Name`, sorted by count.

## 5. Assembling the dashboard

Combine the sheets from each CSV into three Tableau **Dashboards** (one per
file above), then a top-level **Story** or a single Dashboard with sheet
swapping if you want one URL to share. Add a state/date filter action so
clicking a bar in the delivery-delay chart filters the revenue-by-category
chart alongside it — this is the "interactivity" a plain export can't show.

## Note on the Brazil map

Tableau's built-in geocoding recognizes Brazilian state abbreviations
inconsistently depending on version/locale. If `customer_state` doesn't
resolve on the map automatically: right-click the field → **Geographic
Role → State/Province**, and if points still don't place correctly, use
**Edit Locations** to manually match the two-letter codes (SP, RJ, MG, …)
to their state names.
