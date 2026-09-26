"""
simulate_experiment.py

Generates synthetic checkout-experiment data for the Retail Insights Copilot
project. This mirrors the existing synthetic Brazilian e-commerce dataset
style already used in this repo, so the experiment data reads as an extension
of the warehouse rather than a bolted-on toy dataset.

Scenario: a checkout redesign test.
  - Control: current single-page checkout.
  - Treatment: a shortened checkout with a visible free-shipping threshold
    banner ("Add 42 more for free shipping").

Two outcome metrics are produced, on purpose, so the analysis script has to
handle both a binary metric and a continuous one:
  1. converted (bool)      -> did the visitor complete checkout
  2. order_value_brl (float) -> final order value, only meaningful for
                                 converters

The effect sizes below are deliberately modest (a few percentage points on
conversion, a small lift on order value) because that is what a real
checkout test usually looks like. Nothing here is tuned to produce a "clean"
significant result on every run; sometimes the treatment will lose, and the
analysis script has to say so honestly.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG_SEED = 20260926

CONTROL_CONVERSION_RATE = 0.114      # baseline checkout completion rate
TREATMENT_CONVERSION_LIFT = 0.021    # absolute lift, e.g. 11.4% -> 13.5%

CONTROL_ORDER_VALUE_MEAN = 187.40    # BRL, lognormal underlying mean
CONTROL_ORDER_VALUE_SIGMA = 0.62     # lognormal shape parameter
TREATMENT_ORDER_VALUE_LIFT = 0.035   # 3.5% relative lift from the shipping
                                      # threshold nudging basket size up

DEVICE_MIX = {"mobile": 0.61, "desktop": 0.31, "tablet": 0.08}
TRAFFIC_MIX = {"organic_search": 0.34, "paid_search": 0.22,
               "direct": 0.19, "social": 0.15, "email": 0.10}

EXPERIMENT_START = datetime(2026, 8, 3)
EXPERIMENT_DAYS = 21


def _draw_categorical(rng: np.random.Generator, mix: dict, n: int) -> np.ndarray:
    labels = list(mix.keys())
    weights = np.array(list(mix.values()))
    weights = weights / weights.sum()
    return rng.choice(labels, size=n, p=weights)


def simulate(n_per_group: int = 9800, seed: int = RNG_SEED) -> pd.DataFrame:
    """Simulate a two-arm checkout experiment.

    Args:
        n_per_group: visitors assigned to each arm. Kept asymmetric to the
            real world is avoided on purpose; a real 50/50 split assignment
            job rarely lands on a perfectly round number after exclusions,
            so a small amount of post-assignment drop-out is applied below.
        seed: RNG seed, fixed so the dataset is reproducible across machines.

    Returns:
        A DataFrame with one row per visitor who reached the checkout page.
    """
    rng = np.random.default_rng(seed)

    rows = []
    visitor_counter = 100000

    for group, conversion_rate, order_lift in [
        ("control", CONTROL_CONVERSION_RATE, 0.0),
        ("treatment", CONTROL_CONVERSION_RATE + TREATMENT_CONVERSION_LIFT,
         TREATMENT_ORDER_VALUE_LIFT),
    ]:
        # Small amount of pre-analysis attrition: bots and instrumentation
        # drops that get filtered before the data ever reaches an analyst.
        n_assigned = int(n_per_group * rng.uniform(0.985, 1.0))

        converted = rng.random(n_assigned) < conversion_rate

        devices = _draw_categorical(rng, DEVICE_MIX, n_assigned)
        traffic = _draw_categorical(rng, TRAFFIC_MIX, n_assigned)

        # Order values only exist for converters. Lognormal keeps the
        # right-skew you actually see in basket sizes (lots of small
        # orders, a thin tail of large ones).
        mu = np.log(CONTROL_ORDER_VALUE_MEAN * (1 + order_lift))
        order_values = np.where(
            converted,
            rng.lognormal(mean=mu, sigma=CONTROL_ORDER_VALUE_SIGMA, size=n_assigned),
            np.nan,
        )

        days_offset = rng.integers(0, EXPERIMENT_DAYS, size=n_assigned)
        seconds_offset = rng.integers(0, 86400, size=n_assigned)
        timestamps = [
            EXPERIMENT_START + timedelta(days=int(d), seconds=int(s))
            for d, s in zip(days_offset, seconds_offset)
        ]

        for i in range(n_assigned):
            visitor_counter += 1
            rows.append({
                "visitor_id": f"v_{visitor_counter}",
                "group": group,
                "visit_ts": timestamps[i],
                "device": devices[i],
                "traffic_source": traffic[i],
                "converted": bool(converted[i]),
                "order_value_brl": None if np.isnan(order_values[i]) else round(float(order_values[i]), 2),
            })

    df = pd.DataFrame(rows).sort_values("visit_ts").reset_index(drop=True)
    return df


if __name__ == "__main__":
    data = simulate()
    out_path = "data/checkout_experiment.csv"
    data.to_csv(out_path, index=False)

    n_control = (data["group"] == "control").sum()
    n_treatment = (data["group"] == "treatment").sum()
    print(f"Wrote {len(data)} rows to {out_path}")
    print(f"  control:   {n_control}")
    print(f"  treatment: {n_treatment}")
