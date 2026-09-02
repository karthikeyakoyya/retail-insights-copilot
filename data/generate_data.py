"""
generate_data.py
----------------
Generates a synthetic Brazilian-marketplace e-commerce dataset, structurally
modeled on the public Olist e-commerce dataset (customers, sellers,
products, orders, order line items). This is SYNTHETIC data created locally
with Faker + numpy -- it is not a copy of the real Olist dataset, but it
mirrors its shape and scale so the dbt project's staging models
(models/staging/stg_*.sql) can load it via `{{ source('raw_olist', ...) }}`
exactly as they would load a real warehouse export.

Column names match dbt_project/models/staging/_sources.yml exactly:
  customers(customer_id, customer_state, customer_city)
  sellers(seller_id, seller_state)
  products(product_id, product_category, base_price, weight_g)
  orders(order_id, customer_id, order_status, order_purchase_date,
         order_estimated_delivery_date, order_delivered_date, order_total_value)
  order_items(order_item_id, order_id, product_id, seller_id, price, freight_value)

Run: python3 generate_data.py [--orders 5000] [--seed 42]
Outputs CSVs into ../sample_data/ by default -- the folder the dbt project's
raw-data loader (warehouse_load_raw.py) reads from.
"""
import argparse
import os

import numpy as np
import pandas as pd
from faker import Faker

BR_STATES = [
    "SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "PE",
    "CE", "PA", "ES", "MT", "MS", "MA", "PB", "RN", "AL", "PI",
    "SE", "RO", "TO", "AC", "AM", "AP", "RR",
]

CATEGORIES = [
    "bed_bath_table", "sports_leisure", "furniture_decor", "health_beauty",
    "housewares", "computers_accessories", "toys", "auto", "watches_gifts",
    "telephony", "garden_tools", "cool_stuff", "electronics", "stationery",
    "baby", "office_furniture", "fashion_shoes", "musical_instruments",
]


def _state_weights():
    # roughly mirrors real Brazilian population / e-commerce concentration,
    # long-tailed across all 27 states so every state has at least a few orders
    w = np.array([22, 10, 8, 5, 4, 3.5, 4, 3, 2.5, 3.5,
                  3, 2.5, 2, 1.8, 1.6, 1.6, 1.3, 1.3, 1.2, 1.2,
                  1.1, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    return w / w.sum()


def generate(n_orders: int, seed: int, out_dir: str):
    np.random.seed(seed)
    fake = Faker("pt_BR")
    Faker.seed(seed)

    os.makedirs(out_dir, exist_ok=True)

    # ---- customers (some repeat customers, so RFM has real variance) ----
    n_customers = int(n_orders * 0.5)
    customers = pd.DataFrame({
        "customer_id": [f"CUST{i:06d}" for i in range(1, n_customers + 1)],
        "customer_state": np.random.choice(BR_STATES, n_customers, p=_state_weights()),
        "customer_city": [fake.city() for _ in range(n_customers)],
    })

    # ---- sellers ----
    n_sellers = max(60, n_orders // 17)
    sellers = pd.DataFrame({
        "seller_id": [f"SELL{i:05d}" for i in range(1, n_sellers + 1)],
        "seller_state": np.random.choice(BR_STATES, n_sellers, p=_state_weights()),
    })

    # ---- products ----
    n_products = max(240, n_orders // 4)
    products = pd.DataFrame({
        "product_id": [f"PROD{i:06d}" for i in range(1, n_products + 1)],
        "product_category": np.random.choice(CATEGORIES, n_products),
        "base_price": np.round(np.random.lognormal(mean=3.7, sigma=0.7, size=n_products), 2),
        "weight_g": np.random.gamma(2.0, 400, n_products).round().astype(int).clip(50, 15000),
    })

    # ---- orders (status + dates; total value filled in after order_items) ----
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2025-12-31")
    order_ids = [f"ORD{i:07d}" for i in range(1, n_orders + 1)]
    purchase_date = pd.to_datetime(
        np.random.randint(start.value // 10**9, end.value // 10**9, n_orders), unit="s"
    ).normalize()

    order_customer = np.random.choice(customers["customer_id"], n_orders)
    cust_state_lookup = customers.set_index("customer_id")["customer_state"]
    order_cust_state = cust_state_lookup.loc[order_customer].values

    # a handful of states run structurally later, so the delivery dashboard has
    # something real to surface
    problem_states = {"MA", "PI", "AL", "PA", "AC", "RR", "AP"}
    base_transit_days = np.random.gamma(3.0, 2.2, n_orders).clip(1, 40)
    transit_penalty = np.array([
        np.random.uniform(3, 9) if s in problem_states else 0.0 for s in order_cust_state
    ])
    transit_days = (base_transit_days + transit_penalty).round().astype(int)
    estimated_days = np.random.randint(7, 20, n_orders)

    order_status = np.random.choice(
        ["delivered", "shipped", "canceled", "processing"],
        n_orders, p=[0.875, 0.07, 0.03, 0.025],
    )

    orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": order_customer,
        "order_status": order_status,
        "order_purchase_date": purchase_date.strftime("%Y-%m-%d"),
        "order_estimated_delivery_date": (purchase_date + pd.to_timedelta(estimated_days, unit="D")).strftime("%Y-%m-%d"),
        "order_delivered_date": (purchase_date + pd.to_timedelta(transit_days, unit="D")).strftime("%Y-%m-%d"),
    })
    not_delivered = orders["order_status"].isin(["canceled", "processing", "shipped"])
    orders.loc[not_delivered, "order_delivered_date"] = ""

    # ---- order_items (1-3 lines per order) ----
    rows = []
    item_id = 1
    for oid in order_ids:
        n_items = np.random.choice([1, 1, 1, 2, 2, 3], p=[0.45, 0.2, 0.1, 0.15, 0.05, 0.05])
        for _ in range(n_items):
            prod = products.sample(1).iloc[0]
            price = round(float(prod["base_price"] * np.random.uniform(0.85, 1.25)), 2)
            freight = round(price * np.random.uniform(0.04, 0.18), 2)
            rows.append({
                "order_item_id": item_id,
                "order_id": oid,
                "product_id": prod["product_id"],
                "seller_id": np.random.choice(sellers["seller_id"]),
                "price": price,
                "freight_value": freight,
            })
            item_id += 1
    order_items = pd.DataFrame(rows)

    # ---- fill order_total_value from the items just generated ----
    totals = (
        order_items.assign(line_total=order_items["price"] + order_items["freight_value"])
        .groupby("order_id")["line_total"].sum().round(2)
        .rename("order_total_value")
    )
    orders = orders.merge(totals, on="order_id", how="left")
    orders["order_total_value"] = orders["order_total_value"].fillna(0.0)

    customers.to_csv(f"{out_dir}/customers.csv", index=False)
    sellers.to_csv(f"{out_dir}/sellers.csv", index=False)
    products.to_csv(f"{out_dir}/products.csv", index=False)
    orders.to_csv(f"{out_dir}/orders.csv", index=False)
    order_items.to_csv(f"{out_dir}/order_items.csv", index=False)

    print(f"customers:   {len(customers):>7,}")
    print(f"sellers:     {len(sellers):>7,}")
    print(f"products:    {len(products):>7,}")
    print(f"orders:      {len(orders):>7,}")
    print(f"order_items: {len(order_items):>7,}")
    print(f"\nwrote CSVs to {out_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=5000, help="number of orders to generate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "sample_data"),
        help="output directory (default: ../sample_data, which the dbt project reads from)",
    )
    args = parser.parse_args()
    generate(args.orders, args.seed, args.out)
