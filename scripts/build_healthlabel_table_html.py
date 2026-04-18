"""Build out/healthlabel_table.html — unified GLM + full interaction table."""
import pandas as pd
import numpy as np
import os

OUT = "out"

def _load(f): return pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()

c     = _load(f"{OUT}/HL_full_coefs.csv").set_index("term")
an    = _load(f"{OUT}/HL_full_anova.csv").set_index("term")
an_ix = _load(f"{OUT}/HL_full_anova_ix.csv").set_index("term")
sm    = _load(f"{OUT}/HL_full_summary.csv").set_index("Metric")["Value"]
msd   = _load(f"{OUT}/HL_means_sds.csv").rename(columns={"Unnamed: 0":"key"}).set_index("key")
cmsd  = _load(f"{OUT}/HL_cell_means.csv").set_index("key")   # cell means for interactions

# ── Helpers ───────────────────────────────────────────────────────────────────
def fp(p):
    try:
        p = float(p)
        if np.isnan(p): return "—"
        if p < 0.001: return "<.001"
        return f"{p:.3f}"
    except: return "—"

def fv(v, dec=3):
    try:
        v = float(v)
        return "—" if np.isnan(v) else f"{v:.{dec}f}"
    except: return "—"

def fdf(v):
    try:
        v = float(v)
        return "—" if np.isnan(v) else str(int(round(v)))
    except: return "—"

def sig(p):
    try:
        p = float(p)
        if np.isnan(p): return ""
        if p < 0.01:  return "***"
        if p < 0.05:  return "**"
        if p < 0.10:  return "*"
        return ""
    except: return ""

def sc(p):
    try:
        p = float(p)
        if p < 0.01:  return "sig1"
        if p < 0.05:  return "sig5"
        if p < 0.10:  return "sig10"
        return ""
    except: return ""

def fmsd(key):
    try:
        m = float(msd.loc[key, "mean"]); s = float(msd.loc[key, "sd"])
        return "—" if np.isnan(m) else f"{m:.2f} ({s:.2f})"
    except: return "—"

def fmsd_cell(key):
    try:
        m = float(cmsd.loc[key, "mean"]); s = float(cmsd.loc[key, "sd"])
        return "—" if np.isnan(m) else f"{m:.2f} ({s:.2f})"
    except: return "—"

def cr(term):
    return c.loc[term] if (not c.empty and term in c.index) else None

def ar(term, anova=None):
    df = anova if anova is not None else an
    return df.loc[term] if (not df.empty and term in df.index) else {}

# Columns: Predictor | df | F | β | SE | t | p | Sig. | Mean(SD)
NCOLS = 9

# ── TABLE 1 ROWS ──────────────────────────────────────────────────────────────
def sec(label):
    return f'<tr class="sec-hdr"><td colspan="{NCOLS}"><i>{label}</i></td></tr>'

def div():
    return f'<tr class="divider"><td colspan="{NCOLS}"></td></tr>'

def fac_row(label, ref, aterm, msd_key=None):
    """Omnibus factor row: df + F from ANOVA, β/SE/t blank."""
    r   = ar(aterm)
    df_ = r.get("df", np.nan);  f_ = r.get("F", np.nan);  p_ = r.get("p", np.nan)
    msd_str = fmsd(msd_key) if msd_key else "—"
    cls = sc(p_)
    return (
        f'<tr class="fhdr">'
        f'<td><b>{label}</b> <span class="ref">ref:&nbsp;{ref}</span></td>'
        f'<td class="num">{fdf(df_)}</td>'
        f'<td class="num {cls}">{fv(f_, 2)}</td>'
        f'<td class="num">—</td>'          # β
        f'<td class="num">—</td>'          # SE
        f'<td class="num">—</td>'          # t
        f'<td class="num {cls}">{fp(p_)}</td>'
        f'<td class="sig {cls}">{sig(p_)}</td>'
        f'<td class="num msd">{msd_str}</td>'
        f'</tr>'
    )

