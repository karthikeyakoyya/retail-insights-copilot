"""
query_copilot.py
-----------------
A small GenAI-over-the-warehouse layer: takes a plain-English business
question, drafts a SQL query against the dbt marts, runs it against DuckDB,
and returns a plain-English answer.

Two modes:
  1. TEMPLATE MODE (default, no API key needed) — matches the question
     against a bank of question templates and fills in the right SQL. This
     is what runs out of the box.
  2. LLM MODE (optional) — if OPENAI_API_KEY is set in the environment,
     the question is sent to the OpenAI API with the warehouse schema as
     context, asking it to write the SQL itself. The generated SQL is still
     validated (read-only, single statement, known tables only) before it
     is ever executed.

Run directly for a quick CLI demo:
    python3 query_copilot.py "which state has the worst delivery delay?"

Or serve it over HTTP:
    uvicorn app:app --reload      (see app.py in this folder)
"""
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Optional

import duckdb

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "warehouse", "retail_insights.duckdb"
)

SCHEMA_CONTEXT = """
main_marts.fct_orders(order_item_id, order_id, customer_id, seller_id, product_id,
    order_status, purchase_date, price, freight_value, item_total_value)
main_marts.fct_delivery_performance(order_id, customer_id, customer_state, purchase_date,
    estimated_delivery_date, delivered_date, actual_delivery_days, estimated_delivery_days,
    delivery_delay_days, delivery_outcome)
main_marts.fct_customer_rfm(customer_id, recency_days, frequency, monetary_value,
    recency_score, frequency_score, monetary_score, rfm_total, segment)
main_marts.dim_customers(customer_id, customer_state, customer_city)
main_marts.dim_products(product_id, product_category, base_price, weight_g, weight_class)
main_marts.dim_sellers(seller_id, seller_state)
main_marts.dim_date(calendar_date, year, quarter, month, year_month, iso_week, day_of_week, day_name)
"""

ALLOWED_TABLES = {
    "main_marts.fct_orders", "main_marts.fct_delivery_performance",
    "main_marts.fct_customer_rfm", "main_marts.dim_customers",
    "main_marts.dim_products", "main_marts.dim_sellers", "main_marts.dim_date",
}


@dataclass
class QueryResult:
    question: str
    sql: str
    answer: str
    mode: str  # "template" or "llm"


# ---------------------------------------------------------------------------
# Template bank: (matcher keywords, sql, answer formatter)
# ---------------------------------------------------------------------------
def _fmt_money(v):
    return f"${v:,.2f}"


TEMPLATES: list[tuple[list[str], str, Callable]] = [
    (
        ["worst", "delay", "state", "delivery"],
        """
        select customer_state, round(avg(delivery_delay_days), 1) as avg_delay,
               round(100.0 * sum(case when delivery_outcome='on_time' then 1 else 0 end)
                     / count(*), 1) as on_time_rate,
               count(*) as n
        from main_marts.fct_delivery_performance
        group by customer_state
        having count(*) >= 5
        order by avg_delay desc
        limit 1
        """,
        lambda row: (
            f"{row['customer_state']} runs latest, averaging "
            f"{'+' if row['avg_delay'] > 0 else ''}{row['avg_delay']} days past the "
            f"estimate, with only {row['on_time_rate']}% of its {int(row['n'])} orders on time."
        ),
    ),
    (
        ["best", "month", "revenue"],
        """
        select strftime(purchase_date, '%Y-%m') as month,
               sum(item_total_value) as revenue, count(distinct order_id) as orders
        from main_marts.fct_orders
        group by 1 order by revenue desc limit 1
        """,
        lambda row: (
            f"{row['month']} was the strongest month, with {_fmt_money(row['revenue'])} "
            f"in revenue across {int(row['orders'])} orders."
        ),
    ),
    (
        ["category", "revenue", "product"],
        """
        select p.product_category as category, sum(o.item_total_value) as revenue,
               count(distinct o.order_id) as orders
        from main_marts.fct_orders o
        join main_marts.dim_products p using (product_id)
        group by 1 order by revenue desc limit 1
        """,
        lambda row: (
            f"{row['category'].replace('_', ' ')} leads, generating "
            f"{_fmt_money(row['revenue'])} across {int(row['orders'])} orders."
        ),
    ),
    (
        ["churn", "at risk", "risk", "lost", "customers"],
        """
        select count(*) as n
        from main_marts.fct_customer_rfm
        where segment in ('at_risk_loyal', 'lost')
        """,
        lambda row: (
            f"{int(row['n'])} customers fall into \"at-risk loyal\" or \"lost\" — "
            f"worth a win-back campaign before they're gone for good."
        ),
    ),
    (
        ["on time", "on-time", "overall", "delivery rate"],
        """
        select round(100.0 * sum(case when delivery_outcome='on_time' then 1 else 0 end)
                     / count(*), 1) as rate
        from main_marts.fct_delivery_performance
        """,
        lambda row: f"{row['rate']}% of delivered orders arrived on or before the estimated date.",
    ),
    (
        ["average order value", "aov", "average order"],
        """
        select round(sum(item_total_value) / count(distinct order_id), 2) as aov
        from main_marts.fct_orders
        """,
        lambda row: f"The average order value is {_fmt_money(row['aov'])}.",
    ),
    (
        ["top seller", "best seller", "top sellers"],
        """
        select seller_id, sum(item_total_value) as revenue, count(*) as items_sold
        from main_marts.fct_orders
        group by seller_id order by revenue desc limit 1
        """,
        lambda row: (
            f"Seller {row['seller_id']} leads, with {_fmt_money(row['revenue'])} "
            f"across {int(row['items_sold'])} items sold."
        ),
    ),
    (
        ["champions", "how many champions", "loyal customers"],
        """
        select count(*) as n from main_marts.fct_customer_rfm where segment = 'champions'
        """,
        lambda row: f"{int(row['n'])} customers are scored as \"champions\" — recent, frequent, and high-spend.",
    ),
]


