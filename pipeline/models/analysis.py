from config.constants import *
import os, re
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.multivariate.manova import MANOVA
def descriptives(df):
    def _m_sd(s):
        arr = pd.to_numeric(s, errors="coerce")
        return "NA" if arr.notna().sum() == 0 else f"{np.nanmean(arr):.2f} ± {np.nanstd(arr, ddof=1):.2f}"

    out = {}
    overall = {
        "Lab":      [_m_sd(df[COL_RATE_LAB])]    if COL_RATE_LAB in df.columns else [],
        "Premium":  [_m_sd(df[COL_RATE_PREM])]   if COL_RATE_PREM in df.columns else [],
        "Basic":    [_m_sd(df[COL_RATE_BASIC])]  if COL_RATE_BASIC in df.columns else [],
        "Attitude": [_m_sd(df[COL_ATT])]         if COL_ATT in df.columns else [],
        "Behavior": [_m_sd(df[COL_BEH])]         if COL_BEH in df.columns else [],
        "Economic": [_m_sd(df[COL_ECON])]        if COL_ECON in df.columns else []
    }
    tbl_overall = pd.DataFrame({k:v for k,v in overall.items() if v}).rename(index={0:"Overall"})
    out["Overall"] = tbl_overall

    cols = [c for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC, COL_ATT, COL_BEH, COL_ECON] if c in df.columns]
    if "Category" in df.columns and cols:
        out["ByCluster"] = df.groupby("Category")[cols].agg(["mean","std","count"])
    else:
        out["ByCluster"] = pd.DataFrame()
    return out



def one_way_anovas(df):
    """
    One-way ANOVAs: rating ~ Cluster (eta² reported).
    Always returns a DataFrame with columns: Tuna, df1, df2, F, p, eta2
    """
    rows = []
    for rating_col, tuna in [(COL_RATE_LAB,"Lab"), (COL_RATE_PREM,"Premium"), (COL_RATE_BASIC,"Basic")]:
        if rating_col not in df.columns or "Category" not in df.columns:
            continue
        sub = df[[rating_col, "Category"]].dropna()
        if sub["Category"].nunique() < 2:
            continue
        try:
            model = smf.ols(f"{rating_col} ~ C(Category)", data=sub).fit()
            a = anova_lm(model, typ=2)
            # Defensive fetch of p
            if "PR(>F)" in a.columns:
                pval = a.loc["C(Category)","PR(>F)"]
            else:
                # statsmodels sometimes emits lowercase or other variants
                p_candidates = [c for c in a.columns if c.lower() in {"pr(>f)","p","pvalue","p-value"}]
                pval = a.loc["C(Category)", p_candidates[0]] if p_candidates else np.nan

            ss_between = a.loc["C(Category)","sum_sq"]
            ss_resid   = a.loc["Residual","sum_sq"]
            ss_total = ss_between + ss_resid
            eta2 = (ss_between / ss_total) if ss_total > 0 else np.nan

            rows.append({
                "Tuna": tuna,
                "df1": a.loc["C(Category)","df"],
                "df2": a.loc["Residual","df"],
                "F":   a.loc["C(Category)","F"],
                "p":   pval,
                "eta2": eta2
            })
        except Exception:
            continue
    return pd.DataFrame(rows)




def factorial_anovas(df):
    """Type III ANOVAs per tuna (CSV-friendly).

    Returns a dict of tables keyed by sheet-like names:
      - Lab, Premium, Basic: ANOVA table (Type III)
      - Lab_Meta, ...: metadata tables
      - Notes: if nothing analyzable
    """
    res = {}
    base_factors = [COL_PRICE_LVL, COL_NUTR_LVL, COL_TASTE_LVL]

    any_written = False
    for col, tuna in [(COL_RATE_LAB,"Lab"), (COL_RATE_PREM,"Premium"), (COL_RATE_BASIC,"Basic")]:
        if col not in df.columns:
            res[f"{tuna}_Notes"] = pd.DataFrame({"note":[f"{tuna}: DV column '{col}' not found."]})
            continue
        if any(f not in df.columns for f in base_factors):
            res[f"{tuna}_Notes"] = pd.DataFrame({"note":[f"{tuna}: missing one or more factor columns (PriceLvl/NutriLvl/TasteLvl)."]})
            continue

        sub = df[[col, "Category"] + base_factors].dropna()
        if sub.empty or sub["Category"].astype(str).nunique() < 2:
            res[f"{tuna}_Notes"] = pd.DataFrame({"note":[f"{tuna}: no analyzable rows or insufficient cluster levels."]})
            continue

        levels_meta = {f: sub[f].astype(str).nunique() for f in base_factors}
        if any(v < 2 for v in levels_meta.values()):
            res[f"{tuna}_Levels"] = pd.DataFrame({"factor": list(levels_meta.keys()), "n_levels": list(levels_meta.values())})
            res[f"{tuna}_Notes"] = pd.DataFrame({"note":[f"{tuna}: at least one factor has <2 levels in available rows."]})
            continue

        sub = sub.copy()
        sub["Category"] = sub["Category"].astype("category")
        for f in base_factors:
            sub[f] = sub[f].astype("category")

        rhs = "C(Category) + C(PriceLvl) + C(NutriLvl) + C(TasteLvl)"
        rhs += " + C(PriceLvl):C(NutriLvl) + C(PriceLvl):C(TasteLvl) + C(NutriLvl):C(TasteLvl)"
        try:
            model = smf.ols(f"{col} ~ {rhs}", data=sub).fit()
            a3 = sm.stats.anova_lm(model, typ=3).rename_axis("Source").reset_index()
            a3.insert(0, "Tuna", tuna)
            res[tuna] = a3
            res[f"{tuna}_Meta"] = pd.DataFrame({
                "Rows_Used":[len(sub)],
                "Levels_Price":[levels_meta[COL_PRICE_LVL]],
                "Levels_Nutrition":[levels_meta[COL_NUTR_LVL]],
                "Levels_Taste":[levels_meta[COL_TASTE_LVL]]
            })
            any_written = True
        except Exception as e:
            res[f"{tuna}_Error"] = pd.DataFrame({"error":[str(e)]})

    if not any_written:
        res["Notes"] = pd.DataFrame({"note":["No analyzable data for factorial ANOVAs."]})
    return res

