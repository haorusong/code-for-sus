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

    return out
