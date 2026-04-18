"""
Plotting utilities (matplotlib-only, publication-friendly).

Drop-in replacement for: pipeline/plots/plots.py

Compatibility:
- plot_everything(df, Xz=..., labels=..., out_dir=..., cluster_col=...)  ✅
  (Xz/labels are optional; when provided, elbow + dendrogram are produced.)
- No code executed at import time.

Key goals:
- Robust to missing factor levels (e.g., Low not present).
- Value labels on bars/lines and annotated heatmap cells.
- Adds high-ROI figures for RQ2 (Price×Nutrition interactions) and RQ3 (consideration-set profile).
"""

from __future__ import annotations

import os
from typing import Optional, Sequence, Dict, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Optional deps (only used if present)
try:
    from sklearn.cluster import KMeans
except Exception:  # pragma: no cover
    KMeans = None

try:
    from scipy.cluster.hierarchy import linkage, dendrogram
except Exception:  # pragma: no cover
    linkage = None
    dendrogram = None


# ---------------------------------------------------------------------
# Constants (prefer project constants; fall back to common names)
# ---------------------------------------------------------------------
try:
    from config.constants import (  # type: ignore
        COL_ATT,
        COL_BEH,
        COL_RATE_LAB,
        COL_RATE_PREM,
        COL_RATE_BASIC,
        COL_PRICE_LVL,
        COL_NUTR_LVL,
        COL_TASTE_LVL,
    )
except Exception:
    COL_ATT = "Attitude"
    COL_BEH = "Behavior"
    COL_RATE_LAB = "Lab"
    COL_RATE_PREM = "Premium"
    COL_RATE_BASIC = "Basic"
    COL_PRICE_LVL = "PriceLevel"
    COL_NUTR_LVL = "NutritionLevel"
    COL_TASTE_LVL = "TasteLevel"


DEFAULT_CLUSTER_COL_CANDIDATES = ("Category", "Cluster", "segment", "Segment", "cluster")