def lev_row(label, term, msd_key=None):
    """Level contrast row: β + SE + t from coef table."""
    r = cr(term)
    msd_str = fmsd(msd_key) if msd_key else "—"
    if r is None:
        return (f'<tr><td class="ind2">{label}</td>'
                f'<td colspan="{NCOLS-2}" class="num">—</td>'
                f'<td class="num msd">{msd_str}</td></tr>')
    p_ = float(r["p"]); cls = sc(p_)
    return (
        f'<tr>'
        f'<td class="ind2">{label}</td>'
        f'<td class="num">—</td>'          # df
        f'<td class="num">—</td>'          # F
        f'<td class="num {cls}">{fv(r["coef"])}</td>'
        f'<td class="num {cls}">{fv(r["std_err"])}</td>'
        f'<td class="num {cls}">{fv(r["t"])}</td>'
        f'<td class="num {cls}">{fp(p_)}</td>'
        f'<td class="sig {cls}">{sig(p_)}</td>'
        f'<td class="num msd">{msd_str}</td>'
        f'</tr>'
    )

def cont_row(label, term, msd_key=None):
    """Continuous predictor: β + SE + t, no df/F."""
    r = cr(term)
    msd_str = fmsd(msd_key) if msd_key else "—"
    if r is None:
        return (f'<tr><td class="ind1">{label}</td>'
                f'<td colspan="{NCOLS-2}" class="num">—</td>'
                f'<td class="num msd">{msd_str}</td></tr>')
    p_ = float(r["p"]); cls = sc(p_)
    return (
        f'<tr>'
        f'<td class="ind1">{label}</td>'
        f'<td class="num">—</td>'
        f'<td class="num">—</td>'
        f'<td class="num {cls}">{fv(r["coef"])}</td>'
        f'<td class="num {cls}">{fv(r["std_err"])}</td>'
        f'<td class="num {cls}">{fv(r["t"])}</td>'
        f'<td class="num {cls}">{fp(p_)}</td>'
        f'<td class="sig {cls}">{sig(p_)}</td>'
        f'<td class="num msd">{msd_str}</td>'
        f'</tr>'
    )

# Build Table 1
n   = int(float(sm.get("N",      0)))
r2  = float(sm.get("R2",         np.nan))
ar2 = float(sm.get("Adj_R2",     np.nan))

t1 = "\n".join([
    sec("Product Attributes"),
    fac_row("Product Type",            "Basic",     "C(Product)",     "Product__Basic"),
    lev_row("Lab-grown",               "C(Product)[T.Lab]",           "Product__Lab"),
    lev_row("Premium",                 "C(Product)[T.Premium]",       "Product__Premium"),
    fac_row("Price Level",             "Low",       "C(PriceLvl)",    "PriceLvl__Low"),
    lev_row("Mid",                     "C(PriceLvl)[T.Mid]",          "PriceLvl__Mid"),
    lev_row("High",                    "C(PriceLvl)[T.High]",         "PriceLvl__High"),
    fac_row("Nutrition Level",         "Low",       "C(NutriLvl)"),
    lev_row("Mid",                     "C(NutriLvl)[T.Mid]",          "NutriLvl__Mid"),
    lev_row("High",                    "C(NutriLvl)[T.High]",         "NutriLvl__High"),
    fac_row("Taste Level",             "Low",       "C(TasteLvl)",    "TasteLvl__Low"),
    lev_row("Mid",                     "C(TasteLvl)[T.Mid]",          "TasteLvl__Mid"),
    lev_row("High",                    "C(TasteLvl)[T.High]",         "TasteLvl__High"),
    fac_row("Health &amp; Safety Label","No",       "C(HealthLabel)", "HealthLabel__0"),
    lev_row("Yes",                     "C(HealthLabel)[T.1]",         "HealthLabel__1"),
    div(),
    sec("Psychographic &amp; Price"),
    cont_row("Sustainability Orientation","SustainScore_c",  "cont__SustainScore"),
    cont_row("Price (USD)",              "PriceUSD_c",       "cont__PriceUSD"),
    cont_row("Lab Price Gap",            "LabPriceGap_c",    "cont__LabPriceGap"),
    div(),
    sec("Demographics"),
    cont_row("Age",              "Age_num_c",           "cont__Age_num"),
    cont_row("Education",        "Education_num_c",     "cont__Education_num"),
    cont_row("Household Size",   "HouseholdSize_num_c", "cont__HouseholdSize_num"),
    cont_row("Income",           "Income_num_c",        "cont__Income_num"),
    fac_row("Gender",            "Male",      "C(Gender)"),
    fac_row("Marital Status",    "Single",    "C(Marital)"),
    fac_row("Employment",        "Full-time", "C(Employment)"),
    fac_row("Residential Area",  "Urban",     "C(Urban_Rural)"),
    f'<tr class="footer"><td colspan="{NCOLS}"><i>N</i> = {n} &nbsp;|&nbsp; '
    f'<i>R</i>² = {r2:.3f} &nbsp;|&nbsp; Adj. <i>R</i>² = {ar2:.3f}</td></tr>',
])

