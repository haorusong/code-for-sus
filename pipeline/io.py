from config.constants import *
import os, re
import numpy as np
import pandas as pd
def _norm_header(s):
    s = str(s).replace("\u00A0"," ").replace("\u2007"," ").replace("\u202F"," ")
    return " ".join(s.strip().split())



def load_data(path=DATA_FILE):
    if str(path).lower().endswith(".csv"):
        return load_data_from_qualtrics_csv(path)
    df = pd.read_excel(path)
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



def merge_scenario_book(df, scenario_book_path=SCENARIO_BOOK):
    if not os.path.exists(SCENARIO_BOOK):
        return df
    try:
        sb = pd.read_excel(scenario_book_path)
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
    """Normalize scenario levels and create both per-tuna and single proxy columns (including Taste).

    Also preserves pre-normalized scenario-book values (e.g., dollar prices) in `*_raw` columns.
    """
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

    # Preserve raw scenario-book values before normalization (useful for dollar-price analyses)
    for c in [COL_PRICE_LAB, COL_PRICE_PREM, COL_PRICE_BASIC,
              COL_NUTR_LAB,  COL_NUTR_PREM,  COL_NUTR_BASIC,
              COL_SUST_LAB,  COL_SUST_PREM,  COL_SUST_BASIC,
              COL_TASTE_LAB, COL_TASTE_PREM, COL_TASTE_BASIC]:
        if c in df.columns and f"{c}_raw" not in df.columns:
            df[f"{c}_raw"] = df[c]

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


def filter_valid_ratings(df):
    for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    mask = df[COL_RATE_LAB].notna() & df[COL_RATE_PREM].notna() & df[COL_RATE_BASIC].notna()
    mask &= (df[COL_RATE_LAB] > 0) & (df[COL_RATE_PREM] > 0) & (df[COL_RATE_BASIC] > 0)
    return df.loc[mask].copy()

# -------------------------
# Clustering + diagnostics
# -------------------------





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


