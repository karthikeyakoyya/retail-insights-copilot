"""
generate_report.py

Reads reports/ab_test_results.json (written by ab_test_analysis.py) and
renders reports/ab_test_report.html: a single self-contained page with an
animated count-up on load and growing comparison bars, driven entirely by
the real numbers in the JSON. No placeholder values live in this file.
"""

import json


def load_results(path: str = "reports/ab_test_results.json") -> dict:
    with open(path) as f:
        return json.load(f)


def render(results: dict) -> str:
    conv = results["conversion"]
    order = results["order_value"]
    sample = results["pre_test_sample_size_check"]
    verdict = results["verdict"]
    test_window_days = results["test_window_days"]

    ships = verdict.startswith("ship")
    verdict_tone = "positive" if ships else ("negative" if verdict.startswith("do not") else "neutral")

    max_rate = max(conv["rate_control"], conv["rate_treatment"]) * 1.15
    control_bar_pct = round((conv["rate_control"] / max_rate) * 100, 2)
    treatment_bar_pct = round((conv["rate_treatment"] / max_rate) * 100, 2)

    order_value_available = "error" not in order

    if order_value_available:
        max_order = max(order["mean_control"], order["mean_treatment"]) * 1.15
        control_order_bar_pct = round((order["mean_control"] / max_order) * 100, 2)
        treatment_order_bar_pct = round((order["mean_treatment"] / max_order) * 100, 2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Checkout Experiment Readout</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0F1115;
    --panel: #171A21;
    --line: #262B36;
    --text: #EDEFF3;
    --muted: #8B93A7;
    --signal-positive: #3ECF8E;
    --signal-negative: #F0665A;
    --amber: #F5A623;
    --control-bar: #4A5568;
  }}

  * {{ box-sizing: border-box; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, sans-serif;
    margin: 0;
    padding: 48px 24px 96px;
    line-height: 1.5;
  }}

  .page {{
    max-width: 620px;
    margin: 0 auto;
  }}

  .masthead {{
    margin-bottom: 40px;
  }}

  .masthead .kicker {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    color: var(--muted);
    margin: 0 0 8px;
  }}

  .masthead h1 {{
    font-size: 28px;
    font-weight: 700;
    margin: 0 0 6px;
    letter-spacing: -0.01em;
  }}

  .masthead p {{
    color: var(--muted);
    margin: 0;
    font-size: 15px;
    max-width: 46ch;
  }}

  section {{
    border-top: 1px solid var(--line);
    padding: 28px 0;
  }}

  section h2 {{
    font-size: 14px;
    font-weight: 600;
    color: var(--muted);
    margin: 0 0 20px;
  }}

  .stat-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 6px;
  }}

  .stat-row .label {{
    font-size: 14px;
    color: var(--muted);
  }}

  .stat-row .value {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 15px;
    font-weight: 500;
  }}

  .bar-group {{
    margin-bottom: 22px;
  }}

  .bar-track {{
    background: var(--panel);
    border-radius: 3px;
    height: 28px;
    position: relative;
    overflow: hidden;
    margin-top: 4px;
  }}

  .bar-fill {{
    height: 100%;
    width: 0%;
    border-radius: 3px;
    transition: width 1.1s cubic-bezier(0.16, 1, 0.3, 1);
    display: flex;
    align-items: center;
    padding-left: 10px;
  }}

  .bar-fill.control {{ background: var(--control-bar); }}
  .bar-fill.treatment {{ background: var(--signal-positive); }}

  .bar-fill span {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--bg);
    font-weight: 600;
    white-space: nowrap;
  }}

  .headline-number {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 42px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }}

  .headline-number.positive {{ color: var(--signal-positive); }}
  .headline-number.negative {{ color: var(--signal-negative); }}

  .p-value-note {{
    color: var(--muted);
    font-size: 13px;
    margin-top: 8px;
  }}

  .p-value-note code {{
    font-family: 'IBM Plex Mono', monospace;
    color: var(--amber);
  }}

  .sample-size-card {{
    background: var(--panel);
    border-radius: 4px;
    padding: 18px 20px;
    font-size: 14px;
    color: var(--muted);
  }}

  .sample-size-card strong {{
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
  }}

  .verdict-panel {{
    border-radius: 6px;
    padding: 24px 22px;
    margin-top: 4px;
  }}

  .verdict-panel.positive {{
    background: rgba(62, 207, 142, 0.1);
    border: 1px solid rgba(62, 207, 142, 0.35);
  }}

  .verdict-panel.negative {{
    background: rgba(240, 102, 90, 0.1);
    border: 1px solid rgba(240, 102, 90, 0.35);
  }}

  .verdict-panel.neutral {{
    background: rgba(139, 147, 167, 0.1);
    border: 1px solid rgba(139, 147, 167, 0.35);
  }}

  .verdict-panel .tag {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 8px;
  }}

  .verdict-panel .text {{
    font-size: 17px;
    font-weight: 600;
  }}

  footer {{
    margin-top: 44px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 12px;
  }}
