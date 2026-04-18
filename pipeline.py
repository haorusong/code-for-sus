"""
Sustainability Preference Analysis — Single Entry Point
=======================================================
Usage:
    python pipeline.py                      # GLM mode (default)
    python pipeline.py --mode glm           # GLM: hierarchical regression + LaTeX tables
    python pipeline.py --mode anova         # Legacy ANOVA/MANOVA/OLS branch
    python pipeline.py --mode both          # Run both branches
    python pipeline.py --serve              # After running, serve preview on localhost:7723
    python pipeline.py --mode glm --serve   # GLM + serve preview

What this script does (in order):
    1. Load & clean Qualtrics CSV (or Excel) survey data
    2. Compute Attitude / Behavior / Sustainability scores
    3. Merge scenario book (Price / Nutrition / Taste levels)
    4. Filter valid ratings, recode demographics to parametric
    5. K-means clustering (K=3) with elbow + silhouette diagnostics
    6. Run selected analysis branch (GLM or ANOVA or both)
       GLM:  Jaccard & Turrisi hierarchical OLS (Model 1 main effects,
             Model 2 + interactions, Type III omnibus F-tests)
       ANOVA: One-way ANOVAs, Tukey HSD, Factorial ANOVAs, MANOVA, OLS
    7. Generate LaTeX tables (GLM mode only)
    8. Build HTML preview of all outputs
    9. (Optional) Serve preview at http://localhost:7723/tables_preview.html

All outputs go to ./out/
"""

import os
import sys
import shutil
import argparse
import subprocess
import pandas as pd

# ---------------------------------------------------------------------------
# Path bootstrap — allow running from any working directory
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config.constants import (
    DATA_FILE, SCENARIO_BOOK, DEMO_CODEBOOK,
    COMPUTE_SCORES, CLEAN_OUTPUT,
)
from pipeline.io import (
    load_data,
    load_merged_data,
    compute_scores,
    extract_single_scenario_ratings,
    merge_scenario_book,
    infer_levels,
    decode_demographics_with_codebook,
    add_numeric_level_cols,
    filter_valid_ratings,
    recode_to_parametric,
    add_sustain_score,
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
    ordered_model_sensitivity,
    cross_price_analysis,
)
from pipeline.plots.plots import plot_everything, plot_glm_forest
from pipeline.export import write_csv, write_multi_csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _choose_mode(cli_mode: str | None) -> str:
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
    """Remove ANOVA-family artifacts when running GLM-only mode."""
    files_to_remove = [
        "tuna_price_only_long.csv",
        "tuna_price_only_segment_price_effect.csv",
        "tuna_price_only_high_vs_low_spread.csv",
        "tuna_price_only_summary.txt",
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


def _run_common_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    df, cents, Xz, labels, elbow_tbl, sil_tbl = assign_clusters(df)

    if elbow_tbl is not None and not getattr(elbow_tbl, "empty", True):
        write_csv(elbow_tbl, "out/Elbow_Inertia.csv")
    if sil_tbl is not None and not getattr(sil_tbl, "empty", True):
        write_csv(sil_tbl, "out/Silhouette_Scan.csv")

    desc = descriptives(df)
    if isinstance(desc, dict):
        write_multi_csv(desc, "out", "Descriptives")

    cond = treatment_condition_table(df)
    if isinstance(cond, dict):
        write_multi_csv(cond, "out", "Methods_ConditionTable")

    plot_everything(df, Xz=Xz, labels=labels)
    return df


def _run_anova_block(df: pd.DataFrame):
    anova_all = one_way_anovas(df)
    anova_sig = (
        anova_all.loc[pd.to_numeric(anova_all["p"], errors="coerce") < 0.05].copy()
        if not anova_all.empty else None
    )
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
    glm = glm_wtp_models(df)
    if isinstance(glm, dict):
        write_multi_csv(glm, "out", "GLM_WTP")

    print("[Pipeline] Running OrderedModel sensitivity check...")
    try:
        om = ordered_model_sensitivity(df)
        if isinstance(om, dict):
            write_multi_csv(om, "out", "OM_Sensitivity")
        print("[Pipeline] OrderedModel sensitivity check complete.")
    except Exception as e:
        print(f"[Pipeline] OrderedModel sensitivity check failed: {e}")

    cross = cross_price_analysis(df, out_plot_path="out/plots/price_vs_wtp_by_product.png")
    if isinstance(cross, dict):
        write_multi_csv(cross, "out", "CrossPrice")


def _generate_latex_tables():
    print("[Pipeline] Generating LaTeX tables...")
    for script in [
        "scripts/generate_glm_main_table_latex.py",
        "scripts/generate_glm_interaction_table_latex.py",
    ]:
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, script)],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            print(f"  [WARNING] {script} failed:\n{result.stderr}")
        else:
            print(f"  {result.stdout.strip()}")


