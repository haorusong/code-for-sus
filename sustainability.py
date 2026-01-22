# -*- coding: utf-8 -*-
"""
Sustainability Preference Analysis — full pipeline
--------------------------------------------------
What this file does (short + practical):
1) Load survey data.
2) Compute/use Attitude, Behavior, Economic scores (Q2–Q20).
3) Merge scenario book (Price/Nutrition/Sustainability levels).
4) Drop rows missing any Lab/Premium/Basic rating or having zeros.
5) Cluster participants (K=3 for analysis), print/plot K diagnostics.
6) Descriptives, one-way ANOVAs, Tukey HSD, factorial ANOVAs (Type III),
   ANOVAs with demographics, MANOVA, and OLS per tuna.
7) Save clean outputs (always fresh) to ./out

Author: H. Song with AI assistance from ChatGPT
"""

import os, shutil, warnings, glob
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from scipy.cluster.hierarchy import linkage, dendrogram

import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.multivariate.manova import MANOVA

# -------------------------
# Files + core settings
# -------------------------

DATA_FILE = "Exploring Consumer Preferences and Willingness to Pay for Sustainable and Lab-Grown Tuna_September 2, 2025_15.40 2 copy.xlsx"

SCENARIO_BOOK = "scenario book.xlsx"
DEMO_CODEBOOK = "Demographic_Codebook.xlsx"

COMPUTE_SCORES = True
INCLUDE_ECON = False

K_ANALYSIS = 3
SILHOUETTE_K_RANGE = range(2, 7)
CLEAN_OUTPUT = True
VERBOSE = False

# Column names
COL_PID        = "ParticipantID"
COL_ATT        = "Attitude score"
COL_BEH        = "Behavior Score"
COL_ECON       = "Economic score"
COL_SCENARIO   = "Scenario"
COL_RATE_LAB   = "Lab_Rating"
COL_RATE_PREM  = "Premium_Rating"
COL_RATE_BASIC = "Basic_Rating"

#
# Scenario-per-tuna level columns
COL_PRICE_LAB  = "Price_Lab"
COL_PRICE_PREM = "Price_Premium"
COL_PRICE_BASIC= "Price_Basic"
COL_NUTR_LAB   = "Nutrition_Lab"
COL_NUTR_PREM  = "Nutrition_Premium"
COL_NUTR_BASIC = "Nutrition_Basic"
COL_SUST_LAB   = "Sustainability_Lab"
COL_SUST_PREM  = "Sustainability_Premium"
COL_SUST_BASIC = "Sustainability_Basic"

# Taste (new factor)
COL_TASTE_LAB   = "Taste_Lab"
COL_TASTE_PREM  = "Taste_Premium"
COL_TASTE_BASIC = "Taste_Basic"
COL_TASTE_LVL   = "TasteLvl"

# Proxies used in analyses/plots
COL_PRICE_LVL  = "PriceLvl"
COL_NUTR_LVL   = "NutriLvl"
COL_SUST_LVL   = "SustainLvl"

DEMOG_COLS = ["Age", "Gender", "Education", "Marital", "HouseholdSize", "Income", "Employment", "Urban_Rural"]

# Qualtrics items (only if COMPUTE_SCORES=True)
ATT_ITEMS  = ["Q2_1","Q3_1","Q4_1","Q5_1","Q6_1"]
BEH_ITEMS  = ["Q8_1","Q9_1","Q10_1","Q11_1","Q12_1","Q13_1","Q14_1"]
ECON_ITEMS = ["Q15_1","Q16_1","Q17_1","Q18_1","Q19_1","Q20_1"]

# -------------------------
# Utilities
# -------------------------

def setup_outdir():
    if CLEAN_OUTPUT and os.path.exists("out"):
        shutil.rmtree("out")
    os.makedirs("out/plots", exist_ok=True)

def _norm_header(s):
    s = str(s).replace("\u00A0"," ").replace("\u2007"," ").replace("\u202F"," ")
    return " ".join(s.strip().split())

def load_data():
    df = pd.read_excel(DATA_FILE)
    df = df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed", na=False)]
    df.columns = [_norm_header(c) for c in df.columns]

    ren = {}
    for c in df.columns:
        cl = c.lower()
        if "attitude" in cl and "score" in cl and c != COL_ATT: ren[c] = COL_ATT
        elif ("behavior" in cl or "behaviour" in cl) and "score" in cl and c != COL_BEH: ren[c] = COL_BEH
        elif "economic" in cl and "score" in cl and c != COL_ECON: ren[c] = COL_ECON
        elif "lab" in cl and "rating" in cl and c != COL_RATE_LAB: ren[c] = COL_RATE_LAB
        elif "premium" in cl and "rating" in cl and c != COL_RATE_PREM: ren[c] = COL_RATE_PREM
        elif "basic" in cl and "rating" in cl and c != COL_RATE_BASIC: ren[c] = COL_RATE_BASIC
        elif cl in ["participantid","participant id","responseid","pid"] and c != COL_PID: ren[c] = COL_PID
        elif cl in ["scenario id","scenario_id"] and c != COL_SCENARIO: ren[c] = COL_SCENARIO
        elif c == "Category (K=4)": ren[c] = "Category"
    if ren:
        df = df.rename(columns=ren)

    # Coerce Qualtrics item strings like "7 - Strongly agree" -> 7.0
    def _coerce(series):
        def _to_num(x):
            if pd.isna(x): return np.nan
            sx = str(x)
            for t in sx.split():
                try: return float(t)
                except: pass
            try: return float(sx)
            except: return np.nan
        return series.apply(_to_num)

    for c in df.columns:
        if c.startswith("Q") and "_" in c:
            df[c] = _coerce(df[c])

    if COL_PID not in df.columns:
        df[COL_PID] = [f"P{i+1}" for i in range(len(df))]

    return df

def compute_scores(df):
    if not COMPUTE_SCORES:
        return df
    for items, out in [(ATT_ITEMS, COL_ATT), (BEH_ITEMS, COL_BEH), (ECON_ITEMS, COL_ECON)]:
        has = [c for c in items if c in df.columns]
        if has:
            df[out] = df[has].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    return df

def extract_single_scenario_ratings(df):
    have_tidy = any([(c in df.columns and df[c].notna().any())
                    for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC]])
    if have_tidy and (COL_SCENARIO in df.columns and df[COL_SCENARIO].notna().any()):
        return df

    for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC, COL_SCENARIO]:
        if c not in df.columns: df[c] = np.nan

    qnums = range(42, 72)
    def _triplet(row, q):
        c1, c2, c3 = f"Q{q}_1", f"Q{q}_2", f"Q{q}_3"
        v1 = row[c1] if c1 in row.index else np.nan
        v2 = row[c2] if c2 in row.index else np.nan
        v3 = row[c3] if c3 in row.index else np.nan
        return v1, v2, v3

    scen, lab, prem, bas = [], [], [], []
    for _, r in df.iterrows():
        pick_q, trip = None, (np.nan, np.nan, np.nan)
        for q in qnums:
            v1, v2, v3 = _triplet(r, q)
            if pd.notna(v1) or pd.notna(v2) or pd.notna(v3):
                pick_q, trip = q, (v1, v2, v3)
                break
        if pick_q is not None:
            scen.append(int(pick_q - 41)); lab.append(trip[0]); prem.append(trip[1]); bas.append(trip[2])
        else:
            scen.append(np.nan); lab.append(np.nan); prem.append(np.nan); bas.append(np.nan)

    df[COL_SCENARIO]   = df[COL_SCENARIO].where(df[COL_SCENARIO].notna(), scen)
    df[COL_RATE_LAB]   = df[COL_RATE_LAB].where(df[COL_RATE_LAB].notna(), lab)
    df[COL_RATE_PREM]  = df[COL_RATE_PREM].where(df[COL_RATE_PREM].notna(), prem)
    df[COL_RATE_BASIC] = df[COL_RATE_BASIC].where(df[COL_RATE_BASIC].notna(), bas)
    return df

