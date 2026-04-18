"""
Generate combined GLM main-effects LaTeX table.

Column structure (6 cols):  Predictor | β (SE) | t | p | Mean (SD) | Sig.
  • Factor header rows reuse: Predictor | blank | df | F | p_omnibus | stars
  • Level rows keep original: Predictor | β(SE) | t | p | Mean(SD) | stars
  • Continuous rows:          Predictor | β(SE) | t | p | Mean(SD) | stars

Reads:
  out/GLM_WTP__GLM_Model1_Coefs.csv
  out/GLM_WTP__GLM_AnovaType3.csv
  out/GLM_WTP__GLM_Model1_Summary.csv
  out/GLM_WTP__LongData.csv
Writes:
  out/GLM_main_effects_table.tex
"""

import os
import pandas as pd
import numpy as np

OUT_DIR   = "out"
COEF_CSV  = os.path.join(OUT_DIR, "GLM_WTP__GLM_Model1_Coefs.csv")
ANOVA_CSV = os.path.join(OUT_DIR, "GLM_WTP__GLM_AnovaType3.csv")
SUM_CSV   = os.path.join(OUT_DIR, "GLM_WTP__GLM_Model1_Summary.csv")
LONG_CSV  = os.path.join(OUT_DIR, "GLM_WTP__LongData.csv")
TEX_OUT   = os.path.join(OUT_DIR, "GLM_main_effects_table.tex")

# Factor definitions: (patsy_anova_term, label, ref_label, ordered_levels_with_labels)
FACTORS = [
    ("C(Product)",  "Product Type",   "Basic",
     [("Lab",     "Lab-grown"),
      ("Premium", "Premium")]),
    ("C(PriceLvl)", "Price Level",    "Low",
     [("Mid",  "Mid"),
      ("High", "High")]),
    ("C(NutriLvl)", "Nutrition Level","Low",
     [("Mid",  "Mid"),
      ("High", "High")]),
    ("C(TasteLvl)", "Taste Level",    "Low",
     [("Mid",  "Mid"),
      ("High", "High")]),
]

# Continuous predictors (parametric)
CONTINUOUS = [
    ("SustainScore_c",      "SustainScore",      "Sustainability Orientation"),
    ("PriceUSD_c",          "PriceUSD",          "Price (USD)"),
    ("LabPriceGap_c",       "LabPriceGap",       "Lab Price Gap"),
    ("Age_num_c",           "Age_num",           "Age"),
    ("Education_num_c",     "Education_num",     "Education"),
    ("HouseholdSize_num_c", "HouseholdSize_num", "Household Size"),
    ("Income_num_c",        "Income_num",        "Income"),
]

# Categorical demographics: omnibus header only, no level breakdown
CAT_DEMOS = [
    ("C(Gender)",      "Gender"),
    ("C(Marital)",     "Marital Status"),
    ("C(Employment)",  "Employment Status"),
    ("C(Urban_Rural)", "Residential Area"),
]