def anova_with_demographics(df):
    """Type III ANOVAs per tuna including demographics as main effects (CSV-friendly).

    Returns dict of tables keyed by sheet-like names:
      - Lab / Premium / Basic: ANOVA table
      - Lab_Meta: metadata (rows used, factors, demos kept/dropped)
      - Notes: global notes
    """
    TUKEY_ALPHA = 0.05
    MIN_PROP_OVERALL = 0.10
    MIN_PROP_SUBSET  = 0.10
    MIN_ROWS         = 10

    per_map = {
        COL_RATE_LAB:   ["PriceLvl_Lab","NutriLvl_Lab","SustainLvl_Lab","TasteLvl_Lab"],
        COL_RATE_PREM:  ["PriceLvl_Premium","NutriLvl_Premium","SustainLvl_Premium","TasteLvl_Premium"],
        COL_RATE_BASIC: ["PriceLvl_Basic","NutriLvl_Basic","SustainLvl_Basic","TasteLvl_Basic"],
    }
    proxy_factors = [COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL]

    demo_candidates = [d for d in DEMOG_COLS if d in df.columns]
    n_total = len(df)
    demo_overall = []
    for d in demo_candidates:
        nonnull = df[d].notna().sum()
        if nonnull >= max(MIN_ROWS, int(MIN_PROP_OVERALL * n_total)):
            demo_overall.append(d)

    res = {}
    notes_msgs = []
    if not demo_overall:
        notes_msgs.append("No usable demographic columns (need >=10% non-null overall or >=10 rows).")

    any_result = False
    for col, tuna in [(COL_RATE_LAB,"Lab"), (COL_RATE_PREM,"Premium"), (COL_RATE_BASIC,"Basic")]:
        if col not in df.columns:
            notes_msgs.append(f"{tuna}: DV column '{col}' not found.")
            continue

        facs = [f for f in per_map.get(col, []) if f in df.columns]
        if not facs:
            facs = [f for f in proxy_factors if f in df.columns]
        if not facs:
            notes_msgs.append(f"{tuna}: no scenario factor columns found.")
            continue

        base = df[[col, "Category"] + facs].dropna(subset=[col, "Category"]).copy()
        if base.empty or base["Category"].astype(str).nunique() < 2:
            notes_msgs.append(f"{tuna}: insufficient rows or <2 cluster levels after filtering.")
            continue

        facs_use = [f for f in facs if base[f].dropna().astype(str).nunique() >= 2]
        if not facs_use:
            notes_msgs.append(f"{tuna}: no scenario factor shows >=2 levels in available rows.")
            continue

        idx = base.index
        demo_use, dropped_demo = [], []
        for d in demo_overall:
            s = df.loc[idx, d]
            nn = s.notna().sum()
            nu = s.dropna().astype(str).nunique()
            if nn >= max(MIN_ROWS, int(MIN_PROP_SUBSET * len(base))) and nu >= 2:
                demo_use.append(d)
            else:
                dropped_demo.append({"demo": d, "nonnull_in_subset": int(nn), "levels_in_subset": int(nu)})

        cols_use = [col, "Category"] + facs_use + demo_use
        sub = df.loc[idx, cols_use].dropna(subset=[col, "Category"]).copy()
        if sub.empty or sub["Category"].astype(str).nunique() < 2:
            notes_msgs.append(f"{tuna}: insufficient data after merging demographics.")
            continue

        sub["Category"] = sub["Category"].astype("category")
        for f in facs_use:
            sub[f] = sub[f].astype("category")
        for d in demo_use:
            # keep as category unless numeric
            if not pd.api.types.is_numeric_dtype(sub[d]):
                sub[d] = sub[d].astype("category")

        rhs = "C(Category)" + "".join([f" + C({f})" for f in facs_use]) + "".join([f" + C({d})" for d in demo_use])
        try:
            model = smf.ols(f"{col} ~ {rhs}", data=sub).fit()
            a3 = sm.stats.anova_lm(model, typ=3).rename_axis("Source").reset_index()
            a3.insert(0, "Tuna", tuna)
            res[tuna] = a3
            res[f"{tuna}_Meta"] = pd.DataFrame({
                "Rows_Used":[len(sub)],
                "Scenario_Factors":[", ".join(facs_use)],
                "Demographics_Used":[", ".join(demo_use) if demo_use else "(none)"],
                "Demographics_Dropped":[len(dropped_demo)]
            })
            if dropped_demo:
                res[f"{tuna}_DroppedDemos"] = pd.DataFrame(dropped_demo)
            any_result = True
        except Exception as e:
            res[f"{tuna}_Error"] = pd.DataFrame({"error":[str(e)]})

    res["Notes"] = pd.DataFrame({"note": notes_msgs if notes_msgs else ["OK"]})
    if not any_result:
        res["NoResults"] = pd.DataFrame({"note":["No analyzable data for demographics ANOVAs."]})
    return res