def merge_scenario_book(df):
    if not os.path.exists(SCENARIO_BOOK):
        return df
    try:
        sb = pd.read_excel(SCENARIO_BOOK)
    except Exception:
        return df
    sb.columns = [_norm_header(c) for c in sb.columns]

    ren = {}
    for c in sb.columns:
        if c.lower() in ["scenario","scenario id","scenario_id"]: ren[c] = COL_SCENARIO
        elif c in ["Price Lab","Price (Lab)","Price- Lab",COL_PRICE_LAB]: ren[c] = COL_PRICE_LAB
        elif c in ["Price Premium","Price (Premium)","Price- Premium",COL_PRICE_PREM]: ren[c] = COL_PRICE_PREM
        elif c in ["Price Basic","Price (Basic)","Price- Basic",COL_PRICE_BASIC]: ren[c] = COL_PRICE_BASIC
        elif c in ["Nutrition Lab","Nutrition (Lab)","Nutrition- Lab",COL_NUTR_LAB]: ren[c] = COL_NUTR_LAB
        elif c in ["Nutrition Premium","Nutrition (Premium)","Nutrition- Premium",COL_NUTR_PREM]: ren[c] = COL_NUTR_PREM
        elif c in ["Nutrition Basic","Nutrition (Basic)","Nutrition- Basic",COL_NUTR_BASIC]: ren[c] = COL_NUTR_BASIC
        elif c in ["Sustainability Lab","Sustainability (Lab)","Sustainability- Lab",COL_SUST_LAB]: ren[c] = COL_SUST_LAB
        elif c in ["Sustainability Premium","Sustainability (Premium)","Sustainability- Premium",COL_SUST_PREM]: ren[c] = COL_SUST_PREM
        elif c in ["Sustainability Basic","Sustainability (Basic)","Sustainability- Basic",COL_SUST_BASIC]: ren[c] = COL_SUST_BASIC
        elif c in ["Taste Lab","Taste (Lab)","Taste- Lab",COL_TASTE_LAB]: ren[c] = COL_TASTE_LAB
        elif c in ["Taste Premium","Taste (Premium)","Taste- Premium",COL_TASTE_PREM]: ren[c] = COL_TASTE_PREM
        elif c in ["Taste Basic","Taste (Basic)","Taste- Basic",COL_TASTE_BASIC]: ren[c] = COL_TASTE_BASIC
        elif c == "Price": ren[c] = "Price"
        elif c == "Nutrition": ren[c] = "Nutrition"
        elif c == "Sustainability": ren[c] = "Sustainability"
        elif c == "Taste": ren[c] = "Taste"
    if ren: sb = sb.rename(columns=ren)

    if COL_SCENARIO not in sb.columns:
        sb = sb.rename(columns={sb.columns[0]: COL_SCENARIO})

    df = df.merge(sb, on=COL_SCENARIO, how="left", suffixes=("", "_map"))
    for c in [COL_PRICE_LAB, COL_PRICE_PREM, COL_PRICE_BASIC,
              COL_NUTR_LAB,  COL_NUTR_PREM,  COL_NUTR_BASIC,
              COL_SUST_LAB,  COL_SUST_PREM,  COL_SUST_BASIC,
              COL_TASTE_LAB, COL_TASTE_PREM, COL_TASTE_BASIC,
              "Price","Nutrition","Sustainability","Taste"]:
        cm = f"{c}_map"
        if cm in df.columns:
            df[c] = df[c].where(df[c].notna(), df[cm])
            df.drop(columns=[cm], inplace=True)
    return df

def infer_levels(df):
    """Normalize scenario levels and create both per-tuna and single proxy columns (including Taste)."""
    ordered = pd.CategoricalDtype(categories=["Low","Mid","High"], ordered=True)

    def _normalize_one(x):
        if pd.isna(x):
            return np.nan
        s = str(x).strip().lower()
        # numeric encodings (scenario book now uses 1/2/3)
        try:
            v = float(s)
            if v == 1: return "Low"
            if v == 2: return "Mid"
            if v == 3: return "High"
        except Exception:
            pass
        # letter/word encodings
        if s in {"l","lo","low","lower","lowest"} or "low" in s:
            return "Low"
        if s in {"m","mid","med","medium","middle"} or "medium" in s or "mid" in s:
            return "Mid"
        if s in {"h","hi","high","higher","highest"} or "high" in s:
            return "High"
        return np.nan

    def _norm_series(series):
        vals = series if isinstance(series, pd.Series) else pd.Series(series, index=df.index)
        out = vals.map(_normalize_one)
        return out.astype("category").cat.set_categories(ordered.categories, ordered=True)

    # Normalize any per-tuna columns coming from the scenario book if present
    for c in [COL_PRICE_LAB, COL_PRICE_PREM, COL_PRICE_BASIC,
              COL_NUTR_LAB,  COL_NUTR_PREM,  COL_NUTR_BASIC,
              COL_SUST_LAB,  COL_SUST_PREM,  COL_SUST_BASIC,
              COL_TASTE_LAB, COL_TASTE_PREM, COL_TASTE_BASIC]:
        if c in df.columns:
            df[c] = _norm_series(df[c])

    # Create per-tuna normalized level columns (always present in the snapshot)
    per_tuna_map = [
        ("PriceLvl_Lab",       COL_PRICE_LAB),
        ("PriceLvl_Premium",   COL_PRICE_PREM),
        ("PriceLvl_Basic",     COL_PRICE_BASIC),
        ("NutriLvl_Lab",       COL_NUTR_LAB),
        ("NutriLvl_Premium",   COL_NUTR_PREM),
        ("NutriLvl_Basic",     COL_NUTR_BASIC),
        ("SustainLvl_Lab",     COL_SUST_LAB),
        ("SustainLvl_Premium", COL_SUST_PREM),
        ("SustainLvl_Basic",   COL_SUST_BASIC),
        ("TasteLvl_Lab",       COL_TASTE_LAB),
        ("TasteLvl_Premium",   COL_TASTE_PREM),
        ("TasteLvl_Basic",     COL_TASTE_BASIC),
    ]
    for out_col, src in per_tuna_map:
        if src in df.columns:
            df[out_col] = _norm_series(df[src])
        else:
            df[out_col] = pd.Categorical([np.nan]*len(df), categories=ordered.categories, ordered=True)

    # Single proxies (prefer Lab→Premium→Basic→global)
    for proxy, per_cols, global_col in [
        (COL_PRICE_LVL, [COL_PRICE_LAB, COL_PRICE_PREM, COL_PRICE_BASIC], "Price"),
        (COL_NUTR_LVL,  [COL_NUTR_LAB,  COL_NUTR_PREM,  COL_NUTR_BASIC],  "Nutrition"),
        (COL_SUST_LVL,  [COL_SUST_LAB,  COL_SUST_PREM,  COL_SUST_BASIC],  "Sustainability"),
        (COL_TASTE_LVL, [COL_TASTE_LAB, COL_TASTE_PREM, COL_TASTE_BASIC], "Taste"),
    ]:
        cur = pd.Series([np.nan]*len(df), index=df.index, dtype="object")
        for c in per_cols:
            if c in df.columns:
                cur = cur.where(cur.notna(), df[c])
        if global_col in df.columns:
            cur = cur.where(cur.notna(), df[global_col])
        df[proxy] = _norm_series(cur)

    return df


