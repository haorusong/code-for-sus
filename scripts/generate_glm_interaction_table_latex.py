"""
Generate LaTeX table for GLM interaction effects (Model 2 incremental terms).

Reads:
  out/GLM_WTP__GLM_Model2_Coefs.csv
  out/GLM_WTP__GLM_Model2_Summary.csv
Writes:
  out/GLM_interaction_effects_table.tex
"""

import os
import pandas as pd
import numpy as np

OUT_DIR  = "out"
COEF_CSV = os.path.join(OUT_DIR, "GLM_WTP__GLM_Model2_Coefs.csv")
SUM_CSV  = os.path.join(OUT_DIR, "GLM_WTP__GLM_Model2_Summary.csv")
TEX_OUT  = os.path.join(OUT_DIR, "GLM_interaction_effects_table.tex")

# Interaction groups: (group_label, ref_note, [(coef_term, row_label), ...])
INTERACTIONS = [
    (
        "Sustainability $\\times$ Product Type", "ref: Basic",
        [
            ("SustainScore_c:C(Product)[T.Lab]",     "$\\times$ Lab-grown"),
            ("SustainScore_c:C(Product)[T.Premium]", "$\\times$ Premium"),
        ]
    ),
    (
        "Sustainability $\\times$ Price Level", "ref: Low",
        [
            ("SustainScore_c:C(PriceLvl)[T.Mid]",  "$\\times$ Mid"),
            ("SustainScore_c:C(PriceLvl)[T.High]", "$\\times$ High"),
        ]
    ),
    (
        "Sustainability $\\times$ Nutrition Level", "ref: Low",
        [
            ("SustainScore_c:C(NutriLvl)[T.Mid]",  "$\\times$ Mid"),
            ("SustainScore_c:C(NutriLvl)[T.High]", "$\\times$ High"),
        ]
    ),
    (
        "Lab Price Gap $\\times$ Product Type", "ref: Basic",
        [
            ("LabPriceGap_c:C(Product)[T.Lab]",     "$\\times$ Lab-grown"),
            ("LabPriceGap_c:C(Product)[T.Premium]", "$\\times$ Premium"),
        ]
    ),
    (
        "Price USD $\\times$ Product Type", "ref: Basic",
        [
            ("PriceUSD_c:C(Product)[T.Lab]",     "$\\times$ Lab-grown"),
            ("PriceUSD_c:C(Product)[T.Premium]", "$\\times$ Premium"),
        ]
    ),
    (
        "Price Level $\\times$ Nutrition Level", "ref: Low $\\times$ Low",
        [
            ("C(PriceLvl)[T.Mid]:C(NutriLvl)[T.Mid]",   "Mid $\\times$ Mid"),
            ("C(PriceLvl)[T.High]:C(NutriLvl)[T.Mid]",  "High $\\times$ Mid"),
            ("C(PriceLvl)[T.Mid]:C(NutriLvl)[T.High]",  "Mid $\\times$ High"),
            ("C(PriceLvl)[T.High]:C(NutriLvl)[T.High]", "High $\\times$ High"),
        ]
    ),
]

# ── Helpers ────────────────────────────────────────────────────────────────────
def sig_stars(p):
    if pd.isna(p): return ""
    if p < 0.01:   return "***"
    if p < 0.05:   return "**"
    if p < 0.10:   return "*"
    return ""

def fmt_p(p):
    if pd.isna(p): return "---"
    if p < 0.001:  return r"$<$.001"
    return f"{p:.3f}"

def fmt_beta_se(b, se):
    if pd.isna(b) or pd.isna(se): return "---"
    return rf"{b:.3f} ({se:.3f})"

def fmt_t(t):
    if pd.isna(t): return "---"
    return f"{t:.3f}"

def fmt_delta_r2(dr2):
    return f"{dr2:.3f}"

def fmt_f(f):
    if pd.isna(f): return "---"
    return f"{f:.2f}"

def group_header(label, ref):
    return (
        rf"\quad \textbf{{{label}}} ({ref}) & & & & \\"
    )

def level_row(label, b, se, t, p):
    return (
        rf"\qquad {label} "
        rf"& {fmt_beta_se(b, se)} & {fmt_t(t)} & {fmt_p(p)} & {sig_stars(p)} \\"
    )

def section_row(label):
    return rf"\multicolumn{{5}}{{l}}{{\textit{{{label}}}}} \\"


def main():
    for path in [COEF_CSV, SUM_CSV]:
        if not os.path.exists(path):
            print(f"[interaction table] {path} not found — run the pipeline first.")
            return

    coefs = pd.read_csv(COEF_CSV)
    ci    = coefs.set_index("term")

    summ  = pd.read_csv(SUM_CSV).set_index("Metric")["Value"]
    r2     = float(summ.get("R2",      0))
    adj_r2 = float(summ.get("Adj_R2",  0))
    dr2    = float(summ.get("DeltaR2", 0))
    f_chg  = float(summ.get("F_change",np.nan))
    p_chg  = float(summ.get("p_change",np.nan))
    dk     = int(float(summ.get("dk",     0)))
    df_err = int(float(summ.get("df_error",0)))
    n      = int(float(summ.get("N",       0)))

    # Format footer — no surrounding $ here; outer math mode added in f-string
    p_chg_str = r"< .001" if p_chg < 0.001 else f"{p_chg:.3f}"

    rows = []
    for grp_label, ref_note, terms in INTERACTIONS:
        rows.append(group_header(grp_label, ref_note))
        for coef_term, row_label in terms:
            if coef_term not in ci.index:
                continue
            r = ci.loc[coef_term]
            rows.append(level_row(row_label, r["coef"], r["std_err"], r["t"], r["p"]))

    footer_line = (
        rf"$\Delta R^2 = {fmt_delta_r2(dr2)}$,\quad "
        rf"$F$\text{{-change}}$({dk},\ {df_err}) = {fmt_f(f_chg)}$,\quad "
        rf"$p {p_chg_str}$"
    )

    tex = "\n".join([
        r"\begin{table}[ht]",
        r"\centering",
        rf"\caption{{GLM Interaction Effects — Model 2 Incremental ($N={n}$)}}",
        r"\label{tab:glm_interactions}",
        r"\begin{threeparttable}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"Predictor & $\beta\ (SE)$ & $t$ & $p$ & Sig. \\",
        r"\midrule",
        "\n".join(rows),
        r"\midrule",
        rf"\multicolumn{{5}}{{l}}{{{footer_line}}} \\",
        rf"\multicolumn{{5}}{{l}}{{Model 2: $R^2 = {r2:.3f}$,\quad Adj.\ $R^2 = {adj_r2:.3f}$}} \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\begin{tablenotes}\footnotesize",
        r"\item Interaction terms only (Model 2 incremental over Model 1)."
        r" $\beta$/SE/$t$/$p$ from OLS with HC3 robust SE."
        r" All continuous predictors mean-centred (Jaccard \& Turrisi, 2003).",
        rf"$N={n}$ observations (268 participants $\times$ 3 products).",
        r"Significance: *** $p<.01$, ** $p<.05$, * $p<.10$.",
        r"\end{tablenotes}",
        r"\end{threeparttable}",
        r"\end{table}",
    ])

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(TEX_OUT, "w", encoding="utf-8") as fh:
        fh.write(tex)
    print(f"[interaction table] Written → {TEX_OUT}")


if __name__ == "__main__":
    main()
