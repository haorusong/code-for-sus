
import os, shutil
import pandas as pd

from config.constants import *
from pipeline.io import load_data, compute_scores, extract_single_scenario_ratings, merge_scenario_book, infer_levels, decode_demographics_with_codebook, add_numeric_level_cols,  filter_valid_ratings
from pipeline.segmentation import assign_clusters
from pipeline.models.analysis import descriptives, one_way_anovas, tukey_for_significant_anovas, factorial_anovas, anova_with_demographics, demographic_descriptives, manova_joint_csv, ols_models
from pipeline.plots.plots import plot_everything
from pipeline.export import write_csv, write_multi_csv

def main():
    # Clean output folder
    if CLEAN_OUTPUT and os.path.exists("out"):
        shutil.rmtree("out")
    os.makedirs("out", exist_ok=True)
    os.makedirs("out/plots", exist_ok=True)

    df = load_data(DATA_FILE)

    if COMPUTE_SCORES:
        df = compute_scores(df)

    df = extract_single_scenario_ratings(df)
    df = merge_scenario_book(df, SCENARIO_BOOK)
    df = infer_levels(df)
    df = decode_demographics_with_codebook(df, DEMO_CODEBOOK)
    df = add_numeric_level_cols(df)
    df = filter_valid_ratings(df)

    df, cents, Xz, labels, elbow_tbl, sil_tbl = assign_clusters(df)

    # Export clustering diagnostics (CSV-only)
    if elbow_tbl is not None and getattr(elbow_tbl, "empty", False) is False:
        write_csv(elbow_tbl, "out/Elbow_Inertia.csv")
    if sil_tbl is not None and getattr(sil_tbl, "empty", False) is False:
        write_csv(sil_tbl, "out/Silhouette_Scan.csv")


    # Analyses
    desc = descriptives(df)  # returns dict of tables
    # Convert multi-sheet to CSVs
    if isinstance(desc, dict):
        write_multi_csv(desc, "out", "Descriptives")

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

    # MANOVA and OLS already write TXT; we will keep those and additionally emit csv summaries if returned.
    manova = manova_joint_csv(df)
    if isinstance(manova, dict):
        write_multi_csv(manova, "out", "MANOVA_joint")

    ols = ols_models(df)
    if isinstance(ols, dict):
        write_multi_csv(ols, "out", "OLS_ByTuna")

    plot_everything(df, Xz=Xz, labels=labels)

if __name__ == "__main__":
    main()
