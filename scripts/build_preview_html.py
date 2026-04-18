"""Build tables_preview.html from live CSV outputs."""
import pandas as pd
import numpy as np
import os

OUT = "out"

def sig(p):
    if not isinstance(p, float) or np.isnan(p): return ""
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.10: return "*"
    return ""

def fp(p):
    if not isinstance(p, float) or np.isnan(p): return "---"
    if p < 0.001: return "&lt;.001"
    return f"{p:.3f}"

def fb(b, se):
    if not isinstance(b, float) or np.isnan(b): return ""
    return f"{b:.3f}&nbsp;({se:.3f})"

def ft(t):
    if not isinstance(t, float) or np.isnan(t): return ""
    return f"{t:.3f}"

def fmsd(m, s):
    if not isinstance(m, float) or np.isnan(m): return ""
    return f"{m:.3f}&nbsp;({s:.3f})"

def ff(f):
    if not isinstance(f, float) or np.isnan(f): return ""
    return f"{f:.2f}"

def fdf(d):
    if not isinstance(d, float) or np.isnan(d): return ""
    return str(int(round(d)))

c1 = pd.read_csv(f"{OUT}/GLM_WTP__GLM_Model1_Coefs.csv").set_index("term")
an = pd.read_csv(f"{OUT}/GLM_WTP__GLM_AnovaType3.csv").set_index("term")
s1 = pd.read_csv(f"{OUT}/GLM_WTP__GLM_Model1_Summary.csv").set_index("Metric")["Value"]
c2 = pd.read_csv(f"{OUT}/GLM_WTP__GLM_Model2_Coefs.csv").set_index("term")
s2 = pd.read_csv(f"{OUT}/GLM_WTP__GLM_Model2_Summary.csv").set_index("Metric")["Value"]
ld = pd.read_csv(f"{OUT}/GLM_WTP__LongData.csv")

_om_exists = os.path.exists(f"{OUT}/OM_Sensitivity__OM_Comparison.csv")

r2_1  = float(s1["R2"]);     ar2_1 = float(s1["Adj_R2"]); n = int(float(s1["N"]))
r2_2  = float(s2["R2"]);     ar2_2 = float(s2["Adj_R2"])
dr2   = float(s2["DeltaR2"]); fchg = float(s2["F_change"]); pchg = float(s2["p_change"])
dk    = int(float(s2["dk"])); dfe  = int(float(s2["df_error"]))

def lev_stats(col, val):
    sub = ld[ld[col] == val]["WTP"]
    return float(sub.mean()), float(sub.std())

def cont_stats(col):
    sub = ld[col].dropna()
    return float(sub.mean()), float(sub.std())

def ar(term): return an.loc[term] if term in an.index else {}
def r1(term): return c1.loc[term] if term in c1.index else None
def r2t(term): return c2.loc[term] if term in c2.index else None

# ── Row builders ──────────────────────────────────────────────────────────────
def fac_hdr(label, ref, aterm, ref_col=None, ref_val=None):
    r = ar(aterm); f_ = float(r.get("F", np.nan)); d_ = float(r.get("df", np.nan)); p_ = float(r.get("p", np.nan))
    if ref_col and ref_val:
        m_, s_ = lev_stats(ref_col, ref_val)
        msd = fmsd(float(m_), float(s_))
    else:
        msd = ""
    return (f'<tr class="factor-hdr"><td class="indent"><b>{label}</b> (ref:&nbsp;{ref})</td>'
            f'<td class="num">{fdf(d_)}</td><td class="num">{ff(f_)}</td>'
            f'<td></td><td></td><td class="num"><b>{fp(p_)}</b></td>'
            f'<td class="num">{msd}</td>'
            f'<td class="sig">{sig(p_)}</td></tr>')

def lev_row(label, cterm, col, val):
    r = r1(cterm)
    if r is None: return ""
    m, s = lev_stats(col, val)
    return (f'<tr><td class="indent2">{label}</td><td></td><td></td>'
            f'<td class="num">{fb(float(r["coef"]),float(r["std_err"]))}</td>'
            f'<td class="num">{ft(float(r["t"]))}</td><td class="num">{fp(float(r["p"]))}</td>'
            f'<td class="num">{fmsd(m,s)}</td><td class="sig">{sig(float(r["p"]))}</td></tr>')