# ── TABLE 2 ROWS ──────────────────────────────────────────────────────────────
def ix_sec(label):
    return f'<tr class="ix-sec"><td colspan="{NCOLS}"><b>{label}</b></td></tr>'

def ix_omnibus(label, aterm):
    """Interaction block omnibus row: df + F from full-model ANOVA."""
    r   = ar(aterm, an_ix)
    df_ = r.get("df", np.nan); f_ = r.get("F", np.nan); p_ = r.get("p", np.nan)
    cls = sc(p_)
    return (
        f'<tr class="fhdr">'
        f'<td><b>{label}</b></td>'
        f'<td class="num">{fdf(df_)}</td>'
        f'<td class="num {cls}">{fv(f_, 2)}</td>'
        f'<td class="num">—</td>'
        f'<td class="num">—</td>'
        f'<td class="num">—</td>'
        f'<td class="num {cls}">{fp(p_)}</td>'
        f'<td class="sig {cls}">{sig(p_)}</td>'
        f'<td class="num msd">—</td>'
        f'</tr>'
    )

def ix_row(label, term, msd_key=None):
    r = cr(term)
    msd_str = fmsd_cell(msd_key) if msd_key else "—"
    if r is None:
        return (f'<tr><td class="ind2 grey">{label}</td>'
                f'<td class="num grey">—</td>'
                f'<td class="num grey">—</td>'
                f'<td colspan="5" class="num grey">—</td>'
                f'<td class="num msd">{msd_str}</td></tr>')
    p_ = float(r["p"]); cls = sc(p_)
    return (
        f'<tr>'
        f'<td class="ind2">{label}</td>'
        f'<td class="num">—</td>'
        f'<td class="num">—</td>'
        f'<td class="num {cls}">{fv(r["coef"])}</td>'
        f'<td class="num {cls}">{fv(r["std_err"])}</td>'
        f'<td class="num {cls}">{fv(r["t"])}</td>'
        f'<td class="num {cls}">{fp(p_)}</td>'
        f'<td class="sig {cls}">{sig(p_)}</td>'
        f'<td class="num msd">{msd_str}</td>'
        f'</tr>'
    )

