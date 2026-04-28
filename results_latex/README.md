# Results Section — Standalone LaTeX Bundle

Self-contained folder to drop into `main.tex` as a replacement for `\section{Results}`.

Built against the **merged dataset** (Sept 2025 + April 2026):
- N = 1,743 observations (581 participants × 3 products)
- Model 1 R² = 0.146 | Model 2 R² = 0.186 | ΔR² = 0.040, p < .001

## Folder contents

```
results_latex/
├── README.md                           (this file)
├── results_section.tex                 (the main rewrite — \section{Results})
├── standalone_preview.tex              (compilable standalone for quick review)
├── tables/
│   ├── GLM_main_effects_table.tex      (Table 1 — Type III + HC3 contrasts)
│   ├── GLM_interaction_effects_table.tex  (Table 2 — Model 2 interactions)
│   └── demographics_table.tex          (PLACEHOLDER — regenerate from pipeline)
└── figures/
    ├── elbow_method.png                (§5.2)
    ├── hierarchical_dendrogram.png     (§5.2)
    ├── cluster_counts.png              (§5.2)
    ├── attitude_behavior_scatter.png   (§5.2)
    ├── fig_moderation_simple_slopes.png  (§5.4 — flagship moderation plot)
    ├── fig_healthlabel_interactions.png  (§5.6)
    ├── fig_glm_forest.png              (optional, forest plot)
    ├── fig_sustainability_distribution.png  (optional)
    ├── fig_demographics_summary.png    (optional)
    └── fig_age_distribution.png        (optional)
```

## How to use

### Option A — drop into existing `main.tex`

1. Copy this `results_latex/` folder next to your `main.tex`.
2. In `main.tex`, replace the entire existing `\section{Results}` (…) with:
   ```latex
   \input{results_latex/results_section.tex}
   ```
3. Add to preamble if not already present:
   ```latex
   \usepackage{booktabs}
   \usepackage{threeparttable}
   \usepackage{graphicx}
   ```
4. Regenerate `tables/demographics_table.tex` from live data — see below.
5. Compile.

### Option B — standalone compile for review

```bash
cd results_latex/
pdflatex standalone_preview.tex
bibtex   standalone_preview
pdflatex standalone_preview.tex
pdflatex standalone_preview.tex
```

Produces `standalone_preview.pdf` with the rewrite rendered end-to-end.

## Regenerating the tables from the live pipeline

The two GLM tables update automatically when the pipeline runs:

```bash
python3 pipeline.py --mode glm --merge-old
cp out/GLM_main_effects_table.tex        results_latex/tables/
cp out/GLM_interaction_effects_table.tex results_latex/tables/
```

The **demographics table** currently ships as a placeholder because `scripts/generate_demographics_table_latex.py` depends on a Prolific export CSV path that was only present on the original Windows machine. To regenerate:
1. Update the CSV path in `scripts/generate_demographics_table_latex.py`.
2. Run the script.
3. Copy `out/demographics_table.tex` into `results_latex/tables/`.

## Structural changes vs. original Results section

| Change | Reason |
|---|---|
| **MANOVA subsection removed** | Singular covariance error + replaced by full interaction model in Model 2 |
| **"Psychographic" term removed** | Renamed to "sustainability-related orientation" per reviewer feedback |
| **SustainScore split into AttScore + BehScore** | Separates values from behaviors; item labels corrected after paper/code audit revealed ATT_ITEMS and BEH_ITEMS were swapped in constants |
| **K-means demoted to descriptive-only** | Continuous scores have more statistical power; K-means kept for interpretation continuity |
| **New subsection §5.6 on Health-Label wave** | April 2026 wave introduced the label manipulation + revised price coding |
| **Ordered-logit sensitivity check added (§5.7)** | Consultant-flagged reviewer concern about OLS on Likert outcome |
| **New GLM table format (8 columns)** | df · F · β(SE) · t · p · Mean(SD) · Sig. — combines Type III omnibus with HC3 contrasts |
| **All coefficient values updated** | Reflect merged N=1,743 with new price coding and corrected item labels |

## Open action items

- [ ] Regenerate `tables/demographics_table.tex` from live Prolific export
- [ ] Verify `bibliography.bib` has: `jaccard2003`, `mackinnon1985`, `agresti2010`, `siegrist2020`, `kollmuss2002`, `marcus2015`, `theisz2025`
- [ ] Delete from original `main.tex`: `tab:manova_results`, `tab:glm_pooled_grouped_mapped`, `fig:glm_predicted_wtp`, and the RQ3 MANOVA subsection
- [ ] Update §2 (Intro) and §6 (Discussion) to remove all occurrences of "psychographic"
- [ ] Update §3 (Methods) to describe: two survey waves, HealthLabel indicator, revised April 2026 price coding, LabPriceGap variable, hierarchical Model 1/Model 2 spec