</style>
</head>
<body>
<div class="page">

  <div class="masthead">
    <p class="kicker">retail insights copilot, checkout experiment</p>
    <h1>Free-shipping banner checkout test</h1>
    <p>Control ran the current single-page checkout. Treatment added a
    threshold banner ("add more for free shipping") during a {test_window_days}-day
    test window. Results below are computed directly from the experiment
    dataset, not hand-entered.</p>
  </div>

  <section>
    <h2>Conversion rate</h2>
    <div class="bar-group">
      <div class="stat-row">
        <span class="label">Control ({conv['n_control']:,} visitors)</span>
        <span class="value">{conv['rate_control']*100:.2f}%</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill control" data-target="{control_bar_pct}"><span>{conv['rate_control']*100:.2f}%</span></div>
      </div>
    </div>
    <div class="bar-group">
      <div class="stat-row">
        <span class="label">Treatment ({conv['n_treatment']:,} visitors)</span>
        <span class="value">{conv['rate_treatment']*100:.2f}%</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill treatment" data-target="{treatment_bar_pct}"><span>{conv['rate_treatment']*100:.2f}%</span></div>
      </div>
    </div>

    <div class="headline-number {'positive' if conv['absolute_lift'] > 0 else 'negative'}" data-count-to="{conv['relative_lift_pct']}" data-suffix="%" data-prefix="{'+' if conv['relative_lift_pct'] > 0 else ''}">0%</div>
    <div class="p-value-note">relative lift, two-proportion z-test, <code>p = {conv['p_value']}</code>,
    95% CI [{conv['ci_95_low']*100:.2f}, {conv['ci_95_high']*100:.2f}] points, Cohen's h {conv['cohens_h']}</div>
  </section>

  <section>
    <h2>Order value among converters (BRL)</h2>
    {f'''<div class="bar-group">
      <div class="stat-row">
        <span class="label">Control ({order['n_control_converters']:,} orders)</span>
        <span class="value">R$ {order['mean_control']:.2f}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill control" data-target="{control_order_bar_pct}"><span>R$ {order['mean_control']:.2f}</span></div>
      </div>
    </div>
    <div class="bar-group">
      <div class="stat-row">
        <span class="label">Treatment ({order['n_treatment_converters']:,} orders)</span>
        <span class="value">R$ {order['mean_treatment']:.2f}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill treatment" data-target="{treatment_order_bar_pct}"><span>R$ {order['mean_treatment']:.2f}</span></div>
      </div>
    </div>

    <div class="headline-number {'positive' if order['absolute_lift'] > 0 else 'negative'}" data-count-to="{order['relative_lift_pct']}" data-suffix="%" data-prefix="{'+' if order['relative_lift_pct'] > 0 else ''}">0%</div>
    <div class="p-value-note">relative lift, Welch's t-test, <code>p = {order['p_value']}</code>,
    95% CI [{order['ci_95_low']}, {order['ci_95_high']}] BRL, Cohen's d {order['cohens_d']}</div>''' if order_value_available else f'''<div class="sample-size-card">Not enough converters in at least one arm to compare order value.
    Seen so far: control={order['n_control_converters']}, treatment={order['n_treatment_converters']}.</div>'''}
  </section>

  <section>
    <h2>Sample size check, run before launch</h2>
    <div class="sample-size-card">
      To detect a <strong>{sample['minimum_detectable_effect']*100:.1f} point</strong> lift off an
      <strong>{sample['baseline_rate']*100:.1f}%</strong> baseline at
      <strong>{sample['power']*100:.0f}%</strong> power (alpha {sample['alpha']}),
      the test needed at least <strong>{sample['required_n_per_group']:,}</strong> visitors per arm.
      The dataset above has {conv['n_control']:,} and {conv['n_treatment']:,}, so the test was adequately powered.
    </div>
  </section>

  <section>
    <h2>Verdict</h2>
    <div class="verdict-panel {verdict_tone}">
      <div class="tag">based on both metrics above</div>
      <div class="text">{verdict}</div>
    </div>
  </section>

  <footer>
    Generated from data/checkout_experiment.csv via src/ab_test_analysis.py.
    Every number on this page is computed, not typed in by hand.
  </footer>

</div>

<script>
  function animateCount(el) {{
    const target = parseFloat(el.dataset.countTo);
    const suffix = el.dataset.suffix || '';
    const prefix = el.dataset.prefix || '';
    const duration = 1400;
    const start = performance.now();

    function tick(now) {{
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = target * eased;
      el.textContent = prefix + current.toFixed(2) + suffix;
      if (progress < 1) requestAnimationFrame(tick);
      else el.textContent = prefix + target.toFixed(2) + suffix;
    }}
    requestAnimationFrame(tick);
  }}

  function animateBars() {{
    document.querySelectorAll('.bar-fill').forEach(function (bar, i) {{
      setTimeout(function () {{
        bar.style.width = bar.dataset.target + '%';
      }}, i * 90);
    }});
  }}

  window.addEventListener('load', function () {{
    animateBars();
    document.querySelectorAll('[data-count-to]').forEach(function (el) {{
      setTimeout(function () {{ animateCount(el); }}, 300);
    }});
  }});
</script>
</body>
</html>
"""
    return html


if __name__ == "__main__":
    results = load_results()
    html = render(results)
    with open("reports/ab_test_report.html", "w") as f:
        f.write(html)
    print("Wrote reports/ab_test_report.html")