def manova_joint(df):
    """
    Robust MANOVA across Lab/Premium/Basic with automatic coverage checks and
    iterative model reduction to avoid singular design matrices.

    Effects reported (if supported by data):
      • Intercept
      • Cluster (Category)
      • Price Level (PriceLvl)
      • Nutrition Level (NutriLvl)
      • Sustainability Level (SustainLvl)
      • Taste Level (TasteLvl)
    """
    import re
    from statsmodels.multivariate.manova import MANOVA
    os.makedirs("out", exist_ok=True)

    rating_cols = [c for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC] if c in df.columns]
    if len(rating_cols) < 2:
        note = "MANOVA not run: fewer than 2 rating columns present."
        with open("out/MANOVA_joint.txt","w",encoding="utf-8") as f: f.write(note)
        with pd.ExcelWriter("out/MANOVA_joint.xlsx", engine="openpyxl") as xw:
            pd.DataFrame({"notes":[note]}).to_excel(xw, sheet_name="Notes", index=False)
        return "out/MANOVA_joint.txt"

    # Build base (DVs + Cluster)
    base = df[[*rating_cols, "Category"]].copy()
    for dv in rating_cols:
        base[dv] = pd.to_numeric(base[dv], errors="coerce")
    base = base.dropna(subset=rating_cols + ["Category"])
    if base.empty or base["Category"].astype(str).nunique() < 2:
        note = "MANOVA not run: require at least two observed Cluster levels after DV filtering."
        with open("out/MANOVA_joint.txt","w",encoding="utf-8") as f: f.write(note)
        with pd.ExcelWriter("out/MANOVA_joint.xlsx", engine="openpyxl") as xw:
            pd.DataFrame({"notes":[note]}).to_excel(xw, sheet_name="Notes", index=False)
        return "out/MANOVA_joint.txt"

    # Candidate IVs and pretty names
    candidate_factors = [COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL]
    pretty = {
        "Intercept": "Intercept",
        "C(Category)": "Cluster",
        f"C({COL_PRICE_LVL})": "Price Level",
        f"C({COL_NUTR_LVL})": "Nutrition Level",
        f"C({COL_SUST_LVL})": "Sustainability Level",
        f"C({COL_TASTE_LVL})": "Taste Level",
    }
    headline = ["Intercept","C(Category)", *[f"C({c})" for c in candidate_factors]]

    # Attach IVs to base index
    work = base.copy()
    for fct in candidate_factors:
        work[fct] = df.loc[work.index, fct] if fct in df.columns else pd.NA

    # Normalize factor encodings and remove unused categories later
    for fct in candidate_factors:
        if fct in work.columns:
            work[fct] = work[fct].replace({"1":"Low","2":"Mid","3":"High"})
            work[fct] = work[fct].astype("category")

    # Coverage table per factor (need >=10% non-missing, >=2 levels AND >=5 rows per level)
    MIN_PROP = 0.10
    MIN_ROWS_PER_LEVEL = 5
    cov_rows = []
    include = []
    n_base = len(work)
    for fct in candidate_factors:
        s = work[fct]
        nn = int(s.notna().sum())
        prop = (nn / n_base) if n_base else 0.0
        levels = s.dropna().astype(str)
        nlev = int(levels.nunique())
        ok = False
        min_per_level = 0
        if nn and nlev >= 2:
            counts = levels.value_counts()
            min_per_level = int(counts.min())
            ok = (prop >= MIN_PROP) and (min_per_level >= MIN_ROWS_PER_LEVEL)
        cov_rows.append({
            "Factor": fct, "Rows in base": n_base, "Non-missing": nn,
            "Prop non-missing": round(prop,3), "Observed levels": nlev,
            "Min rows/level": min_per_level, "Included": "Yes" if ok else "No"
        })
        if ok: include.append(fct)

    # Build complete-case modeling frame for the *included* IVs
    model_cols = rating_cols + ["Category"] + include
    sub = work[model_cols].dropna().copy()
    sub["Category"] = sub["Category"].astype("category")
    sub["Category"] = sub["Category"].cat.remove_unused_categories()
    for fct in include:
        sub[fct] = sub[fct].astype("category").cat.remove_unused_categories()

    # Helper: try fitting MANOVA with a set of factors; drop weakest coverage iteratively if singular
    def try_fit(factors):
        rhs_terms = ["C(Category)"] + [f"C({f})" for f in factors]
        rhs = " + ".join(rhs_terms)
        lhs = " + ".join(rating_cols)
        # Complete-case for the current factor set
        need_cols = rating_cols + ["Category"] + factors
        sub2 = work[need_cols].dropna().copy()
        if sub2.empty or sub2["Category"].astype(str).nunique() < 2:
            return None, "Insufficient rows or cluster variation", rhs_terms, sub2
        sub2["Category"] = sub2["Category"].astype("category").cat.remove_unused_categories()
        for fct in factors:
            sub2[fct] = sub2[fct].astype("category").cat.remove_unused_categories()
        try:
            mv = MANOVA.from_formula(f"{lhs} ~ {rhs}", data=sub2)
            res = mv.mv_test()
            return (res, None, rhs_terms, sub2)
        except Exception as e:
            return (None, str(e), rhs_terms, sub2)

    # Iteratively drop factors (worst coverage first) until fit works or nothing left but Cluster
    factors_sorted = sorted(include, key=lambda f: (
        next((r["Min rows/level"] for r in cov_rows if r["Factor"]==f), 0),
        next((r["Prop non-missing"] for r in cov_rows if r["Factor"]==f), 0.0)
    ))
    factors_sorted = factors_sorted[::-1]  # best → worst
    mv_res, fit_err, rhs_terms_used, sub_used = try_fit(factors_sorted)
    if mv_res is None and factors_sorted:
        # drop one by one from the tail (worst)
        drop_list = []
        for _ in range(len(factors_sorted)):
            drop_list.append(factors_sorted.pop())  # drop worst
            mv_res, fit_err, rhs_terms_used, sub_used = try_fit(factors_sorted)
            if mv_res is not None:
                break

    # ---------- TXT report ----------
    def _fmt_p(p):
        try:
            p = float(p)
        except:
            return "p = NA"
        return "p < .001" if p < 0.001 else f"p = {p:.3f}".replace("0.", ".")

    def _fmt_mv_row(row):
        try:
            val = float(row.get("Value", np.nan))
            Fv  = float(row.get("F Value", np.nan))
            num = int(round(float(row.get("Num DF", np.nan))))
            den = int(round(float(row.get("Den DF", np.nan))))
            pv  = float(row.get("Pr > F", np.nan))
            return f"Value = {val:.3f}, F({num}, {den}) = {Fv:.3f}, " + _fmt_p(pv)
        except Exception:
            return "(unavailable)"

    included_keys = set(rhs_terms_used if mv_res is not None else ["C(Category)"] + [f"C({f})" for f in include])
    # Intercept should always appear in output; do not “exclude” it just because we didn’t coverage-check it
    included_keys_with_intercept = {"Intercept"} | included_keys

    # Always show the full intended design (PI-requested presentation),
    # regardless of which factors were dropped during fitting.
    design_human = "Cluster + Price Level + Nutrition Level + Sustainability Level + Taste Level"

    lines = []
    lines.append("Multivariate Tests (SPSS-style; Pillai, Wilks, Hotelling–Lawley, Roy)")
    lines.append(f"Dependent Variables: {', '.join(rating_cols)}")
    lines.append("Design (IVs): Cluster + Price Level + Nutrition Level + Sustainability Level + Taste Level")
    lines.append("")

    if mv_res is None:
        # Print structure with reasons
        for eff in headline:
            label = pretty.get(eff, eff)
            if eff == "Intercept":
                lines.append(label)
                lines.append("  (not estimable)")
                lines.append("")
                continue
            if eff in included_keys:
                lines.append(label)
                lines.append("  Pillai’s Trace: (not estimable)")
                lines.append("  Wilks’ Lambda: (not estimable)")
                lines.append("  Hotelling–Lawley Trace: (not estimable)")
                lines.append("  Roy’s Largest Root: (not estimable)")
                lines.append("")
            else:
                lines.append(label)
                lines.append("  (excluded: insufficient coverage or iterative reduction due to singularity)")
                lines.append("")
        if fit_err:
            lines.append(f"Note: MANOVA fit error: {fit_err}")
    else:
        blocks = mv_res.results
        for eff in headline:
            label = pretty.get(eff, eff)
            # Show Intercept if present in results, otherwise show note
            if eff == "Intercept":
                blk = blocks.get("Intercept")
                lines.append(label)
                if blk is None or "stat" not in blk or blk["stat"].empty:
                    lines.append("  (not estimable)")
                    lines.append("")
                    continue
                stat = blk["stat"]
                idx = {str(i).strip().lower(): i for i in stat.index}
                for raw, pretty_name in [
                    ("pillai's trace","Pillai’s Trace"),
                    ("wilks' lambda","Wilks’ Lambda"),
                    ("hotelling-lawley trace","Hotelling–Lawley Trace"),
                    ("roy's greatest root","Roy’s Largest Root"),
                ]:
                    if raw in idx:
                        row = stat.loc[idx[raw]]
                        if raw == "wilks' lambda":
                            try:
                                eta2 = 1.0 - float(row.get("Value", np.nan))
                                lines.append(f"  {pretty_name}: " + _fmt_mv_row(row) + f"; η² ≈ {eta2:.3f}")
                            except Exception:
                                lines.append(f"  {pretty_name}: " + _fmt_mv_row(row))
                        else:
                            lines.append(f"  {pretty_name}: " + _fmt_mv_row(row))
                lines.append("")
                continue

            # non-intercept effects
            key = eff
            if eff not in included_keys:
                lines.append(label)
                lines.append("  (excluded: insufficient coverage or iterative reduction due to singularity)")
                lines.append("")
                continue
            blk = blocks.get(key)
            lines.append(label)
            if blk is None or "stat" not in blk or blk["stat"].empty:
                lines.append("  (not estimable)")
                lines.append("")
                continue
            stat = blk["stat"]
            idx = {str(i).strip().lower(): i for i in stat.index}
            for raw, pretty_name in [
                ("pillai's trace","Pillai’s Trace"),
                ("wilks' lambda","Wilks’ Lambda"),
                ("hotelling-lawley trace","Hotelling–Lawley Trace"),
                ("roy's greatest root","Roy’s Largest Root"),
            ]:
                if raw in idx:
                    row = stat.loc[idx[raw]]
                    if raw == "wilks' lambda":
                        try:
                            eta2 = 1.0 - float(row.get("Value", np.nan))
                            lines.append(f"  {pretty_name}: " + _fmt_mv_row(row) + f"; η² ≈ {eta2:.3f}")
                        except Exception:
                            lines.append(f"  {pretty_name}: " + _fmt_mv_row(row))
                    else:
                        lines.append(f"  {pretty_name}: " + _fmt_mv_row(row))
            lines.append("")

    lines += [
        "a. Exact statistic",
        "b. Computed using alpha = .05",
        "c. The statistic is an upper bound on F that yields a lower bound on the significance level.",
        "d. Design: " + f"{', '.join(rating_cols)} ~ " + (" + ".join(sorted(included_keys_with_intercept - {'Intercept'})) if included_keys_with_intercept else "(none)")
    ]
    with open("out/MANOVA_joint.txt","w",encoding="utf-8") as f:
        f.write("\n".join(lines))

    # XLSX: Summary, Coverage, and one sheet per included effect (including Intercept)
    with pd.ExcelWriter("out/MANOVA_joint.xlsx", engine="openpyxl") as xw:
        # Summary
        pd.DataFrame({
            "Dependent Variables": [", ".join(rating_cols)],
            "Rows used (complete-case)": [len(sub_used) if mv_res is not None else 0],
            "Design (IVs)": ["Cluster + Price Level + Nutrition Level + Sustainability Level + Taste Level"]
        }).to_excel(xw, sheet_name="Summary", index=False)
        # Coverage
        pd.DataFrame(cov_rows).to_excel(xw, sheet_name="Coverage", index=False)

        def write_effect_sheet(key, label):
            sheet = label[:31]
            if mv_res is None:
                pd.DataFrame({"notes":[f"Not estimable; {fit_err or 'singular design'}"]}).to_excel(xw, sheet_name=sheet, index=False)
                return
            blk = mv_res.results.get(key)
            if blk is None or "stat" not in blk or blk["stat"].empty:
                pd.DataFrame({"notes":["Not estimable (insufficient variation)."]}).to_excel(xw, sheet_name=sheet, index=False)
                return
            stat = blk["stat"].rename(columns={
                "Value":"Value","F Value":"F","Num DF":"Hypothesis df","Den DF":"Error df","Pr > F":"Sig."
            }).copy()
            try:
                idx = {str(i).strip().lower(): i for i in stat.index}
                if "wilks' lambda" in idx:
                    stat.loc[idx["wilks' lambda"], "Partial Eta Squared"] = max(0.0, 1.0 - float(stat.loc[idx["wilks' lambda"], "Value"]))
            except Exception:
                pass
            stat.insert(0, "Effect", label)
            stat.to_excel(xw, sheet_name=sheet, index=True)

        # Write sheets for Intercept + every target factor (always create a sheet)
        effects_to_write = [("Intercept","Intercept"),
                            ("C(Category)","Cluster"),
                            (f"C({COL_PRICE_LVL})","Price Level"),
                            (f"C({COL_NUTR_LVL})","Nutrition Level"),
                            (f"C({COL_SUST_LVL})","Sustainability Level"),
                            (f"C({COL_TASTE_LVL})","Taste Level")]
        for key, label in effects_to_write:
            write_effect_sheet(key, label)

    return "out/MANOVA_joint.txt"





