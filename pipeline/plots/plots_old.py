from config.constants import *

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def annotate_points(ax, x_vals, y_vals, fmt='{:.2f}', dy=0.08):
    for x, y in zip(x_vals, y_vals):
        try:
            if pd.isna(y):
                continue
        except Exception:
            pass
        ax.text(x, y + dy, fmt.format(float(y)), ha='center', va='bottom', fontsize=11)


def apply_plot_style():
    # More aesthetic defaults (no seaborn)
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.size": 12,
        "axes.titlesize": 18,
        "axes.labelsize": 14,
        "legend.fontsize": 12,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def _plot_effect_lines(df, level_col, title, xlab, outname):
    apply_plot_style()
    order = ["Low", "Mid", "High"]

    if level_col not in df.columns:
        plt.figure(figsize=(11,7))
        plt.title(title, fontsize=22, pad=12)
        plt.text(0.5, 0.5, "No such factor column", ha="center", va="center", fontsize=14)
        plt.axis("off")
        fig.tight_layout()
        fig.savefig(outname, dpi=300)
        plt.close(fig)
        return

    rcols = [c for c in [COL_RATE_LAB, COL_RATE_PREM, COL_RATE_BASIC] if c in df.columns]
    if not rcols:
        plt.figure(figsize=(11,7))
        plt.title(title, fontsize=22, pad=12)
        plt.text(0.5, 0.5, "No rating columns found", ha="center", va="center", fontsize=14)
        plt.axis("off")
        fig.tight_layout()
        fig.savefig(outname, dpi=300)
        plt.close(fig)
        return

    work = df.dropna(subset=[level_col])[[level_col] + rcols].copy()
    for rc in rcols:
        work[rc] = pd.to_numeric(work[rc], errors="coerce")
    work = work.dropna(subset=rcols, how="all")

    if work.empty:
        plt.figure(figsize=(11,7))
        plt.title(title, fontsize=22, pad=12)
        plt.xlabel(xlab, fontsize=16)
        plt.ylabel("Mean Rating", fontsize=16)
        plt.xticks(ticks=range(3), labels=[f"{lv}\n(n=0)" for lv in order])
        plt.text(0.5, 0.5, "No data after filtering", ha="center", va="center", fontsize=14)
        ax.set_ylim(0, 7)
        fig.tight_layout()
        fig.savefig(outname, dpi=300)
        plt.close(fig)
        return

    # Normalize factor labels
    mapping_num = {1: "Low", 2: "Mid", 3: "High", 1.0: "Low", 2.0: "Mid", 3.0: "High"}
    if pd.api.types.is_numeric_dtype(work[level_col]):
        work[level_col] = work[level_col].map(mapping_num)
    else:
        work[level_col] = work[level_col].replace({"1": "Low", "2": "Mid", "3": "High"})

    try:
        work[level_col] = work[level_col].astype("category").cat.set_categories(order, ordered=True)
    except Exception:
        pass

    n_per = work.groupby(level_col)[rcols[0]].size().reindex(order).fillna(0).astype(int)
    order2 = [lv for lv in order if int(n_per.get(lv,0)) > 0]
    if not order2:
        order2 = order
    means = {col: work.groupby(level_col)[col].mean().reindex(order2) for col in rcols}
    grid = pd.DataFrame(means)

    fig, ax = plt.subplots(figsize=(11,7))
    ax.set_title(title, fontsize=22, pad=12)
    x = np.arange(len(order2))
    for col in rcols:
        y = grid[col].values
        ax.plot(x, y, marker='o', linewidth=2, label=col.replace('_', ' '))
        annotate_points(ax, x, y)

    ax.set_xlabel(xlab, fontsize=16)
    ax.set_ylabel('Mean Rating', fontsize=16)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{lv}\\n(n={int(n_per.get(lv,0))})" for lv in order2])
    ax.set_ylim(0, 7)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(outname, dpi=300)
    plt.close(fig)

def plot_everything(df, Xz=None, labels=None):
    """Generate all figures (CSV/paper friendly, matplotlib only)."""
    apply_plot_style()
    os.makedirs("out/plots", exist_ok=True)

    # 1) Cluster distribution
    if "Category" in df.columns:
        counts = df["Category"].value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(8,5))
        ax.set_title("Cluster Distribution", pad=12)
        bars = ax.bar(counts.index.astype(str), counts.values)
        ax.set_ylabel("Participants")
        ax.tick_params(axis="x", rotation=20)
        # Label bars with counts
        for b in bars:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f"{int(b.get_height())}",
                    ha="center", va="bottom", fontsize=11)
        fig.tight_layout()
        fig.savefig("out/plots/cluster_distribution.png", dpi=300)
        plt.close(fig)

    # 2) Attitude vs Behavior scatter (raw)

    if "Category" in df.columns and COL_ATT in df.columns and COL_BEH in df.columns:
        sub = df[[COL_ATT, COL_BEH, "Category"]].dropna()
        if not sub.empty:
            plt.figure(figsize=(7,6))
            plt.title("Attitude vs Behavior by Cluster", pad=12)
            for cat, g in sub.groupby("Category"):
                plt.scatter(g[COL_ATT], g[COL_BEH], s=35, alpha=0.75, label=str(cat))
            plt.xlabel("Attitude (Likert)")
            plt.ylabel("Behavior (Likert)")
            plt.legend(frameon=False, title="Cluster")
            fig.tight_layout()
            plt.savefig("out/plots/attitude_behavior_scatter.png", dpi=300)
            plt.close(fig)

    # 3) Mean ratings by cluster
    rating_cols = [(COL_RATE_LAB, "Lab Grown"), (COL_RATE_PREM, "Premium"), (COL_RATE_BASIC, "Basic")]
    if "Category" in df.columns:
        means = []
        for col, label in rating_cols:
            if col in df.columns:
                tmp = pd.to_numeric(df[col], errors="coerce")
                tmp = pd.concat([df["Category"], tmp.rename(col)], axis=1).dropna()
                if not tmp.empty:
                    means.append(tmp.groupby("Category")[col].mean().rename(label))
        if means:
            mdf = pd.concat(means, axis=1)
            fig, ax = plt.subplots(figsize=(10,6))
            ax.set_title("Mean Ratings by Cluster", pad=12)
            x = np.arange(len(mdf.index))
            width = 0.25 if mdf.shape[1] >= 3 else 0.35
            for i, col in enumerate(mdf.columns):
                xpos = x + (i - (mdf.shape[1]-1)/2)*width
                bars = ax.bar(xpos, mdf[col].values, width=width, label=col)
                # Value labels
                for b in bars:
                    ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.08, f"{b.get_height():.2f}",
                            ha="center", va="bottom", fontsize=10)
            ax.set_xticks(x)
            ax.set_xticklabels(mdf.index.astype(str), rotation=20, ha="right")
            ax.set_ylabel("Mean Rating")
            ax.set_ylim(0,7)
            ax.legend(frameon=False)
            fig.tight_layout()
            fig.savefig("out/plots/ratings_by_cluster.png", dpi=300)
            plt.close(fig)

    # 4) Scenario factor effect lines (overall)

    _plot_effect_lines(df, COL_PRICE_LVL, "Effect of Price Level", "Price Level", "out/plots/effect_price.png")
    _plot_effect_lines(df, COL_NUTR_LVL, "Effect of Nutrition Level", "Nutrition Level", "out/plots/effect_nutrition.png")
    _plot_effect_lines(df, COL_TASTE_LVL, "Effect of Taste Level", "Taste Level", "out/plots/effect_taste.png")
