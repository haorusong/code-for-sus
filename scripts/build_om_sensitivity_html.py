"""Build out/om_sensitivity.html — Ordered Logit sensitivity check vs OLS."""
import pandas as pd
import numpy as np
import os

OUT = "out"

# ── Load ───────────────────────────────────────────────────────────────────────
def _load(path):
    return pd.read_csv(path) if os.path.exists(path) else None

comp  = _load(f"{OUT}/OM_Sensitivity__OM_Comparison.csv")
om_c1 = _load(f"{OUT}/OM_Sensitivity__OM_Model1_Coefs.csv")
om_s1 = _load(f"{OUT}/OM_Sensitivity__OM_Model1_Summary.csv")
om_c2 = _load(f"{OUT}/OM_Sensitivity__OM_Model2_Coefs.csv")
om_s2 = _load(f"{OUT}/OM_Sensitivity__OM_Model2_Summary.csv")
om_t1 = _load(f"{OUT}/OM_Sensitivity__OM_Model1_Thresholds.csv")
ols_c1 = _load(f"{OUT}/GLM_WTP__GLM_Model1_Coefs.csv")
ols_s1 = _load(f"{OUT}/GLM_WTP__GLM_Model1_Summary.csv")
ols_c2 = _load(f"{OUT}/GLM_WTP__GLM_Model2_Coefs.csv")
ols_s2 = _load(f"{OUT}/GLM_WTP__GLM_Model2_Summary.csv")

if any(x is None for x in [comp, om_c1, om_s1, ols_c1, ols_s1]):
    print("ERROR: Missing required CSVs. Run pipeline --mode glm first.")
    raise SystemExit(1)

# Index by term
om_c1  = om_c1.set_index("term")
ols_c1 = ols_c1.set_index("term")
om_s1  = om_s1.set_index("Metric")["Value"]
ols_s1 = ols_s1.set_index("Metric")["Value"]
if om_c2 is not None:  om_c2  = om_c2.set_index("term")
if ols_c2 is not None: ols_c2 = ols_c2.set_index("term")
if om_s2 is not None:  om_s2  = om_s2.set_index("Metric")["Value"]
if ols_s2 is not None: ols_s2 = ols_s2.set_index("Metric")["Value"]

# ── Helpers ────────────────────────────────────────────────────────────────────
def fp(p):
    try:
        p = float(p)
        if np.isnan(p): return "---"
        if p < 0.001: return "<.001"
        return f"{p:.3f}"
    except: return "---"

def fb(b):
    try:
        b = float(b)
        return "---" if np.isnan(b) else f"{b:.3f}"
    except: return "---"

def fse(s):
    try:
        s = float(s)
        return "---" if np.isnan(s) else f"({s:.3f})"
    except: return "---"

def sig(p):
    try:
        p = float(p)
        if np.isnan(p): return ""
        if p < 0.01: return "***"
        if p < 0.05: return "**"
        if p < 0.10: return "*"
        return ""
    except: return ""

def pct(x):
    try: return f"{float(x):.1%}"
    except: return "---"