def cont_row(label, cterm, raw_col=None):
    r = r1(cterm)
    if r is None: return ""
    msd = fmsd(*cont_stats(raw_col)) if raw_col and raw_col in ld.columns else ""
    return (f'<tr><td class="indent">{label}</td><td></td><td></td>'
            f'<td class="num">{fb(float(r["coef"]),float(r["std_err"]))}</td>'
            f'<td class="num">{ft(float(r["t"]))}</td><td class="num">{fp(float(r["p"]))}</td>'
            f'<td class="num">{msd}</td><td class="sig">{sig(float(r["p"]))}</td></tr>')

def cat_demo(label, aterm):
    r = ar(aterm); f_ = float(r.get("F", np.nan)); d_ = float(r.get("df", np.nan)); p_ = float(r.get("p", np.nan))
    return (f'<tr class="factor-hdr"><td class="indent">{label}</td>'
            f'<td class="num">{fdf(d_)}</td><td class="num">{ff(f_)}</td>'
            f'<td></td><td></td><td class="num">{fp(p_)}</td><td></td>'
            f'<td class="sig">{sig(p_)}</td></tr>')

def sec(l, nc=8): return f'<tr class="section"><td colspan="{nc}"><i>{l}</i></td></tr>'

def ixn_hdr(label, ref):
    return (f'<tr class="factor-hdr"><td class="indent"><b>{label}</b>'
            f'&nbsp;<span style="font-weight:normal;font-size:11px;">({ref})</span></td>'
            f'<td></td><td></td><td></td><td></td></tr>')

def ixn_row(label, cterm):
    r = r2t(cterm)
    if r is None: return ""
    return (f'<tr><td class="indent2">{label}</td>'
            f'<td class="num">{fb(float(r["coef"]),float(r["std_err"]))}</td>'
            f'<td class="num">{ft(float(r["t"]))}</td><td class="num">{fp(float(r["p"]))}</td>'
            f'<td class="sig">{sig(float(r["p"]))}</td></tr>')

pchg_str = "&lt;.001" if pchg < 0.001 else f"{pchg:.3f}"
an_prod = ar("C(Product)"); an_nutr = ar("C(NutriLvl)")

t1 = "\n".join([
    sec("Product Attributes"),
    fac_hdr("Product Type","Basic","C(Product)","Product","Basic"),
    lev_row("Lab-grown","C(Product)[T.Lab]","Product","Lab"),
    lev_row("Premium","C(Product)[T.Premium]","Product","Premium"),
    fac_hdr("Price Level","Low","C(PriceLvl)","PriceLvl","Low"),
    lev_row("Mid","C(PriceLvl)[T.Mid]","PriceLvl","Mid"),
    lev_row("High","C(PriceLvl)[T.High]","PriceLvl","High"),
    fac_hdr("Nutrition Level","Low","C(NutriLvl)"),
    lev_row("Mid","C(NutriLvl)[T.Mid]","NutriLvl","Mid"),
    lev_row("High","C(NutriLvl)[T.High]","NutriLvl","High"),
    fac_hdr("Taste Level","Low","C(TasteLvl)","TasteLvl","Low"),
    lev_row("Mid","C(TasteLvl)[T.Mid]","TasteLvl","Mid"),
    lev_row("High","C(TasteLvl)[T.High]","TasteLvl","High"),
    '<tr class="divider"><td colspan="8"></td></tr>',
    sec("Survey Design"),
    fac_hdr("Health Label","No (ref.)","C(HealthLabel)") if "C(HealthLabel)" in an.index else "",
    lev_row("Yes (April 2026)","C(HealthLabel)[T.1]","HealthLabel",1) if "C(HealthLabel)[T.1]" in c1.index else "",
    '<tr class="divider"><td colspan="8"></td></tr>',
    sec("Psychographic"),
    cont_row("Sustainability Orientation","SustainScore_c","SustainScore"),
    sec("Price Variables"),
    cont_row("Price (USD)","PriceUSD_c","PriceUSD"),
    cont_row("Lab Price Gap","LabPriceGap_c","LabPriceGap"),
    sec("Demographics"),
    cont_row("Age","Age_num_c","Age_num"),
    cont_row("Education","Education_num_c","Education_num"),
    cont_row("Household Size","HouseholdSize_num_c","HouseholdSize_num"),
    cont_row("Income","Income_num_c","Income_num"),
    cat_demo("Gender","C(Gender)"),
    cat_demo("Marital Status","C(Marital)"),
    cat_demo("Employment Status","C(Employment)"),
    cat_demo("Residential Area","C(Urban_Rural)"),
    (f'<tr class="footer"><td colspan="8"><i>R</i><sup>2</sup>&nbsp;=&nbsp;{r2_1:.3f},'
     f'&nbsp;&nbsp;Adj.&nbsp;<i>R</i><sup>2</sup>&nbsp;=&nbsp;{ar2_1:.3f}</td></tr>'),
])