# -------------------------
# Demographic codebook decoding
# -------------------------
def decode_demographics_with_codebook(df, codebook_path):
    """
    Map numeric-coded demographics to readable labels using Demographic_Codebook.xlsx.
    Each sheet name should correspond to a demographic column (case-insensitive),
    and contain two columns: a code column (e.g., code/value/id/key) and a label column
    (e.g., label/text/name/desc).
    """
    if not os.path.exists(codebook_path):
        return df

    try:
        xls = pd.ExcelFile(codebook_path)
    except Exception:
        return df

    # Helpers to detect code/label columns
    code_keys = {"code","value","val","id","key","num","number"}
    label_keys = {"label","text","name","desc","meaning","category","value_label"}

    for sheet in xls.sheet_names:
        try:
            mapdf = pd.read_excel(xls, sheet_name=sheet)
        except Exception:
            continue
        if mapdf.empty:
            continue

        # normalize headers
        cols = [str(c).strip().lower() for c in mapdf.columns]
        mapdf.columns = cols

        # find code and label columns
        code_col = None
        label_col = None
        for c in cols:
            if any(k == c or k in c for k in code_keys):
                code_col = c
                break
        for c in cols:
            if any(k == c or k in c for k in label_keys):
                label_col = c
                break
        if code_col is None or label_col is None:
            # try two-column fallback
            if len(cols) >= 2:
                code_col, label_col = cols[0], cols[1]
            else:
                continue

        # match sheet name to a column in df (case-insensitive)
        target = None
        for dfcol in df.columns:
            if str(dfcol).strip().lower() == str(sheet).strip().lower():
                target = dfcol
                break
        if target is None:
            # also try title-cased and underscore variants
            for dfcol in df.columns:
                if str(dfcol).replace("_","").strip().lower() == str(sheet).replace("_","").strip().lower():
                    target = dfcol
                    break
        if target is None or target not in df.columns:
            continue

        # build mapping (allow numeric or string codes)
        m = {}
        for _, r in mapdf[[code_col, label_col]].dropna().iterrows():
            m[str(r[code_col]).strip()] = str(r[label_col]).strip()

        # apply mapping
        ser = df[target].astype(object)
        ser_str = ser.astype(str).str.strip()
        mapped = ser_str.map(m)
        # Only replace where mapping exists
        ser = ser.where(~mapped.notna(), mapped)
        # If mapping produced all-NaN, keep original
        if ser.notna().sum() == 0 and df[target].notna().sum() > 0:
            ser = df[target]
        df[target] = ser

        # cast to category for modeling
        df[target] = df[target].astype("category")
    # --- Fallback mapping for Qualtrics-style demographic questions (Q22–Q29) ---
    qualtrics_demo_map = {
        "Q22": "Age",
        "Q23": "Gender",
        "Q24": "Education",
        "Q25": "Marital",
        "Q26": "HouseholdSize",
        "Q27": "Income",
        "Q28": "Employment",
        "Q29": "Urban_Rural"
    }
    for qcol, democol in qualtrics_demo_map.items():
        if qcol in df.columns and democol not in df.columns:
            df = df.rename(columns={qcol: democol})
        # Ensure dtype is category for analysis if present
        if democol in df.columns:
            df[democol] = df[democol].astype("category")
    return df


# --- Add numeric proxy level columns (High=3, Mid=2, Low=1) ---
def add_numeric_level_cols(df):
    """
    Create numeric versions of the proxy factor columns:
      High=3, Mid=2, Low=1.
    Keeps original categorical columns unchanged for modeling.
    """
    mapping = {"Low": 1, "Mid": 2, "High": 3}
    for proxy in [COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL]:
        if proxy in df.columns:
            df[f"{proxy}_num"] = df[proxy].astype(str).map(mapping).astype("Int64")
        else:
            df[f"{proxy}_num"] = pd.Series([pd.NA]*len(df), dtype="Int64")
    return df

def filter_valid_ratings(df):
    for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    mask = df[COL_RATE_LAB].notna() & df[COL_RATE_PREM].notna() & df[COL_RATE_BASIC].notna()
    mask &= (df[COL_RATE_LAB] > 0) & (df[COL_RATE_PREM] > 0) & (df[COL_RATE_BASIC] > 0)
    return df.loc[mask].copy()

# -------------------------
# Clustering + diagnostics
# -------------------------

def _label_centroid(row):
    a = row.get(f"{COL_ATT}_z", 0.0)
    b = row.get(f"{COL_BEH}_z", 0.0)
    e = row.get(f"{COL_ECON}_z", 0.0) if INCLUDE_ECON else 0.0
    if a > 0.4 and b > 0.4 and (e > 0.0 or not INCLUDE_ECON):
        return "Truly Green"
    if a > 0.2 and b < -0.2:
        return "Supportive but Inactive"
    if a < -0.3 and b < -0.3 and (e < -0.2 or not INCLUDE_ECON):
        return "Don’t Care Much"
    return "Supportive but Inactive"

def get_score_matrix(df):
    need = [COL_ATT, COL_BEH] + ([COL_ECON] if INCLUDE_ECON else [])
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Missing score column: {c}")
    X = df[need].astype(float).values
    mask = ~np.isnan(X).any(axis=1)
    scaler = StandardScaler()
    Xz = scaler.fit_transform(X[mask])
    return Xz, mask, need

def silhouette_scan(Xz, k_range=SILHOUETTE_K_RANGE):
    print("\nSilhouette scan (using z-scores of selected inputs):")
    rows = []
    for k in k_range:
        if k <= 1 or k >= len(Xz):
            continue
        km = KMeans(n_clusters=k, n_init=30, random_state=42)
        lab = km.fit_predict(Xz)
        try:
            s = silhouette_score(Xz, lab)
            rows.append({"K": k, "Silhouette": s})
            print(f"  K={k}: silhouette = {s:.3f}")
        except Exception as e:
            print(f"  K={k}: silhouette N/A ({e})")
    if rows:
        best = max(rows, key=lambda r: r["Silhouette"])
        print(f"> Best K by silhouette in {list(k_range)} is {best['K']} (score={best['Silhouette']:.3f})")
    return pd.DataFrame(rows)