t2 = "\n".join([
    ix_sec("1. Product Type Interactions"),
    ix_omnibus("Product × Price Level",                    "C(Product):C(PriceLvl)"),
    ix_row("  Lab × Price Mid",      "C(Product)[T.Lab]:C(PriceLvl)[T.Mid]",      "ProdLab__PriceMid"),
    ix_row("  Lab × Price High",     "C(Product)[T.Lab]:C(PriceLvl)[T.High]",     "ProdLab__PriceHigh"),
    ix_row("  Premium × Price Mid",  "C(Product)[T.Premium]:C(PriceLvl)[T.Mid]",  "ProdPremium__PriceMid"),
    ix_row("  Premium × Price High", "C(Product)[T.Premium]:C(PriceLvl)[T.High]", "ProdPremium__PriceHigh"),

    ix_omnibus("Product × Nutrition Level",                "C(Product):C(NutriLvl)"),
    ix_row("  Lab × Nutrition Mid",      "C(Product)[T.Lab]:C(NutriLvl)[T.Mid]",      "ProdLab__NutriMid"),
    ix_row("  Lab × Nutrition High",     "C(Product)[T.Lab]:C(NutriLvl)[T.High]",     "ProdLab__NutriHigh"),
    ix_row("  Premium × Nutrition Mid",  "C(Product)[T.Premium]:C(NutriLvl)[T.Mid]",  "ProdPremium__NutriMid"),
    ix_row("  Premium × Nutrition High", "C(Product)[T.Premium]:C(NutriLvl)[T.High]", "ProdPremium__NutriHigh"),

    ix_omnibus("Product × Taste Level",                    "C(Product):C(TasteLvl)"),
    ix_row("  Lab × Taste Mid",      "C(Product)[T.Lab]:C(TasteLvl)[T.Mid]",      "ProdLab__TasteMid"),
    ix_row("  Lab × Taste High",     "C(Product)[T.Lab]:C(TasteLvl)[T.High]",     "ProdLab__TasteHigh"),
    ix_row("  Premium × Taste Mid",  "C(Product)[T.Premium]:C(TasteLvl)[T.Mid]",  "ProdPremium__TasteMid"),
    ix_row("  Premium × Taste High", "C(Product)[T.Premium]:C(TasteLvl)[T.High]", "ProdPremium__TasteHigh"),

    ix_omnibus("Product × Health &amp; Safety Label",      "C(Product):C(HealthLabel)"),
    ix_row("  Lab × Health Label",     "C(Product)[T.Lab]:C(HealthLabel)[T.1]",     "ProdLab__HL1"),
    ix_row("  Premium × Health Label", "C(Product)[T.Premium]:C(HealthLabel)[T.1]", "ProdPremium__HL1"),

    ix_sec("2. Price Level Interactions"),
    ix_omnibus("Price × Nutrition Level",                  "C(PriceLvl):C(NutriLvl)"),
    ix_row("  Mid × Nutrition Mid",   "C(PriceLvl)[T.Mid]:C(NutriLvl)[T.Mid]",   "PriceMid__NutriMid"),
    ix_row("  High × Nutrition Mid",  "C(PriceLvl)[T.High]:C(NutriLvl)[T.Mid]",  "PriceHigh__NutriMid"),
    ix_row("  Mid × Nutrition High",  "C(PriceLvl)[T.Mid]:C(NutriLvl)[T.High]",  "PriceMid__NutriHigh"),
    ix_row("  High × Nutrition High", "C(PriceLvl)[T.High]:C(NutriLvl)[T.High]", "PriceHigh__NutriHigh"),

    ix_omnibus("Price × Taste Level",                      "C(PriceLvl):C(TasteLvl)"),
    ix_row("  Mid × Taste Mid",   "C(PriceLvl)[T.Mid]:C(TasteLvl)[T.Mid]",   "PriceMid__TasteMid"),
    ix_row("  High × Taste Mid",  "C(PriceLvl)[T.High]:C(TasteLvl)[T.Mid]",  "PriceHigh__TasteMid"),
    ix_row("  Mid × Taste High",  "C(PriceLvl)[T.Mid]:C(TasteLvl)[T.High]",  "PriceMid__TasteHigh"),
    ix_row("  High × Taste High", "C(PriceLvl)[T.High]:C(TasteLvl)[T.High]", "PriceHigh__TasteHigh"),

    ix_omnibus("Price × Health &amp; Safety Label",        "C(PriceLvl):C(HealthLabel)"),
    ix_row("  Mid × Health Label",  "C(PriceLvl)[T.Mid]:C(HealthLabel)[T.1]",  "PriceMid__HL1"),
    ix_row("  High × Health Label", "C(PriceLvl)[T.High]:C(HealthLabel)[T.1]", "PriceHigh__HL1"),

    ix_sec("3. Nutrition Level Interactions"),
    ix_omnibus("Nutrition × Taste Level",                  "C(NutriLvl):C(TasteLvl)"),
    ix_row("  Mid × Taste Mid",   "C(NutriLvl)[T.Mid]:C(TasteLvl)[T.Mid]",   "NutriMid__TasteMid"),
    ix_row("  High × Taste Mid",  "C(NutriLvl)[T.High]:C(TasteLvl)[T.Mid]",  "NutriHigh__TasteMid"),
    ix_row("  Mid × Taste High",  "C(NutriLvl)[T.Mid]:C(TasteLvl)[T.High]",  "NutriMid__TasteHigh"),
    ix_row("  High × Taste High", "C(NutriLvl)[T.High]:C(TasteLvl)[T.High]", "NutriHigh__TasteHigh"),

    ix_omnibus("Nutrition × Health &amp; Safety Label",    "C(NutriLvl):C(HealthLabel)"),
    ix_row("  Mid × Health Label",  "C(NutriLvl)[T.Mid]:C(HealthLabel)[T.1]",  "NutriMid__HL1"),
    ix_row("  High × Health Label", "C(NutriLvl)[T.High]:C(HealthLabel)[T.1]", "NutriHigh__HL1"),

    ix_sec("4. Taste Level Interactions"),
    ix_omnibus("Taste × Health &amp; Safety Label",        "C(TasteLvl):C(HealthLabel)"),
    ix_row("  Mid × Health Label",  "C(TasteLvl)[T.Mid]:C(HealthLabel)[T.1]",  "TasteMid__HL1"),
    ix_row("  High × Health Label", "C(TasteLvl)[T.High]:C(HealthLabel)[T.1]", "TasteHigh__HL1"),

    f'<tr class="footer"><td colspan="{NCOLS}"><i>N</i> = {n} &nbsp;|&nbsp; '
    f'<i>R</i>² = {r2:.3f} &nbsp;|&nbsp; '
    f'Ref: Basic, Low price/nutrition/taste, No health label</td></tr>',
])