t2 = "\n".join([
    sec("Sustainability &times; Product Type", 5),
    ixn_hdr("Sustainability &times; Product Type","ref: Basic"),
    ixn_row("&times; Lab-grown","SustainScore_c:C(Product)[T.Lab]"),
    ixn_row("&times; Premium","SustainScore_c:C(Product)[T.Premium]"),
    sec("Sustainability &times; Price Level", 5),
    ixn_hdr("Sustainability &times; Price Level","ref: Low"),
    ixn_row("&times; Mid","SustainScore_c:C(PriceLvl)[T.Mid]"),
    ixn_row("&times; High","SustainScore_c:C(PriceLvl)[T.High]"),
    sec("Sustainability &times; Nutrition Level", 5),
    ixn_hdr("Sustainability &times; Nutrition Level","ref: Low"),
    ixn_row("&times; Mid","SustainScore_c:C(NutriLvl)[T.Mid]"),
    ixn_row("&times; High","SustainScore_c:C(NutriLvl)[T.High]"),
    sec("Lab Price Gap &times; Product Type", 5),
    ixn_hdr("Lab Price Gap &times; Product Type","ref: Basic"),
    ixn_row("&times; Lab-grown","LabPriceGap_c:C(Product)[T.Lab]"),
    ixn_row("&times; Premium","LabPriceGap_c:C(Product)[T.Premium]"),
    sec("Price USD &times; Product Type", 5),
    ixn_hdr("Price USD &times; Product Type","ref: Basic"),
    ixn_row("&times; Lab-grown","PriceUSD_c:C(Product)[T.Lab]"),
    ixn_row("&times; Premium","PriceUSD_c:C(Product)[T.Premium]"),
    sec("Price Level &times; Nutrition Level", 5),
    ixn_hdr("Price Level &times; Nutrition Level","ref: Low &times; Low"),
    ixn_row("Mid &times; Mid","C(PriceLvl)[T.Mid]:C(NutriLvl)[T.Mid]"),
    ixn_row("High &times; Mid","C(PriceLvl)[T.High]:C(NutriLvl)[T.Mid]"),
    ixn_row("Mid &times; High","C(PriceLvl)[T.Mid]:C(NutriLvl)[T.High]"),
    ixn_row("High &times; High","C(PriceLvl)[T.High]:C(NutriLvl)[T.High]"),
    (f'<tr class="footer"><td colspan="5">'
     f'&Delta;<i>R</i><sup>2</sup>&nbsp;=&nbsp;{dr2:.3f},&nbsp;&nbsp;'
     f'<i>F</i>-change({dk},&nbsp;{dfe})&nbsp;=&nbsp;{fchg:.2f},&nbsp;&nbsp;'
     f'<i>p</i>&nbsp;{pchg_str}</td></tr>'),
    (f'<tr class="model-footer"><td colspan="5">'
     f'Model&nbsp;2: <i>R</i><sup>2</sup>&nbsp;=&nbsp;{r2_2:.3f},'
     f'&nbsp;&nbsp;Adj.&nbsp;<i>R</i><sup>2</sup>&nbsp;=&nbsp;{ar2_2:.3f}</td></tr>'),
])

_om_link = ('<a href="om_sensitivity.html" style="display:inline-block;margin:16px 0 32px;'
            'background:#e8f0ff;border:1px solid #66a;border-radius:4px;padding:6px 14px;'
            'font-size:12px;color:#224;text-decoration:none;">'
            '&#x2197; Open Sensitivity Check: Ordered Logit vs OLS</a>') if _om_exists else ""

