import os
import shutil
import argparse
import pandas as pd

from config.constants import *
from pipeline.io import (
    load_data,
    compute_scores,
    extract_single_scenario_ratings,
    merge_scenario_book,
    infer_levels,
    decode_demographics_with_codebook,
    add_numeric_level_cols,
    filter_valid_ratings,
)
from pipeline.segmentation import assign_clusters
from pipeline.models.analysis import (
    descriptives,
    one_way_anovas,
    tukey_for_significant_anovas,
    factorial_anovas,
    anova_with_demographics,
    demographic_descriptives,
    manova_joint_csv,
    ols_models,
    treatment_condition_table,
    glm_wtp_models,
    cross_price_analysis,
)
from pipeline.plots.plots import plot_everything
from pipeline.export import write_csv, write_multi_csv
from scripts.price_analysis_pipeline import run_actual_price_glm_outputs


def _choose_mode(cli_mode: str | None) -> str:
    """
    Modes:
      - glm   : GLM-first outputs (actual USD price), skip ANOVA family
      - anova : legacy ANOVA/MANOVA/OLS outputs
      - both  : run both blocks
    Priority: CLI arg > env PIPELINE_MODE > interactive prompt (default glm)
    """
    if cli_mode:
        m = cli_mode.strip().lower()
        if m in {"glm", "anova", "both"}:
            return m

    env_mode = os.getenv("PIPELINE_MODE", "").strip().lower()
    if env_mode in {"glm", "anova", "both"}:
        return env_mode

    try:
        ans = input("Select pipeline mode (1=GLM, 2=ANOVA, 3=BOTH) [default=1]: ").strip()
    except Exception:
        ans = ""

    if ans == "2":
        return "anova"
    if ans == "3":
        return "both"
    return "glm"


def _clean_glm_only_artifacts(out_dir: str = "out"):
    """Remove older 0~3 / ANOVA artifacts to keep GLM-only output clean."""
    files_to_remove = [
        # price-level (0~3-like) artifacts
        "tuna_price_only_long.csv",
        "tuna_price_only_segment_price_effect.csv",
        "tuna_price_only_high_vs_low_spread.csv",
        "tuna_price_only_summary.txt",
        "tuna_price_only_summary_by_price_wtp.csv",
        "tuna_price_only_summary_by_alt_price_wtp.csv",
        # ANOVA family outputs
        "OneWay_ANOVAs_all.csv",
        "OneWay_ANOVAs_sig.csv",
    ]
    prefixes_to_remove = [
        "Factorial_ANOVA__",
        "Demographics_ANOVA__",
        "MANOVA_joint__",
        "OLS_ByTuna__",
        "PostHoc_ByCluster__",
    ]
    plots_to_remove = [
        "01_overall_price_effect.png",
        "02_price_effect_by_alternative.png",
        "03_segment_price_coefficients.png",
        "04_alt_price_heatmap.png",
    ]

    for fn in files_to_remove:
        p = os.path.join(out_dir, fn)
        if os.path.exists(p):
            os.remove(p)

    if os.path.isdir(out_dir):
        for fn in os.listdir(out_dir):
            if any(fn.startswith(pref) for pref in prefixes_to_remove):
                p = os.path.join(out_dir, fn)
                if os.path.isfile(p):
                    os.remove(p)

    plot_dir = os.path.join(out_dir, "plots")
    for fn in plots_to_remove:
        p = os.path.join(plot_dir, fn)
        if os.path.exists(p):
            os.remove(p)


def _run_common_pipeline(df: pd.DataFrame):
    """Common preprocessing + clustering + always-useful baseline outputs."""
    # Clustering
    df, cents, Xz, labels, elbow_tbl, sil_tbl = assign_clusters(df)

    # clustering diagnostics
    if elbow_tbl is not None and getattr(elbow_tbl, "empty", False) is False:
        write_csv(elbow_tbl, "out/Elbow_Inertia.csv")
    if sil_tbl is not None and getattr(sil_tbl, "empty", False) is False:
        write_csv(sil_tbl, "out/Silhouette_Scan.csv")

    # descriptives
    desc = descriptives(df)
    if isinstance(desc, dict):
        write_multi_csv(desc, "out", "Descriptives")

    # treatment table always useful
    cond = treatment_condition_table(df)
    if isinstance(cond, dict):
        write_multi_csv(cond, "out", "Methods_ConditionTable")

    # baseline plotting
    plot_everything(df, Xz=Xz, labels=labels)

    return df