# ---------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------
def apply_plot_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.size": 12,
        "axes.titlesize": 22,
        "axes.labelsize": 16,
        "legend.fontsize": 12,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _resolve_col(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _as_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _canonical_level_order(levels: Sequence[str]) -> Sequence[str]:
    canonical = ["Low", "Mid", "High"]
    present = [x for x in canonical if x in set(levels)]
    if present:
        extra = [x for x in levels if x not in set(canonical)]
        return present + extra
    return sorted(levels)


def _annotate_bars(ax: plt.Axes, bars, fmt: str = "{:.0f}", dy: float = 0.03) -> None:
    for b in bars:
        h = b.get_height()
        if np.isnan(h):
            continue
        ax.text(
            b.get_x() + b.get_width() / 2,
            h + dy,
            fmt.format(h),
            ha="center",
            va="bottom",
            fontsize=11,
        )


def _annotate_points(ax: plt.Axes, xs, ys, fmt: str = "{:.2f}", dy: float = 0.08) -> None:
    for x, y in zip(xs, ys):
        if y is None or (isinstance(y, float) and np.isnan(y)):
            continue
        ax.text(x, float(y) + dy, fmt.format(float(y)), ha="center", va="bottom", fontsize=11)


# ---------------------------------------------------------------------
# Existing plots (clean + robust)
# ---------------------------------------------------------------------
def plot_cluster_distribution(df: pd.DataFrame, cluster_col: str, outpath: str) -> None:
    apply_plot_style()
    counts = df[cluster_col].value_counts(dropna=True)
    try:
        counts = counts.sort_index()
    except Exception:
        pass

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("Cluster Distribution", pad=14)
    bars = ax.bar(counts.index.astype(str), counts.values)
    ax.set_ylabel("Participants")
    ax.tick_params(axis="x", rotation=20)
    _annotate_bars(ax, bars, fmt="{:.0f}", dy=max(counts.values) * 0.02 if len(counts.values) else 0.8)
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


def plot_attitude_behavior_scatter(
    df: pd.DataFrame,
    cluster_col: str,
    outpath: str,
    jitter: float = 0.08,
) -> None:
    apply_plot_style()
    if COL_ATT not in df.columns or COL_BEH not in df.columns:
        return

    sub = df[[COL_ATT, COL_BEH, cluster_col]].dropna()
    if sub.empty:
        return

    rng = np.random.default_rng(0)
    x = _as_numeric(sub[COL_ATT]).to_numpy()
    y = _as_numeric(sub[COL_BEH]).to_numpy()
    xj = x + rng.uniform(-jitter, jitter, size=len(x))
    yj = y + rng.uniform(-jitter, jitter, size=len(y))

    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.set_title("Attitude vs Behavior by Cluster", pad=14)
    for cat, g in sub.assign(_xj=xj, _yj=yj).groupby(cluster_col):
        ax.scatter(g["_xj"], g["_yj"], s=40, alpha=0.65, label=str(cat), edgecolors="white", linewidths=0.3)

    ax.set_xlabel("Attitude (Likert)")
    ax.set_ylabel("Behavior (Likert)")
    ax.set_xlim(0.7, 7.3)
    ax.set_ylim(0.7, 7.3)
    ax.legend(frameon=False, title="Cluster", loc="lower right")
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


def plot_mean_ratings_by_cluster(df: pd.DataFrame, cluster_col: str, outpath: str) -> None:
    apply_plot_style()

    rating_cols = [
        (COL_RATE_LAB, "Lab Grown"),
        (COL_RATE_PREM, "Premium"),
        (COL_RATE_BASIC, "Basic"),
    ]
    present = [(c, lbl) for c, lbl in rating_cols if c in df.columns]
    if not present:
        return

    tmp = df[[cluster_col] + [c for c, _ in present]].copy()
    for c, _ in present:
        tmp[c] = _as_numeric(tmp[c])
    tmp = tmp.dropna(subset=[c for c, _ in present], how="all")
    if tmp.empty:
        return

    mdf = tmp.groupby(cluster_col)[[c for c, _ in present]].mean()
    rename_map = {c: lbl for c, lbl in present}
    mdf = mdf.rename(columns=rename_map)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_title("Willingness to Purchases by Cluster", pad=14)

    x = np.arange(len(mdf.index))
    width = 0.22 if mdf.shape[1] >= 3 else 0.35

    for i, col in enumerate(mdf.columns):
        xpos = x + (i - (mdf.shape[1] - 1) / 2) * width
        bars = ax.bar(xpos, mdf[col].values, width=width, label=col)
        for b in bars:
            ax.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + 0.08,
                f"{b.get_height():.2f}",
                ha="center",
                va="bottom",
                fontsize=11,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(mdf.index.astype(str), rotation=20, ha="right")
    ax.set_ylabel("Willingness to Purchase (1-7)")
    ax.set_ylim(1, 7)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


def plot_factor_marginal_effect_lines(
    df: pd.DataFrame,
    level_col: str,
    outpath: str,
    title: str,
    xlab: str,
) -> None:
    apply_plot_style()
    if level_col not in df.columns:
        return

    rcols = [c for c in (COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC) if c in df.columns]
    if not rcols:
        return

    work = df[[level_col] + rcols].copy()
    work[level_col] = work[level_col].astype(str)
    for rc in rcols:
        work[rc] = _as_numeric(work[rc])
    work = work.dropna(subset=[level_col])
    work = work.dropna(subset=rcols, how="all")
    if work.empty:
        return

    levels_present = [lvl for lvl in work[level_col].unique() if lvl != "nan"]
    order = list(_canonical_level_order(levels_present))

    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    ax.set_title(title, pad=14)

    xticks = []
    xticklabels = []
    for lvl in order:
        sub = work[work[level_col] == lvl]
        if sub.empty:
            continue
        xticks.append(lvl)
        xticklabels.append(f"{lvl}\n(n={len(sub)})")

    xpos = np.arange(len(xticks))
    label_map = {COL_RATE_LAB: "Lab", COL_RATE_PREM: "Premium", COL_RATE_BASIC: "Basic"}

    for rc in rcols:
        means = [work.loc[work[level_col] == lvl, rc].mean() for lvl in xticks]
        ax.plot(xpos, means, marker="o", linewidth=2.5, label=label_map.get(rc, rc))
        _annotate_points(ax, xpos, means, fmt="{:.2f}", dy=0.08)

    ax.set_xticks(xpos)
    ax.set_xticklabels(xticklabels)
    ax.set_xlabel(xlab)
    ax.set_ylabel("Willingness to Purchase (1-7)")
    ax.set_ylim(1, 7)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------
# NEW: RQ3 consideration-set profile
# ---------------------------------------------------------------------
def plot_cluster_profile_across_tunas(df: pd.DataFrame, cluster_col: str, outpath: str) -> None:
    apply_plot_style()

    cols = []
    labels = []
    for c, lbl in [(COL_RATE_BASIC, "Basic"), (COL_RATE_PREM, "Premium"), (COL_RATE_LAB, "Lab")]:
        if c in df.columns:
            cols.append(c)
            labels.append(lbl)
    if len(cols) < 2 or cluster_col not in df.columns:
        return

    work = df[[cluster_col] + cols].copy()
    for c in cols:
        work[c] = _as_numeric(work[c])
    work = work.dropna(subset=cols, how="all")
    if work.empty:
        return

    means = work.groupby(cluster_col)[cols].mean()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title("Ratings Across Tuna Types by Cluster", pad=14)

    x = np.arange(len(cols))
    for cat, row in means.iterrows():
        y = [row[c] for c in cols]
        ax.plot(x, y, marker="o", linewidth=2.5, label=str(cat))
        _annotate_points(ax, x, y, fmt="{:.2f}", dy=0.08)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Tuna Type")
    ax.set_ylabel("Willingness to Purchase (1-7)")
    ax.set_ylim(1, 7)
    ax.legend(frameon=False, title="Cluster", loc="best")
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------
# NEW: RQ2 Price×Nutrition heatmaps (per tuna)
# ---------------------------------------------------------------------
def _heatmap(ax: plt.Axes, data: np.ndarray, xlabels: Sequence[str], ylabels: Sequence[str], title: str):
    im = ax.imshow(data, aspect="auto")
    ax.set_title(title, pad=12)
    ax.set_xticks(np.arange(len(xlabels)))
    ax.set_xticklabels(xlabels)
    ax.set_yticks(np.arange(len(ylabels)))
    ax.set_yticklabels(ylabels)
    ax.set_xticks(np.arange(-0.5, len(xlabels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ylabels), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1)
    ax.tick_params(which="minor", bottom=False, left=False)
    return im


def plot_price_nutrition_interaction_heatmaps(df: pd.DataFrame, outdir: str) -> None:
    apply_plot_style()
    _ensure_dir(outdir)

    if COL_PRICE_LVL not in df.columns or COL_NUTR_LVL not in df.columns:
        return

    tuna_map = [(COL_RATE_LAB, "Lab"), (COL_RATE_PREM, "Premium"), (COL_RATE_BASIC, "Basic")]
    price_levels = _canonical_level_order([x for x in df[COL_PRICE_LVL].dropna().astype(str).unique()])
    nutr_levels = _canonical_level_order([x for x in df[COL_NUTR_LVL].dropna().astype(str).unique()])

    for rcol, tuna_name in tuna_map:
        if rcol not in df.columns:
            continue

        work = df[[COL_PRICE_LVL, COL_NUTR_LVL, rcol]].copy()
        work[COL_PRICE_LVL] = work[COL_PRICE_LVL].astype(str)
        work[COL_NUTR_LVL] = work[COL_NUTR_LVL].astype(str)
        work[rcol] = _as_numeric(work[rcol])
        work = work.dropna(subset=[COL_PRICE_LVL, COL_NUTR_LVL, rcol])
        if work.empty:
            continue

        mean_tbl = work.pivot_table(index=COL_NUTR_LVL, columns=COL_PRICE_LVL, values=rcol, aggfunc="mean")
        n_tbl = work.pivot_table(index=COL_NUTR_LVL, columns=COL_PRICE_LVL, values=rcol, aggfunc="size")

        mean_tbl = mean_tbl.reindex(index=nutr_levels, columns=price_levels)
        n_tbl = n_tbl.reindex(index=nutr_levels, columns=price_levels)

        data = mean_tbl.to_numpy(dtype=float)

        fig, ax = plt.subplots(figsize=(8.5, 6.5))
        im = _heatmap(
            ax,
            data,
            xlabels=[str(x) for x in price_levels],
            ylabels=[str(y) for y in nutr_levels],
            title=f"Price × Nutrition (Willingness to Purchase): {tuna_name}",
        )
        ax.set_xlabel("Price Level")
        ax.set_ylabel("Nutrition Level")
        ax.set_ylim(len(nutr_levels) - 0.5, -0.5)

        for i in range(len(nutr_levels)):
            for j in range(len(price_levels)):
                m = mean_tbl.iloc[i, j]
                n = n_tbl.iloc[i, j]
                if pd.isna(m):
                    txt = "–"
                else:
                    txt = f"{m:.2f}\n(n={int(n)})" if not pd.isna(n) else f"{m:.2f}"
                ax.text(j, i, txt, ha="center", va="center", fontsize=10)

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Willingness to Purchase")

        fig.tight_layout()
        fig.savefig(os.path.join(outdir, f"heatmap_price_nutrition_{tuna_name.lower()}.png"), dpi=300)
        plt.close(fig)


def plot_factor_level_counts(df: pd.DataFrame, outdir: str) -> None:
    apply_plot_style()
    _ensure_dir(outdir)

    for col, title in [
        (COL_PRICE_LVL, "Price Level counts"),
        (COL_NUTR_LVL, "Nutrition Level counts"),
        (COL_TASTE_LVL, "Taste Level counts"),
    ]:
        if col not in df.columns:
            continue
        ser = df[col].dropna().astype(str)
        if ser.empty:
            continue
        counts = ser.value_counts()
        order = list(_canonical_level_order(list(counts.index)))
        counts = counts.reindex(order)

        fig, ax = plt.subplots(figsize=(8.5, 5))
        ax.set_title(title, pad=14)
        bars = ax.bar(counts.index.astype(str), counts.values)
        ax.set_ylabel("Rows")
        dy = max(counts.values) * 0.02 if len(counts.values) else 0.8
        _annotate_bars(ax, bars, fmt="{:.0f}", dy=dy)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, f"counts_{col}.png"), dpi=300)
        plt.close(fig)