SECTION_GROUPS = [
    ("Product Attributes",   [f[0] for f in FACTORS]),
    ("Psychographic",        ["SustainScore_c"]),
    ("Price Variables",      ["PriceUSD_c", "LabPriceGap_c"]),
    ("Demographics",         ["Age_num_c", "Education_num_c",
                               "HouseholdSize_num_c", "Income_num_c",
                               "C(Gender)", "C(Marital)",
                               "C(Employment)", "C(Urban_Rural)"]),
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

def fmt_f(f):
    if pd.isna(f): return "---"
    return f"{f:.2f}"

def fmt_df(d):
    if pd.isna(d): return "---"
    return str(int(round(d)))

def fmt_beta_se(b, se):
    if pd.isna(b) or pd.isna(se): return "---"
    sign = "" if b >= 0 else "\N{MINUS SIGN}"
    return rf"{b:.3f} ({se:.3f})"

def fmt_t(t):
    if pd.isna(t): return "---"
    return f"{t:.3f}"

def fmt_mean_sd(m, s):
    if pd.isna(m): return "---"
    if pd.isna(s): return f"{m:.3f}"
    return f"{m:.3f} ({s:.3f})"

def is_artifact(term):
    return "?" in str(term)

def section_row(label):
    return rf"\multicolumn{{8}}{{l}}{{\textit{{{label}}}}} \\"

# ── Row builders ───────────────────────────────────────────────────────────────
def factor_header(label, ref, df_, f_, p_, m=np.nan, s=np.nan):
    """Header row: df + F filled; β/t blank; Mean(SD) shows ref category descriptive."""
    mean_sd = fmt_mean_sd(m, s) if not pd.isna(m) else ""
    return (
        rf"\quad \textbf{{{label}}} (ref: {ref}) "
        rf"& {fmt_df(df_)} & {fmt_f(f_)} & & & {fmt_p(p_)} & {mean_sd} & {sig_stars(p_)} \\"
    )

def level_row(label, b, se, t, p, m, s):
    """Level row: df + F blank; rest filled."""
    return (
        rf"\qquad {label} "
        rf"& & & {fmt_beta_se(b, se)} & {fmt_t(t)} & {fmt_p(p)} "
        rf"& {fmt_mean_sd(m, s)} & {sig_stars(p)} \\"
    )

def cont_row(label, b, se, t, p, m, s):
    """Continuous row: df + F blank; rest filled."""
    return (
        rf"\quad {label} "
        rf"& & & {fmt_beta_se(b, se)} & {fmt_t(t)} & {fmt_p(p)} "
        rf"& {fmt_mean_sd(m, s)} & {sig_stars(p)} \\"
    )

def cat_demo_header(label, df_, f_, p_):
    """Categorical demographic: df + F filled; rest blank."""
    return (
        rf"\quad {label} "
        rf"& {fmt_df(df_)} & {fmt_f(f_)} & & & {fmt_p(p_)} & & {sig_stars(p_)} \\"
    )

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    for path in [COEF_CSV, ANOVA_CSV, SUM_CSV, LONG_CSV]:
        if not os.path.exists(path):
            print(f"[GLM table] {path} not found — run the pipeline first.")
            return

    coefs  = pd.read_csv(COEF_CSV)
    coefs  = coefs[~coefs["term"].apply(is_artifact)].copy()
    ci     = coefs.set_index("term")

    anov   = pd.read_csv(ANOVA_CSV)
    ai     = {str(r["term"]).strip(): r for _, r in anov.iterrows()}

    summ   = pd.read_csv(SUM_CSV).set_index("Metric")["Value"]
    r2     = float(summ.get("R2",     0))
    adj_r2 = float(summ.get("Adj_R2", 0))
    n      = int(float(summ.get("N", 0)))

    long   = pd.read_csv(LONG_CSV)

    # Pre-compute descriptive Mean(SD) for categorical levels
    def level_stats(col, val):
        sub = long[long[col] == val]["WTP"]
        return sub.mean(), sub.std()

    def cont_stats(col):
        sub = long[col].dropna()
        return sub.mean(), sub.std()

    # ── Build rows ──
    lines = []

    # map factor anova_term → (factor_obj, section)
    factor_map  = {f[0]: f for f in FACTORS}
    cont_map    = {c[0]: c for c in CONTINUOUS}
    cat_demo_map= {d[0]: d for d in CAT_DEMOS}

    for sec_label, terms in SECTION_GROUPS:
        lines.append(section_row(sec_label))

        for term in terms:
            if term in factor_map:
                anov_term, fac_label, ref_label, levels = factor_map[term]
                ar = ai.get(anov_term, {})
                col_name = "Product" if "Product" in anov_term else \
                           "PriceLvl" if "PriceLvl" in anov_term else \
                           "NutriLvl" if "NutriLvl" in anov_term else "TasteLvl"
                ref_m, ref_s = level_stats(col_name, ref_label)
                lines.append(factor_header(
                    fac_label, ref_label,
                    ar.get("df", np.nan), ar.get("F", np.nan), ar.get("p", np.nan),
                    ref_m, ref_s
                ))
                for level_code, level_label in levels:
                    coef_term = f"{anov_term}[T.{level_code}]"
                    if coef_term not in ci.index:
                        continue
                    row = ci.loc[coef_term]
                    m, s = level_stats(col_name, level_code)
                    lines.append(level_row(
                        level_label,
                        row["coef"], row["std_err"], row["t"], row["p"], m, s
                    ))

            elif term in cont_map:
                coef_term, raw_col, label = cont_map[term]
                if coef_term not in ci.index:
                    continue
                row = ci.loc[coef_term]
                if raw_col in long.columns:
                    m, s = cont_stats(raw_col)
                else:
                    m, s = np.nan, np.nan
                lines.append(cont_row(label, row["coef"], row["std_err"], row["t"], row["p"], m, s))

            elif term in cat_demo_map:
                anov_term, dem_label = cat_demo_map[term]
                ar = ai.get(anov_term, {})
                lines.append(cat_demo_header(
                    dem_label,
                    ar.get("df", np.nan), ar.get("F", np.nan), ar.get("p", np.nan)
                ))

    # ── Assemble LaTeX ──
    col_header = (
        r"Predictor & $df$ & $F$ & $\beta\ (SE)$ & $t$ & $p$ "
        r"& Mean\ $(SD)$ & Sig. \\"
    )
    # Sub-header to clarify dual use
    sub_header = (
        r"\multicolumn{3}{l}{\scriptsize\textit{← omnibus (Type III)}} & "
        r"\multicolumn{4}{l}{\scriptsize\textit{pairwise contrast (HC3) →}} & \\"
    )

    tex = "\n".join([
        r"\begin{table}[ht]",
        r"\centering",
        rf"\caption{{GLM Main Effects — Model 1 ($N={n}$)}}",
        r"\label{tab:glm_main}",
        r"\begin{threeparttable}",
        r"\begin{tabular}{lccccccl}",
        r"\toprule",
        col_header,
        sub_header,
        r"\midrule",
        "\n".join(lines),
        r"\midrule",
        rf"\multicolumn{{8}}{{l}}{{$R^2 = {r2:.3f}$,\quad Adj.\ $R^2 = {adj_r2:.3f}$}} \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\begin{tablenotes}\footnotesize",
        r"\item \textbf{Bold} factor header rows report the omnibus Type~III $F$-test"
        r" ($df$, $F$, $p$); $\beta$/SE/$t$/$p$/Mean~$(SD)$ left blank.",
        r"\item Indented level rows report the pairwise contrast vs.\ reference"
        r" ($\beta$, SE, $t$, $p$ from HC3 robust OLS; Mean~$(SD)$ = descriptive WTP for that level).",
        r"\item All continuous predictors mean-centred (Jaccard \& Turrisi, 2003).",
        rf"$N={n}$ observations (268 participants $\times$ 3 products).",
        r"Significance: *** $p<.01$, ** $p<.05$, * $p<.10$.",
        r"\end{tablenotes}",
        r"\end{threeparttable}",
        r"\end{table}",
    ])

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(TEX_OUT, "w", encoding="utf-8") as fh:
        fh.write(tex)
    print(f"[GLM table] Written → {TEX_OUT}")


if __name__ == "__main__":
    main()
