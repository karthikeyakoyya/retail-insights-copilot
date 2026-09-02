-- Calendar spine for time-intelligence joins in Tableau (year, quarter, month, week).
-- Written in DuckDB syntax for local dev; see docs/BIGQUERY_MIGRATION.md for the
-- couple of lines that change to run this same model against BigQuery.
with date_spine as (
    select unnest(
        generate_series(date '2024-01-01', date '2024-01-01' + interval '900 day', interval '1 day')
    ) as calendar_date
)

select
    calendar_date,
    extract(year from calendar_date) as year,
    extract(quarter from calendar_date) as quarter,
    extract(month from calendar_date) as month,
    strftime(calendar_date, '%Y-%m') as year_month,
    extract(week from calendar_date) as iso_week,
    isodow(calendar_date) as day_of_week,
    strftime(calendar_date, '%A') as day_name
from date_spine