def plot_age_distribution(df: pd.DataFrame, outpath: str, age_col: str = "Age") -> None:
    """Create age distribution bar chart used by ACM manuscript (fig_age_distribution.png)."""
    apply_plot_style()
    if age_col not in df.columns:
        return

    ser = df[age_col].dropna().astype(str).str.strip()
    if ser.empty:
        return

    preferred_order = ["18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75 or older"]

    def _norm_age(x: str) -> str:
        y = x.replace("–", "-").replace("—", "-").replace(" to ", "-").strip()

        # Numeric-coded bins from survey/codebook
        num_map = {
            "1": "18-24",
            "2": "25-34",
            "3": "35-44",
            "4": "45-54",
            "5": "55-64",
            "6": "65-74",
            "7": "75 or older",
        }
        y_num = y
        # handle values like 1.0 / 2.0 from CSV/excel coercion
        try:
            yf = float(y)
            if yf.is_integer():
                y_num = str(int(yf))
        except Exception:
            pass
        if y_num in num_map:
            return num_map[y_num]

        # Text normalization
        yn = y.replace(" ", "").lower()
        yn = yn.replace("18-24years", "18-24").replace("25-34years", "25-34")
        yn = yn.replace("35-44years", "35-44").replace("45-54years", "45-54")
        yn = yn.replace("55-64years", "55-64").replace("65-74years", "65-74")
        yn = yn.replace("75+years", "75orolder")

        text_map = {
            "18-24": "18-24",
            "25-34": "25-34",
            "35-44": "35-44",
            "45-54": "45-54",
            "55-64": "55-64",
            "65-74": "65-74",
            "75orolder": "75 or older",
            "75+": "75 or older",
        }
        return text_map.get(yn, y)

    ser = ser.map(_norm_age)
    counts = ser.value_counts()
    order = [x for x in preferred_order if x in counts.index] + [x for x in counts.index if x not in preferred_order]
    counts = counts.reindex(order)

    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    ax.set_title("Participant Age Distribution", pad=14)
    bars = ax.bar(counts.index.astype(str), counts.values)
    ax.set_xlabel("Age group")
    ax.set_ylabel("Participants")
    ax.tick_params(axis="x", rotation=25)

    total = float(counts.sum()) if len(counts.values) else 0.0
    dy = max(counts.values) * 0.02 if len(counts.values) else 0.8
    for b in bars:
        h = float(b.get_height())
        pct = (h / total * 100.0) if total > 0 else 0.0
        ax.text(
            b.get_x() + b.get_width() / 2,
            h + dy,
            f"{int(h)} ({pct:.1f}%)",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------
# Optional: elbow + dendrogram (if Xz provided)
# ---------------------------------------------------------------------
def plot_elbow_method(Xz: np.ndarray, outpath: str, k_min: int = 1, k_max: int = 10, random_state: int = 0) -> None:
    """KMeans inertia elbow. Requires scikit-learn."""
    apply_plot_style()
    if KMeans is None:
        return
    if Xz is None or len(Xz) == 0:
        return

    ks = list(range(k_min, k_max + 1))
    inertias = []
    for k in ks:
        if k == 1:
            # inertia for k=1 is still defined; KMeans supports it
            pass
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        km.fit(Xz)
        inertias.append(float(km.inertia_))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_title("Elbow method", pad=14)
    ax.plot(ks, inertias, marker="o", linewidth=2.5)
    ax.set_xlabel("K")
    ax.set_ylabel("Inertia")
    _annotate_points(ax, ks, inertias, fmt="{:.0f}", dy=max(inertias) * 0.02 if inertias else 5)
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


def plot_hierarchical_dendrogram(Xz: np.ndarray, outpath: str, labels: Optional[Sequence[Any]] = None) -> None:
    """Ward dendrogram. Requires scipy."""
    apply_plot_style()
    if linkage is None or dendrogram is None:
        return
    if Xz is None or len(Xz) == 0:
        return

    Z = linkage(Xz, method="ward")
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_title("Hierarchical dendrogram (Ward)", pad=14)
    dendrogram(Z, labels=None if labels is None else list(labels), leaf_rotation=90, ax=ax)
    ax.set_xlabel("Samples")
    ax.set_ylabel("Distance")
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)
def plot_combined_level_counts(df: pd.DataFrame, outpath: str) -> None:
    apply_plot_style()

    factors = [
        (COL_PRICE_LVL, "Price"),
        (COL_NUTR_LVL, "Nutrition"),
        (COL_TASTE_LVL, "Taste"),
    ]

    # Collect counts and global y max for aligned axes
    counts_by = []
    y_max = 0
    for col, name in factors:
        if col not in df.columns:
            counts_by.append((name, None))
            continue
        ser = df[col].dropna().astype(str)
        if ser.empty:
            counts_by.append((name, None))
            continue
        counts = ser.value_counts()
        order = list(_canonical_level_order(list(counts.index)))
        counts = counts.reindex(order).fillna(0).astype(int)
        y_max = max(y_max, int(counts.max()))
        counts_by.append((name, counts))

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharey=True)
    fig.suptitle("Scenario Level Counts", fontsize=22, y=1.05)

    for ax, (name, counts) in zip(axes, counts_by):
        ax.set_title(name, pad=10)
        if counts is None:
            ax.text(0.5, 0.5, "Missing", ha="center", va="center")
            ax.set_xticks([])
            continue

        bars = ax.bar(counts.index.astype(str), counts.values)
        ax.set_ylim(0, y_max * 1.15 if y_max else 1)
        ax.set_xlabel("Level")
        ax.grid(True, axis="y", linestyle="--", alpha=0.25)

        # annotate bars
        for b in bars:
            h = b.get_height()
            ax.text(
                b.get_x() + b.get_width() / 2,
                h + (y_max * 0.03 if y_max else 0.2),
                f"{int(h)}",
                ha="center",
                va="bottom",
                fontsize=11,
            )

    axes[0].set_ylabel("Count (rows)")
    fig.tight_layout()
    fig.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------
