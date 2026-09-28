# -*- coding: utf-8 -*-
"""
Direct Wald test: is the Attitude x Lab slope different from the Behavior x Lab slope?

Added 2026-09-21 for the FQP manuscript (main_fqp.tex), which claims that sustainability
*attitude*, not *behavior*, re-ranks preference toward lab-grown tuna. That claim previously rested
on Attitude x Product being significant while Behavior x Product was not; this script tests the
difference between the two sets of slopes directly.

Model = the manuscript's moderation specification: Gaussian identity-link GLM (OLS) on the long-format
data (participant x product), main effects (Product, PriceLvl, NutriLvl, TasteLvl, HealthLabel,
demographic factors, mean-centred Attitude / Behavior / PriceUSD / Age / Education / HouseholdSize /
Income) plus Attitude x Product and Behavior x Product, participant-clustered standard errors.
Sanity check: reproduces Table (moderation): Attitude x Lab = 0.658 (0.107),
Attitude x Product chi2(2) = 38.326, Behavior x Product chi2(2) = 2.296.

Run from the repository root:  python scripts/wald_attitude_vs_behavior.py
(needs data/raw/ as in config/constants.py; does not write to out/).
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from config.constants import *
from pipeline.io import (load_merged_data, compute_scores, extract_single_scenario_ratings,
                         merge_scenario_book, infer_levels, decode_demographics_with_codebook,
                         add_numeric_level_cols, filter_valid_ratings, recode_to_parametric,
                         add_sustain_score)
from pipeline.models.analysis import _build_long_wtp

df = load_merged_data()
# ParticipantID is "P{row}" in each file, so it repeats across the two rounds: make it unique
df[COL_PID] = df["HealthLabel"].astype(str) + "_" + df[COL_PID].astype(str)
if COMPUTE_SCORES:
    df = compute_scores(df)
df = extract_single_scenario_ratings(df)
df = merge_scenario_book(df, SCENARIO_BOOK)
df = infer_levels(df)
df = decode_demographics_with_codebook(df, DEMO_CODEBOOK)
df = add_numeric_level_cols(df)
df = filter_valid_ratings(df)
df = recode_to_parametric(df)
df = add_sustain_score(df)
print(f"Analytic participants: {df[COL_PID].nunique()} "
      f"(no-label {df.loc[df.HealthLabel == 0, COL_PID].nunique()}, "
      f"label {df.loc[df.HealthLabel == 1, COL_PID].nunique()})")

long = _build_long_wtp(df)
sub = long.dropna(subset=["Product", "PriceLvl", "NutriLvl", "TasteLvl"]).copy()
cont = ["AttScore", "BehScore", "PriceUSD", "Age_num", "Education_num", "HouseholdSize_num", "Income_num"]
for c in cont:
    sub[c + "_c"] = sub[c] - sub[c].mean()
cat_demos = [d for d in ["Gender", "Marital", "Employment", "Urban_Rural"]
             if d in sub.columns and sub[d].dropna().astype(str).nunique() >= 2]
m = sub.dropna(subset=["WTP"] + [c + "_c" for c in cont] + cat_demos)

rhs = (["C(Product)", "C(PriceLvl)", "C(NutriLvl)", "C(TasteLvl)", "C(HealthLabel)"]
       + [f"C({d})" for d in cat_demos] + [c + "_c" for c in cont]
       + ["C(Product):AttScore_c", "C(Product):BehScore_c"])
res = smf.ols("WTP ~ " + " + ".join(rhs), data=m).fit(
    cov_type="cluster", cov_kwds={"groups": pd.factorize(m[COL_PID])[0]})
print(f"N observations = {len(m)}, participants = {m[COL_PID].nunique()}")

a_lab, b_lab = "C(Product)[T.Lab]:AttScore_c", "C(Product)[T.Lab]:BehScore_c"
a_pre, b_pre = "C(Product)[T.Premium]:AttScore_c", "C(Product)[T.Premium]:BehScore_c"

def chi2(expr):
    t = res.wald_test(expr, use_f=False, scalar=True)
    return float(t.statistic), float(t.pvalue)

print("\n-- sanity check against the manuscript's moderation table --")
print(f"Attitude x Lab      = {res.params[a_lab]:.3f} ({res.bse[a_lab]:.3f})   [table: 0.658 (0.107)]")
print("Attitude x Product  chi2(2) = %.3f, p = %.4g   [table: 38.326]" % chi2(f"({a_lab} = 0), ({a_pre} = 0)"))
print("Behavior x Product  chi2(2) = %.3f, p = %.4f   [table: 2.296, .317]" % chi2(f"({b_lab} = 0), ({b_pre} = 0)"))

print("\n-- direct test: attitude slope shift = behavior slope shift --")
t = res.t_test(f"{a_lab} - {b_lab} = 0")
d, se = float(t.effect[0]), float(t.sd[0][0])
print(f"(1) Attitude x Lab - Behavior x Lab = {d:.3f} (SE {se:.3f}); Wald chi2(1) = {(d/se)**2:.2f}, p = {float(t.pvalue):.4f}")
print("(2) Joint over Lab and Premium: chi2(2) = %.2f, p = %.4f" % chi2(f"({a_lab} - {b_lab} = 0), ({a_pre} - {b_pre} = 0)"))
for nm, expr in [("Attitude slope, Lab", f"AttScore_c + {a_lab} = 0"), ("Behavior slope, Lab", f"BehScore_c + {b_lab} = 0")]:
    tt = res.t_test(expr)
    print(f"    {nm}: {float(tt.effect[0]):.3f} (SE {float(tt.sd[0][0]):.3f}), p = {float(tt.pvalue):.4f}")