def elbow_and_dendrogram(Xz):
    inertias, Ks = [], range(1, 11)
    for k in Ks:
        km = KMeans(n_clusters=k, n_init=20, random_state=42).fit(Xz)
        inertias.append(km.inertia_)
    plt.figure(figsize=(6,4))
    plt.plot(list(Ks), inertias, marker='o')
    plt.xlabel("K"); plt.ylabel("Inertia"); plt.title("Elbow method")
    plt.grid(True, alpha=.4); plt.tight_layout()
    plt.savefig("out/plots/elbow_method.png", dpi=200); plt.close()

    Z = linkage(Xz, method="ward")
    plt.figure(figsize=(10,6))
    dendrogram(Z, truncate_mode='level', p=5)
    plt.title("Hierarchical dendrogram (Ward)"); plt.xlabel("Samples"); plt.ylabel("Distance")
    plt.tight_layout(); plt.savefig("out/plots/hierarchical_dendrogram.png", dpi=200); plt.close()

    return pd.DataFrame({"K": list(Ks), "Inertia": inertias})

def assign_clusters(df, k=K_ANALYSIS):
    Xz, mask, need = get_score_matrix(df)
    sil_tbl = silhouette_scan(Xz, SILHOUETTE_K_RANGE)
    elbow_tbl = elbow_and_dendrogram(Xz)

    km = KMeans(n_clusters=k, n_init=30, random_state=42).fit(Xz)
    labels = km.labels_

    df = df.copy()
    df["_k_id"] = np.nan
    df.loc[df.index[mask], "_k_id"] = labels

    cents = pd.DataFrame(km.cluster_centers_, columns=[f"{c}_z" for c in need])
    cents["ClusterID"] = range(k)
    cents["Name"] = cents.apply(_label_centroid, axis=1)
    id2name = dict(zip(cents["ClusterID"], cents["Name"]))
    df["Category"] = df["_k_id"].map(id2name)

    cnt = df["Category"].value_counts(dropna=False)
    ax = cnt.plot(kind="bar", rot=0, title=f"Cluster counts (K={k})")
    for i, v in enumerate(cnt.values):
        ax.text(i, v + 0.5, str(v), ha="center")
    plt.tight_layout(); plt.savefig("out/plots/cluster_counts.png", dpi=200); plt.close()

    cents.to_csv("out/cluster_centroids_k3.csv", index=False)
    elbow_tbl.to_excel("out/Elbow_Inertia.xlsx", index=False)

    return df, cents, Xz, labels, elbow_tbl, sil_tbl

# -------------------------
# Analyses
# -------------------------

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

def factorial_anovas(df):
    """
    Type III ANOVAs per tuna using the SAME factors for all tunas:
      C(Category) + C(PriceLvl) + C(NutriLvl) + C(TasteLvl)
      + all two-way interactions among PriceLvl, NutriLvl, TasteLvl.
    """
    res = {}
    out_path = "out/ANOVA_Factorial_ByTuna.xlsx"
    os.makedirs("out", exist_ok=True)
    base_factors = [COL_PRICE_LVL, COL_NUTR_LVL, COL_TASTE_LVL]

    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        any_written = False
        for col, tuna in [(COL_RATE_LAB,"Lab"), (COL_RATE_PREM,"Premium"), (COL_RATE_BASIC,"Basic")]:
            if col not in df.columns:
                continue
            # Require presence of all three base factors
            if any(f not in df.columns for f in base_factors):
                pd.DataFrame({"note":[f"{tuna}: missing one or more factor columns (PriceLvl/NutriLvl/TasteLvl)."]}).to_excel(
                    xw, sheet_name=f"{tuna}_Notes", index=False
                )
                continue
            sub = df[[col, "Category"] + base_factors].dropna()
            if sub.empty or sub["Category"].astype(str).nunique() < 2:
                pd.DataFrame({"note":[f"{tuna}: no analyzable rows or insufficient cluster levels."]}).to_excel(
                    xw, sheet_name=f"{tuna}_Notes", index=False
                )
                continue
            # Ensure each factor has >=2 levels in the subset
            enough = True
            levels_meta = {}
            for f in base_factors:
                lv = sub[f].astype(str).nunique()
                levels_meta[f] = lv
                if lv < 2:
                    enough = False
            if not enough:
                meta = pd.DataFrame({"factor": list(levels_meta.keys()), "n_levels": list(levels_meta.values())})
                meta.to_excel(xw, sheet_name=f"{tuna}_Levels", index=False)
                pd.DataFrame({"note":[f"{tuna}: at least one factor has <2 levels in available rows."]}).to_excel(
                    xw, sheet_name=f"{tuna}_Notes", index=False
                )
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
                a3.to_excel(xw, sheet_name=tuna, index=False)
                # meta sheet
                pd.DataFrame({
                    "Rows_Used":[len(sub)],
                    "Levels_Price":[levels_meta[COL_PRICE_LVL]],
                    "Levels_Nutrition":[levels_meta[COL_NUTR_LVL]],
                    "Levels_Taste":[levels_meta[COL_TASTE_LVL]]
                }).to_excel(xw, sheet_name=f"{tuna}_Meta", index=False)
                res[tuna] = a3
                any_written = True
            except Exception as e:
                pd.DataFrame({"error":[str(e)]}).to_excel(xw, sheet_name=f"{tuna}_Error", index=False)

        if not any_written:
            pd.DataFrame({"note":["No analyzable data for factorial ANOVAs."]}).to_excel(xw, sheet_name="Notes", index=False)

    return res