# --- Ported missing functions from original ---


def tukey_for_significant_anovas(df, anova_sig, alpha=0.05):
    """CSV-only Tukey HSD tables by tuna for significant one-way ANOVAs."""
    return tukey_posthoc_csv(df, anova_sig, alpha=alpha)


# --- Ported from original ---
def descriptive_by_demographics(df):
    """
    Create 'Descriptive_By_Demographics.xlsx' with sheets:
      - By_Gender
      - By_Education
      - By_Income
      - By_Age
      - By_Marital
      - By_HouseholdSize
      - By_Employment
      - By_LivingArea  (Urban_Rural)
      - By_Gender_Education
      - By_Gender_Income
      - By_Gender_Age
      - By_Gender_Marital
      - By_Gender_HouseholdSize
      - By_Gender_Employment
      - By_Gender_LivingArea

    Each sheet lists Mean, Std. Deviation, and N for each Dependent Variable
    (Lab_Rating, Premium_Rating, Basic_Rating) grouped by the sheet's factor(s).
    """
    os.makedirs("out", exist_ok=True)
    out_path = "out/Descriptive_By_Demographics.xlsx"

    # Ensure rating columns exist and are numeric
    rating_cols = [c for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC] if c in df.columns]
    if not rating_cols:
        with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
            pd.DataFrame({"note": ["No rating columns found (Lab_Rating / Premium_Rating / Basic_Rating)."]}).to_excel(
                xw, sheet_name="Notes", index=False
            )
        return out_path
    for rc in rating_cols:
        df[rc] = pd.to_numeric(df[rc], errors="coerce")

    # Map display names and actual dataframe columns
    single_factors = [
        ("By_Gender",         "Gender"),
        ("By_Education",      "Education"),
        ("By_Income",         "Income"),
        ("By_Age",            "Age"),
        ("By_Marital",        "Marital"),
        ("By_HouseholdSize",  "HouseholdSize"),
        ("By_Employment",     "Employment"),
        ("By_LivingArea",     "Urban_Rural"),
    ]
    gender_interactions = [
        ("By_Gender_Education",     ["Gender","Education"]),
        ("By_Gender_Income",        ["Gender","Income"]),
        ("By_Gender_Age",           ["Gender","Age"]),
        ("By_Gender_Marital",       ["Gender","Marital"]),
        ("By_Gender_HouseholdSize", ["Gender","HouseholdSize"]),
        ("By_Gender_Employment",    ["Gender","Employment"]),
        ("By_Gender_LivingArea",    ["Gender","Urban_Rural"]),
    ]

    def _sheet_name(name: str) -> str:
        # Excel limit is 31 chars
        return name[:31] if len(name) > 31 else name

    def _write_group_sheet(xw, group_cols, sheet_name):
        # Keep only rows with non-null group values
        use_cols = list(group_cols) + rating_cols
        sub = df[use_cols].dropna(subset=group_cols).copy()
        if sub.empty:
            pd.DataFrame({"note": ["No data for grouping columns."]}).to_excel(
                xw, sheet_name=_sheet_name(sheet_name), index=False
            )
            return

        # Build long form results across DVs
        frames = []
        for dv in rating_cols:
            tmp = sub.dropna(subset=[dv])
            if tmp.empty:
                continue
            agg = tmp.groupby(group_cols)[dv].agg(["mean","std","count"]).reset_index()
            agg = agg.rename(columns={"mean":"Mean","std":"Std. Deviation","count":"N"})
            agg.insert(0, "Dependent Variable", dv.replace("_", " ").replace("Rating", "Rating"))
            frames.append(agg)
        if not frames:
            pd.DataFrame({"note": ["No valid ratings for this grouping."]}).to_excel(
                xw, sheet_name=_sheet_name(sheet_name), index=False
            )
            return
        out = pd.concat(frames, ignore_index=True)
        out.to_excel(xw, sheet_name=_sheet_name(sheet_name), index=False)

    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        wrote_any = False

        # Singles
        for sheet, col in single_factors:
            if col in df.columns:
                _write_group_sheet(xw, [col], sheet)
                wrote_any = True
            else:
                pd.DataFrame({"note":[f"Column '{col}' not found."]}).to_excel(
                    xw, sheet_name=_sheet_name(sheet), index=False
                )

        # Gender interactions
        for sheet, cols in gender_interactions:
            ok = all(c in df.columns for c in cols)
            if ok:
                _write_group_sheet(xw, cols, sheet)
                wrote_any = True
            else:
                missing = [c for c in cols if c not in df.columns]
                pd.DataFrame({"note":[f"Missing columns: {', '.join(missing)}"]}).to_excel(
                    xw, sheet_name=_sheet_name(sheet), index=False
                )

        if not wrote_any:
            pd.DataFrame({"note":["No demographic columns available to summarize."]}).to_excel(
                xw, sheet_name="Notes", index=False
            )

    return out_path