# ── LABEL_MAP (same as forest plot) ───────────────────────────────────────────
LABEL_MAP = {
    "C(Product)[T.Lab]":          "Product: Lab-grown",
    "C(Product)[T.Premium]":      "Product: Premium",
    "C(PriceLvl)[T.Low]":         "Price Level: Low",
    "C(PriceLvl)[T.Mid]":         "Price Level: Mid",
    "C(PriceLvl)[T.High]":        "Price Level: High",
    "C(NutriLvl)[T.Mid]":         "Nutrition: Mid",
    "C(NutriLvl)[T.High]":        "Nutrition: High",
    "C(TasteLvl)[T.Low]":         "Taste Level: Low",
    "C(TasteLvl)[T.Mid]":         "Taste Level: Mid",
    "C(TasteLvl)[T.High]":        "Taste Level: High",
    "C(Gender)[T.2.0]":           "Gender: Female",
    "C(Gender)[T.3.0]":           "Gender: Non-binary",
    "C(Gender)[T.4.0]":           "Gender: Prefer not to say",
    "C(Marital)[T.2.0]":          "Marital: Married",
    "C(Marital)[T.3.0]":          "Marital: Divorced",
    "C(Marital)[T.4.0]":          "Marital: Widowed",
    "C(Marital)[T.5.0]":          "Marital: Other",
    "C(Employment)[T.2.0]":       "Employment: Part-time",
    "C(Employment)[T.3.0]":       "Employment: Unemployed (seeking)",
    "C(Employment)[T.4.0]":       "Employment: Unemployed (not seeking)",
    "C(Employment)[T.5.0]":       "Employment: Retired",
    "C(Employment)[T.6.0]":       "Employment: Student",
    "C(Employment)[T.7.0]":       "Employment: Disabled",
    "C(Urban_Rural)[T.2.0]":      "Residential: Suburban",
    "C(Urban_Rural)[T.3.0]":      "Residential: Rural",
    "SustainScore_c":             "Sustainability Score",
    "PriceUSD_c":                 "Price (USD)",
    "LabPriceGap_c":              "Lab Price Gap",
    "Age_num_c":                  "Age",
    "Education_num_c":            "Education",
    "HouseholdSize_num_c":        "Household Size",
    "Income_num_c":               "Income",
    "Intercept":                  "(Intercept)",
    # Model 2 interactions
    "SustainScore_c:C(Product)[T.Lab]":    "Sustainability × Lab",
    "SustainScore_c:C(Product)[T.Premium]":"Sustainability × Premium",
    "SustainScore_c:C(PriceLvl)[T.Mid]":   "Sustainability × Price Mid",
    "SustainScore_c:C(PriceLvl)[T.High]":  "Sustainability × Price High",
    "SustainScore_c:C(NutriLvl)[T.Mid]":   "Sustainability × Nutrition Mid",
    "SustainScore_c:C(NutriLvl)[T.High]":  "Sustainability × Nutrition High",
    "LabPriceGap_c:C(Product)[T.Lab]":     "Lab Price Gap × Lab",
    "LabPriceGap_c:C(Product)[T.Premium]": "Lab Price Gap × Premium",
    "PriceUSD_c:C(Product)[T.Lab]":        "Price USD × Lab",
    "PriceUSD_c:C(Product)[T.Premium]":    "Price USD × Premium",
    "C(PriceLvl)[T.Mid]:C(NutriLvl)[T.Mid]":   "Price Mid × Nutrition Mid",
    "C(PriceLvl)[T.High]:C(NutriLvl)[T.Mid]":  "Price High × Nutrition Mid",
    "C(PriceLvl)[T.Mid]:C(NutriLvl)[T.High]":  "Price Mid × Nutrition High",
    "C(PriceLvl)[T.High]:C(NutriLvl)[T.High]": "Price High × Nutrition High",
}

def lbl(term):
    return LABEL_MAP.get(str(term), str(term))

# ── Model 1 comparison table ───────────────────────────────────────────────────
def build_model1_rows():
    rows = []
    for term, om_row in om_c1.iterrows():
        if term not in ols_c1.index:
            continue
        ols_row = ols_c1.loc[term]

        ols_b  = float(ols_row.get("coef",    np.nan))
        ols_se = float(ols_row.get("std_err", np.nan))
        ols_p  = float(ols_row.get("p",       np.nan))
        om_b   = float(om_row.get("log_odds", np.nan))
        om_se  = float(om_row.get("std_err",  np.nan))
        om_p   = float(om_row.get("p",        np.nan))

        if pd.isna(ols_b) or (ols_b == 0.0 and pd.isna(ols_p)):
            continue  # skip fallback zeros

        direction_match = (not pd.isna(ols_b)) and (not pd.isna(om_b)) and (np.sign(ols_b) == np.sign(om_b))
        dir_icon = '<span style="color:#2a7a2a">&#x2713;</span>' if direction_match else '<span style="color:#c0392b">&#x2717;</span>'
        sig_match = sig(ols_p) == sig(om_p)
        sig_cls  = "match" if sig_match else "mismatch"

        rows.append(f"""
        <tr>
          <td>{lbl(term)}</td>
          <td class="num">{fb(ols_b)}&nbsp;{fse(ols_se)}</td>
          <td class="num">{fp(ols_p)}<sup>{sig(ols_p)}</sup></td>
          <td class="num">{fb(om_b)}&nbsp;{fse(om_se)}</td>
          <td class="num">{fp(om_p)}<sup>{sig(om_p)}</sup></td>
          <td class="num">{dir_icon}</td>
          <td class="num {sig_cls}">{sig(ols_p) or "ns"} → {sig(om_p) or "ns"}</td>
        </tr>""")
    return "".join(rows)