# NEW: Moderation simple slopes plot (SustainScore × Product Type)
# ---------------------------------------------------------------------
def plot_moderation_simple_slopes(df: pd.DataFrame, outpath: str,
                                   long_csv: str = "out/GLM_WTP__LongData.csv") -> None:
    """
    Simple slopes plot using Ordered Logit (OrderedModel) expected WTP values.
    Groups participants into SustainScore terciles and plots model-based
    expected WTP (E[Y] = Σ level × P(Y=level)) per group × product type.
    Falls back to raw means if OrderedModel fitting fails.
    """
    apply_plot_style()

    # ── Try OrderedModel on long data ─────────────────────────────────────
    use_ordered = False
    expected_vals = {}

    try:
        from statsmodels.miscmodels.ordinal_model import OrderedModel
        from patsy import dmatrix

        if not os.path.exists(long_csv):
            raise FileNotFoundError(long_csv)

        long = pd.read_csv(long_csv)
        cont_cols = ["SustainScore", "PriceUSD", "LabPriceGap",
                     "Age_num", "Education_num", "HouseholdSize_num", "Income_num"]
        for c in cont_cols:
            if c in long.columns:
                long[c + "_c"] = long[c] - long[c].mean()

        needed_l = ["WTP", "Product", "PriceLvl", "NutriLvl", "TasteLvl", "SustainScore_c"]
        sub = long.dropna(subset=needed_l).copy()
        sub["WTP"] = _as_numeric(sub["WTP"]).astype(int)
        sub = sub[sub["WTP"].between(1, 7)]

        formula_rhs = ("C(Product) + C(PriceLvl) + C(NutriLvl) + C(TasteLvl)"
                       " + SustainScore_c + PriceUSD_c + LabPriceGap_c")
        X = dmatrix(formula_rhs, data=sub, return_type="dataframe")
        if "Intercept" in X.columns:
            X = X.drop(columns=["Intercept"])

        mod = OrderedModel(sub["WTP"].values, X.values, distr="logit")
        res = mod.fit(method="bfgs", disp=False, maxiter=500)

        # Predicted probabilities → expected WTP per observation
        probs = res.predict()                       # (n, 7)
        levels = np.arange(1, probs.shape[1] + 1)  # [1,2,...,7]
        sub["E_WTP"] = probs @ levels

        # Tercile groups on SustainScore_c
        lo = sub["SustainScore_c"].quantile(0.33)
        hi = sub["SustainScore_c"].quantile(0.67)

        def _grp(s):
            if s <= lo:  return "Low"
            if s <= hi:  return "Medium"
            return "High"

        sub["SustainGroup"] = sub["SustainScore_c"].map(_grp)

        for grp in ["Low", "Medium", "High"]:
            for prod in ["Lab", "Premium", "Basic"]:
                mask = (sub["SustainGroup"] == grp) & (sub["Product"] == prod)
                vals = sub.loc[mask, "E_WTP"]
                expected_vals[(grp, prod)] = (vals.mean(), vals.sem(), len(vals))

        use_ordered = True

    except Exception:
        pass

    # ── Fallback: raw means from wide df ──────────────────────────────────
    if not use_ordered:
        needed_w = ["SustainScore", COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC]
        if not all(c in df.columns for c in needed_w):
            return
        work = df[needed_w].copy()
        for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC]:
            work[c] = _as_numeric(work[c])
        work["SustainScore"] = _as_numeric(work["SustainScore"])
        work = work.dropna()
        lo = work["SustainScore"].quantile(0.33)
        hi = work["SustainScore"].quantile(0.67)

        def _grp(s):
            if s <= lo:  return "Low"
            if s <= hi:  return "Medium"
            return "High"

        work["SustainGroup"] = work["SustainScore"].map(_grp)
        prod_col_map = {"Lab": COL_RATE_LAB, "Premium": COL_RATE_PREM, "Basic": COL_RATE_BASIC}
        for grp in ["Low", "Medium", "High"]:
            for prod, col in prod_col_map.items():
                vals = work.loc[work["SustainGroup"] == grp, col]
                expected_vals[(grp, prod)] = (vals.mean(), vals.sem(), len(vals))

    # ── Plot ──────────────────────────────────────────────────────────────
    products = [("Lab", "Lab-grown"), ("Premium", "Premium"), ("Basic", "Basic")]
    groups   = ["Low", "Medium", "High"]
    colors   = ["#e74c3c", "#f39c12", "#2ecc71"]

    subtitle = "Ordered Logit Expected WTP" if use_ordered else "Raw Group Means"

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.set_title(
        f"Moderation Effect: Sustainability Orientation × Product Type\n"
        f"({subtitle})",
        pad=14
    )

    x = np.arange(len(products))
    for grp, color in zip(groups, colors):
        means = [expected_vals[(grp, p)][0] for p, _ in products]
        sems  = [expected_vals[(grp, p)][1] for p, _ in products]
        n_grp = expected_vals[(grp, products[0][0])][2]
        ax.errorbar(
            x, means, yerr=sems,
            marker="o", linewidth=2.5, markersize=8,
            label=f"{grp} Sustainability (n={n_grp})",
            color=color, capsize=4,
        )
        for xi, (m, se) in zip(x, zip(means, sems)):
            ax.text(xi, float(m) + float(se) + 0.10, f"{float(m):.2f}",
                    ha="center", fontsize=10, color=color)

    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl in products])
    ax.set_ylabel("Expected WTP Rating (1–7)")
    ax.set_ylim(1, 7.8)
    ax.legend(frameon=False, loc="upper right", fontsize=11)
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------
# NEW: Sustainability score distribution (histogram + KDE)
# ---------------------------------------------------------------------
def plot_sustainability_distribution(df: pd.DataFrame, outpath: str) -> None:
    apply_plot_style()
    if "SustainScore" not in df.columns:
        return
    scores = _as_numeric(df["SustainScore"]).dropna()
    if len(scores) < 5:
        return

    from scipy.stats import gaussian_kde  # local import — scipy already a dep

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.set_title("Distribution of Sustainability Orientation Score", pad=14)

    ax.hist(scores, bins=20, density=True, alpha=0.55, color="#3498db",
            edgecolor="white", label="Histogram")

    kde = gaussian_kde(scores)
    xs = np.linspace(scores.min(), scores.max(), 300)
    ax.plot(xs, kde(xs), color="#2c3e50", linewidth=2.5, label="KDE")

    mu, sd = float(scores.mean()), float(scores.std())
    ax.axvline(mu, color="#e74c3c", linewidth=2,        label=f"Mean = {mu:.2f}")
    ax.axvline(mu - sd, color="#e74c3c", linewidth=1.5, linestyle="--", alpha=0.7,
               label=f"±1 SD  [{mu-sd:.2f}, {mu+sd:.2f}]")
    ax.axvline(mu + sd, color="#e74c3c", linewidth=1.5, linestyle="--", alpha=0.7)

    lo33 = float(scores.quantile(0.33))
    hi67 = float(scores.quantile(0.67))
    ax.axvspan(float(scores.min()), lo33, alpha=0.07, color="#e74c3c", label="Low tercile")
    ax.axvspan(hi67, float(scores.max()), alpha=0.07, color="#2ecc71", label="High tercile")

    ax.set_xlabel("Sustainability Orientation Score (1–7)")
    ax.set_ylabel("Density")
    ax.legend(frameon=False, fontsize=10)
    fig.tight_layout()
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------
# NEW: Demographics summary (Gender / Education / Income)
# ---------------------------------------------------------------------
def plot_demographics_summary(df: pd.DataFrame, outpath: str) -> None:
    apply_plot_style()

    GENDER_MAP  = {1: "Male", 2: "Female", 3: "Non-binary", 4: "Other"}
    EDUC_MAP    = {1: "<High School", 2: "High School", 3: "Bachelor's",
                   4: "Master's", 5: "Doctorate"}
    INCOME_MAP  = {1: "<$10k", 2: "$10–25k", 3: "$25–50k", 4: "$50–75k",
                   5: "$75–100k", 6: "$100–150k", 7: ">$150k"}

    panels = [
        ("Gender",    GENDER_MAP,  [1, 2, 3, 4]),
        ("Education", EDUC_MAP,    [1, 2, 3, 4, 5]),
        ("Income",    INCOME_MAP,  [1, 2, 3, 4, 5, 6, 7]),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    fig.suptitle("Sample Demographics (N = {})".format(len(df.dropna(subset=["Gender"], how="all"))),
                 fontsize=20, y=1.02)

    for ax, (col, mapping, order) in zip(axes, panels):
        if col not in df.columns:
            ax.text(0.5, 0.5, f"{col}\nnot found", ha="center", va="center",
                    transform=ax.transAxes)
            continue

        ser = df[col].dropna()

        def _decode(v):
            try:
                return mapping.get(int(float(v)), str(v))
            except Exception:
                return str(v)

        decoded = ser.map(_decode)
        label_order = [mapping[k] for k in order if k in mapping]
        counts = decoded.value_counts()
        counts = counts.reindex([l for l in label_order if l in counts.index]).fillna(0).astype(int)
        total  = int(counts.sum())

        bars = ax.bar(range(len(counts)), counts.values, color="#3498db", width=0.6)
        ax.set_title(col, pad=10)
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels(counts.index.tolist(), rotation=35, ha="right", fontsize=10)
        ax.set_ylabel("Participants")

        dy = int(counts.max()) * 0.03 if len(counts) else 0.5
        for b, v in zip(bars, counts.values):
            pct = int(v) / total * 100 if total else 0
            ax.text(b.get_x() + b.get_width() / 2,
                    int(b.get_height()) + dy,
                    f"{int(v)}\n({pct:.0f}%)",
                    ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    fig.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------
# NEW: Health Label interaction plots
# ---------------------------------------------------------------------
def plot_healthlabel_interactions(df: pd.DataFrame, outpath: str) -> None:
    """
    Two-panel figure showing significant HealthLabel interactions:
      Panel A: HealthLabel × Price (USD) — regression lines per group (formally sig. p=.007)
      Panel B: Mean WTP by Product × HealthLabel — bar chart (descriptive, p=.138)
    Only rendered if HealthLabel column is present with both values.
    """
    apply_plot_style()
    if "HealthLabel" not in df.columns or df["HealthLabel"].nunique() < 2:
        return

    import statsmodels.formula.api as smf
    from pipeline.models.analysis import _build_long_wtp
    from pipeline.io import recode_to_parametric, add_sustain_score

    df = recode_to_parametric(df.copy())
    df = add_sustain_score(df)
    long = _build_long_wtp(df)
    long = long.dropna(subset=["Product", "PriceLvl", "NutriLvl", "TasteLvl"]).copy()
    if long.empty or "PriceUSD" not in long.columns:
        return

    long["HealthLabel"] = pd.to_numeric(long["HealthLabel"], errors="coerce")
    long = long.dropna(subset=["WTP", "PriceUSD", "HealthLabel"])

    GROUP_LABELS = {0: "No Health Label\n(Sept 2025)", 1: "Health Label\n(April 2026)"}
    COLORS       = {0: "#2166ac", 1: "#d6604d"}
    MARKERS      = {0: "o", 1: "s"}

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle("Health Label × Predictor Interactions", fontsize=13, fontweight="bold", y=1.01)

    # ── Panel A: HealthLabel × Price (significant, p = .007) ──────────────
    ax = axes[0]
    price_vals = np.linspace(long["PriceUSD"].quantile(0.05),
                             long["PriceUSD"].quantile(0.95), 80)

    for hl in [0, 1]:
        sub = long[long["HealthLabel"] == hl].copy()
        if sub.empty:
            continue
        # Fit simple OLS within group for the regression line
        try:
            mdl = smf.ols("WTP ~ PriceUSD", data=sub).fit()
            pred = mdl.params["Intercept"] + mdl.params["PriceUSD"] * price_vals
            ci   = mdl.get_prediction(pd.DataFrame({"PriceUSD": price_vals})).conf_int()
            ax.fill_between(price_vals, ci[:, 0], ci[:, 1],
                            alpha=0.12, color=COLORS[hl])
            ax.plot(price_vals, pred, color=COLORS[hl], lw=2.5,
                    label=f"{GROUP_LABELS[hl]} (β={mdl.params['PriceUSD']:.3f})")
        except Exception:
            pass
        # Scatter: mean WTP per price bin
        sub["price_bin"] = pd.cut(sub["PriceUSD"], bins=6)
        agg = sub.groupby("price_bin", observed=True)["WTP"].mean()
        mids = [iv.mid for iv in agg.index]
        ax.scatter(mids, agg.values, color=COLORS[hl], marker=MARKERS[hl],
                   s=60, zorder=5, alpha=0.85)

    ax.set_xlabel("Price (USD)", fontsize=11)
    ax.set_ylabel("Mean WTP (1–7)", fontsize=11)
    ax.set_title("Panel A: Health Label × Price\n(interaction β=+0.320, p=.007***)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, frameon=False)
    ax.grid(True, alpha=0.25)
    ax.annotate("↑ Label attenuates\nprice sensitivity",
                xy=(long["PriceUSD"].max() * 0.72, 3.0),
                fontsize=8.5, color="#d6604d", style="italic")

    # ── Panel B: Mean WTP by Product × HealthLabel (descriptive) ──────────
    ax = axes[1]
    products = ["Basic", "Premium", "Lab"]
    x      = np.arange(len(products))
    width  = 0.35
    means  = {}
    sems   = {}
    for hl in [0, 1]:
        sub = long[long["HealthLabel"] == hl]
        means[hl] = [sub[sub["Product"] == p]["WTP"].mean() for p in products]
        sems[hl]  = [sub[sub["Product"] == p]["WTP"].sem()  for p in products]

    for i, hl in enumerate([0, 1]):
        offset = (i - 0.5) * width
        bars = ax.bar(x + offset, means[hl], width,
                      color=COLORS[hl], alpha=0.82,
                      label=GROUP_LABELS[hl].replace("\n", " "),
                      yerr=sems[hl], capsize=4, error_kw={"linewidth": 1.2})
        for bar, m in zip(bars, means[hl]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.07,
                    f"{m:.2f}", ha="center", va="bottom", fontsize=8)

    # Annotate Lab difference
    lab_idx = products.index("Lab")
    delta = means[1][lab_idx] - means[0][lab_idx]
    ax.annotate(f"Δ={delta:+.2f}",
                xy=(x[lab_idx], max(means[0][lab_idx], means[1][lab_idx]) + 0.35),
                ha="center", fontsize=9, color="#c0392b", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(products, fontsize=11)
    ax.set_ylabel("Mean WTP (1–7)", fontsize=11)
    ax.set_xlabel("Product Type", fontsize=11)
    ax.set_title("Panel B: Health Label × Product\n(descriptive; β=+0.60, p=.138)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, frameon=False)
    ax.set_ylim(0, max(max(means[0]), max(means[1])) + 0.8)
    ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    fig.savefig(outpath, dpi=180, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------
# NEW: GLM coefficient forest plot (reads Model 1 Coefs CSV)
# ---------------------------------------------------------------------
def plot_glm_forest(coefs_csv: str, outpath: str) -> None:
    """Forest plot of GLM Model 1 HC3 coefficients with 95% CI."""
    import re
    apply_plot_style()
    if not os.path.exists(coefs_csv):
        return

    coefs = pd.read_csv(coefs_csv)
    if coefs.empty or "term" not in coefs.columns:
        return

    LABEL_MAP = {
        "Intercept":                    None,
        # Product / scenario factors
        "C(Product)[T.Lab]":            "Product: Lab-grown",
        "C(Product)[T.Premium]":        "Product: Premium",
        "C(PriceLvl)[T.Mid]":           "Price Level: Mid",
        "C(PriceLvl)[T.High]":          "Price Level: High",
        "C(NutriLvl)[T.Mid]":           "Nutrition Level: Mid",
        "C(NutriLvl)[T.High]":          "Nutrition Level: High",
        "C(TasteLvl)[T.Mid]":           "Taste Level: Mid",
        "C(TasteLvl)[T.High]":          "Taste Level: High",
        # Continuous predictors
        "SustainScore_c":               "Sustainability Orientation",
        "PriceUSD_c":                   "Price (USD)",
        "LabPriceGap_c":                "Lab Price Gap",
        "Age_num_c":                    "Age (continuous)",
        "Education_num_c":              "Education (years)",
        "HouseholdSize_num_c":          "Household Size",
        "Income_num_c":                 "Income (continuous)",
        # Gender (ref = Male = 1)
        "C(Gender)[T.2.0]":             "Gender: Female",
        "C(Gender)[T.3.0]":             "Gender: Non-binary",
        "C(Gender)[T.4.0]":             "Gender: Prefer not to say",
        # Marital Status (ref = Single = 1)
        "C(Marital)[T.2.0]":            "Marital: Married",
        "C(Marital)[T.3.0]":            "Marital: Divorced",
        "C(Marital)[T.4.0]":            "Marital: Widowed",
        "C(Marital)[T.5.0]":            "Marital: Other",
        # Employment (ref = Employed full-time = 1)
        "C(Employment)[T.2.0]":         "Employment: Part-time",
        "C(Employment)[T.3.0]":         "Employment: Unemployed (seeking)",
        "C(Employment)[T.4.0]":         "Employment: Unemployed (not seeking)",
        "C(Employment)[T.5.0]":         "Employment: Retired",
        "C(Employment)[T.6.0]":         "Employment: Student",
        "C(Employment)[T.7.0]":         "Employment: Disabled",
        # Urban/Rural (ref = Urban = 1)
        "C(Urban_Rural)[T.2.0]":        "Living Area: Suburban",
        "C(Urban_Rural)[T.3.0]":        "Living Area: Rural",
    }

    def _label(term):
        if term in LABEL_MAP:
            return LABEL_MAP[term]
        # Fallback: try without .0 suffix (e.g. T.2 instead of T.2.0)
        term_norm = re.sub(r"\[T\.(\d+)\.0\]", r"[T.\1.0]", term)
        if term_norm in LABEL_MAP:
            return LABEL_MAP[term_norm]
        m = re.match(r"C\((\w+)\)\[T\.(.+)\]", term)
        if m:
            return f"{m.group(1)}: {m.group(2)}"
        return term

    rows = []
    for _, r in coefs.iterrows():
        lbl = _label(str(r["term"]))
        if lbl is None:
            continue
        try:
            rows.append({"label": lbl, "coef": float(r["coef"]),
                         "se": float(r["std_err"]), "p": float(r["p"])})
        except Exception:
            continue

    if not rows:
        return

    plot_df = pd.DataFrame(rows).sort_values("coef").reset_index(drop=True)
    ci = 1.96 * plot_df["se"]

    def _color(p):
        if p < 0.01:  return "#e74c3c"
        if p < 0.05:  return "#e67e22"
        if p < 0.10:  return "#f1c40f"
        return "#95a5a6"

    colors = [_color(p) for p in plot_df["p"]]

    fig, ax = plt.subplots(figsize=(10, max(6, len(plot_df) * 0.42)))
    ax.set_title("GLM Model 1 — Coefficient Plot (95% CI, HC3 Robust SE)", pad=14)

    y = np.arange(len(plot_df))
    ax.barh(y, plot_df["coef"], xerr=ci, align="center",
            color=colors, height=0.6, ecolor="#555", capsize=3)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"], fontsize=11)
    ax.set_xlabel("Coefficient (β) with 95% CI")

    from matplotlib.patches import Patch
    legend_els = [
        Patch(color="#e74c3c", label="p < .01 ***"),
        Patch(color="#e67e22", label="p < .05 **"),
        Patch(color="#f1c40f", label="p < .10 *"),
        Patch(color="#95a5a6", label="ns"),
    ]
    ax.legend(handles=legend_els, frameon=False, loc="lower right", fontsize=10)
    fig.tight_layout()
    fig.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------
# Orchestrator (backward compatible)
# ---------------------------------------------------------------------
def plot_everything(
    df: pd.DataFrame,
    out_dir: str = "out/plots",
    cluster_col: Optional[str] = None,
    Xz: Optional[np.ndarray] = None,
    labels: Optional[Sequence[Any]] = None,
    **_: Any,
) -> Dict[str, str]:
    """
    Generate all figures. Backward compatible with calls like:
        plot_everything(df, Xz=Xz, labels=labels)

    Returns dict plot_name -> filepath.
    """
    apply_plot_style()
    _ensure_dir(out_dir)

    if cluster_col is None:
        cluster_col = _resolve_col(df, DEFAULT_CLUSTER_COL_CANDIDATES)

    out: Dict[str, str] = {}

    # Optional clustering diagnostics if caller passes Xz/labels
    if Xz is not None:
        fp = os.path.join(out_dir, "elbow_method.png")
        plot_elbow_method(Xz, fp)
        out["elbow_method"] = fp

        fp = os.path.join(out_dir, "hierarchical_dendrogram.png")
        plot_hierarchical_dendrogram(Xz, fp, labels=labels)
        out["hierarchical_dendrogram"] = fp

    # Cluster visuals
    if cluster_col is not None and cluster_col in df.columns:
        fp = os.path.join(out_dir, "cluster_distribution.png")
        plot_cluster_distribution(df, cluster_col, fp)
        out["cluster_distribution"] = fp

        fp = os.path.join(out_dir, "attitude_behavior_scatter.png")
        plot_attitude_behavior_scatter(df, cluster_col, fp)
        out["attitude_behavior_scatter"] = fp

        fp = os.path.join(out_dir, "ratings_by_cluster.png")
        plot_mean_ratings_by_cluster(df, cluster_col, fp)
        out["ratings_by_cluster"] = fp

        fp = os.path.join(out_dir, "cluster_profile_across_tunas.png")
        plot_cluster_profile_across_tunas(df, cluster_col, fp)
        out["cluster_profile_across_tunas"] = fp

    # Marginal effects
    fp = os.path.join(out_dir, "effect_price.png")
    plot_factor_marginal_effect_lines(df, COL_PRICE_LVL, fp, "Effect of Price Level", "Price Level")
    out["effect_price"] = fp

    fp = os.path.join(out_dir, "effect_nutrition.png")
    plot_factor_marginal_effect_lines(df, COL_NUTR_LVL, fp, "Effect of Nutrition Level", "Nutrition Level")
    out["effect_nutrition"] = fp

    fp = os.path.join(out_dir, "effect_taste.png")
    plot_factor_marginal_effect_lines(df, COL_TASTE_LVL, fp, "Effect of Taste Level", "Taste Level")
    out["effect_taste"] = fp

    # Interactions + counts
    plot_price_nutrition_interaction_heatmaps(df, out_dir)
    out["heatmap_price_nutrition_lab"] = os.path.join(out_dir, "heatmap_price_nutrition_lab.png")
    out["heatmap_price_nutrition_premium"] = os.path.join(out_dir, "heatmap_price_nutrition_premium.png")
    out["heatmap_price_nutrition_basic"] = os.path.join(out_dir, "heatmap_price_nutrition_basic.png")

    plot_factor_level_counts(df, out_dir)
    fp = os.path.join(out_dir, "counts_combined.png")
    plot_combined_level_counts(df, fp)
    out["counts_combined"] = fp

    fp = os.path.join(out_dir, "fig_age_distribution.png")
    plot_age_distribution(df, fp, age_col="Age")
    out["fig_age_distribution"] = fp

    # New paper figures
    fp = os.path.join(out_dir, "fig_moderation_simple_slopes.png")
    plot_moderation_simple_slopes(df, fp)
    out["fig_moderation_simple_slopes"] = fp

    fp = os.path.join(out_dir, "fig_sustainability_distribution.png")
    plot_sustainability_distribution(df, fp)
    out["fig_sustainability_distribution"] = fp

    fp = os.path.join(out_dir, "fig_demographics_summary.png")
    plot_demographics_summary(df, fp)
    out["fig_demographics_summary"] = fp

    # Health label interactions (only rendered if HealthLabel column present)
    if "HealthLabel" in df.columns and df["HealthLabel"].nunique() >= 2:
        fp = os.path.join(out_dir, "fig_healthlabel_interactions.png")
        plot_healthlabel_interactions(df, fp)
        out["fig_healthlabel_interactions"] = fp

    return out