# --- Ported from original ---
def ols_by_tuna(df):
    """
    Improved OLS per tuna with:
      • Same IVs as MANOVA (Cluster + PriceLvl + NutriLvl + SustainLvl + TasteLvl) + optional demographics
      • Robust handling of sparse/rare categories and perfect collinearity with iterative back-off
      • HC3 robust SEs, Type II & III ANOVA tables, VIFs, and standardized (beta) coefficients
      • Clear notes on what was included/dropped and the exact formula used

    Output (out/OLS_ByTuna.xlsx), per tuna:
      - Coefs
      - StdBetas
      - Model_ANOVA_TypeII
      - Model_ANOVA_TypeIII
      - VIF
      - Summary
      - Notes
    """
    os.makedirs("out", exist_ok=True)
    out_xlsx = "out/OLS_ByTuna.xlsx"

    # Use per‑tuna factors if available; otherwise fall back to the proxy factors
    per_map = {
        COL_RATE_LAB:   ["PriceLvl_Lab","NutriLvl_Lab","SustainLvl_Lab","TasteLvl_Lab"],
        COL_RATE_PREM:  ["PriceLvl_Premium","NutriLvl_Premium","SustainLvl_Premium","TasteLvl_Premium"],
        COL_RATE_BASIC: ["PriceLvl_Basic","NutriLvl_Basic","SustainLvl_Basic","TasteLvl_Basic"],
    }
    proxy_factors = [COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL]

    # Demographic columns (already decoded earlier if a codebook was provided)
    demo_all = [d for d in DEMOG_COLS if d in df.columns]

    # ---------- helpers ----------
    def _clean_categorical(s: pd.Series, name: str, min_count: int = 5) -> pd.Series:
        """Drop rare levels; force Gender to Male/Female only; return categorical with remaining levels."""
        s = s.copy()
        if str(name).strip().lower() == "gender":
            base = s.astype(str).str.strip()
            map_to_label = {
                "1": "Male", "male": "Male", "m": "Male",
                "2": "Female", "female": "Female", "f": "Female",
            }
            base = base.str.lower().map(map_to_label).fillna(base.str.title())
            mask = base.isin(["Male", "Female"])
            s = base.where(mask, np.nan)

        vc = s.value_counts(dropna=True)
        keep = set(vc[vc >= min_count].index.tolist())
        s = s.where(s.isin(keep), np.nan)
        return s.astype("category")

    def _ensure_two_levels(s: pd.Series) -> bool:
        """Return True if the series has ≥2 levels after cleaning."""
        return s.dropna().astype(str).nunique() >= 2

    def _standardized_betas(model):
        """Compute standardized coefficients by z-scoring y and all design columns (excluding intercept)."""
        try:
            y = model.model.endog.astype(float)
            X = pd.DataFrame(model.model.exog, columns=model.model.exog_names).astype(float)
            # Drop intercept columns for standardization
            for c in ["Intercept", "const"]:
                if c in X.columns:
                    X = X.drop(columns=[c])
            # z-score
            y_std = (y - y.mean()) / (y.std(ddof=0) if y.std(ddof=0) != 0 else 1.0)
            Xz = X.copy()
            for c in Xz.columns:
                std = Xz[c].std(ddof=0)
                Xz[c] = 0.0 if std == 0 else (Xz[c] - Xz[c].mean()) / std
            Xz = sm.add_constant(Xz)
            mdl = sm.OLS(y_std, Xz).fit()
            out = pd.DataFrame({
                "term": mdl.params.index,
                "std_beta": mdl.params.values,
                "std_beta_se": mdl.bse.values,
                "t": mdl.tvalues.values,
                "p": mdl.pvalues.values
            })
            return out
        except Exception:
            return pd.DataFrame(columns=["term","std_beta","std_beta_se","t","p"])

    def _vif_for_model(model):
        """Variance Inflation Factors (drop intercept; numeric design only)."""
        try:
            from statsmodels.stats.outliers_influence import variance_inflation_factor
            X = pd.DataFrame(model.model.exog, columns=model.model.exog_names)
            for c in ["Intercept", "const"]:
                if c in X.columns:
                    X = X.drop(columns=[c])
            # only numeric
            X = X.apply(pd.to_numeric, errors="coerce")
            if X.shape[1] < 2:
                return pd.DataFrame({"term": X.columns, "VIF": [np.nan]*X.shape[1]})
            vifs = []
            for i in range(X.shape[1]):
                try:
                    vifs.append(variance_inflation_factor(X.values.astype(float), i))
                except Exception:
                    vifs.append(np.nan)
            return pd.DataFrame({"term": X.columns, "VIF": vifs})
        except Exception:
            return pd.DataFrame({"term": [], "VIF": []})

    def _fit_with_backoff(formula, data, demo_terms_original):
        """
        Try to fit; on failure, iteratively drop sparsest DEMOGRAPHIC term (not scenario factors, not Cluster).
        If still failing, fall back to a base model with no demographics.
        Returns: (model, final_formula, note)
        """
        # first attempt
        try:
            mdl = smf.ols(formula, data=data).fit(cov_type="HC3")
            return mdl, formula, None
        except Exception as e:
            last_err = str(e)

        # parse terms
        lhs, rhs = [x.strip() for x in formula.split("~", 1)]
        rhs_terms = [t.strip() for t in rhs.split("+") if t.strip()]
        demos = [t for t in rhs_terms if (t.startswith("C(") and any(d in t for d in demo_terms_original)) or (t in demo_terms_original)]

        # drop demographics one-by-one (sparsest first)
        def _sparsity(name: str) -> tuple:
            col = name.replace("C(", "").replace(")", "")
            s = data[col]
            return (s.dropna().astype(str).nunique(), -s.notna().sum())  # more levels first, then fewer rows

        demos_sorted = sorted(demos, key=_sparsity, reverse=True)
        for drop in demos_sorted:
            rhs_new = " + ".join([t for t in rhs_terms if t != drop])
            formula_new = f"{lhs} ~ {rhs_new}"
            try:
                mdl = smf.ols(formula_new, data=data).fit(cov_type="HC3")
                return mdl, formula_new, f"Dropped {drop} due to singularity/sparsity."
            except Exception as e:
                last_err = str(e)
                rhs_terms = [t for t in rhs_terms if t != drop]
                continue

        # final fallback: base model without any demographics
        base_terms = [t for t in rhs_terms if not any(d in t for d in demo_terms_original)]
        formula_base = f"{lhs} ~ {' + '.join(base_terms)}"
        try:
            mdl = smf.ols(formula_base, data=data).fit(cov_type="HC3")
            return mdl, formula_base, "Fell back to base model without demographics."
        except Exception as e:
            return None, formula_base, f"Fit failed: {e}"

    # ---------- main loop ----------
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as xw:
        wrote_any = False

        for dv, tuna in [(COL_RATE_LAB,"Lab"), (COL_RATE_PREM,"Premium"), (COL_RATE_BASIC,"Basic")]:
            if dv not in df.columns:
                continue

            # choose scenario factors
            facs = [f for f in per_map.get(dv, []) if f in df.columns]
            if not facs:
                facs = [f for f in proxy_factors if f in df.columns]

            # build dataframe subset
            use_cols = ["Category", dv] + facs + demo_all
            sub = df[use_cols].copy()

            # numeric DV & drop missing DV/Cluster
            sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
            sub = sub.dropna(subset=[dv, "Category"])
            if sub.empty or sub["Category"].astype(str).nunique() < 2:
                pd.DataFrame({"note":[f"{tuna}: insufficient rows or <2 cluster levels after DV filtering."]}).to_excel(
                    xw, sheet_name=f"{tuna}_Notes", index=False
                )
                continue

            # clean factors and demographics
            sub["Category"] = sub["Category"].astype("category")
            for f in facs:
                sub[f] = _clean_categorical(sub[f], f)

            demo_present = [d for d in demo_all if d in sub.columns]
            for d in demo_present:
                if pd.api.types.is_numeric_dtype(sub[d]) and sub[d].nunique(dropna=True) > 12:
                    # keep as numeric covariate
                    continue
                sub[d] = _clean_categorical(sub[d], d)

            # drop rows with any missing predictors after cleaning
            model_cols = ["Category"] + facs + demo_present + [dv]
            sub = sub[model_cols].dropna()
            # must still have ≥2 cluster levels & at least two levels for each scenario factor
            if sub.empty or sub["Category"].astype(str).nunique() < 2:
                pd.DataFrame({"note":[f"{tuna}: insufficient rows or <2 cluster levels after cleaning."]}).to_excel(
                    xw, sheet_name=f"{tuna}_Notes", index=False
                )
                continue
            facs = [f for f in facs if _ensure_two_levels(sub[f])]
            if not facs:
                pd.DataFrame({"note":[f"{tuna}: no scenario factors retained with ≥2 levels."]}).to_excel(
                    xw, sheet_name=f"{tuna}_Notes", index=False
                )
                continue

            # Build formula: main effects; force categorical treatment coding via C()
            rhs_terms = ["C(Category)"] + [f"C({f})" for f in facs]
            demo_terms_formula = []
            demo_terms_names = []
            for d in demo_present:
                if pd.api.types.is_numeric_dtype(sub[d]) and sub[d].nunique(dropna=True) > 12:
                    demo_terms_formula.append(d)   # numeric covariate
                    demo_terms_names.append(d)
                elif _ensure_two_levels(sub[d]):
                    demo_terms_formula.append(f"C({d})")
                    demo_terms_names.append(d)
            rhs_all = rhs_terms + demo_terms_formula
            formula = f"{dv} ~ {' + '.join(rhs_all)}"

            # Fit with back-off (drop sparse demographics first; keep scenario factors and Cluster)
            model, final_formula, note = _fit_with_backoff(formula, sub, demo_terms_names)
            if model is None:
                pd.DataFrame({"error":[note or "Fit failed"], "formula":[formula]}).to_excel(
                    xw, sheet_name=f"{tuna}_Error", index=False
                )
                continue

            # ---- Write outputs ----
            # Coefficients
            coefs = pd.DataFrame({
                "term": model.params.index,
                "coef": model.params.values,
                "std_err": model.bse.values,
                "t": model.tvalues.values,
                "p": model.pvalues.values
            })
            conf = model.conf_int()
            conf.columns = ["ci_low","ci_high"]
            coefs = coefs.join(conf, how="left")
            coefs.to_excel(xw, sheet_name=f"{tuna}_Coefs", index=False)

            # Standardized betas
            betas = _standardized_betas(model)
            if not betas.empty:
                betas.to_excel(xw, sheet_name=f"{tuna}_StdBetas", index=False)

            # ANOVA tables (Type II & Type III)
            try:
                a2 = sm.stats.anova_lm(model, typ=2).reset_index().rename(columns={"index":"Source","PR(>F)":"p"})
                a2.to_excel(xw, sheet_name=f"{tuna}_ANOVA_TypeII", index=False)
            except Exception as e:
                pd.DataFrame({"anova_error":[str(e)]}).to_excel(xw, sheet_name=f"{tuna}_ANOVA_TypeII_Error", index=False)
            try:
                a3 = sm.stats.anova_lm(model, typ=3).reset_index().rename(columns={"index":"Source","PR(>F)":"p"})
                a3.to_excel(xw, sheet_name=f"{tuna}_ANOVA_TypeIII", index=False)
            except Exception as e:
                pd.DataFrame({"anova_error":[str(e)]}).to_excel(xw, sheet_name=f"{tuna}_ANOVA_TypeIII_Error", index=False)

            # VIF
            vif = _vif_for_model(model)
            if not vif.empty:
                vif.to_excel(xw, sheet_name=f"{tuna}_VIF", index=False)

            # Summary / meta
            pd.DataFrame({
                "Metric": ["N","R2","Adj_R2","F","F_p","AIC","BIC","Scale","Cov_Type","Formula_Used","Backoff_Note"],
                "Value":  [int(model.nobs), model.rsquared, model.rsquared_adj,
                           getattr(model, "fvalue", np.nan), getattr(model, "f_pvalue", np.nan),
                           model.aic, model.bic, model.scale, model.cov_type, final_formula, (note or "")]
            }).to_excel(xw, sheet_name=f"{tuna}_Summary", index=False)

            # Notes
            pd.DataFrame({
                "Note":[
                    "Design: main effects only — C(Category) + C(Price) + C(Nutrition) + C(Sustainability) + C(Taste) + demographics (where available).",
                    "Categoricals use treatment coding with an implicit reference level; rare levels (<5 rows) dropped.",
                    "Gender restricted to Male/Female for stability. SE: HC3 robust."
                ]
            }).to_excel(xw, sheet_name=f"{tuna}_Notes", index=False)

            wrote_any = True

        if not wrote_any:
            pd.DataFrame({"note":["No analyzable data for any OLS model."]}).to_excel(
                xw, sheet_name="Notes", index=False
            )

    return out_xlsx