def _run_anova_block(df: pd.DataFrame):
    """Legacy ANOVA/MANOVA/OLS branch (kept intact)."""
    anova_all = one_way_anovas(df)
    anova_sig = anova_all.loc[pd.to_numeric(anova_all["p"], errors="coerce") < 0.05].copy() if not anova_all.empty else None

    write_csv(anova_all, "out/OneWay_ANOVAs_all.csv")
    if anova_sig is not None:
        write_csv(anova_sig, "out/OneWay_ANOVAs_sig.csv")

    tukey_tables = tukey_for_significant_anovas(df, anova_sig)
    if isinstance(tukey_tables, dict):
        write_multi_csv(tukey_tables, "out", "PostHoc_ByCluster")

    fact = factorial_anovas(df)
    if isinstance(fact, dict):
        write_multi_csv(fact, "out", "Factorial_ANOVA")

    demo = anova_with_demographics(df)
    if isinstance(demo, dict):
        write_multi_csv(demo, "out", "Demographics_ANOVA")

    demod = demographic_descriptives(df)
    if isinstance(demod, dict):
        write_multi_csv(demod, "out", "Demographics_Descriptives")

    manova = manova_joint_csv(df)
    if isinstance(manova, dict):
        write_multi_csv(manova, "out", "MANOVA_joint")

    ols = ols_models(df)
    if isinstance(ols, dict):
        write_multi_csv(ols, "out", "OLS_ByTuna")


def _run_glm_block(df: pd.DataFrame):
    """GLM-first branch + actual-price-only outputs."""
    # Project GLM tables from pipeline models
    glm = glm_wtp_models(df)
    if isinstance(glm, dict):
        write_multi_csv(glm, "out", "GLM_WTP")

    cross = cross_price_analysis(df, out_plot_path="out/plots/price_vs_wtp_by_product.png")
    if isinstance(cross, dict):
        write_multi_csv(cross, "out", "CrossPrice")

    # Actual USD GLM visual + coefficients (clean, no 0~3 artifacts)
    run_actual_price_glm_outputs(DATA_FILE, out_dir="out", plots_dir="out/plots")


def main(mode: str | None = None):
    # Clean output folder
    if CLEAN_OUTPUT and os.path.exists("out"):
        shutil.rmtree("out")
    os.makedirs("out", exist_ok=True)
    os.makedirs("out/plots", exist_ok=True)

    selected_mode = _choose_mode(mode)
    print(f"[Pipeline] Running mode: {selected_mode.upper()}")

    # Data preparation
    df = load_data(DATA_FILE)

    if COMPUTE_SCORES:
        df = compute_scores(df)

    df = extract_single_scenario_ratings(df)
    df = merge_scenario_book(df, SCENARIO_BOOK)
    df = infer_levels(df)
    df = decode_demographics_with_codebook(df, DEMO_CODEBOOK)
    df = add_numeric_level_cols(df)
    df = filter_valid_ratings(df)

    df = _run_common_pipeline(df)

    # Choose ANOVA vs GLM vs BOTH
    if selected_mode in {"anova", "both"}:
        _run_anova_block(df)

    if selected_mode in {"glm", "both"}:
        _run_glm_block(df)

    if selected_mode == "glm":
        _clean_glm_only_artifacts("out")

    print("[Pipeline] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tuna pipeline runner")
    parser.add_argument("--mode", choices=["glm", "anova", "both"], default=None,
                        help="Run mode: glm | anova | both")
    args = parser.parse_args()
    main(mode=args.mode)