def load_data_from_qualtrics_csv(path, scenario_book_path=SCENARIO_BOOK):
    """
    Load a raw Qualtrics CSV export (new survey format).

    Qualtrics exports 3 header rows:
      row 0 = column header names  (kept as df.columns)
      row 1 = question text        (skipped)
      row 2 = import IDs           (skipped)

    Each respondent saw exactly ONE scenario block (Q42–Q71).
    Scenario n maps to Q(41+n): Q42→1, Q43→2, …, Q71→30.

    USD prices by Q-range (from original study design):
      Q42-47 : Basic $4.00, Premium $6.50, Lab $7.50
      Q48-53 : Basic $5.00, Premium $5.00, Lab $6.50
      Q54-59 : Basic $4.50, Premium $6.50, Lab $6.50
      Q60-65 : Basic $4.20, Premium $7.00, Lab $6.00
      Q66-71 : Basic $5.50, Premium $5.50, Lab $4.50
    """
    USD_MAP = {
        (42, 47): {"Basic": 4.0,  "Premium": 6.5, "Lab": 7.5},
        (48, 53): {"Basic": 5.0,  "Premium": 5.0, "Lab": 6.5},
        (54, 59): {"Basic": 4.5,  "Premium": 6.5, "Lab": 6.5},
        (60, 65): {"Basic": 4.2,  "Premium": 7.0, "Lab": 6.0},
        (66, 71): {"Basic": 5.5,  "Premium": 5.5, "Lab": 4.5},
    }

    def _get_usd(q, product):
        for (a, b), m in USD_MAP.items():
            if a <= q <= b:
                return m[product]
        return np.nan

    LVL_MAP = {1: "Low", 2: "Mid", 3: "High"}

    # Load skipping the two Qualtrics meta-rows
    df_raw = pd.read_csv(path, skiprows=[1, 2], low_memory=False)

    # Keep only finished responses
    df_raw = df_raw[df_raw["Finished"].astype(str) == "1"].copy()
    df_raw = df_raw.reset_index(drop=True)

    # Coerce all Qualtrics item cols to numeric
    for c in df_raw.columns:
        if c.startswith("Q"):
            df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")

    # Load scenario book
    sb = pd.read_excel(scenario_book_path)
    sb = sb.set_index("Scenario")

    rows = []
    for idx, row in df_raw.iterrows():
        # Find which scenario block this respondent answered
        scenario_q = None
        for q in range(42, 72):
            cols = [f"Q{q}_1", f"Q{q}_2", f"Q{q}_3"]
            if all(c in df_raw.columns for c in cols):
                if row[[f"Q{q}_1", f"Q{q}_2", f"Q{q}_3"]].notna().any():
                    scenario_q = q
                    break
        if scenario_q is None:
            continue

        scenario_num = scenario_q - 41          # Q42→1 … Q71→30
        sb_row = sb.loc[scenario_num] if scenario_num in sb.index else None

        rec = {
            COL_PID:          f"P{idx+1}",
            COL_SCENARIO:     scenario_num,
            COL_RATE_LAB:     row.get(f"Q{scenario_q}_1", np.nan),
            COL_RATE_PREM:    row.get(f"Q{scenario_q}_2", np.nan),
            COL_RATE_BASIC:   row.get(f"Q{scenario_q}_3", np.nan),
            # Demographics (raw codes — same coding as original)
            "Age":            row.get("Q22", np.nan),
            "Gender":         row.get("Q23", np.nan),
            "Education":      row.get("Q24", np.nan),
            "Marital":        row.get("Q25", np.nan),
            "HouseholdSize":  row.get("Q26", np.nan),
            "Income":         row.get("Q27", np.nan),
            "Employment":     row.get("Q28", np.nan),
            "Urban_Rural":    row.get("Q29", np.nan),
            # USD prices
            f"{COL_PRICE_LAB}_raw":   _get_usd(scenario_q, "Lab"),
            f"{COL_PRICE_PREM}_raw":  _get_usd(scenario_q, "Premium"),
            f"{COL_PRICE_BASIC}_raw": _get_usd(scenario_q, "Basic"),
        }

        # Attitude / Behavior / Economic items
        for item in ATT_ITEMS + BEH_ITEMS + ECON_ITEMS:
            rec[item] = row.get(item, np.nan)

        # Scenario-book levels
        if sb_row is not None:
            for prod_col, dest in [
                ("Price_Lab",       COL_PRICE_LAB),
                ("Price_Premium",   COL_PRICE_PREM),
                ("Price_Basic",     COL_PRICE_BASIC),
                ("Nutrition_Lab",   COL_NUTR_LAB),
                ("Nutrition_Premium", COL_NUTR_PREM),
                ("Nutrition_Basic", COL_NUTR_BASIC),
                ("Taste_Lab",       COL_TASTE_LAB),
                ("Taste_Premium",   COL_TASTE_PREM),
                ("Taste_Basic",     COL_TASTE_BASIC),
            ]:
                val = sb_row.get(prod_col, np.nan)
                rec[dest] = LVL_MAP.get(int(val), str(val)) if not pd.isna(val) else np.nan

        rows.append(rec)

    df = pd.DataFrame(rows).reset_index(drop=True)
    return df


