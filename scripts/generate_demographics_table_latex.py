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

PROLIFIC_V1 = "data/raw/prolific_V1_demo.csv"
PROLIFIC_V2 = "data/raw/prolific_V2_demo.csv"
LONG_CSV    = "out/GLM_WTP__LongData.csv"
TEX_OUT     = "out/demographics_table.tex"

# ── Load ───────────────────────────────────────────────────────────────────────
long  = pd.read_csv(LONG_CSV)
wide  = long.drop_duplicates(subset=["ParticipantID"]).copy()
N     = len(wide)

# Pool both Prolific CSVs → race/ethnicity
prol_v1 = pd.read_csv(PROLIFIC_V1)
prol_v2 = pd.read_csv(PROLIFIC_V2)
prolific = pd.concat([prol_v1, prol_v2], ignore_index=True)
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

# Continuous-variable means (for reporting in Sample Characteristics prose,
# not in the table — the Continuous Variables block was removed to keep the
# demographics table on a single page).
age_m      = wide["Age_num"].mean()
age_sd     = wide["Age_num"].std()
att_m      = wide["AttScore"].mean()
att_sd     = wide["AttScore"].std()
beh_m      = wide["BehScore"].mean()
beh_sd     = wide["BehScore"].std()

# ── Assemble ───────────────────────────────────────────────────────────────────
tex = "\n".join([
    r"\begin{table}[H]",
    r"\centering",
    r"\small",
    rf"\caption{{Sample Characteristics (Merged Sept~2025 + April~2026, $N = {N}$)}}",
    r"\label{tab:sample_demographics}",
    r"\begin{threeparttable}",
    r"\begin{tabular}{lrr}",
    r"\toprule",
    rf"Characteristic & $n$ & \% \\",
    r"\midrule",
    "\n".join(lines),
    r"\bottomrule",
    r"\end{tabular}",
    r"\begin{tablenotes}\footnotesize",
    rf"\item $^{{a}}$ Race/Ethnicity based on pooled Prolific demographic exports ($n = {N_prol}$ approved participants across both waves).",
    r"\item Percentages for all other variables based on survey respondents with valid scenario data.",
    rf"\item Continuous variables (reported in text): Age $M={age_m:.1f}$ ($SD={age_sd:.1f}$); Sustainability Attitude $M={att_m:.2f}$ ($SD={att_sd:.2f}$, $\alpha=.918$); Sustainability Behavior $M={beh_m:.2f}$ ($SD={beh_sd:.2f}$, $\alpha=.848$).",
    r"\end{tablenotes}",
    r"\end{threeparttable}",
    r"\end{table}",
])

os.makedirs("out", exist_ok=True)
with open(TEX_OUT, "w", encoding="utf-8") as f:
    f.write(tex)
print(f"Written: {TEX_OUT}  (N={N} survey participants, Prolific approved N={N_prol})")
print(f"Continuous stats for Sample Characteristics prose:")
print(f"  Age:       M={age_m:.1f}, SD={age_sd:.1f}")
print(f"  Attitude:  M={att_m:.2f}, SD={att_sd:.2f}")
print(f"  Behavior:  M={beh_m:.2f}, SD={beh_sd:.2f}")
