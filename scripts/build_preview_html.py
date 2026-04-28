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
    sec("Sustainability Attitude"),
    cont_row("Attitude Score","AttScore_c","AttScore"),
    sec("Sustainability Behavior"),
    cont_row("Behavior Score","BehScore_c","BehScore"),
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

# ─── Build interaction table mirroring LaTeX generator (cross-interactions
#     among the 8 main-effect-significant variables; show only rows with p<.10) ──
SIG_THRESHOLD = 0.10

# Each group: (label, ref_note, [(coef_term, row_label), ...])
INTERACTIONS = [
    ("Product Type &times; Nutrition Level", "ref: Basic &times; Low", [
        ("C(Product)[T.Lab]:C(NutriLvl)[T.Mid]",      "Lab &times; Mid"),
        ("C(Product)[T.Lab]:C(NutriLvl)[T.High]",     "Lab &times; High"),
        ("C(Product)[T.Premium]:C(NutriLvl)[T.Mid]",  "Premium &times; Mid"),
        ("C(Product)[T.Premium]:C(NutriLvl)[T.High]", "Premium &times; High"),
    ]),
    ("Product Type &times; Taste Level", "ref: Basic &times; Low", [
        ("C(Product)[T.Lab]:C(TasteLvl)[T.Mid]",      "Lab &times; Mid"),
        ("C(Product)[T.Lab]:C(TasteLvl)[T.High]",     "Lab &times; High"),
        ("C(Product)[T.Premium]:C(TasteLvl)[T.Mid]",  "Premium &times; Mid"),
        ("C(Product)[T.Premium]:C(TasteLvl)[T.High]", "Premium &times; High"),
    ]),
    ("Product Type &times; Health &amp; Safety Label", "ref: Basic &times; No", [
        ("C(Product)[T.Lab]:C(HealthLabel)[T.1]",     "Lab &times; Yes"),
        ("C(Product)[T.Premium]:C(HealthLabel)[T.1]", "Premium &times; Yes"),
    ]),
    ("Product Type &times; Attitude Score", "ref: Basic", [
        ("C(Product)[T.Lab]:AttScore_c",     "Lab &times; Attitude"),
        ("C(Product)[T.Premium]:AttScore_c", "Premium &times; Attitude"),
    ]),
    ("Product Type &times; Behavior Score", "ref: Basic", [
        ("C(Product)[T.Lab]:BehScore_c",     "Lab &times; Behavior"),
        ("C(Product)[T.Premium]:BehScore_c", "Premium &times; Behavior"),
    ]),
    ("Product Type &times; Price (USD)", "ref: Basic", [
        ("C(Product)[T.Lab]:PriceUSD_c",     "Lab &times; PriceUSD"),
        ("C(Product)[T.Premium]:PriceUSD_c", "Premium &times; PriceUSD"),
    ]),
    ("Product Type &times; Education", "ref: Basic", [
        ("C(Product)[T.Lab]:Education_num_c",     "Lab &times; Education"),
        ("C(Product)[T.Premium]:Education_num_c", "Premium &times; Education"),
    ]),
    ("Nutrition Level &times; Taste Level", "ref: Low &times; Low", [
        ("C(NutriLvl)[T.Mid]:C(TasteLvl)[T.Mid]",   "Mid &times; Mid"),
        ("C(NutriLvl)[T.High]:C(TasteLvl)[T.Mid]",  "High &times; Mid"),
        ("C(NutriLvl)[T.Mid]:C(TasteLvl)[T.High]",  "Mid &times; High"),
        ("C(NutriLvl)[T.High]:C(TasteLvl)[T.High]", "High &times; High"),
    ]),
    ("Nutrition Level &times; Health &amp; Safety Label", "ref: Low &times; No", [
        ("C(NutriLvl)[T.Mid]:C(HealthLabel)[T.1]",  "Mid &times; Yes"),
        ("C(NutriLvl)[T.High]:C(HealthLabel)[T.1]", "High &times; Yes"),
    ]),
    ("Nutrition Level &times; Attitude Score", "ref: Low", [
        ("C(NutriLvl)[T.Mid]:AttScore_c",  "Mid &times; Attitude"),
        ("C(NutriLvl)[T.High]:AttScore_c", "High &times; Attitude"),
    ]),
    ("Nutrition Level &times; Behavior Score", "ref: Low", [
        ("C(NutriLvl)[T.Mid]:BehScore_c",  "Mid &times; Behavior"),
        ("C(NutriLvl)[T.High]:BehScore_c", "High &times; Behavior"),
    ]),
    ("Nutrition Level &times; Price (USD)", "ref: Low", [
        ("C(NutriLvl)[T.Mid]:PriceUSD_c",  "Mid &times; PriceUSD"),
        ("C(NutriLvl)[T.High]:PriceUSD_c", "High &times; PriceUSD"),
    ]),
    ("Nutrition Level &times; Education", "ref: Low", [
        ("C(NutriLvl)[T.Mid]:Education_num_c",  "Mid &times; Education"),
        ("C(NutriLvl)[T.High]:Education_num_c", "High &times; Education"),
    ]),
    ("Taste Level &times; Health &amp; Safety Label", "ref: Low &times; No", [
        ("C(TasteLvl)[T.Mid]:C(HealthLabel)[T.1]",  "Mid &times; Yes"),
        ("C(TasteLvl)[T.High]:C(HealthLabel)[T.1]", "High &times; Yes"),
    ]),
    ("Taste Level &times; Attitude Score", "ref: Low", [
        ("C(TasteLvl)[T.Mid]:AttScore_c",  "Mid &times; Attitude"),
        ("C(TasteLvl)[T.High]:AttScore_c", "High &times; Attitude"),
    ]),
    ("Taste Level &times; Behavior Score", "ref: Low", [
        ("C(TasteLvl)[T.Mid]:BehScore_c",  "Mid &times; Behavior"),
        ("C(TasteLvl)[T.High]:BehScore_c", "High &times; Behavior"),
    ]),
    ("Taste Level &times; Price (USD)", "ref: Low", [
        ("C(TasteLvl)[T.Mid]:PriceUSD_c",  "Mid &times; PriceUSD"),
        ("C(TasteLvl)[T.High]:PriceUSD_c", "High &times; PriceUSD"),
    ]),
    ("Taste Level &times; Education", "ref: Low", [
        ("C(TasteLvl)[T.Mid]:Education_num_c",  "Mid &times; Education"),
        ("C(TasteLvl)[T.High]:Education_num_c", "High &times; Education"),
    ]),
    ("Health &amp; Safety Label &times; Attitude Score", "ref: No", [
        ("C(HealthLabel)[T.1]:AttScore_c", "Yes &times; Attitude"),
    ]),
    ("Health &amp; Safety Label &times; Behavior Score", "ref: No", [
        ("C(HealthLabel)[T.1]:BehScore_c", "Yes &times; Behavior"),
    ]),
    ("Health &amp; Safety Label &times; Price (USD)", "ref: No", [
        ("C(HealthLabel)[T.1]:PriceUSD_c", "Yes &times; PriceUSD"),
    ]),
    ("Health &amp; Safety Label &times; Education", "ref: No", [
        ("C(HealthLabel)[T.1]:Education_num_c", "Yes &times; Education"),
    ]),
    ("Attitude Score &times; Behavior Score", "", [
        ("AttScore_c:BehScore_c", "Attitude &times; Behavior"),
    ]),
    ("Attitude Score &times; Price (USD)", "", [
        ("AttScore_c:PriceUSD_c", "Attitude &times; PriceUSD"),
    ]),
    ("Attitude Score &times; Education", "", [
        ("AttScore_c:Education_num_c", "Attitude &times; Education"),
    ]),
    ("Behavior Score &times; Price (USD)", "", [
        ("BehScore_c:PriceUSD_c", "Behavior &times; PriceUSD"),
    ]),
    ("Behavior Score &times; Education", "", [
        ("BehScore_c:Education_num_c", "Behavior &times; Education"),
    ]),
    ("Price (USD) &times; Education", "", [
        ("PriceUSD_c:Education_num_c", "PriceUSD &times; Education"),
    ]),
]

