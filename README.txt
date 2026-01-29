
SUSTAINABILITY PIPELINE (PARITY MODULAR REFACTOR) - CSV OUTPUTS
=============================================================

Run:
  python run_pipeline.py

Inputs expected in working directory:
- DATA_FILE (see config/constants.py)
- scenario book.xlsx
- Demographic_Codebook.xlsx

Outputs:
- out/*.csv (one per former Excel sheet)
- out/*.txt (MANOVA, OLS)
- out/plots/*.png

Plots upgraded for aesthetics via matplotlib rcParams in pipeline/plots/plots.py


V2 FIXES:
- Fixed missing add_numeric_level_cols (ported from original)
- Fixed function signatures for load_data and merge_scenario_book to accept explicit paths
- Updated run_pipeline imports/calls accordingly