# -------------------------
# APA helpers + plotting
# -------------------------


# --- Ported from original ---
def tukey_posthoc(df, oneway, alpha=0.05, out_path="out/PostHoc_ByCluster.xlsx"):
    """
    Run Tukey HSD pairwise tests for Cluster *only for tunas with significant one-way ANOVA*.
    Robust to different column names for p-values and to empty/partial ANOVA tables.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # If ANOVA table is missing or empty, write a note and exit
    if oneway is None or getattr(oneway, "empty", True):
        with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
            pd.DataFrame({"note": ["No one-way ANOVAs were computed or results table is empty."]}).to_excel(
                xw, sheet_name="Notes", index=False
            )
        return out_path

    # Normalize possible p-value column names to 'p'
    lower_map = {c.lower(): c for c in oneway.columns}
    pcol = None
    for cand in ["p", "pr(>f)", "pvalue", "p-value", "p_val", "p-val"]:
        if cand in lower_map:
            pcol = lower_map[cand]
            break

    # If still not found, try to create a 'p' column from statsmodels naming
    if pcol is None:
        # If the table came directly from anova_lm typ=2 it should have 'PR(>F)'
        if "PR(>F)" in oneway.columns:
            oneway = oneway.rename(columns={"PR(>F)": "p"})
            pcol = "p"
        # Or if already has a lowercase/other variant
        elif any("pr(>f)" == c.lower() for c in oneway.columns):
            true_col = [c for c in oneway.columns if c.lower() == "pr(>f)"][0]
            oneway = oneway.rename(columns={true_col: "p"})
            pcol = "p"

    # If we still couldn't identify a p-value column, bail out gracefully
    if pcol is None and "p" not in oneway.columns:
        with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
            pd.DataFrame({"note": ["Tukey HSD skipped: could not find a p-value column in ANOVA results."]}).to_excel(
                xw, sheet_name="Notes", index=False
            )
        return out_path

    # From here on, use 'p' as the canonical p-value column
    if pcol != "p" and pcol is not None:
        oneway = oneway.rename(columns={pcol: "p"})

    # Identify significant rows
    try:
        sig = oneway.loc[pd.to_numeric(oneway["p"], errors="coerce") < alpha]
    except Exception:
        sig = pd.DataFrame()

    tuna2col = {"Lab": COL_RATE_LAB, "Premium": COL_RATE_PREM, "Basic": COL_RATE_BASIC}

    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        wrote_any = False

        # If ANOVA table is present but no sig rows, write a clear note
        if sig is None or sig.empty:
            pd.DataFrame({"note": [f"No one-way ANOVAs were significant at alpha={alpha:.2f}; no Tukey HSD run."]}).to_excel(
                xw, sheet_name="Notes", index=False
            )
            return out_path

        # Run Tukey per significant tuna
        for _, r in sig.iterrows():
            tuna = str(r["Tuna"]) if "Tuna" in r else None
            rating_col = tuna2col.get(tuna)
            if not rating_col or rating_col not in df.columns or "Category" not in df.columns:
                continue

            sub = df[[rating_col, "Category"]].dropna()
            # Need at least two groups and some rows per group
            if sub.empty or sub["Category"].nunique() < 2 or sub.groupby("Category")[rating_col].size().min() < 2:
                # Emit a note sheet per tuna explaining why Tukey was skipped
                pd.DataFrame({"note": [f"{tuna}: not enough data per cluster for Tukey HSD."]}).to_excel(
                    xw, sheet_name=f"{tuna}_Notes", index=False
                )
                wrote_any = True
                continue

            try:
                tk = pairwise_tukeyhsd(endog=pd.to_numeric(sub[rating_col], errors="coerce"),
                                       groups=sub["Category"].astype(str),
                                       alpha=alpha)
                tk_tbl = pd.DataFrame(tk._results_table.data[1:], columns=tk._results_table.data[0])
                means = sub.groupby("Category")[rating_col].agg(["mean","std","count"]).reset_index()
                tk_tbl.to_excel(xw, sheet_name=f"{tuna}_Tukey", index=False)
                means.to_excel(xw, sheet_name=f"{tuna}_GroupMeans", index=False)
                wrote_any = True
            except Exception as e:
                pd.DataFrame({"error": [str(e)]}).to_excel(xw, sheet_name=f"{tuna}_Error", index=False)
                wrote_any = True

        if not wrote_any:
            pd.DataFrame({"note": ["Tukey HSD produced no output."]}).to_excel(xw, sheet_name="Notes", index=False)

    return out_path



# -------------------------
# Compatibility shims (keep runner stable)
# -------------------------

def demographic_descriptives(df):
    """Shim: original function name is descriptive_by_demographics."""
    return descriptive_by_demographics(df)

def ols_models(df):
    """Shim: original function name is ols_by_tuna."""
    return ols_by_tuna(df)

def tukey_for_significant_anovas(df, anova_sig, alpha=0.05):
    """Shim: uses tukey_posthoc on the one-way ANOVA table."""
    return tukey_posthoc(df, anova_sig, alpha=alpha)


# =========================
# CSV-only outputs (v6)
# =========================
def tukey_posthoc_csv(df, oneway, alpha=0.05):
    """Run Tukey HSD pairwise tests for Cluster for tunas with significant one-way ANOVA. Returns dict-of-DFs."""
    from statsmodels.stats.multicomp import pairwise_tukeyhsd
    tables = {}

    if oneway is None or getattr(oneway, "empty", True):
        tables["Notes"] = pd.DataFrame({"note":["No significant one-way ANOVAs provided; Tukey skipped."]})
        return tables

    # Normalize p column
    lower_map = {c.lower(): c for c in oneway.columns}
    pcol = None
    for cand in ["p","pr(>f)","pvalue","p-value","p_val","p-val"]:
        if cand in lower_map:
            pcol = lower_map[cand]; break
    if pcol is None and "PR(>F)" in oneway.columns:
        oneway = oneway.rename(columns={"PR(>F)":"p"}); pcol="p"
    if pcol is None:
        pcol="p" if "p" in oneway.columns else None
    if pcol is None:
        tables["Notes"] = pd.DataFrame({"note":["Could not find p-value column in ANOVA table; Tukey skipped."]})
        return tables

    # Identify tuna/DV label column if present
    tuna_col = None
    for c in ["Tuna","tuna","DV","dv","Dependent Variable","dependent_variable","Outcome","outcome"]:
        if c in oneway.columns:
            tuna_col = c; break

    # Map tuna label -> DV column name
    dv_map = {
        "Lab": COL_RATE_LAB, "Lab Grown": COL_RATE_LAB, "Lab_Grown": COL_RATE_LAB,
        "Premium": COL_RATE_PREM, "Basic": COL_RATE_BASIC,
        COL_RATE_LAB: COL_RATE_LAB, COL_RATE_PREM: COL_RATE_PREM, COL_RATE_BASIC: COL_RATE_BASIC
    }

    def _tukey_one(dv, prefix):
        sub = df[[dv, "Category"]].copy()
        sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
        sub = sub.dropna()
        if sub.empty or sub["Category"].astype(str).nunique() < 2:
            tables[f"{prefix}_Notes"] = pd.DataFrame({"note":[f"{dv}: insufficient data for Tukey (need >=2 cluster levels)."]})
            return
        try:
            tk = pairwise_tukeyhsd(endog=sub[dv].values, groups=sub["Category"].astype(str).values, alpha=alpha)
            tbl = pd.DataFrame(tk.summary().data[1:], columns=tk.summary().data[0])
            tables[f"{prefix}_Tukey"] = tbl
        except Exception as e:
            tables[f"{prefix}_Error"] = pd.DataFrame({"error":[str(e)]})

    if tuna_col is None:
        # run for all available rating DVs
        for dv, prefix in [(COL_RATE_LAB,"Lab"),(COL_RATE_PREM,"Premium"),(COL_RATE_BASIC,"Basic")]:
            if dv in df.columns:
                _tukey_one(dv, prefix)
        return tables

    sig = oneway.loc[pd.to_numeric(oneway[pcol], errors="coerce") < alpha].copy()
    if sig.empty:
        tables["Notes"] = pd.DataFrame({"note":[f"No ANOVAs significant at alpha={alpha}; Tukey skipped."]})
        return tables

    for tuna in sig[tuna_col].astype(str).unique():
        dv = dv_map.get(tuna, tuna)
        if dv in df.columns:
            prefix = str(tuna).replace(" ","_")
            _tukey_one(dv, prefix)
    return tables

def descriptive_by_demographics_tables(df):
    """Return demographic descriptives as dict-of-DataFrames (CSV-only)."""
    rating_cols = [c for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC] if c in df.columns]
    tables = {}
    if not rating_cols:
        tables["Notes"] = pd.DataFrame({"note":["No rating columns found (Lab_Rating / Premium_Rating / Basic_Rating)."]})
        return tables

    work = df.copy()
    for rc in rating_cols:
        work[rc] = pd.to_numeric(work[rc], errors="coerce")

    def _agg(by_cols, sheet_name):
        cols = [*by_cols, *rating_cols]
        sub = work[cols].dropna(subset=by_cols, how="any")
        if sub.empty:
            tables[sheet_name] = pd.DataFrame({"note":[f"No data for grouping columns: {by_cols}"]})
            return
        frames=[]
        for dv in rating_cols:
            tmp=sub[by_cols+[dv]].dropna()
            if tmp.empty:
                continue
            g=tmp.groupby(by_cols)[dv].agg(["mean","std","count"]).reset_index()
            g=g.rename(columns={"mean":"Mean","std":"Std. Deviation","count":"N"})
            g.insert(0,"Dependent Variable",dv)
            frames.append(g)
        tables[sheet_name]=pd.concat(frames, ignore_index=True) if frames else pd.DataFrame({"note":[f"No valid ratings for {sheet_name}"]})

    singles = [
        ("Gender", "By_Gender"),
        ("Education", "By_Education"),
        ("Income", "By_Income"),
        ("Age", "By_Age"),
        ("Marital", "By_Marital"),
        ("HouseholdSize", "By_HouseholdSize"),
        ("Employment", "By_Employment"),
        ("Urban_Rural", "By_LivingArea"),
    ]
    for col, sheet in singles:
        if col in work.columns:
            _agg([col], sheet)

    if "Gender" in work.columns:
        for col, sheet in [
            ("Education","By_Gender_Education"),
            ("Income","By_Gender_Income"),
            ("Age","By_Gender_Age"),
            ("Marital","By_Gender_Marital"),
            ("HouseholdSize","By_Gender_HouseholdSize"),
            ("Employment","By_Gender_Employment"),
            ("Urban_Rural","By_Gender_LivingArea"),
        ]:
            if col in work.columns:
                _agg(["Gender", col], sheet)

    if not tables:
        tables["Notes"] = pd.DataFrame({"note":["No demographic columns available to summarize."]})
    return tables

def demographic_descriptives(df):
    """CSV-only demographic descriptives; replaces legacy Excel output."""
    return descriptive_by_demographics_tables(df)

def manova_joint_csv(df):
    """CSV-only MANOVA summary tables (Wilks' Lambda etc.)."""
    from statsmodels.multivariate.manova import MANOVA
    tables = {}
    dvs = [c for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC] if c in df.columns]
    if len(dvs) < 2:
        tables["Notes"] = pd.DataFrame({"note":["MANOVA skipped: fewer than 2 rating columns present."]})
        return tables

    base_cols = ["Category", COL_PRICE_LVL, COL_NUTR_LVL, COL_TASTE_LVL]
    base_cols = [c for c in base_cols if c in df.columns]
    sub = df[dvs + base_cols].copy()
    for dv in dvs:
        sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
    sub = sub.dropna(subset=dvs + ["Category"])
    if sub.empty or sub["Category"].astype(str).nunique() < 2:
        tables["Notes"] = pd.DataFrame({"note":["MANOVA skipped: insufficient data or <2 cluster levels."]})
        return tables

    # Build formula with available factors; always include Cluster
    rhs = ["C(Category)"]
    for f in [COL_PRICE_LVL, COL_NUTR_LVL, COL_TASTE_LVL]:
        if f in sub.columns and sub[f].astype(str).nunique() >= 2:
            rhs.append(f"C({f})")
    formula = " + ".join(dvs) + " ~ " + " + ".join(rhs)

    try:
        mv = MANOVA.from_formula(formula, data=sub)
        test = mv.mv_test()
        # Extract a compact table for each effect
        for effect_name, effect_res in test.results.items():
            stat = effect_res.get("stat")
            if stat is None:
                continue
            # statsmodels returns a DataFrame with multivariate test statistics
            stat_tbl = stat.copy()
            stat_tbl.insert(0, "Effect", effect_name)
            tables[str(effect_name)] = stat_tbl.reset_index().rename(columns={"index":"Test"})
        tables["Meta"] = pd.DataFrame({"formula":[formula], "n":[len(sub)], "dvs":[", ".join(dvs)]})
    except Exception as e:
        tables["Notes"] = pd.DataFrame({"error":[str(e)], "formula":[formula]})
    return tables