t2_rows = []
n_total = 0; n_sig = 0; n_groups_total = 0
for grp_label, ref_note, terms in INTERACTIONS:
    n_groups_total += 1
    all_rows = []
    for cterm, rlabel in terms:
        n_total += 1
        if cterm not in c2.index:
            continue
        r = c2.loc[cterm]
        p = float(r["p"])
        if np.isnan(p):
            continue
        all_rows.append((rlabel, r))
        if p < SIG_THRESHOLD:
            n_sig += 1
    if not all_rows:
        continue
    if ref_note:
        t2_rows.append(
            f'<tr class="factor-hdr"><td class="indent"><b>{grp_label}</b>'
            f'&nbsp;<span style="font-weight:normal;font-size:11px;">({ref_note})</span></td>'
            f'<td></td><td></td><td></td><td></td></tr>'
        )
    else:
        t2_rows.append(
            f'<tr class="factor-hdr"><td class="indent"><b>{grp_label}</b></td>'
            f'<td></td><td></td><td></td><td></td></tr>'
        )
    for rlabel, r in all_rows:
        p = float(r["p"])
        t2_rows.append(
            f'<tr><td class="indent2">{rlabel}</td>'
            f'<td class="num">{fb(float(r["coef"]),float(r["std_err"]))}</td>'
            f'<td class="num">{ft(float(r["t"]))}</td>'
            f'<td class="num">{fp(p)}</td>'
            f'<td class="sig">{sig(p)}</td></tr>'
        )

if not t2_rows:
    t2_rows = ['<tr><td colspan="5" style="text-align:center;color:#888;font-style:italic;">No estimable interactions.</td></tr>']

# Footer rows
t2_rows.append(
    f'<tr class="footer"><td colspan="5">'
    f'&Delta;<i>R</i><sup>2</sup>&nbsp;=&nbsp;{dr2:.3f},&nbsp;&nbsp;'
    f'<i>F</i>-change({dk},&nbsp;{dfe})&nbsp;=&nbsp;{fchg:.2f},&nbsp;&nbsp;'
    f'<i>p</i>&nbsp;{pchg_str}</td></tr>'
)
t2_rows.append(
    f'<tr class="model-footer"><td colspan="5">'
    f'Model&nbsp;2: <i>R</i><sup>2</sup>&nbsp;=&nbsp;{r2_2:.3f},'
    f'&nbsp;&nbsp;Adj.&nbsp;<i>R</i><sup>2</sup>&nbsp;=&nbsp;{ar2_2:.3f}'
    f'&nbsp;&nbsp;|&nbsp;&nbsp;Full pairwise cross-comparison: all {n_groups_total} groups, {n_sig} of {n_total} cells significant</td></tr>'
)
t2 = "\n".join(t2_rows)

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