def anova_with_demographics(df):
    """
    Type III ANOVAs per tuna including demographics as additional main effects.
    Always creates out/ANOVA_With_Demographics.xlsx with at least one visible sheet.
    Tolerant to sparse demographics and factor coverage.
    """
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    os.makedirs("out", exist_ok=True)
    out_path = "out/ANOVA_With_Demographics.xlsx"
    TUKEY_ALPHA = 0.05

    # thresholds (relax if your data is sparse)
    MIN_PROP_OVERALL = 0.10   # keep demo if >=10% non-null overall OR >= MIN_ROWS
    MIN_PROP_SUBSET  = 0.10   # and >=10% non-null within the tuna subset
    MIN_ROWS         = 10

    # Prefer per‑tuna factors; fallback to proxies; include Sustainability + Taste
    per_map = {
        COL_RATE_LAB:   ["PriceLvl_Lab","NutriLvl_Lab","SustainLvl_Lab","TasteLvl_Lab"],
        COL_RATE_PREM:  ["PriceLvl_Premium","NutriLvl_Premium","SustainLvl_Premium","TasteLvl_Premium"],
        COL_RATE_BASIC: ["PriceLvl_Basic","NutriLvl_Basic","SustainLvl_Basic","TasteLvl_Basic"],
    }
    proxy_factors = [COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL]

    # 1) Pick demographics that have some data overall
    demo_candidates = [d for d in DEMOG_COLS if d in df.columns]
    n_total = len(df)
    demo_overall = []
    for d in demo_candidates:
        nonnull = df[d].notna().sum()
        if nonnull >= max(MIN_ROWS, int(MIN_PROP_OVERALL * n_total)):
            demo_overall.append(d)

    # --- open writer and create an initial Notes sheet so the file is always valid ---
    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        # Seed a Notes sheet first; we’ll append more sheets after
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

            # keep only factors that vary within this subset
            facs_use = [f for f in facs if base[f].dropna().astype(str).nunique() >= 2]
            if not facs_use:
                notes_msgs.append(f"{tuna}: no scenario factor shows >=2 levels in available rows.")
                continue
            base = base[[col, "Category"] + facs_use]

            # 2) pick demographics that still have coverage within this subset
            demo_use, dropped_demo = [], []
            idx = base.index
            for d in demo_overall:
                s = df.loc[idx, d]
                nn = s.notna().sum()
                nu = s.dropna().astype(str).nunique()
                if nn >= max(MIN_ROWS, int(MIN_PROP_SUBSET * len(base))) and nu >= 2:
                    demo_use.append(d)
                else:
                    dropped_demo.append({"demo": d, "nonnull_in_subset": int(nn), "levels_in_subset": int(nu)})

            sub = df.loc[idx, [col, "Category"] + facs_use + demo_use].dropna(subset=[col, "Category"]).copy()
            if sub.empty or sub["Category"].astype(str).nunique() < 2:
                notes_msgs.append(f"{tuna}: insufficient data after merging demographics.")
                continue

            sub["Category"] = sub["Category"].astype("category")
            for f in facs_use:
                sub[f] = sub[f].astype("category")

            rhs = "C(Category)" + "".join([f" + C({f})" for f in facs_use])
            for d in demo_use:
                if (not pd.api.types.is_numeric_dtype(sub[d])) or (sub[d].nunique(dropna=True) <= 12):
                    sub[d] = sub[d].astype("category")
                    rhs += f" + C({d})"
                else:
                    rhs += f" + {d}"

            model_df = sub[[col, "Category"] + facs_use + demo_use].dropna()
            if len(model_df) < max(MIN_ROWS, 8):
                notes_msgs.append(f"{tuna}: <{max(MIN_ROWS,8)} complete rows after NA removal.")
                # still log what would have been used
                pd.DataFrame({
                    "Predictors_Proposed":[rhs],
                    "Rows_Complete":[len(model_df)],
                    "Demographics_Considered":[", ".join(demo_use) if demo_use else "(none)"]
                }).to_excel(xw, sheet_name=f"{tuna}_Meta", index=False)
                continue

            try:
                model = smf.ols(f"{col} ~ {rhs}", data=model_df).fit()
                a3 = sm.stats.anova_lm(model, typ=3).rename_axis("Source").reset_index()
                a3.insert(0, "Tuna", tuna)
                a3.to_excel(xw, sheet_name=tuna, index=False)
                # meta sheets
                pd.DataFrame({
                    "Predictors_Used":[rhs],
                    "Rows_Used":[len(model_df)],
                    "Demographics_Used":[", ".join(demo_use) if demo_use else "(none)"]
                }).to_excel(xw, sheet_name=f"{tuna}_Meta", index=False)
                if dropped_demo:
                    pd.DataFrame(dropped_demo).to_excel(xw, sheet_name=f"{tuna}_DroppedDemos", index=False)
                any_result = True
                # --- NEW: Post-hoc Tukey HSD for categorical demographics ---
                # Default: run post-hoc for any categorical demographic that is significant at alpha,
                # PLUS always run Male vs Female post-hoc for Gender if analysable (>=2 per group),
                # even if Gender was not significant in the Type III ANOVA.
                try:
                    TUKEY_ALPHA = 0.05

                    # Normalize p-value column name defensively
                    pcol = None
                    for cand in ["PR(>F)", "Pr(>F)", "p", "pvalue", "p-value"]:
                        if cand in a3.columns:
                            pcol = cand
                            break

                    # Identify significant categorical demographics among those actually used in the model
                    sig_demos = []
                    if pcol is not None:
                        for d in demo_use:
                            # Only consider categorical demos for post-hoc
                            is_cat = (not pd.api.types.is_numeric_dtype(model_df[d])) or (model_df[d].nunique(dropna=True) <= 12)
                            if not is_cat:
                                continue
                            a3_key = f"C({d})"
                            try:
                                pval = float(a3.loc[a3["Source"] == a3_key, pcol].values[0])
                            except Exception:
                                pval = np.nan
                            if pd.notna(pval) and pval <= TUKEY_ALPHA:
                                sig_demos.append(d)

                    # Always attempt Gender post-hoc (Male vs Female) if data supports it,
                    # even if Gender wasn't significant or wasn't included in the ANOVA model.
                    ALWAYS_GENDER_POSTHOC = True
                    if ALWAYS_GENDER_POSTHOC and ("Gender" in df.columns):
                        # Build from the *same row subset* used by the model (index = model_df.index if available)
                        idx_for_gender = model_df.index if 'model_df' in locals() else base.index
                        tmp_g = df.loc[idx_for_gender, [col, "Gender"]].dropna().copy()
                        if not tmp_g.empty:
                            s = tmp_g["Gender"].astype(str).str.strip()
                            # Map common encodings to canonical labels
                            map_to_label = {
                                "1": "Male", "male": "Male", "m": "Male",
                                "2": "Female", "female": "Female", "f": "Female",
                            }
                            s_norm = s.str.lower().map(map_to_label).fillna(s.str.title())
                            keep_mask = s_norm.isin(["Male", "Female"])
                            tmp_g = tmp_g.loc[keep_mask].copy()
                            tmp_g["Gender"] = s_norm.loc[keep_mask]
                            # Only add to post-hoc queue if both Male and Female exist with >= 2 rows each
                            if (tmp_g["Gender"].nunique() >= 2) and (tmp_g.groupby("Gender")[col].size().min() >= 2):
                                if "Gender" not in sig_demos:
                                    sig_demos.append("Gender")

                    # Helper for Excel-safe sheet names (31 char limit)
                    def _sheet(name: str) -> str:
                        return (name[:31]) if len(name) > 31 else name

                    # Run Tukey per demographic in sig_demos (which now may include Gender even if not significant)
                    from statsmodels.stats.multicomp import pairwise_tukeyhsd
                    for d in sig_demos:
                        # Build two-column frame for DV and the demographic factor
                        # Use model_df rows if available so we align with the ANOVA sample; else fall back to base
                        idx_for_demo = model_df.index if 'model_df' in locals() else base.index
                        tmp = df.loc[idx_for_demo, [col, d]].dropna().copy()

                        # Special handling: limit Gender post-hoc to Male/Female only and map codes → labels
                        if str(d).strip().lower() == "gender":
                            s = tmp[d].astype(str).str.strip()
                            map_to_label = {
                                "1": "Male", "male": "Male", "m": "Male",
                                "2": "Female", "female": "Female", "f": "Female",
                            }
                            s_norm = s.str.lower().map(map_to_label).fillna(s.str.title())
                            keep_mask = s_norm.isin(["Male", "Female"])
                            tmp = tmp.loc[keep_mask].copy()
                            tmp[d] = s_norm.loc[keep_mask]

                        # Ensure group column is string for Tukey
                        tmp[d] = tmp[d].astype(str)

                        # Need at least two groups, each with at least 2 rows
                        if tmp.empty or tmp[d].nunique() < 2 or tmp.groupby(d)[col].size().min() < 2:
                            pd.DataFrame({
                                "note":[f"{d}: not enough data per group for Tukey (need ≥2 groups and ≥2 rows per group)."],
                                "groups_present": [", ".join(sorted(tmp[d].unique())) if not tmp.empty else "(none)"]
                            }).to_excel(
                                xw, sheet_name=_sheet(f"{tuna}_PH_{d}_Notes"), index=False
                            )
                            continue

                        try:
                            tk = pairwise_tukeyhsd(
                                endog=pd.to_numeric(tmp[col], errors="coerce"),
                                groups=tmp[d],
                                alpha=TUKEY_ALPHA
                            )
                            tk_tbl = pd.DataFrame(tk._results_table.data[1:], columns=tk._results_table.data[0])

                            # Group means with readable labels
                            means = (tmp.groupby(d)[col]
                                     .agg(["mean","std","count"])
                                     .reset_index()
                                     .rename(columns={"mean":"Mean","std":"Std. Deviation","count":"N"}))

                            # If this is Gender, ensure only 'Male' and 'Female' appear and in a consistent order
                            if str(d).strip().lower() == "gender":
                                order = ["Male", "Female"]
                                means[d] = pd.Categorical(means[d], categories=order, ordered=True)
                                means = means.sort_values(d)

                            # Write sheets
                            tk_sheet = _sheet(f"{tuna}_PH_{d}")
                            gm_sheet = _sheet(f"{tuna}_PH_{d}_Means")
                            tk_tbl.to_excel(xw, sheet_name=tk_sheet, index=False)
                            means.to_excel(xw, sheet_name=gm_sheet, index=False)

                            # Add a note if Gender post-hoc was run without significance
                            if str(d).strip().lower() == "gender" and pcol is not None:
                                try:
                                    a3_key = "C(Gender)"
                                    pval_gender = float(a3.loc[a3["Source"] == a3_key, pcol].values[0])
                                except Exception:
                                    pval_gender = np.nan
                                if not (pd.notna(pval_gender) and pval_gender <= TUKEY_ALPHA):
                                    pd.DataFrame({
                                        "note": [f"Gender post-hoc (Male vs Female) was run even though the main effect was not significant at α={TUKEY_ALPHA}."],
                                        "ANOVA_p_for_Gender": [pval_gender]
                                    }).to_excel(xw, sheet_name=_sheet(f"{tuna}_PH_Gender_Notes2"), index=False)

                        except Exception as e:
                            pd.DataFrame({"error":[str(e)], "demo":[d]}).to_excel(
                                xw, sheet_name=_sheet(f"{tuna}_PH_{d}_Error"), index=False
                            )
                except Exception as e:
                    # Do not fail the whole workbook if post-hoc step errors; just log the issue.
                    pd.DataFrame({"posthoc_error":[str(e)]}).to_excel(xw, sheet_name=f"{tuna}_PH_Error", index=False)
            except Exception as e:
                pd.DataFrame({"error":[str(e)], "Predictors":[rhs]}).to_excel(xw, sheet_name=f"{tuna}_Error", index=False)

        # Write/refresh Notes last (so there is always at least one visible sheet)
        if not notes_msgs and any_result:
            notes_msgs = ["ANOVA with demographics ran successfully for at least one tuna. See sheets."]
        elif not any_result and not notes_msgs:
            notes_msgs = ["No analyzable data for ANOVA with demographics after filtering."]
        pd.DataFrame({"notes": notes_msgs}).to_excel(xw, sheet_name="Notes", index=False)

    # Return empty dict to keep caller compatible
    return {}


