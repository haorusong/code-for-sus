from config.constants import *
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from scipy.cluster.hierarchy import linkage, dendrogram
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
    elbow_tbl.to_csv("out/Elbow_Inertia.csv", index=False)  # v6: CSV-only

    return df, cents, Xz, labels, elbow_tbl, sil_tbl

# -------------------------
# Analyses
# -------------------------



