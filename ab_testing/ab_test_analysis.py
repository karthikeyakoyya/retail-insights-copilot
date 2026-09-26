"""
ab_test_analysis.py

Runs the actual statistical tests on the checkout experiment data produced
by simulate_experiment.py, and writes a structured JSON result plus a
plain-text report to reports/.

Two tests are run, because a real experiment almost never has just one
metric:

  1. Conversion rate (binary): two-proportion z-test.
  2. Order value among converters (continuous): Welch's t-test, which does
     not assume equal variances between the two groups. A plain Student's
     t-test is the wrong tool here on principle, since there is no reason
     to assume checkout order values have identical variance across two
     different UI treatments, so this script does not use it.

A pre-test sample size calculator is included separately as
required_sample_size(), so this file also answers the question that
usually gets skipped: "how long would this test have needed to run before
you trusted the result?"
"""

import json
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest
from statsmodels.stats.power import NormalIndPower


def analyze_conversion(df: pd.DataFrame) -> dict:
    control = df[df["group"] == "control"]
    treatment = df[df["group"] == "treatment"]

    n_control, n_treatment = len(control), len(treatment)
    conv_control = int(control["converted"].sum())
    conv_treatment = int(treatment["converted"].sum())

    rate_control = conv_control / n_control
    rate_treatment = conv_treatment / n_treatment

    z_stat, p_value = proportions_ztest(
        count=[conv_treatment, conv_control],
        nobs=[n_treatment, n_control],
        alternative="two-sided",
    )

    # Wald confidence interval on the difference in proportions.
    diff = rate_treatment - rate_control
    se_diff = np.sqrt(
        rate_control * (1 - rate_control) / n_control
        + rate_treatment * (1 - rate_treatment) / n_treatment
    )
    ci_low = diff - 1.96 * se_diff
    ci_high = diff + 1.96 * se_diff

    # Cohen's h, the standard effect size measure for two proportions.
    phi_control = 2 * np.arcsin(np.sqrt(rate_control))
    phi_treatment = 2 * np.arcsin(np.sqrt(rate_treatment))
    cohens_h = phi_treatment - phi_control

    return {
        "metric": "conversion_rate",
        "n_control": n_control,
        "n_treatment": n_treatment,
        "rate_control": round(rate_control, 4),
        "rate_treatment": round(rate_treatment, 4),
        "absolute_lift": round(diff, 4),
        "relative_lift_pct": round((diff / rate_control) * 100, 2),
        "z_statistic": round(float(z_stat), 4),
        "p_value": round(float(p_value), 5),
        "ci_95_low": round(ci_low, 4),
        "ci_95_high": round(ci_high, 4),
        "cohens_h": round(float(cohens_h), 4),
        "significant_at_0_05": bool(p_value < 0.05),
    }


def analyze_order_value(df: pd.DataFrame) -> dict:
    control_vals = df.loc[
        (df["group"] == "control") & df["converted"], "order_value_brl"
    ].dropna()
    treatment_vals = df.loc[
        (df["group"] == "treatment") & df["converted"], "order_value_brl"
    ].dropna()

    # A real low-traffic experiment can genuinely land here, for example
    # a brand new landing page with only one or two conversions so far.
    # Welch's t-test and the pooled-variance effect size below both need
    # at least 2 observations per group to compute a variance at all, so
    # fail loudly with a clear reason instead of crashing on a division
    # by zero deep inside the effect size formula.
    if len(control_vals) < 2 or len(treatment_vals) < 2:
        return {
            "metric": "order_value_brl",
            "n_control_converters": int(len(control_vals)),
            "n_treatment_converters": int(len(treatment_vals)),
            "error": "insufficient converters in at least one group (need 2+ per group) to run a t-test",
            "significant_at_0_05": False,
        }

    t_stat, p_value = stats.ttest_ind(
        treatment_vals, control_vals, equal_var=False
    )

    mean_control = control_vals.mean()
    mean_treatment = treatment_vals.mean()
    diff = mean_treatment - mean_control

    se_diff = np.sqrt(
        control_vals.var(ddof=1) / len(control_vals)
        + treatment_vals.var(ddof=1) / len(treatment_vals)
    )
    ci_low = diff - 1.96 * se_diff
    ci_high = diff + 1.96 * se_diff

    # Cohen's d using pooled standard deviation, standard for reporting
    # effect size on a t-test even when Welch's correction was used for
    # the significance test itself.
    pooled_std = np.sqrt(
        ((len(control_vals) - 1) * control_vals.var(ddof=1)
         + (len(treatment_vals) - 1) * treatment_vals.var(ddof=1))
        / (len(control_vals) + len(treatment_vals) - 2)
    )
    cohens_d = diff / pooled_std

    return {
        "metric": "order_value_brl",
        "n_control_converters": int(len(control_vals)),
        "n_treatment_converters": int(len(treatment_vals)),
        "mean_control": round(float(mean_control), 2),
        "mean_treatment": round(float(mean_treatment), 2),
        "absolute_lift": round(float(diff), 2),
        "relative_lift_pct": round(float(diff / mean_control) * 100, 2),
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_value), 5),
        "ci_95_low": round(float(ci_low), 2),
        "ci_95_high": round(float(ci_high), 2),
        "cohens_d": round(float(cohens_d), 4),
        "significant_at_0_05": bool(p_value < 0.05),
    }