# -------------------------
# Descriptive tables by demographics (PI-style summaries)
# -------------------------
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

def _fmt_p(p):
    try:
        p = float(p)
    except:
        return "p = NA"
    return "p < .001" if p < 0.001 else f"p = {p:.3f}".replace("0.", ".")

def _fmt_eta(e):
    return "" if e is None or pd.isna(e) else f", η² = {e:.2f}"

def apa_oneway(oneway):
    lines = ["One-way ANOVAs by cluster (Dependent variable: rating)"]
    if oneway is None or oneway.empty:
        lines.append("  (no analyzable data)")
        return lines
    for _, r in oneway.iterrows():
        try:
            df1 = int(round(r["df1"])); df2 = int(round(r["df2"]))
            Fv  = float(r["F"]); pv = float(r["p"])
            eta = float(r["eta2"]) if "eta2" in r and pd.notna(r["eta2"]) else None
            lines.append(f"  {r['Tuna']}: F({df1}, {df2}) = {Fv:.2f}, {_fmt_p(pv)}{_fmt_eta(eta)}")
        except:
            continue
    lines.append("")
    return lines

def apa_factorial(fact_dict):
    """
    Build APA-style lines for factorial ANOVAs.
    Includes Cluster + (Price, Nutrition, Taste) mains
    and all two-way interactions among those three scenario factors.
    Works whether tables used proxy names (e.g., PriceLvl) or per-tuna names.
    """
    import re

    lines = ["Factorial ANOVAs (Type III): rating ~ Cluster + Price + Nutrition + Taste + two-way interactions"]
    if not fact_dict:
        lines.append("  (no analyzable data)")
        return lines

    # Regex buckets to normalize per-tuna names to semantic factors
    MAIN_PATTERNS = [
        (re.compile(r"^C\((PriceLvl(?:_(Lab|Premium|Basic))?)\)$"), "Price"),
        (re.compile(r"^C\((NutriLvl(?:_(Lab|Premium|Basic))?)\)$"), "Nutrition"),
        (re.compile(r"^C\((TasteLvl(?:_(Lab|Premium|Basic))?)\)$"), "Taste"),
        (re.compile(r"^C\(Category\)$"), "Cluster"),
    ]

    # For interactions, we normalize each side using the same bucket logic
    def normalize_factor(src: str):
        for pat, pretty in MAIN_PATTERNS:
            if pat.match(src):
                return pretty
        return None

    def parse_source_label(src: str):
        """
        Return pretty label for a main effect or two-way interaction we care about;
        otherwise return None to skip.
        """
        src = str(src)
        # Main effects
        pretty = normalize_factor(src)
        if pretty is not None and pretty != "Cluster":
            return pretty  # report only scenario mains here; Cluster handled by oneway

        # Interactions: expect like 'C(A):C(B)'
        m = re.match(r"^C\(([^)]+)\):C\(([^)]+)\)$", src)
        if m:
            left = normalize_factor(f"C({m.group(1)})")
            right = normalize_factor(f"C({m.group(2)})")
            PAIRS_KEEP = {"Price","Nutrition","Taste"}
            if left in PAIRS_KEEP and right in PAIRS_KEEP and left != right:
                # Alphabetize for consistent labeling
                a, b = sorted([left, right])
                return f"{a} × {b}"
        return None

    for tuna, tbl in fact_dict.items():
        lines.append(f"  {tuna}:")
        # Residual df for denominator
        try:
            df2_vals = tbl.loc[tbl["Source"] == "Residual", "df"].values
            df2 = int(round(float(df2_vals[0]))) if len(df2_vals) else None
        except Exception:
            df2 = None

        # Collect the strongest (first) row per label (in case both proxy and per-tuna appear)
        reported = set()
        for _, row in tbl.iterrows():
            src = row.get("Source", "")
            label = parse_source_label(src)
            if label is None or label in reported:
                continue
            try:
                df1 = int(round(float(row["df"])))
                Fv  = float(row["F"])
                pv  = float(row["PR(>F)"])
            except Exception:
                continue
            if df2 is not None and not (pd.isna(Fv) or pd.isna(pv)):
                lines.append(f"    {label}: F({df1}, {df2}) = {Fv:.2f}, {_fmt_p(pv)}")
                reported.add(label)

        if not reported:
            lines.append("    (no analyzable terms)")
        lines.append("")

    return lines