def load_old_xlsx_as_long(path=None, scenario_book_path=SCENARIO_BOOK):
    """
    Load the September 2025 xlsx (no health label) into the same long-format
    as load_data_from_qualtrics_csv().

    xlsx structure:
      row 0  = column names (ResponseId, Q2_1, …)
      row 1  = label text  → skip
      rows 2+ = data
    """
    from config.constants import OLD_DATA_FILE
    if path is None:
        path = OLD_DATA_FILE

    USD_MAP = {
        (42, 47): {"Basic": 4.0,  "Premium": 6.5, "Lab": 7.5},
        (48, 53): {"Basic": 5.0,  "Premium": 5.0, "Lab": 6.5},
        (54, 59): {"Basic": 4.5,  "Premium": 6.5, "Lab": 6.5},
        (60, 65): {"Basic": 4.2,  "Premium": 7.0, "Lab": 6.0},
        (66, 71): {"Basic": 5.5,  "Premium": 5.5, "Lab": 4.5},
    }

    def _get_usd(q, product):
        for (a, b), m in USD_MAP.items():
            if a <= q <= b:
                return m[product]
        return np.nan

    LVL_MAP = {1: "Low", 2: "Mid", 3: "High"}

    df_raw = pd.read_excel(path, header=0, skiprows=[1])
    # Coerce Q-columns to numeric
    for c in df_raw.columns:
        if str(c).startswith("Q"):
            df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")

    sb = pd.read_excel(scenario_book_path).set_index("Scenario")

    rows = []
    for idx, row in df_raw.iterrows():
        scenario_q = None
        for q in range(42, 72):
            cols = [f"Q{q}_1", f"Q{q}_2", f"Q{q}_3"]
            if all(c in df_raw.columns for c in cols):
                if row[[f"Q{q}_1", f"Q{q}_2", f"Q{q}_3"]].notna().any():
                    scenario_q = q
                    break
        if scenario_q is None:
            continue

        scenario_num = scenario_q - 41
        sb_row = sb.loc[scenario_num] if scenario_num in sb.index else None

        pid = str(row.get("ResponseId", f"OLD_P{idx+1}"))
        rec = {
            COL_PID:          f"OLD_{pid}",
            COL_SCENARIO:     scenario_num,
            COL_RATE_LAB:     row.get(f"Q{scenario_q}_1", np.nan),
            COL_RATE_PREM:    row.get(f"Q{scenario_q}_2", np.nan),
            COL_RATE_BASIC:   row.get(f"Q{scenario_q}_3", np.nan),
            "Age":            row.get("Q22", np.nan),
            "Gender":         row.get("Q23", np.nan),
            "Education":      row.get("Q24", np.nan),
            "Marital":        row.get("Q25", np.nan),
            "HouseholdSize":  row.get("Q26", np.nan),
            "Income":         row.get("Q27", np.nan),
            "Employment":     row.get("Q28", np.nan),
            "Urban_Rural":    row.get("Q29", np.nan),
            f"{COL_PRICE_LAB}_raw":   _get_usd(scenario_q, "Lab"),
            f"{COL_PRICE_PREM}_raw":  _get_usd(scenario_q, "Premium"),
            f"{COL_PRICE_BASIC}_raw": _get_usd(scenario_q, "Basic"),
        }

        for item in ATT_ITEMS + BEH_ITEMS + ECON_ITEMS:
            rec[item] = row.get(item, np.nan)

        if sb_row is not None:
            for prod_col, dest in [
                ("Price_Lab",         COL_PRICE_LAB),
                ("Price_Premium",     COL_PRICE_PREM),
                ("Price_Basic",       COL_PRICE_BASIC),
                ("Nutrition_Lab",     COL_NUTR_LAB),
                ("Nutrition_Premium", COL_NUTR_PREM),
                ("Nutrition_Basic",   COL_NUTR_BASIC),
                ("Taste_Lab",         COL_TASTE_LAB),
                ("Taste_Premium",     COL_TASTE_PREM),
                ("Taste_Basic",       COL_TASTE_BASIC),
            ]:
                val = sb_row.get(prod_col, np.nan)
                rec[dest] = LVL_MAP.get(int(val), str(val)) if not pd.isna(val) else np.nan

        rows.append(rec)

    df = pd.DataFrame(rows).reset_index(drop=True)
    return df


def load_merged_data(new_path=None, old_path=None, scenario_book_path=SCENARIO_BOOK):
    """
    Merge new (April 2026, HealthLabel=1) and old (Sept 2025, HealthLabel=0) surveys.
    Returns a wide-format dataframe with HealthLabel column.
    """
    from config.constants import DATA_FILE, OLD_DATA_FILE
    if new_path is None:
        new_path = DATA_FILE
    if old_path is None:
        old_path = OLD_DATA_FILE

    new_df = load_data_from_qualtrics_csv(new_path, scenario_book_path)
    new_df["HealthLabel"] = 1

    old_df = load_old_xlsx_as_long(old_path, scenario_book_path)
    old_df["HealthLabel"] = 0

    merged = pd.concat([new_df, old_df], ignore_index=True)
    return merged


def recode_to_parametric(df):
    """Convert ordinal demographic codes to parametric numeric equivalents."""
    for col, mapping, new_col in [
        ("Age",           AGE_MIDPOINTS,      "Age_num"),
        ("Education",     EDUCATION_YEARS,    "Education_num"),
        ("HouseholdSize", HOUSEHOLD_SIZE_NUM, "HouseholdSize_num"),
        ("Income",        INCOME_MIDPOINTS,   "Income_num"),
    ]:
        if col in df.columns:
            df[new_col] = pd.to_numeric(df[col], errors="coerce").map(mapping)
        else:
            df[new_col] = np.nan
    return df


def add_sustain_score(df):
    """Compute continuous SustainScore (mean of ATT + BEH items), AttScore, BehScore."""
    att_present = [c for c in ATT_ITEMS if c in df.columns]
    beh_present = [c for c in BEH_ITEMS if c in df.columns]
    all_present = att_present + beh_present

    df["AttScore"]     = df[att_present].mean(axis=1)     if att_present else np.nan
    df["BehScore"]     = df[beh_present].mean(axis=1)     if beh_present else np.nan
    df["SustainScore"] = df[all_present].mean(axis=1)     if all_present else np.nan
    return df