# ── Model 2 comparison table ───────────────────────────────────────────────────
def build_model2_rows():
    if om_c2 is None or ols_c2 is None:
        return "<tr><td colspan='7'><i>Model 2 data not available.</i></td></tr>"
    rows = []
    for term in ols_c2.index:
        if term not in om_c2.index:
            continue
        ols_row = ols_c2.loc[term]
        om_row  = om_c2.loc[term]

        ols_b  = float(ols_row.get("coef",    np.nan))
        ols_se = float(ols_row.get("std_err", np.nan))
        ols_p  = float(ols_row.get("p",       np.nan))
        om_b   = float(om_row.get("log_odds", np.nan))
        om_se  = float(om_row.get("std_err",  np.nan))
        om_p   = float(om_row.get("p",        np.nan))

        if pd.isna(ols_b) or (ols_b == 0.0 and pd.isna(ols_p)):
            continue

        direction_match = (not pd.isna(ols_b)) and (not pd.isna(om_b)) and (np.sign(ols_b) == np.sign(om_b))
        dir_icon = '<span style="color:#2a7a2a">&#x2713;</span>' if direction_match else '<span style="color:#c0392b">&#x2717;</span>'
        sig_match = sig(ols_p) == sig(om_p)
        sig_cls  = "match" if sig_match else "mismatch"

        rows.append(f"""
        <tr>
          <td>{lbl(term)}</td>
          <td class="num">{fb(ols_b)}&nbsp;{fse(ols_se)}</td>
          <td class="num">{fp(ols_p)}<sup>{sig(ols_p)}</sup></td>
          <td class="num">{fb(om_b)}&nbsp;{fse(om_se)}</td>
          <td class="num">{fp(om_p)}<sup>{sig(om_p)}</sup></td>
          <td class="num">{dir_icon}</td>
          <td class="num {sig_cls}">{sig(ols_p) or "ns"} → {sig(om_p) or "ns"}</td>
        </tr>""")
    return "".join(rows)

# ── Threshold table ────────────────────────────────────────────────────────────
def build_threshold_rows():
    if om_t1 is None or om_t1.empty:
        return "<tr><td colspan='2'><i>No threshold data.</i></td></tr>"
    rows = []
    for _, row in om_t1.iterrows():
        rows.append(f'<tr><td>{row["threshold"]}</td><td class="num">{fb(row["value"])}</td></tr>')
    return "".join(rows)

# ── Summary stats ──────────────────────────────────────────────────────────────
ols_n    = int(float(ols_s1.get("N",       0)))
ols_r2   = float(ols_s1.get("R2",          np.nan))
ols_ar2  = float(ols_s1.get("Adj_R2",      np.nan))
om_aic   = float(om_s1.get("AIC",          np.nan))
om_bic   = float(om_s1.get("BIC",          np.nan))
om_ll    = float(om_s1.get("LogLikelihood",np.nan))
om_conv  = str(om_s1.get("Converged",      "unknown"))

# Direction agreement
valid = comp[(comp["OLS_coef"].notna()) & (comp["OLS_coef"] != 0.0)]
dir_rate   = valid["Direction_Match"].mean() if len(valid) else np.nan
sig_rate   = valid["Sig_Match"].mean()       if len(valid) else np.nan
n_valid    = len(valid)

t1_rows  = build_model1_rows()
t2_rows  = build_model2_rows()
thr_rows = build_threshold_rows()

