"""
Generate out/demographics_table.tex — Table 0: Sample Characteristics.

Sources:
  - out/GLM_WTP__LongData.csv  (survey demographics, N=319)
  - Prolific export CSV         (race/ethnicity, N=300)
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
import numpy as np

PROLIFIC_CSV = r"F:\xwechat_files\wxid_4tn29ju2hbg312_1325\msg\file\2026-04\prolific_demographic_export_69b18f4a4423342a4223d951 (2).csv"
LONG_CSV     = "out/GLM_WTP__LongData.csv"
TEX_OUT      = "out/demographics_table.tex"

# ── Load ───────────────────────────────────────────────────────────────────────
long  = pd.read_csv(LONG_CSV)
wide  = long.drop_duplicates(subset=["ParticipantID"]).copy()
N     = len(wide)

prolific   = pd.read_csv(PROLIFIC_CSV)
approved   = prolific[prolific["Status"] == "APPROVED"]
N_prol     = len(approved)
eth_counts = approved["Ethnicity simplified"].value_counts()

# ── Codebooks ──────────────────────────────────────────────────────────────────
AGE_MAP    = {1:"18--24", 2:"25--34", 3:"35--44", 4:"45--54",
              5:"55--64", 6:"65--74", 7:"75 or older"}
GENDER_MAP = {1:"Male", 2:"Female",
              3:"Non-binary / Third gender", 4:"Prefer not to say"}
EDUC_MAP   = {1:"Less than high school", 2:"High school graduate",
              3:"University / College", 4:"Graduate degree", 5:"Doctorate"}
MARITAL_MAP= {1:"Single", 2:"Married", 3:"Divorced",
              4:"Widowed", 5:"Other"}
HHSIZE_MAP = {1:"1", 2:"2", 3:"3", 4:"4", 5:"More than 5"}
INCOME_MAP = {1:r"\$0--\$9,999", 2:r"\$10,000--\$24,999",
              3:r"\$25,000--\$49,999", 4:r"\$50,000--\$74,999",
              5:r"\$75,000--\$99,999", 6:r"\$100,000--\$149,999",
              7:r"\$150,000+"}
EMPLOY_MAP = {1:"Employed full-time", 2:"Employed part-time",
              3:"Unemployed (seeking)", 4:"Unemployed (not seeking)",
              5:"Retired", 6:"Student", 7:"Disabled"}
URBAN_MAP  = {1:"Urban", 2:"Suburban", 3:"Rural"}

# ── Helpers ────────────────────────────────────────────────────────────────────
def freq_rows(series, mapping, order, denom=None):
    D = denom or N
    rows = []
    for code in order:
        n   = int((series == code).sum())
        if n == 0:
            continue
        pct = n / D * 100
        rows.append((mapping[code], n, pct))
    return rows

def eth_rows():
    order = ["White","Asian","Black","Mixed","Other","Prefer not to say"]
    rows  = []
    for lbl in order:
        n   = int(eth_counts.get(lbl, 0))
        if n == 0:
            continue
        pct = n / N_prol * 100
        rows.append((lbl, n, pct))
    return rows

# ── Build LaTeX rows ───────────────────────────────────────────────────────────
def sec_row(label):
    return rf"\multicolumn{{3}}{{l}}{{\textbf{{{label}}}}} \\"

def data_row(label, n, pct):
    return rf"\quad {label} & {n} & {pct:.1f}\% \\"

SECTIONS = [
    ("Age",                       freq_rows(wide["Age"],           AGE_MAP,    [1,2,3,4,5,6,7])),
    ("Gender",                    freq_rows(wide["Gender"],        GENDER_MAP, [1,2,3,4])),
    ("Race / Ethnicity$^{a}$",    eth_rows()),
    ("Education",                 freq_rows(wide["Education"],     EDUC_MAP,   [1,2,3,4,5])),
    ("Marital Status",            freq_rows(wide["Marital"],       MARITAL_MAP,[1,2,3,4,5])),
    ("Household Size",            freq_rows(wide["HouseholdSize"], HHSIZE_MAP, [1,2,3,4,5])),
    ("Annual Household Income",   freq_rows(wide["Income"],        INCOME_MAP, [1,2,3,4,5,6,7])),
    ("Employment Status",         freq_rows(wide["Employment"],    EMPLOY_MAP, [1,2,3,4,5,6,7])),
    ("Residential Area",          freq_rows(wide["Urban_Rural"],   URBAN_MAP,  [1,2,3])),
]

lines = []
for sec_label, rows in SECTIONS:
    lines.append(sec_row(sec_label))
    for lbl, n, pct in rows:
        lines.append(data_row(lbl, n, pct))
    lines.append(r"\addlinespace[2pt]")

# Continuous variables block
sustain_m  = wide["SustainScore"].mean()
sustain_sd = wide["SustainScore"].std()
age_m      = wide["Age_num"].mean()
age_sd     = wide["Age_num"].std()

cont_block = "\n".join([
    r"\midrule",
    r"\multicolumn{3}{l}{\textbf{Continuous Variables}} \\",
    rf"\quad Age (midpoint, years) & \multicolumn{{2}}{{l}}{{$M = {age_m:.1f}$, $SD = {age_sd:.1f}$}} \\",
    rf"\quad Sustainability Orientation (1--7) & \multicolumn{{2}}{{l}}{{$M = {sustain_m:.2f}$, $SD = {sustain_sd:.2f}$}} \\",
])

# ── Assemble ───────────────────────────────────────────────────────────────────
tex = "\n".join([
    r"\begin{table}[ht]",
    r"\centering",
    rf"\caption{{Sample Characteristics ($N = {N}$)}}",
    r"\label{tab:sample_demographics}",
    r"\begin{threeparttable}",
    r"\begin{tabular}{lrr}",
    r"\toprule",
    rf"Characteristic & $n$ & \% \\",
    r"\midrule",
    "\n".join(lines),
    cont_block,
    r"\bottomrule",
    r"\end{tabular}",
    r"\begin{tablenotes}\footnotesize",
    rf"\item $^{{a}}$ Race/Ethnicity based on Prolific demographic export ($n = {N_prol}$ approved participants).",
    r"\item Percentages for all other variables based on survey respondents with valid scenario data.",
    r"\item Sustainability Orientation Score = mean of 12 attitude and behavior items (Cronbach's $\alpha = .91$).",
    r"\end{tablenotes}",
    r"\end{threeparttable}",
    r"\end{table}",
])

os.makedirs("out", exist_ok=True)
with open(TEX_OUT, "w", encoding="utf-8") as f:
    f.write(tex)
print(f"Written: {TEX_OUT}")
