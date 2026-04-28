"""
Generate LaTeX table for GLM interaction effects (Model 2 incremental terms).

Filters: only rows with p < .10 are shown (any star).
Groups with no significant rows are skipped entirely.

Reads:
  out/GLM_WTP__GLM_Model2_Coefs.csv
  out/GLM_WTP__GLM_Model2_Summary.csv
Writes:
  out/GLM_interaction_effects_table.tex
"""

import os
import pandas as pd
import numpy as np

OUT_DIR       = "out"
COEF_CSV      = os.path.join(OUT_DIR, "GLM_WTP__GLM_Model2_Coefs.csv")
SUM_CSV       = os.path.join(OUT_DIR, "GLM_WTP__GLM_Model2_Summary.csv")
TEX_OUT_SIG   = os.path.join(OUT_DIR, "GLM_interaction_effects_table.tex")          # paper body — only sig rows
TEX_OUT_FULL  = os.path.join(OUT_DIR, "GLM_interaction_effects_full_table.tex")     # appendix — full pairwise

SIG_THRESHOLD = 0.10  # rows with p >= this are filtered out

# Interaction groups: pairwise interactions among the 8 vars significant as
# main effects (Product, Nutri, Taste, HealthLabel, Att, Beh, PriceUSD, Edu).
# Groups with no row reaching p<.10 are skipped.
INTERACTIONS = [
    # ── Product × X ────────────────────────────────────────────────────────────
    (
        "Product Type $\\times$ Nutrition Level", "ref: Basic $\\times$ Low",
        [
            ("C(Product)[T.Lab]:C(NutriLvl)[T.Mid]",      "Lab $\\times$ Mid"),
            ("C(Product)[T.Lab]:C(NutriLvl)[T.High]",     "Lab $\\times$ High"),
            ("C(Product)[T.Premium]:C(NutriLvl)[T.Mid]",  "Premium $\\times$ Mid"),
            ("C(Product)[T.Premium]:C(NutriLvl)[T.High]", "Premium $\\times$ High"),
        ]
    ),
    (
        "Product Type $\\times$ Taste Level", "ref: Basic $\\times$ Low",
        [
            ("C(Product)[T.Lab]:C(TasteLvl)[T.Mid]",      "Lab $\\times$ Mid"),
            ("C(Product)[T.Lab]:C(TasteLvl)[T.High]",     "Lab $\\times$ High"),
            ("C(Product)[T.Premium]:C(TasteLvl)[T.Mid]",  "Premium $\\times$ Mid"),
            ("C(Product)[T.Premium]:C(TasteLvl)[T.High]", "Premium $\\times$ High"),
        ]
    ),
    (
        "Product Type $\\times$ Health \\& Safety Label", "ref: Basic $\\times$ No",
        [
            ("C(Product)[T.Lab]:C(HealthLabel)[T.1]",     "Lab $\\times$ Yes"),
            ("C(Product)[T.Premium]:C(HealthLabel)[T.1]", "Premium $\\times$ Yes"),
        ]
    ),
    (
        "Product Type $\\times$ Attitude Score", "ref: Basic",
        [
            ("C(Product)[T.Lab]:AttScore_c",     "Lab $\\times$ Attitude"),
            ("C(Product)[T.Premium]:AttScore_c", "Premium $\\times$ Attitude"),
        ]
    ),
    (
        "Product Type $\\times$ Behavior Score", "ref: Basic",
        [
            ("C(Product)[T.Lab]:BehScore_c",     "Lab $\\times$ Behavior"),
            ("C(Product)[T.Premium]:BehScore_c", "Premium $\\times$ Behavior"),
        ]
    ),
    (
        "Product Type $\\times$ Price (USD)", "ref: Basic",
        [
            ("C(Product)[T.Lab]:PriceUSD_c",     "Lab $\\times$ PriceUSD"),
            ("C(Product)[T.Premium]:PriceUSD_c", "Premium $\\times$ PriceUSD"),
        ]
    ),
    (
        "Product Type $\\times$ Education", "ref: Basic",
        [
            ("C(Product)[T.Lab]:Education_num_c",     "Lab $\\times$ Education"),
            ("C(Product)[T.Premium]:Education_num_c", "Premium $\\times$ Education"),
        ]
    ),
    # ── Nutrition × X ──────────────────────────────────────────────────────────
    (
        "Nutrition Level $\\times$ Taste Level", "ref: Low $\\times$ Low",
        [
            ("C(NutriLvl)[T.Mid]:C(TasteLvl)[T.Mid]",   "Mid $\\times$ Mid"),
            ("C(NutriLvl)[T.High]:C(TasteLvl)[T.Mid]",  "High $\\times$ Mid"),
            ("C(NutriLvl)[T.Mid]:C(TasteLvl)[T.High]",  "Mid $\\times$ High"),
            ("C(NutriLvl)[T.High]:C(TasteLvl)[T.High]", "High $\\times$ High"),
        ]
    ),
    (
        "Nutrition Level $\\times$ Health \\& Safety Label", "ref: Low $\\times$ No",
        [
            ("C(NutriLvl)[T.Mid]:C(HealthLabel)[T.1]",  "Mid $\\times$ Yes"),
            ("C(NutriLvl)[T.High]:C(HealthLabel)[T.1]", "High $\\times$ Yes"),
        ]
    ),
    (
        "Nutrition Level $\\times$ Attitude Score", "ref: Low",
        [
            ("C(NutriLvl)[T.Mid]:AttScore_c",  "Mid $\\times$ Attitude"),
            ("C(NutriLvl)[T.High]:AttScore_c", "High $\\times$ Attitude"),
        ]
    ),
    (
        "Nutrition Level $\\times$ Behavior Score", "ref: Low",
        [
            ("C(NutriLvl)[T.Mid]:BehScore_c",  "Mid $\\times$ Behavior"),
            ("C(NutriLvl)[T.High]:BehScore_c", "High $\\times$ Behavior"),
        ]
    ),
    (
        "Nutrition Level $\\times$ Price (USD)", "ref: Low",
        [
            ("C(NutriLvl)[T.Mid]:PriceUSD_c",  "Mid $\\times$ PriceUSD"),
            ("C(NutriLvl)[T.High]:PriceUSD_c", "High $\\times$ PriceUSD"),
        ]
    ),
    (
        "Nutrition Level $\\times$ Education", "ref: Low",
        [
            ("C(NutriLvl)[T.Mid]:Education_num_c",  "Mid $\\times$ Education"),
            ("C(NutriLvl)[T.High]:Education_num_c", "High $\\times$ Education"),
        ]
    ),
    # ── Taste × X ──────────────────────────────────────────────────────────────
    (
        "Taste Level $\\times$ Health \\& Safety Label", "ref: Low $\\times$ No",
        [
            ("C(TasteLvl)[T.Mid]:C(HealthLabel)[T.1]",  "Mid $\\times$ Yes"),
            ("C(TasteLvl)[T.High]:C(HealthLabel)[T.1]", "High $\\times$ Yes"),
        ]
    ),
    (
        "Taste Level $\\times$ Attitude Score", "ref: Low",
        [
            ("C(TasteLvl)[T.Mid]:AttScore_c",  "Mid $\\times$ Attitude"),
            ("C(TasteLvl)[T.High]:AttScore_c", "High $\\times$ Attitude"),
        ]
    ),
    (
        "Taste Level $\\times$ Behavior Score", "ref: Low",
        [
            ("C(TasteLvl)[T.Mid]:BehScore_c",  "Mid $\\times$ Behavior"),
            ("C(TasteLvl)[T.High]:BehScore_c", "High $\\times$ Behavior"),
        ]
    ),
    (
        "Taste Level $\\times$ Price (USD)", "ref: Low",
        [
            ("C(TasteLvl)[T.Mid]:PriceUSD_c",  "Mid $\\times$ PriceUSD"),
            ("C(TasteLvl)[T.High]:PriceUSD_c", "High $\\times$ PriceUSD"),
        ]
    ),
    (
        "Taste Level $\\times$ Education", "ref: Low",
        [
            ("C(TasteLvl)[T.Mid]:Education_num_c",  "Mid $\\times$ Education"),
            ("C(TasteLvl)[T.High]:Education_num_c", "High $\\times$ Education"),
        ]
    ),
    # ── HealthLabel × continuous ───────────────────────────────────────────────
    (
        "Health \\& Safety Label $\\times$ Attitude Score", "ref: No",
        [
            ("C(HealthLabel)[T.1]:AttScore_c", "Yes $\\times$ Attitude"),
        ]
    ),
    (
        "Health \\& Safety Label $\\times$ Behavior Score", "ref: No",
        [
            ("C(HealthLabel)[T.1]:BehScore_c", "Yes $\\times$ Behavior"),
        ]
    ),
    (
        "Health \\& Safety Label $\\times$ Price (USD)", "ref: No",
        [
            ("C(HealthLabel)[T.1]:PriceUSD_c", "Yes $\\times$ PriceUSD"),
        ]
    ),
    (
        "Health \\& Safety Label $\\times$ Education", "ref: No",
        [
            ("C(HealthLabel)[T.1]:Education_num_c", "Yes $\\times$ Education"),
        ]
    ),
    # ── Continuous × continuous ────────────────────────────────────────────────
    (
        "Attitude Score $\\times$ Behavior Score", "",
        [("AttScore_c:BehScore_c", "Attitude $\\times$ Behavior")]
    ),
    (
        "Attitude Score $\\times$ Price (USD)", "",
        [("AttScore_c:PriceUSD_c", "Attitude $\\times$ PriceUSD")]
    ),
    (
        "Attitude Score $\\times$ Education", "",
        [("AttScore_c:Education_num_c", "Attitude $\\times$ Education")]
    ),
    (
        "Behavior Score $\\times$ Price (USD)", "",
        [("BehScore_c:PriceUSD_c", "Behavior $\\times$ PriceUSD")]
    ),
    (
        "Behavior Score $\\times$ Education", "",
        [("BehScore_c:Education_num_c", "Behavior $\\times$ Education")]
    ),
    (
        "Price (USD) $\\times$ Education", "",
        [("PriceUSD_c:Education_num_c", "PriceUSD $\\times$ Education")]
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
    return rf"\quad \textbf{{{label}}} ({ref}) & & & & \\"

def level_row(label, b, se, t, p):
    return (
        rf"\qquad {label} "
        rf"& {fmt_beta_se(b, se)} & {fmt_t(t)} & {fmt_p(p)} & {sig_stars(p)} \\"
    )


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

    p_chg_str = r"< .001" if p_chg < 0.001 else f"{p_chg:.3f}"

    # Walk the spec once, collect every estimable cell with its p
    full_rows_by_group = []   # list of (label, ref_note, [(label, β, SE, t, p), ...])
    n_total_attempted  = 0
    n_groups_total     = 0
    n_sig_rows         = 0

    for grp_label, ref_note, terms in INTERACTIONS:
        n_groups_total += 1
        all_rows = []
        for coef_term, row_label in terms:
            n_total_attempted += 1
            if coef_term not in ci.index:
                continue
            r = ci.loc[coef_term]
            p = float(r["p"])
            if pd.isna(p):
                continue
            all_rows.append((row_label, r["coef"], r["std_err"], r["t"], p))
            if p < SIG_THRESHOLD:
                n_sig_rows += 1
        if all_rows:
            full_rows_by_group.append((grp_label, ref_note, all_rows))

    footer_line = (
        rf"$\Delta R^2 = {fmt_delta_r2(dr2)}$,\quad "
        rf"$F$\text{{-change}}$({dk},\ {df_err}) = {fmt_f(f_chg)}$,\quad "
        rf"$p {p_chg_str}$"
    )

    def render(filtered, *, label, caption, foot_extra):
        """Build a complete LaTeX table from the row spec.
        filtered=True  → keep only groups with at least one p<.10 row, and
                          show only those sig rows within the kept groups.
        filtered=False → show every group + every estimable row.
        """
        body = []
        n_kept_groups = 0
        n_kept_rows   = 0
        for grp_label, ref_note, rs in full_rows_by_group:
            if filtered:
                rs = [r for r in rs if r[4] < SIG_THRESHOLD]
                if not rs:
                    continue
            n_kept_groups += 1
            body.append(group_header(grp_label, ref_note))
            for row_label, b, se, t, p in rs:
                body.append(level_row(row_label, b, se, t, p))
                n_kept_rows += 1
        empty_msg = (
            r"\multicolumn{5}{l}{\textit{No interaction terms reached $p<.10$.}} \\"
            if filtered
            else r"\multicolumn{5}{l}{\textit{No interaction terms estimable.}} \\"
        )
        # ── longtable form: breaks across pages naturally; renders right where placed ──
        # NOTE: requires \usepackage{longtable} in the preamble.
        return "\n".join([
            r"\begin{center}",
            r"\begin{longtable}{lcccc}",
            rf"\caption{{{caption}}}\label{{{label}}} \\",
            r"\toprule",
            r"Predictor & $\beta\ (SE)$ & $t$ & $p$ & Sig. \\",
            r"\midrule",
            r"\endfirsthead",
            rf"\multicolumn{{5}}{{l}}{{\textit{{Table~\ref{{{label}}} continued from previous page.}}}} \\",
            r"\toprule",
            r"Predictor & $\beta\ (SE)$ & $t$ & $p$ & Sig. \\",
            r"\midrule",
            r"\endhead",
            r"\midrule",
            r"\multicolumn{5}{r}{\textit{Continued on next page\ldots}} \\",
            r"\endfoot",
            rf"\multicolumn{{5}}{{l}}{{{footer_line}}} \\",
            rf"\multicolumn{{5}}{{l}}{{Model 2: $R^2 = {r2:.3f}$,\quad Adj.\ $R^2 = {adj_r2:.3f}$}} \\",
            r"\bottomrule",
            rf"\multicolumn{{5}}{{p{{0.95\linewidth}}}}{{\footnotesize \textit{{Note.}} {foot_extra} "
            r"$\beta$/SE/$t$/$p$ from OLS with HC3 robust SE. "
            r"All continuous predictors mean-centred (Jaccard \& Turrisi, 2003). "
            rf"$N={n}$ observations ({n//3} participants $\times$ 3 products). "
            r"Significance: *** $p<.01$, ** $p<.05$, * $p<.10$.}} \\",
            r"\endlastfoot",
            "\n".join(body) if body else empty_msg,
            r"\end{longtable}",
            r"\end{center}",
        ]), n_kept_groups, n_kept_rows

    os.makedirs(OUT_DIR, exist_ok=True)

    sig_caption = (
        rf"GLM Interaction Effects --- Model 2 Incremental, Significant Terms Only ($N={n}$). "
        rf"Pairwise cross-interactions among the eight main-effect-significant variables; "
        rf"only rows reaching $p<.10$ are shown."
    )
    sig_foot = (
        rf"This table reports the {n_sig_rows} of {n_total_attempted} estimated pairwise interaction coefficients "
        rf"that reached $p<.10$, organized into the {{n_sig_grp}} retained interaction groups. "
        rf"The complete pairwise cross-comparison "
        rf"(all $\binom{{8}}{{2}} = {n_groups_total}$ groups, all {n_total_attempted} cells) "
        rf"appears in Appendix~\ref{{tab:glm_interactions_full}}."
    )
    sig_tex, n_sig_grp, _ = render(
        filtered=True, label="tab:glm_interactions",
        caption=sig_caption,
        foot_extra=sig_foot.replace("{n_sig_grp}", str(n_sig_grp := 0) or "X"),
    )
    # Re-render now that we know n_sig_grp (count groups with >=1 sig row)
    n_sig_grp = sum(1 for (_, _, rs) in full_rows_by_group
                    if any(r[4] < SIG_THRESHOLD for r in rs))
    sig_foot = (
        rf"This table reports the {n_sig_rows} of {n_total_attempted} estimated pairwise interaction coefficients "
        rf"that reached $p<.10$, organized into the {n_sig_grp} retained interaction groups. "
        rf"The complete pairwise cross-comparison "
        rf"(all $\binom{{8}}{{2}} = {n_groups_total}$ groups, all {n_total_attempted} cells) "
        rf"appears in Appendix Table~\ref{{tab:glm_interactions_full}}."
    )
    sig_tex, _, _ = render(
        filtered=True, label="tab:glm_interactions",
        caption=sig_caption, foot_extra=sig_foot,
    )

    full_caption = (
        rf"GLM Interaction Effects --- Full Pairwise Cross-Comparison ($N={n}$). "
        rf"All $\binom{{8}}{{2}} = {n_groups_total}$ pairwise interactions among the eight main-effect-significant variables "
        rf"(Product, Nutrition, Taste, Health Label, Attitude, Behavior, Price USD, Education). "
        rf"Stars flag rows reaching $p<.10$."
    )
    full_foot = (
        rf"Full pairwise cross-comparison: all {n_groups_total} interaction groups, "
        rf"{n_total_attempted} estimated coefficients in total; {n_sig_rows} reached $p<.10$ "
        rf"(see Table~\ref{{tab:glm_interactions}} in the main text for the significant subset)."
    )
    full_tex, _, _ = render(
        filtered=False, label="tab:glm_interactions_full",
        caption=full_caption, foot_extra=full_foot,
    )

    with open(TEX_OUT_SIG, "w", encoding="utf-8") as fh:
        fh.write(sig_tex)
    with open(TEX_OUT_FULL, "w", encoding="utf-8") as fh:
        fh.write(full_tex)
    print(f"[interaction table] Written → {TEX_OUT_SIG}  (sig only: {n_sig_grp} groups, {n_sig_rows} rows)")
    print(f"[interaction table] Written → {TEX_OUT_FULL}  (full: {n_groups_total} groups, {n_total_attempted} rows)")


if __name__ == "__main__":
    main()