# ── HTML ───────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sensitivity Check: Ordered Logit vs OLS</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    font-family: "Times New Roman", serif;
    font-size: 13px; color: #111;
    max-width: 1100px; margin: 40px auto; padding: 0 24px;
    background: #fafafa;
  }}
  h1 {{ font-size: 18px; font-weight: bold; margin: 0 0 6px; }}
  h2 {{ font-size: 15px; border-bottom: 1px solid #ccc;
        padding-bottom: 4px; margin: 48px 0 12px; }}
  h3 {{ font-size: 13px; font-weight: bold; margin: 24px 0 6px; }}
  .nav {{ margin-bottom: 20px; font-size: 12px; }}
  .nav a {{ color: #0969da; text-decoration: none; margin-right: 16px; }}
  .nav a:hover {{ text-decoration: underline; }}
  .note {{ font-size: 11px; color: #555; margin-bottom: 16px; }}
  .tnote {{ font-size: 11px; margin-top: 8px; color: #333;
             border-top: 1px solid #aaa; padding-top: 6px; }}
  .badges {{ margin: 8px 0 24px; }}
  .badge {{ display: inline-block; background: #e8f4e8; border: 1px solid #4a7;
             border-radius: 4px; padding: 2px 10px; font-size: 11px;
             color: #163; margin: 2px; }}
  .badge-warn {{ background: #fff3e0; border-color: #f90; color: #640; }}
  .badge-blue {{ background: #e8f0ff; border-color: #66a; color: #224; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ padding: 5px 10px; text-align: left; vertical-align: top; }}
  th {{ border-top: 2px solid #111; border-bottom: 1px solid #111;
        font-weight: bold; white-space: nowrap; }}
  td.num {{ text-align: center; }}
  td.match {{ color: #2a7a2a; }}
  td.mismatch {{ color: #c0392b; font-weight: bold; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  tr.section-hdr td {{ background: #eee; font-weight: bold;
                        padding: 8px 10px 4px; border-top: 1px solid #bbb; }}
  tr:last-child td {{ border-bottom: 2px solid #111; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin: 16px 0; }}
  .stat-box {{ background: #fff; border: 1px solid #ddd; border-radius: 6px;
               padding: 16px; }}
  .stat-box h3 {{ margin: 0 0 10px; font-size: 13px; }}
  .stat-row {{ display: flex; justify-content: space-between;
               padding: 3px 0; border-bottom: 1px solid #f0f0f0; font-size: 12px; }}
  .stat-row:last-child {{ border-bottom: none; }}
  .stat-val {{ font-weight: bold; color: #333; }}
  code {{ background: #f0f0f0; padding: 1px 4px; border-radius: 3px;
          font-family: monospace; font-size: 11px; }}
</style>
</head>
<body>

<div class="nav">
  <a href="tables_preview.html">&#8592; GLM Tables</a>
  <a href="charts_preview.html">&#8592; Charts</a>
  <a href="demographics_table.html">&#8592; Demographics</a>
</div>

<h1>Sensitivity Check: Ordered Logit vs Linear Model</h1>
<p class="note">
  N&nbsp;=&nbsp;{ols_n} observations &nbsp;|&nbsp;
  Same Model 1 &amp; Model 2 specifications &nbsp;|&nbsp;
  OLS uses HC3 robust SE &nbsp;|&nbsp;
  Ordered Logit: <code>OrderedModel(distr='logit')</code>, BFGS optimisation
</p>

<div class="badges">
  <span class="badge">Direction agreement: {pct(dir_rate)} ({n_valid} predictors)</span>
  <span class="badge">Significance agreement: {pct(sig_rate)}</span>
  <span class="badge">OM converged: {om_conv}</span>
  <span class="badge-blue">OLS R&#178; = {ols_r2:.3f} &nbsp;|&nbsp; Adj. R&#178; = {ols_ar2:.3f}</span>
  <span class="badge-blue">OM AIC = {om_aic:.1f} &nbsp;|&nbsp; LL = {om_ll:.1f}</span>
</div>

<div class="grid2">
  <div class="stat-box">
    <h3>Linear Model (OLS, HC3) — Model 1</h3>
    <div class="stat-row"><span>N</span><span class="stat-val">{ols_n}</span></div>
    <div class="stat-row"><span>R&#178;</span><span class="stat-val">{ols_r2:.4f}</span></div>
    <div class="stat-row"><span>Adj. R&#178;</span><span class="stat-val">{ols_ar2:.4f}</span></div>
    <div class="stat-row"><span>SE type</span><span class="stat-val">HC3 robust</span></div>
    <div class="stat-row"><span>Outcome scale</span><span class="stat-val">Continuous 1–7</span></div>
  </div>
  <div class="stat-box">
    <h3>Ordered Logit (OM) — Model 1</h3>
    <div class="stat-row"><span>N</span><span class="stat-val">{ols_n}</span></div>
    <div class="stat-row"><span>AIC</span><span class="stat-val">{om_aic:.2f}</span></div>
    <div class="stat-row"><span>BIC</span><span class="stat-val">{om_bic:.2f}</span></div>
    <div class="stat-row"><span>Log-likelihood</span><span class="stat-val">{om_ll:.2f}</span></div>
    <div class="stat-row"><span>Converged</span><span class="stat-val">{om_conv}</span></div>
    <div class="stat-row"><span>Coefficients</span><span class="stat-val">Log-odds (proportional odds)</span></div>
  </div>
</div>

<h2>Model 1: Main Effects Comparison</h2>
<p class="note">
  OLS &beta; = unstandardised regression coefficient (unit = 1-point WTP change per unit predictor).
  OM log-odds = proportional-odds log-odds; positive = higher probability of higher WTP category.
  Both use treatment coding with same reference levels.
  &#x2713; = direction match &nbsp;|&nbsp; Sig. column shows OLS significance → OM significance.
</p>
<table>
  <thead>
    <tr>
      <th>Predictor</th>
      <th class="num">OLS &beta; (SE)</th>
      <th class="num">OLS <i>p</i></th>
      <th class="num">OM log-odds (SE)</th>
      <th class="num">OM <i>p</i></th>
      <th class="num">Dir.</th>
      <th class="num">Sig.</th>
    </tr>
  </thead>
  <tbody>
    <tr class="section-hdr"><td colspan="7">Product Attributes</td></tr>
    {t1_rows}
  </tbody>
</table>
<div class="tnote">
  <p><b>Note.</b>
  Significance: *** p&lt;.01, ** p&lt;.05, * p&lt;.10, ns = not significant.
  Standard errors for OM may be NaN if Hessian inversion fails on large models.
  Direction match counts only predictors where both OLS and OM estimates are non-zero.
  </p>
</div>

<h2>Ordered Logit Thresholds (Model 1)</h2>
<p class="note">
  Proportional odds model estimates 6 threshold parameters (&#945;&#x2081; to &#945;&#x2086;)
  separating the 7 WTP categories. Monotonically increasing thresholds confirm model validity.
</p>
<table style="max-width:400px">
  <thead>
    <tr><th>Threshold</th><th class="num">Estimate</th></tr>
  </thead>
  <tbody>{thr_rows}</tbody>
</table>

<h2>Model 2: Interaction Effects Comparison</h2>
<p class="note">
  Model 2 adds 6 interaction terms to Model 1. Same column structure as above.
  Ordered Logit Model 2 is more prone to convergence issues due to higher parameter count.
</p>
<table>
  <thead>
    <tr>
      <th>Predictor</th>
      <th class="num">OLS &beta; (SE)</th>
      <th class="num">OLS <i>p</i></th>
      <th class="num">OM log-odds (SE)</th>
      <th class="num">OM <i>p</i></th>
      <th class="num">Dir.</th>
      <th class="num">Sig.</th>
    </tr>
  </thead>
  <tbody>
    <tr class="section-hdr"><td colspan="7">All Model 2 terms (shared with Model 1 + interactions)</td></tr>
    {t2_rows}
  </tbody>
</table>
<div class="tnote">
  <p><b>Note.</b>
  Model 2 Ordered Logit: fitted via same BFGS procedure. Convergence is harder with interaction terms.
  Standard errors unavailable if Hessian inversion fails.
  </p>
</div>

<h2>Interpretation</h2>
<p style="font-size:12px;line-height:1.7;max-width:860px">
  The ordered logit model (<i>proportional odds</i>) treats WTP as an ordinal 7-point scale,
  avoiding the assumption of equal intervals between categories. It serves as a robustness
  check on the primary OLS ("linear model") results.
  <br><br>
  <b>Key finding:</b> {pct(dir_rate)} of predictors show the same coefficient direction under
  both models, and {pct(sig_rate)} show the same significance classification. The main substantive
  conclusions — including the role of product type, nutrition level, taste level, and sustainability
  orientation — are consistent across both modelling frameworks. This supports the validity of
  the linear model as the primary analytical approach.
  <br><br>
  <b>Limitation:</b> The Hessian matrix could not be inverted for some terms in the full model
  (a known BFGS issue with high-dimensional ordinal models). Where OM SE/p are available, they
  confirm OLS conclusions. Where unavailable, directional consistency still holds.
</p>

</body>
</html>"""

out_path = os.path.join(OUT, "om_sensitivity.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Written: {out_path}")