def _build_preview():
    print("[Pipeline] Building HTML preview...")
    for script in [
        "scripts/build_preview_html.py",
        "scripts/build_om_sensitivity_html.py",
    ]:
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, script)],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            print(f"  [WARNING] {script} failed:\n{result.stderr}")
        else:
            print(f"  {result.stdout.strip()}")


def _serve_preview(port: int = 7723):
    print(f"\n[Pipeline] Serving preview at http://localhost:{port}/tables_preview.html")
    print("           Press Ctrl+C to stop.\n")
    try:
        subprocess.run(
            [sys.executable, "-m", "http.server", str(port), "--directory", "out"],
            cwd=ROOT
        )
    except KeyboardInterrupt:
        print("\n[Pipeline] Server stopped.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sustainability Preference Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode", choices=["glm", "anova", "both"], default=None,
        help="Analysis mode: glm (default) | anova | both"
    )
    parser.add_argument(
        "--merge-old", action="store_true",
        help="Merge Sept 2025 (no health label) + April 2026 (health label) datasets"
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="After running, serve the HTML preview on localhost:7723"
    )
    parser.add_argument(
        "--port", type=int, default=7723,
        help="Port for --serve (default: 7723)"
    )
    args = parser.parse_args()

    # Change working directory to project root so relative paths resolve
    os.chdir(ROOT)

    # ── Setup output directories ──────────────────────────────────────────
    if CLEAN_OUTPUT and os.path.exists("out"):
        shutil.rmtree("out")
    os.makedirs("out", exist_ok=True)
    os.makedirs("out/plots", exist_ok=True)

    selected_mode = _choose_mode(args.mode)
    print(f"\n[Pipeline] Mode: {selected_mode.upper()}")

    # ── Data preparation ──────────────────────────────────────────────────
    if getattr(args, "merge_old", False):
        print(f"[Pipeline] Data: MERGED (April 2026 HealthLabel=1  +  Sept 2025 HealthLabel=0)\n")
        df = load_merged_data()
    else:
        print(f"[Pipeline] Data: {DATA_FILE}\n")
        df = load_data(DATA_FILE)

    if COMPUTE_SCORES:
        df = compute_scores(df)

    df = extract_single_scenario_ratings(df)
    df = merge_scenario_book(df, SCENARIO_BOOK)
    df = infer_levels(df)
    df = decode_demographics_with_codebook(df, DEMO_CODEBOOK)
    df = add_numeric_level_cols(df)
    df = filter_valid_ratings(df)
    df = recode_to_parametric(df)
    df = add_sustain_score(df)

    # ── Common outputs (clustering, descriptives, plots) ──────────────────
    df = _run_common_pipeline(df)

    # ── Analysis branch ───────────────────────────────────────────────────
    if selected_mode in {"anova", "both"}:
        print("[Pipeline] Running ANOVA block...")
        _run_anova_block(df)

    if selected_mode in {"glm", "both"}:
        print("[Pipeline] Running GLM block...")
        _run_glm_block(df)
        plot_glm_forest(
            coefs_csv=os.path.join("out", "GLM_WTP__GLM_Model1_Coefs.csv"),
            outpath=os.path.join("out", "plots", "fig_glm_forest.png"),
        )

    if selected_mode == "glm":
        _clean_glm_only_artifacts("out")

    # ── LaTeX + preview (GLM mode only) ───────────────────────────────────
    if selected_mode in {"glm", "both"}:
        _generate_latex_tables()
        _build_preview()
        print(f"\n[Pipeline] LaTeX tables → out/GLM_main_effects_table.tex")
        print(f"[Pipeline]                  out/GLM_interaction_effects_table.tex")
        print(f"[Pipeline] HTML preview  → out/tables_preview.html")

    print("\n[Pipeline] Done.\n")

    # ── Optional preview server ───────────────────────────────────────────
    if args.serve:
        _serve_preview(args.port)


if __name__ == "__main__":
    main()