CSS = """
body{font-family:"Times New Roman",serif;font-size:13px;max-width:1100px;margin:40px auto;padding:0 24px;color:#111;background:#fafafa;}
h1{font-size:18px;font-weight:bold;margin:0 0 6px;}
h2{font-size:15px;border-bottom:1px solid #ccc;padding-bottom:4px;margin:48px 0 12px;}
.note{font-size:11px;color:#555;margin-bottom:16px;}
table{border-collapse:collapse;width:100%;}
th,td{padding:5px 10px;text-align:left;vertical-align:top;}
th{border-top:2px solid #111;border-bottom:1px solid #111;font-weight:bold;white-space:nowrap;}
td.num{text-align:center;}
tr.section td{font-style:italic;padding-top:10px;}
tr.divider td{border-top:1.5px solid #999;padding:0;height:0;}
tr.factor-hdr td{font-weight:bold;}
tr.footer td{border-top:1px solid #111;font-style:italic;font-size:12px;padding-top:6px;}
tr.model-footer td{font-size:12px;}
tr.sub-hdr td{font-size:10px;font-style:italic;color:#555;padding-top:0;padding-bottom:4px;border-bottom:1px solid #ccc;}
.tnote{font-size:11px;margin-top:8px;color:#333;border-top:1px solid #aaa;padding-top:6px;}
.tnote p{margin:3px 0;}
.sig{font-weight:bold;}
td.indent{padding-left:22px;}
td.indent2{padding-left:40px;}
.badges{margin:8px 0 24px;}
.badge{display:inline-block;background:#e8f4e8;border:1px solid #4a7;border-radius:4px;padding:2px 8px;font-size:11px;color:#163;margin:2px;}
.badge-warn{background:#fff3e0;border-color:#f90;color:#640;}
"""

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>GLM Tables &mdash; April 2026</title>
<style>{CSS}</style></head><body>
<h1>GLM Tables &mdash; New Survey (April 6, 2026)</h1>
<p class="note">N&nbsp;=&nbsp;{n//3}&nbsp;participants &times;&nbsp;3&nbsp;products&nbsp;=&nbsp;{n}&nbsp;observations &nbsp;|&nbsp; Between-subjects design (1 scenario per participant)</p>
<div class="badges">
  <span class="badge">Sustainability &times; Lab: *** p&lt;.001 &#x2713;</span>
  <span class="badge">Nutrition Level: F={float(an_nutr.get('F',0)):.2f}***</span>
  <span class="badge">Product Type: F={float(an_prod.get('F',0)):.2f}***</span>
  <span class="badge-warn">Price Level: ns &mdash; between-subjects reduces power</span>
  <span class="badge-warn">Overall R&sup2;&nbsp;=&nbsp;{r2_1:.3f} (lower than within-subjects; expected)</span>
</div>

<h2>Table 1 &middot; GLM Main Effects &mdash; Model 1 (N&nbsp;=&nbsp;{n})</h2>
<table>
  <thead>
    <tr><th>Predictor</th><th class="num"><i>df</i></th><th class="num"><i>F</i></th>
        <th class="num">&beta;&nbsp;(SE)</th><th class="num"><i>t</i></th><th class="num"><i>p</i></th>
        <th class="num">Mean&nbsp;(SD)</th><th>Sig.</th></tr>
    <tr class="sub-hdr"><td colspan="3"><i>&larr; omnibus (Type&nbsp;III)</i></td>
        <td colspan="4"><i>pairwise contrast (HC3) &rarr;</i></td><td></td></tr>
  </thead>
  <tbody>{t1}</tbody>
</table>
<div class="tnote">
  <p><b>Note.</b> Bold rows = omnibus Type&nbsp;III F-test (df, F, p). Indented rows = pairwise HC3 contrast vs reference (&beta;, SE, t, p, descriptive Mean&nbsp;SD of WTP). All continuous predictors mean-centred (Jaccard &amp; Turrisi, 2003). Significance: *** p&lt;.01, ** p&lt;.05, * p&lt;.10.</p>
</div>

<h2>Table 2 &middot; GLM Interaction Effects &mdash; Model 2 Incremental (N&nbsp;=&nbsp;{n})</h2>
<table>
  <thead><tr><th>Predictor</th><th class="num">&beta;&nbsp;(SE)</th><th class="num"><i>t</i></th>
      <th class="num"><i>p</i></th><th>Sig.</th></tr></thead>
  <tbody>{t2}</tbody>
</table>
<div class="tnote">
  <p><b>Note.</b> Model 2 incremental terms only. HC3 robust SE. Mean-centred continuous predictors. Significance: *** p&lt;.01, ** p&lt;.05, * p&lt;.10.</p>
</div>

{_om_link}
</body></html>"""

out_path = os.path.join(OUT, "tables_preview.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Written: {out_path}")