def save_apa(oneway, factorial):
    lines = []
    lines += apa_oneway(oneway)
    lines += apa_factorial(factorial)

    # de-duplicate adjacent lines to avoid accidental repeats
    cleaned = []
    for i, ln in enumerate(lines):
        if i == 0 or ln != lines[i-1]:
            cleaned.append(ln)

    with open("out/APA_F_Reports.txt","w",encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    return "out/APA_F_Reports.txt"

def _plot_effect_lines(df, level_col, title, xlab, outname):
    order = ["Low", "Mid", "High"]
    if level_col not in df.columns: 
        plt.figure(figsize=(11,7))
        plt.title(title, fontsize=22, pad=12)
        plt.text(0.5, 0.5, "No such factor column", ha="center", va="center", fontsize=14)
        plt.axis("off")
        plt.tight_layout(); plt.savefig(outname, dpi=200); plt.close()
        return

    rcols = [c for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC] if c in df.columns]
    if not rcols:
        plt.figure(figsize=(11,7))
        plt.title(title, fontsize=22, pad=12)
        plt.text(0.5, 0.5, "No rating columns found", ha="center", va="center", fontsize=14)
        plt.axis("off")
        plt.tight_layout(); plt.savefig(outname, dpi=200); plt.close()
        return

    work = df.dropna(subset=[level_col])[[level_col] + rcols].copy()
    for rc in rcols:
        work[rc] = pd.to_numeric(work[rc], errors="coerce")
    work = work.dropna(subset=rcols, how="all")

    if work.empty:
        plt.figure(figsize=(11,7))
        plt.title(title, fontsize=22, pad=12)
        plt.xlabel(xlab, fontsize=16); plt.ylabel("Mean Rating", fontsize=16)
        plt.xticks(ticks=range(3), labels=[f"{lv}\n(n=0)" for lv in order])
        plt.text(0.5, 0.5, "No data after filtering", ha="center", va="center", fontsize=14)
        plt.ylim(0,7); plt.grid(True, alpha=.25, linestyle="--")
        plt.tight_layout(); plt.savefig(outname, dpi=200); plt.close()
        return

    # Ensure the factor is in Low/Mid/High; if numeric 1/2/3, map first.
    mapping_num = {1: "Low", 2: "Mid", 3: "High", 1.0: "Low", 2.0: "Mid", 3.0: "High"}
    if pd.api.types.is_numeric_dtype(work[level_col]):
        work[level_col] = work[level_col].map(mapping_num)
    else:
        # sometimes numeric strings like "1", "2", "3"
        work[level_col] = work[level_col].replace({"1":"Low","2":"Mid","3":"High"})
    try:
        work[level_col] = work[level_col].astype("category").cat.set_categories(order, ordered=True)
    except Exception:
        pass

    n_per = work.groupby(level_col)[rcols[0]].size().reindex(order).fillna(0).astype(int)
    means = {col: work.groupby(level_col)[col].mean().reindex(order) for col in rcols}
    grid = pd.DataFrame(means)

    if grid.isna().all().all():
        plt.figure(figsize=(11,7))
        plt.title(title, fontsize=22, pad=12)
        plt.xlabel(xlab, fontsize=16); plt.ylabel("Mean Rating", fontsize=16)
        plt.xticks(ticks=range(3), labels=[f"{lv}\n(n={int(n_per.get(lv,0))})" for lv in order])
        plt.text(0.5, 0.5, "No valid means to plot", ha="center", va="center", fontsize=14)
        plt.ylim(0,7); plt.grid(True, alpha=.25, linestyle="--")
        plt.tight_layout(); plt.savefig(outname, dpi=200); plt.close()
        return

    legend_map = {COL_RATE_LAB: "Lab", COL_RATE_PREM: "Premium", COL_RATE_BASIC: "Basic"}
    grid = grid.rename(columns=legend_map)
    xticks = [f"{lvl}\n(n={int(n_per.get(lvl, 0))})" for lvl in order]

    plt.figure(figsize=(11, 7))
    for col in grid.columns:
        y = grid[col].values.astype(float)
        plt.plot(grid.index, y, marker='o', linewidth=3, label=col)
        for i, v in enumerate(y):
            if not np.isnan(v):
                plt.text(i, v + 0.08, f"{v:.2f}", ha='center', va='bottom', fontsize=11)
    plt.title(title, fontsize=22, pad=12)
    plt.xlabel(xlab, fontsize=16); plt.ylabel("Mean Rating", fontsize=16)
    plt.ylim(1, 7); plt.grid(True, alpha=0.25, linestyle='--')
    plt.legend(title=None, frameon=True, fontsize=16)
    plt.xticks(ticks=range(len(xticks)), labels=xticks)
    plt.tight_layout()
    plt.savefig(outname, dpi=200)
    plt.close()

def plot_everything(df, Xz=None, labels=None):
    _plot_effect_lines(df, COL_PRICE_LVL, "Price effect on ratings (by tuna)", "Price Level", "out/plots/plot_price_effect.png")
    _plot_effect_lines(df, COL_NUTR_LVL,  "Nutrition effect on ratings (by tuna)", "Nutrition Level", "out/plots/plot_nutrition_effect.png")
    # _plot_effect_lines(df, COL_SUST_LVL,  "Sustainability effect on ratings (by tuna)", "Sustain Level", "out/plots/plot_sustain_effect.png")
    # NEW: Taste effect plot
    _plot_effect_lines(df, COL_TASTE_LVL, "Taste effect on ratings (by tuna)", "Taste Level", "out/plots/plot_taste_effect.png")

    # 2D cluster scatter on raw Likert scores (1–7) for Attitude vs Behavior
    try:
        if "Category" in df.columns and COL_ATT in df.columns and COL_BEH in df.columns:
            plot_df = df[[COL_ATT, COL_BEH, "Category"]].dropna()

            # Fixed color map for clusters
            color_map = {
                "Don’t Care Much": "tab:blue",   # blue
                "Truly Green": "tab:green",      # green
                "Supportive but Inactive": "tab:orange",  # orange
            }

            # Order legend exactly as requested
            legend_order = [
                "Don’t Care Much",
                "Supportive but Inactive",
                "Truly Green",
            ]

            plt.figure(figsize=(6,5))
            for name in legend_order:
                sub = plot_df.loc[plot_df["Category"] == name]
                if sub.empty:
                    continue
                plt.scatter(
                    sub[COL_ATT], sub[COL_BEH],
                    s=40, alpha=0.85, edgecolors="none",
                    color=color_map.get(name, "tab:gray"),
                    label=name,
                )

            # Axes on 1–7 Likert scale with a tiny margin so 7 isn't clipped
            plt.xlabel("Attitude (1–7)")
            plt.ylabel("Behavior (1–7)")
            plt.title("Clusters in Attitude vs Behavior (raw Likert)")
            plt.xlim(0.9, 7.1)
            plt.ylim(0.9, 7.1)
            plt.xticks(range(1, 8))
            plt.yticks(range(1, 8))
            plt.margins(x=0.02, y=0.02)
            plt.grid(True, alpha=.3)

            # Legend uses the plotted handles to ensure color/label match
            plt.legend(title="Cluster", loc="best", frameon=True)

            plt.tight_layout()
            plt.savefig("out/plots/attitude_behavior_clusters.png", dpi=200)
            plt.close()
    except Exception:
        pass