# ── HTML ──────────────────────────────────────────────────────────────────────
THEAD = """
  <thead>
    <tr>
      <th class="pred" rowspan="2">Predictor</th>
      <th class="num" rowspan="2"><i>df</i></th>
      <th class="num" rowspan="2"><i>F</i></th>
      <th class="num" rowspan="2">&beta;</th>
      <th class="num" rowspan="2">SE</th>
      <th class="num" rowspan="2"><i>t</i></th>
      <th class="num" rowspan="2"><i>p</i></th>
      <th class="num" rowspan="2">Sig.</th>
      <th class="num msd" rowspan="2">Mean&nbsp;(SD)</th>
    </tr>
    <tr></tr>
  </thead>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Health &amp; Safety Label — GLM Tables</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  font-family: "Times New Roman", serif;
  font-size: 12.5px; color: #111;
  max-width: 1080px; margin: 40px auto; padding: 0 24px;
  background: #fafafa;
}}
h1 {{ font-size: 17px; font-weight: bold; margin: 0 0 4px; }}
h2 {{ font-size: 14px; font-weight: bold; border-bottom: 1px solid #ccc;
      padding-bottom: 4px; margin: 44px 0 10px; }}
p.note {{ font-size: 11px; color: #555; margin: 0 0 18px; }}
.nav {{ font-size: 12px; margin-bottom: 20px; }}
.nav a {{ color: #0969da; text-decoration: none; margin-right: 14px; }}
.nav a:hover {{ text-decoration: underline; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 6px; }}
th, td {{ padding: 4px 7px; vertical-align: middle; white-space: nowrap; }}
th {{ border-top: 2px solid #111; border-bottom: 1px solid #111;
      font-weight: bold; text-align: center; background: #fff; }}
th.pred {{ text-align: left; white-space: normal; min-width: 200px; }}
td.num  {{ text-align: right; }}
td.msd  {{ text-align: center; background: #f5f0ff; font-size: 11.5px; color: #444; white-space: nowrap; }}
th.msd  {{ background: #f5f0ff; }}
td.sig  {{ text-align: center; font-weight: bold; letter-spacing: 0.02em; }}
td.grey {{ color: #bbb; }}
tr.fhdr td {{ font-weight: bold; background: #f7f7f7; padding-top: 8px; }}
tr.ix-sec td {{ background: #eef2ff; padding: 6px 7px 3px; font-size: 12px;
                border-top: 2px solid #99b; color: #224; }}
td.ind1 {{ padding-left: 16px; text-align: left; white-space: normal; }}
td.ind2 {{ padding-left: 28px; text-align: left; white-space: normal; }}
tr.sec-hdr td {{ font-style: italic; color: #666; padding-top: 9px;
                  font-size: 11px; border-top: 1px solid #e0e0e0;
                  white-space: normal; }}
tr.divider td {{ border-top: 1.5px solid #bbb; padding: 0; height: 0; }}
tr.footer td {{ border-top: 2px solid #111; font-style: italic;
                 font-size: 11px; padding-top: 5px; white-space: normal; }}
tr:not(.fhdr):not(.sec-hdr):not(.divider):not(.footer):not(.ix-sec):hover td {{
  background: #f0f5ff; }}
td.sig1, .sig1  {{ color: #c0392b; }}
td.sig5, .sig5  {{ color: #e67e22; }}
td.sig10, .sig10 {{ color: #7d6608; }}
.ref {{ font-weight: normal; font-size: 11px; color: #888; }}
.tnote {{ font-size: 11px; border-top: 1px solid #bbb;
           padding-top: 6px; margin-top: 8px; color: #333; line-height: 1.6; }}
</style>
</head>
<body>

<div class="nav">
  <a href="tables_preview.html">&#8592; GLM Tables</a>
  <a href="charts_preview.html">&#8592; Charts</a>
  <a href="om_sensitivity.html">&#8592; OM Sensitivity</a>
</div>

<h1>Health &amp; Safety Label — GLM Analysis</h1>
<p class="note">
  Merged: Sept 2025 no label (<i>n</i>=273) + April 2026 label (<i>n</i>=320) &nbsp;|&nbsp;
  OLS, HC3 robust SE &nbsp;|&nbsp; Continuous predictors mean-centred &nbsp;|&nbsp;
  Bold rows = omnibus Type&nbsp;III <i>F</i>-test &nbsp;|&nbsp;
  Indented rows = pairwise HC3 contrast vs reference &nbsp;|&nbsp;
  *** <i>p</i>&lt;.01 &nbsp; ** <i>p</i>&lt;.05 &nbsp; * <i>p</i>&lt;.10
</p>

<h2>Table 1 &middot; Main Effects Model (N&nbsp;=&nbsp;{n})</h2>
<table>{THEAD}
  <tbody>
{t1}
  </tbody>
</table>
<div class="tnote">
  <b>Note.</b> <i>df</i> and <i>F</i> apply to omnibus Type III tests (bold rows).
  &beta;, SE, and <i>t</i> apply to pairwise HC3 contrasts vs reference (indented rows).
  Mean (SD) = mean WTP (1–7) for that level; for continuous predictors, mean and SD of the raw variable.
  Health &amp; Safety Label: No = Sept 2025 survey, Yes = April 2026 survey.
</div>

<h2>Table 2 &middot; All Two-Way Interaction Effects (N&nbsp;=&nbsp;{n})</h2>
<p class="note">
  Bold rows = omnibus Type III <i>F</i> for that interaction block (from full interaction model).
  Indented rows = individual contrast coefficients (HC3 robust SE).
</p>
<table>{THEAD}
  <tbody>
{t2}
  </tbody>
</table>
<div class="tnote">
  <b>Note.</b> All interactions tested simultaneously with main effects in a single model.
  Reference: Product = Basic, PriceLvl = Low, NutriLvl = Low, TasteLvl = Low, HealthLabel = No.
</div>

</body>
</html>"""

out_path = os.path.join(OUT, "healthlabel_table.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Written: {out_path}")