def ols_models(df):
    """CSV-only OLS outputs (coefs + summary) per tuna."""
    return ols_by_tuna_tables(df)

def ols_by_tuna_tables(df):
    """Robust OLS (HC3) with main effects; returns dict-of-DataFrames."""
    tables = {}
    proxy_factors = [COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL]
    demo_all = [d for d in DEMOG_COLS if d in df.columns]

    for dv,tuna in [(COL_RATE_LAB,"Lab"),(COL_RATE_PREM,"Premium"),(COL_RATE_BASIC,"Basic")]:
        if dv not in df.columns:
            continue
        use_factors=[f for f in proxy_factors if f in df.columns and df[f].astype(str).nunique()>=2]
        sub=df[["Category",dv]+use_factors+demo_all].copy()
        sub[dv]=pd.to_numeric(sub[dv], errors="coerce")
        sub=sub.dropna(subset=["Category",dv])
        if sub.empty or sub["Category"].astype(str).nunique()<2:
            tables[f"{tuna}_Notes"]=pd.DataFrame({"note":[f"{tuna}: insufficient data after filtering."]})
            continue

        rhs=["C(Category)"]+[f"C({f})" for f in use_factors]
        for d in demo_all:
            if d in sub.columns and sub[d].dropna().astype(str).nunique()>=2:
                rhs.append(f"C({d})")
        formula=f"{dv} ~ " + " + ".join(rhs)

        try:
            model=smf.ols(formula, data=sub.dropna()).fit(cov_type="HC3")
            coefs=pd.DataFrame({
                "term":model.params.index,
                "coef":model.params.values,
                "std_err":model.bse.values,
                "t":model.tvalues.values,
                "p":model.pvalues.values
            })
            conf=model.conf_int()
            conf.columns=["ci_low","ci_high"]
            coefs=coefs.join(conf, how="left")
            tables[f"{tuna}_Coefs"]=coefs

            tables[f"{tuna}_Summary"]=pd.DataFrame({
                "Metric":["N","R2","Adj_R2","F","F_p","AIC","BIC","Cov_Type","Formula_Used"],
                "Value":[int(model.nobs), model.rsquared, model.rsquared_adj,
                         getattr(model,"fvalue",None), getattr(model,"f_pvalue",None),
                         model.aic, model.bic, getattr(model,"cov_type","HC3"), formula]
            })
        except Exception as e:
            tables[f"{tuna}_Error"]=pd.DataFrame({"error":[str(e)], "formula":[formula]})

    if not tables:
        tables["Notes"]=pd.DataFrame({"note":["No analyzable data for OLS models."]})
    return tables
