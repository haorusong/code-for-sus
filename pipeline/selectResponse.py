import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from scipy.spatial.distance import euclidean

# -----------------------------
# CONFIG
# -----------------------------
SCORE_FILE = "Exploring Consumer Preferences and Willingness to Pay for Sustainable and Lab-Grown Tuna_September 2, 2025_15.40 2 copy - sus score (2).csv"
DEMO_FILE  = "Exploring Consumer Preferences and Willingness to Pay for Sustainable and Lab-Grown Tuna_September 2, 2025_15.40 2 copy - Exploring Consumer Preferences  (1).csv"

OUT_FILE = "centroid_purposive_sample_12_per_segment_gender_balanced.csv"

K = 3
RANDOM_STATE = 42
N_PER_SEGMENT = 12  # <- requested

# -----------------------------
# Helpers (match your pipeline)
# -----------------------------
def label_centroid(a_z: float, b_z: float) -> str:
    if a_z > 0.4 and b_z > 0.4:
        return "Supportive and Active"
    if a_z > 0.2 and b_z < -0.2:
        return "Supportive and Inactive"
    if a_z < -0.3 and b_z < -0.3:
        return "Unsupportive and Inactive"
    return "Supportive but Inactive"

def find_gender_col_from_first_row(df_demo: pd.DataFrame) -> str:
    first_row = df_demo.iloc[0]
    matches = [
        col for col, val in first_row.items()
        if isinstance(val, str) and "what is your gender" in val.lower()
    ]
    if not matches:
        raise ValueError("Could not find the gender column by 'What is your gender?' text in row 0.")
    return matches[0]

def pick_balanced_by_centroid_distance(group_sorted: pd.DataFrame, n: int) -> pd.DataFrame:
    """
    Purposeful sampling: prefer smaller dist_to_centroid (more prototypical),
    while trying to balance gender *within the segment* as close as possible.

    Target split:
      - If n is even: n/2 male, n/2 female (when available)
      - If n is odd : (n//2, n - n//2)
    """
    # Keep only known gender (optional; comment out to keep unknowns)
    g = group_sorted.copy()
    # If you want to allow unknown gender to fill gaps, remove next line
    # g = g[g["Gender"].isin(["Male", "Female"])]

    target_m = n // 2
    target_f = n - target_m

    males = g[g["Gender"] == "Male"]
    females = g[g["Gender"] == "Female"]

    # Take closest candidates by gender
    pick_m = males.head(min(target_m, len(males)))
    pick_f = females.head(min(target_f, len(females)))

    picked = pd.concat([pick_m, pick_f]).drop_duplicates(subset=["ResponseID"])

    # If short (because one gender is scarce), fill with next-closest overall
    if len(picked) < n:
        remaining = g[~g["ResponseID"].isin(picked["ResponseID"])].sort_values("dist_to_centroid")
        need = n - len(picked)
        filler = remaining.head(need)
        picked = pd.concat([picked, filler]).drop_duplicates(subset=["ResponseID"]).head(n)

    return picked

# -----------------------------
# 1) Load scored dataset
# -----------------------------
df_raw = pd.read_csv(SCORE_FILE)
df = df_raw.iloc[1:].copy().reset_index(drop=True)  # drop question-text row

df = df.rename(columns={
    "Unnamed: 5": "Attitude_score",
    "Unnamed: 13": "Behavior_score",
    "Q100": "Email",
    "ResponseId": "ResponseID",
})

df["Attitude_score"] = pd.to_numeric(df["Attitude_score"], errors="coerce")
df["Behavior_score"] = pd.to_numeric(df["Behavior_score"], errors="coerce")

# Keep valid email + ResponseID + scores; remove prolific
df = df.dropna(subset=["Attitude_score", "Behavior_score", "Email", "ResponseID"])
df = df[df["Email"].astype(str).str.contains("@", na=False)]
df = df[~df["Email"].str.contains("email.prolific.com", na=False)].copy()

# -----------------------------
# 2) Standardize + KMeans (exact pipeline logic)
# -----------------------------
X = df[["Attitude_score", "Behavior_score"]].astype(float).values
scaler = StandardScaler()
Xz = scaler.fit_transform(X)

df["Att_z"] = Xz[:, 0]
df["Beh_z"] = Xz[:, 1]

km = KMeans(n_clusters=K, n_init=30, random_state=RANDOM_STATE)
df["ClusterID"] = km.fit_predict(Xz)

centroids = km.cluster_centers_  # z-space centroids
cluster_names = {i: label_centroid(a, b) for i, (a, b) in enumerate(centroids)}
df["Segment"] = df["ClusterID"].map(cluster_names)

# Distance to own centroid
df["dist_to_centroid"] = df.apply(
    lambda r: euclidean([r["Att_z"], r["Beh_z"]], centroids[int(r["ClusterID"])]),
    axis=1
)

# -----------------------------
# 3) Load demographics, extract Gender by question text, align by ResponseID
# -----------------------------
df_demo = pd.read_csv(DEMO_FILE).rename(columns={"ResponseId": "ResponseID"})
gender_col = find_gender_col_from_first_row(df_demo)

df_demo_data = df_demo.iloc[1:].copy()  # drop question-text row
df_demo_data[gender_col] = pd.to_numeric(df_demo_data[gender_col], errors="coerce")
df_demo_data["Gender"] = df_demo_data[gender_col].map({1: "Male", 2: "Female"})

df = df.merge(df_demo_data[["ResponseID", "Gender"]], on="ResponseID", how="left", validate="one_to_one")

# -----------------------------
# 4) Centroid-based purposive sampling: 12 per segment, balanced gender
# -----------------------------
samples = []
for seg, g in df.groupby("Segment"):
    g_sorted = g.sort_values("dist_to_centroid").reset_index(drop=True)

    if len(g_sorted) < N_PER_SEGMENT:
        print(f"[WARN] Segment '{seg}' has only {len(g_sorted)} eligible rows; taking all of them.")
        picked = g_sorted
    else:
        picked = pick_balanced_by_centroid_distance(g_sorted, N_PER_SEGMENT)

    samples.append(picked)

sample = pd.concat(samples, ignore_index=True)

# -----------------------------
# 5) Quick checks + save
# -----------------------------
print("\nCounts per segment:")
print(sample["Segment"].value_counts(), "\n")

print("Gender breakdown per segment:")
print(pd.crosstab(sample["Segment"], sample["Gender"], dropna=False), "\n")

print("Overall gender counts:")
print(sample["Gender"].value_counts(dropna=False), "\n")

out = sample[["ResponseID", "Email", "Segment", "Gender", "dist_to_centroid", "Att_z", "Beh_z"]].copy()
out.to_csv(OUT_FILE, index=False)
print(f"Saved: {OUT_FILE}")