def match_template(question: str):
    qlow = question.lower()
    best, best_score = None, 0
    for keywords, sql, fmt in TEMPLATES:
        score = sum(1 for k in keywords if k in qlow)
        if score > best_score:
            best, best_score = (sql, fmt), score
    return best


def _validate_readonly_sql(sql: str) -> bool:
    """Defense in depth for LLM mode: single SELECT, only known marts, no writes."""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return False
    if not re.match(r"^\s*(with|select)\b", stripped, re.IGNORECASE):
        return False
    forbidden = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|copy|export|pragma)\b", re.IGNORECASE)
    if forbidden.search(stripped):
        return False
    referenced = set(re.findall(r"main_marts\.\w+", stripped))
    if not referenced or not referenced.issubset(ALLOWED_TABLES):
        return False
    return True


def ask_llm(question: str) -> Optional[tuple[str, str]]:
    """Optional live mode: ask the OpenAI API to write the SQL. Requires
    OPENAI_API_KEY. Returns (sql, prose_answer) or None if unavailable."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        print("openai package not installed; falling back to template mode "
              "(pip install openai to enable LLM mode)", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    system = (
        "You are a SQL analyst for a DuckDB warehouse. Write exactly one read-only "
        "SELECT statement (no semicolons, no other statements) against these tables:\n"
        f"{SCHEMA_CONTEXT}\nReturn ONLY the SQL, nothing else."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": question}],
        temperature=0,
    )
    sql = resp.choices[0].message.content.strip().strip("`").strip()
    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()
    if not _validate_readonly_sql(sql):
        print("LLM produced SQL that failed validation; falling back to template mode.", file=sys.stderr)
        return None

    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute(sql).fetchdf()
    con.close()

    summarizer = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Summarize this query result in one plain-English sentence for a business user. No SQL, no jargon."},
            {"role": "user", "content": f"Question: {question}\nResult: {df.to_dict(orient='records')[:5]}"},
        ],
        temperature=0.2,
    )
    return sql, summarizer.choices[0].message.content.strip()


def answer(question: str) -> QueryResult:
    llm_result = ask_llm(question)
    if llm_result:
        sql, prose = llm_result
        return QueryResult(question=question, sql=sql, answer=prose, mode="llm")

    match = match_template(question)
    if not match:
        return QueryResult(
            question=question,
            sql="-- no template matched",
            answer=(
                "I don't have a canned query for that one yet. Try asking about "
                "delivery delay, best month, top category, at-risk customers, "
                "on-time rate, average order value, top seller, or champions."
            ),
            mode="template",
        )
    sql, fmt = match
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute(sql).fetchdf()
    con.close()
    row = df.iloc[0]
    return QueryResult(question=question, sql=sql.strip(), answer=fmt(row), mode="template")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "which state has the worst delivery delay?"
    result = answer(q)
    print(f"Q: {result.question}")
    print(f"[{result.mode} mode]")
    print("--- SQL ---")
    print(result.sql)
    print("--- Answer ---")
    print(result.answer)