def required_sample_size(
    baseline_rate: float,
    minimum_detectable_effect: float,
    power: float = 0.8,
    alpha: float = 0.05,
) -> dict:
    """Pre-test sample size calculation for a proportions test.

    This is the calculation that should happen before an experiment
    launches, not after. It answers: given the smallest lift worth caring
    about, how many visitors per arm do we need to reliably detect it.
    """
    effect_size = 2 * (
        np.arcsin(np.sqrt(baseline_rate + minimum_detectable_effect))
        - np.arcsin(np.sqrt(baseline_rate))
    )
    analysis = NormalIndPower()
    n_per_group = analysis.solve_power(
        effect_size=abs(effect_size),
        alpha=alpha,
        power=power,
        ratio=1.0,
        alternative="two-sided",
    )
    return {
        "baseline_rate": baseline_rate,
        "minimum_detectable_effect": minimum_detectable_effect,
        "power": power,
        "alpha": alpha,
        "required_n_per_group": int(np.ceil(n_per_group)),
    }


def build_verdict(conversion_result: dict, order_value_result: dict) -> str:
    conv_sig = conversion_result["significant_at_0_05"]
    conv_positive = conversion_result["absolute_lift"] > 0
    order_sig = order_value_result.get("significant_at_0_05", False)
    order_positive = order_value_result.get("absolute_lift", 0) > 0

    if conv_sig and conv_positive:
        if order_sig and order_positive:
            return "ship: treatment wins on both conversion and order value"
        return "ship: treatment wins on conversion, order value inconclusive"
    if conv_sig and not conv_positive:
        return "do not ship: treatment reduced conversion"
    return "inconclusive: no significant conversion difference detected, extend the test or increase traffic"


def main():
    df = pd.read_csv("data/checkout_experiment.csv", parse_dates=["visit_ts"])
    # pandas reliably infers real bool dtype for a clean True/False column,
    # but if this file is ever hand-edited or re-saved by another tool the
    # column can come back as the strings "True"/"False" instead. A plain
    # .astype(bool) on a string column would treat every non-empty string
    # as True, silently marking 100% of rows as converted. Handle both
    # cases explicitly instead of assuming the friendlier one.
    if df["converted"].dtype == object:
        df["converted"] = df["converted"].map({"True": True, "False": False})
    df["converted"] = df["converted"].astype(bool)

    conversion_result = analyze_conversion(df)
    order_value_result = analyze_order_value(df)
    sample_size_check = required_sample_size(
        baseline_rate=conversion_result["rate_control"],
        minimum_detectable_effect=0.02,
    )
    verdict = build_verdict(conversion_result, order_value_result)

    test_window_days = int((df["visit_ts"].max() - df["visit_ts"].min()).days) + 1

    results = {
        "conversion": conversion_result,
        "order_value": order_value_result,
        "pre_test_sample_size_check": sample_size_check,
        "verdict": verdict,
        "test_window_days": test_window_days,
    }

    with open("reports/ab_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    lines = []
    lines.append("CHECKOUT REDESIGN A/B TEST RESULTS")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Conversion rate")
    lines.append(f"  Control:    {conversion_result['rate_control']*100:.2f}% (n={conversion_result['n_control']})")
    lines.append(f"  Treatment:  {conversion_result['rate_treatment']*100:.2f}% (n={conversion_result['n_treatment']})")
    lines.append(f"  Lift:       {conversion_result['absolute_lift']*100:+.2f} pts ({conversion_result['relative_lift_pct']:+.2f}% relative)")
    lines.append(f"  p-value:    {conversion_result['p_value']}")
    lines.append(f"  95% CI:     [{conversion_result['ci_95_low']*100:.2f}, {conversion_result['ci_95_high']*100:.2f}] pts")
    lines.append(f"  Cohen's h:  {conversion_result['cohens_h']}")
    lines.append("")
    lines.append("Order value among converters (BRL)")
    if "error" in order_value_result:
        lines.append(f"  Not computed: {order_value_result['error']}")
        lines.append(f"  Converters seen: control={order_value_result['n_control_converters']}, treatment={order_value_result['n_treatment_converters']}")
    else:
        lines.append(f"  Control:    {order_value_result['mean_control']} (n={order_value_result['n_control_converters']})")
        lines.append(f"  Treatment:  {order_value_result['mean_treatment']} (n={order_value_result['n_treatment_converters']})")
        lines.append(f"  Lift:       {order_value_result['absolute_lift']:+.2f} ({order_value_result['relative_lift_pct']:+.2f}% relative)")
        lines.append(f"  p-value:    {order_value_result['p_value']}")
        lines.append(f"  95% CI:     [{order_value_result['ci_95_low']}, {order_value_result['ci_95_high']}]")
        lines.append(f"  Cohen's d:  {order_value_result['cohens_d']}")
    lines.append("")
    lines.append("Pre-test sample size check")
    lines.append(f"  To detect a {sample_size_check['minimum_detectable_effect']*100:.1f} pt lift off a {sample_size_check['baseline_rate']*100:.1f}% baseline")
    lines.append(f"  at {sample_size_check['power']*100:.0f}% power, alpha {sample_size_check['alpha']}: need {sample_size_check['required_n_per_group']} visitors per arm")
    lines.append("")
    lines.append(f"Verdict: {verdict}")

    report_text = "\n".join(lines)
    with open("reports/ab_test_report.md", "w") as f:
        f.write("```\n" + report_text + "\n```\n")

    print(report_text)


if __name__ == "__main__":
    main()