def print_status(label, patterns):
    exists = any([any(glob.glob(p)) for p in patterns])
    status = "(outputted)" if exists else "(failed to output)"
    print(f"   - {label} {status}")

# -------------------------
# Main
# -------------------------

def main():
    setup_outdir()
    df = load_data()
    df = compute_scores(df)
    df = extract_single_scenario_ratings(df)
    df = merge_scenario_book(df)
    df = infer_levels(df)
    df = decode_demographics_with_codebook(df, DEMO_CODEBOOK)
    df = add_numeric_level_cols(df)
    df = filter_valid_ratings(df)

    # Show counts for Low/Mid/High so we can see factor coverage
    for c in ["PriceLvl_Lab","PriceLvl_Premium","PriceLvl_Basic",
              "NutriLvl_Lab","NutriLvl_Premium","NutriLvl_Basic",
              "SustainLvl_Lab","SustainLvl_Premium","SustainLvl_Basic",
              "TasteLvl_Lab","TasteLvl_Premium","TasteLvl_Basic",
              COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL]:
        if c in df.columns:
            print(f"{c}: non-null = {int(df[c].notna().sum())}")

    need = [COL_ATT, COL_BEH] + ([COL_ECON] if INCLUDE_ECON else [])
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Missing expected score column: {c}. Turn COMPUTE_SCORES=True if needed.")

    df, cents, Xz, labels, elbow_tbl, sil_tbl = assign_clusters(df, k=K_ANALYSIS)

    desc = descriptives(df)
    one_way = one_way_anovas(df)
    # --- Make sure 'p' column exists for downstream Tukey ---
    if one_way is not None and not one_way.empty and "p" not in one_way.columns:
        for alt in ["PR(>F)", "pvalue", "p-value"]:
            if alt in one_way.columns:
                one_way = one_way.rename(columns={alt: "p"})
                break
    tukey_posthoc(df, one_way, out_path="out/PostHoc_ByCluster.xlsx")
    fact = factorial_anovas(df)
    anova_demo = anova_with_demographics(df)
    # Descriptive tables by demographics (PI-style summaries)
    descriptive_by_demographics(df)
    manova_text = manova_joint(df)
    ols_out = ols_by_tuna(df)

    with pd.ExcelWriter("out/Descriptives.xlsx", engine="openpyxl") as xw:
        desc["Overall"].to_excel(xw, sheet_name="Overall")
        if not desc["ByCluster"].empty:
            desc["ByCluster"].to_excel(xw, sheet_name="ByCluster")
        if elbow_tbl is not None and not elbow_tbl.empty:
            elbow_tbl.to_excel(xw, sheet_name="Elbow_Inertia", index=False)
        if sil_tbl is not None and not sil_tbl.empty:
            sil_tbl.to_excel(xw, sheet_name="Silhouette", index=False)

    apa_path = save_apa(one_way, fact)
    plot_everything(df, Xz=Xz, labels=labels)

    # Participant snapshot (includes SustainLvl and Taste)
    front = [COL_PID, COL_SCENARIO, COL_ATT, COL_BEH] + ([COL_ECON] if COL_ECON in df.columns else []) \
            + ["Category",
               # single proxies (categorical)
               COL_PRICE_LVL, COL_NUTR_LVL, COL_SUST_LVL, COL_TASTE_LVL,
               # numeric proxies (High=3, Mid=2, Low=1)
               f"{COL_PRICE_LVL}_num", f"{COL_NUTR_LVL}_num", f"{COL_SUST_LVL}_num", f"{COL_TASTE_LVL}_num",
               # include raw 'Taste' column if present in scenario book
               "Taste",
               # per-tuna proxies (categorical)
               "PriceLvl_Lab","PriceLvl_Premium","PriceLvl_Basic",
               "NutriLvl_Lab","NutriLvl_Premium","NutriLvl_Basic",
               "SustainLvl_Lab","SustainLvl_Premium","SustainLvl_Basic",
               "TasteLvl_Lab","TasteLvl_Premium","TasteLvl_Basic",
               # ratings
               COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC]
    front = [c for c in front if c in df.columns]
    rest  = [c for c in df.columns if c not in front]
    df_out = df[front + rest].copy()
    df_out.to_excel("out/participant_analysis_snapshot.xlsx", index=False)

    print(f"\nChosen K for analysis: {K_ANALYSIS} (diagnostics plotted across K={SILHOUETTE_K_RANGE.start}..{SILHOUETTE_K_RANGE.stop-1})")
    print("\n✅ Done. Outputs in ./out/")
    if one_way is not None and not one_way.empty:
        one_way.to_excel("out/ANOVA_OneWay_ByCluster.xlsx", index=False)
    else:
        with pd.ExcelWriter("out/ANOVA_OneWay_ByCluster.xlsx", engine="openpyxl") as xw:
            pd.DataFrame({"note": ["No analyzable one-way ANOVAs."]}).to_excel(xw, sheet_name="Notes", index=False)

    print_status("Descriptives.xlsx", ["out/Descriptives.xlsx"])
    print_status("ANOVA_OneWay_ByCluster.xlsx", ["out/ANOVA_OneWay_ByCluster.xlsx"])
    print_status("PostHoc_ByCluster.xlsx", ["out/PostHoc_ByCluster.xlsx"])
    print_status("ANOVA_Factorial_ByTuna.xlsx", ["out/ANOVA_Factorial_ByTuna.xlsx"])
    print_status("ANOVA_With_Demographics.xlsx", ["out/ANOVA_With_Demographics.xlsx"])
    print_status("Descriptive_By_Demographics.xlsx", ["out/Descriptive_By_Demographics.xlsx"])
    print_status("MANOVA_joint.txt", ["out/MANOVA_joint.txt"])
    print_status("OLS_ByTuna.xlsx", ["out/OLS_ByTuna.xlsx"])
    print_status("APA_F_Reports.txt", ["out/APA_F_Reports.txt"])
    print_status("participant_analysis_snapshot.xlsx", ["out/participant_analysis_snapshot.xlsx"])
    print_status("cluster_centroids_k3.csv", ["out/cluster_centroids_k3.csv"])
    print_status("plots", ["out/plots/*.png"])

if __name__ == "__main__":
    main()