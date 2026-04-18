"""
Build out/demographics_table.html — Sample Characteristics Table (Table 0).

Merges:
  - Survey long data (out/GLM_WTP__LongData.csv) for Age, Gender, Education,
    Income, Marital Status, Household Size, Employment, Residential Area
  - Prolific demographic export for Race/Ethnicity

Outputs:
  out/demographics_table.html
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np

PROLIFIC_CSV = r"F:\xwechat_files\wxid_4tn29ju2hbg312_1325\msg\file\2026-04\prolific_demographic_export_69b18f4a4423342a4223d951 (2).csv"
LONG_CSV     = "out/GLM_WTP__LongData.csv"
OUT_HTML     = "out/demographics_table.html"

# ── Load data ──────────────────────────────────────────────────────────────────
long    = pd.read_csv(LONG_CSV)
wide    = long.drop_duplicates(subset=["ParticipantID"]).copy()
N_total = len(wide)

prolific = pd.read_csv(PROLIFIC_CSV)
prolific_approved = prolific[prolific["Status"] == "APPROVED"].copy()
N_prolific = len(prolific_approved)
eth = prolific_approved["Ethnicity simplified"].value_counts()

# ── Codebooks ──────────────────────────────────────────────────────────────────
AGE_MAP = {
    1: "18–24", 2: "25–34", 3: "35–44",
    4: "45–54", 5: "55–64", 6: "65–74", 7: "75 or older"
}
GENDER_MAP = {
    1: "Male", 2: "Female", 3: "Non-binary / Third gender", 4: "Prefer not to say"
}
EDUC_MAP = {
    1: "Less than high school", 2: "High school graduate",
    3: "University / College", 4: "Graduate degree", 5: "Doctorate"
}
MARITAL_MAP = {
    1: "Single", 2: "Married", 3: "Divorced", 4: "Widowed", 5: "Other"
}
HHSIZE_MAP = {
    1: "1", 2: "2", 3: "3", 4: "4", 5: "More than 5"
}
INCOME_MAP = {
    1: "$0–$9,999", 2: "$10,000–$24,999", 3: "$25,000–$49,999",
    4: "$50,000–$74,999", 5: "$75,000–$99,999",
    6: "$100,000–$149,999", 7: "$150,000+"
}
EMPLOY_MAP = {
    1: "Employed full-time", 2: "Employed part-time",
    3: "Unemployed (seeking)", 4: "Unemployed (not seeking)",
    5: "Retired", 6: "Student", 7: "Disabled"
}
URBAN_MAP = {
    1: "Urban", 2: "Suburban", 3: "Rural"
}

# ── Helper: count + pct rows ───────────────────────────────────────────────────
def freq_rows(series, mapping, order=None):
    """Returns list of (label, n, pct) for each category in mapping."""
    if order is None:
        order = sorted(mapping.keys())
    rows = []
    for code in order:
        label = mapping[code]
        n = int((series == code).sum())
        pct = n / N_total * 100
        rows.append((label, n, pct))
    return rows

def eth_rows():
    order = ["White", "Asian", "Black", "Mixed", "Other", "Prefer not to say"]
    rows = []
    for label in order:
        n = int(eth.get(label, 0))
        pct = n / N_prolific * 100
        rows.append((label, n, pct))
    return rows

# ── Build sections ────────────────────────────────────────────────────────────
SECTIONS = [
    ("Age",              freq_rows(wide["Age"],           AGE_MAP,     [1,2,3,4,5,6,7])),
    ("Gender",           freq_rows(wide["Gender"],        GENDER_MAP,  [1,2,3,4])),
    ("Race / Ethnicity", eth_rows()),
    ("Education",        freq_rows(wide["Education"],     EDUC_MAP,    [1,2,3,4,5])),
    ("Marital Status",   freq_rows(wide["Marital"],       MARITAL_MAP, [1,2,3,4,5])),
    ("Household Size",   freq_rows(wide["HouseholdSize"], HHSIZE_MAP,  [1,2,3,4,5])),
    ("Annual Household Income", freq_rows(wide["Income"], INCOME_MAP,  [1,2,3,4,5,6,7])),
    ("Employment Status",freq_rows(wide["Employment"],    EMPLOY_MAP,  [1,2,3,4,5,6,7])),
    ("Residential Area", freq_rows(wide["Urban_Rural"],   URBAN_MAP,   [1,2,3])),
]

# ── Render HTML rows ───────────────────────────────────────────────────────────
def render_rows(sections):
    html = []
    for sec_label, rows in sections:
        # Section header
        html.append(
            f'<tr class="sec-hdr"><td colspan="3"><b>{sec_label}</b></td></tr>'
        )
        # Filter out zero rows
        visible = [(lbl, n, pct) for lbl, n, pct in rows if n > 0]
        for lbl, n, pct in visible:
            html.append(
                f'<tr>'
                f'<td class="indent">{lbl}</td>'
                f'<td class="num">{n}</td>'
                f'<td class="num">{pct:.1f}%</td>'
                f'</tr>'
            )
    return "\n".join(html)

table_rows = render_rows(SECTIONS)

# ── Continuous descriptives ────────────────────────────────────────────────────
sustain_mean = wide["SustainScore"].mean() if "SustainScore" in wide.columns else float("nan")
sustain_sd   = wide["SustainScore"].std()  if "SustainScore" in wide.columns else float("nan")
age_mean     = wide["Age_num"].mean()      if "Age_num" in wide.columns      else float("nan")
age_sd       = wide["Age_num"].std()       if "Age_num" in wide.columns      else float("nan")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Table 0 — Sample Characteristics</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 13.5px; color: #1f2328;
    padding: 40px 48px; max-width: 720px; margin: 0 auto;
  }}
  h2 {{ font-size: 1.15rem; font-weight: 700; margin-bottom: 4px; }}
  .sub {{ color: #57606a; font-size: .85rem; margin-bottom: 24px; }}
  .note {{ color: #57606a; font-size: .8rem; margin-top: 14px; line-height: 1.5; }}
  .nav {{ margin-bottom: 20px; }}
  .nav a {{ font-size:.82rem; color:#0969da; text-decoration:none; margin-right:16px; }}
  .nav a:hover {{ text-decoration:underline; }}

  table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
  thead th {{
    border-top: 2px solid #111; border-bottom: 1px solid #111;
    padding: 7px 10px; text-align: left; font-size: 12.5px;
  }}
  thead th.num {{ text-align: right; }}
  tbody td {{ padding: 4px 10px; vertical-align: top; }}
  td.indent {{ padding-left: 22px; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

  tr.sec-hdr td {{
    padding: 10px 10px 3px; font-weight: 700;
    border-top: 1px solid #ccc; color: #1f2328;
    font-size: 12.5px; background: #f6f8fa;
  }}
  tr:last-child td {{ border-bottom: 2px solid #111; }}

  .footer-line {{
    border-top: 1px solid #ccc; margin-top: 14px; padding-top: 10px;
  }}
  .cont-table {{ margin-top: 20px; }}
  .cont-table td {{ padding: 4px 10px; }}
</style>
</head>
<body>

<div class="nav">
  <a href="tables_preview.html">← GLM Tables</a>
  <a href="charts_preview.html">← Charts</a>
</div>

<h2>Table 0 &nbsp;·&nbsp; Sample Characteristics</h2>
<p class="sub">
  Survey N = {N_total} participants &nbsp;|&nbsp;
  Prolific N = {N_prolific} approved &nbsp;|&nbsp;
  Race/ethnicity sourced from Prolific demographic export
</p>

<table>
  <thead>
    <tr>
      <th>Characteristic</th>
      <th class="num"><i>n</i></th>
      <th class="num">%</th>
    </tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>

<div class="footer-line">
  <table class="cont-table">
    <thead>
      <tr>
        <th>Continuous variable</th>
        <th class="num">Mean</th>
        <th class="num">SD</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="indent">Age (midpoint, years)</td>
        <td class="num">{age_mean:.1f}</td>
        <td class="num">{age_sd:.1f}</td>
      </tr>
      <tr>
        <td class="indent">Sustainability Orientation Score (1–7)</td>
        <td class="num">{sustain_mean:.2f}</td>
        <td class="num">{sustain_sd:.2f}</td>
      </tr>
    </tbody>
  </table>
</div>

<p class="note">
  <b>Note.</b>
  Percentages for survey items (Age, Gender, Education, Marital Status,
  Household Size, Income, Employment, Residential Area) are based on
  N&nbsp;=&nbsp;{N_total} survey respondents with valid scenario data.
  Race/Ethnicity percentages are based on N&nbsp;=&nbsp;{N_prolific} Prolific-approved
  participants using Prolific's simplified ethnicity classification.
  Sustainability Orientation Score = mean of 12 attitude and behavior items
  (Cronbach's α = .91).
</p>

</body>
</html>
"""

os.makedirs("out", exist_ok=True)
with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Written: {OUT_HTML}")
