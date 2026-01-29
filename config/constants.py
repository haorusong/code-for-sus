# -*- coding: utf-8 -*-
"""
Sustainability Preference Analysis — full pipeline
--------------------------------------------------
What this file does (short + practical):
1) Load survey data.
2) Compute/use Attitude, Behavior, Economic scores (Q2–Q20).
3) Merge scenario book (Price/Nutrition/Sustainability levels).
4) Drop rows missing any Lab/Premium/Basic rating or having zeros.
5) Cluster participants (K=3 for analysis), print/plot K diagnostics.
6) Descriptives, one-way ANOVAs, Tukey HSD, factorial ANOVAs (Type III),
   ANOVAs with demographics, MANOVA, and OLS per tuna.
7) Save clean outputs (always fresh) to ./out

Author: H. Song with AI assistance from ChatGPT
"""

import os, shutil, warnings, glob
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from scipy.cluster.hierarchy import linkage, dendrogram

import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.multivariate.manova import MANOVA

# -------------------------
# Files + core settings
# -------------------------

DATA_FILE = "data/raw/Exploring Consumer Preferences and Willingness to Pay for Sustainable and Lab-Grown Tuna_September 2, 2025_15.40 2 copy.xlsx"

SCENARIO_BOOK = "data/raw/scenario book.xlsx"
DEMO_CODEBOOK = "data/raw/Demographic_Codebook.xlsx"

COMPUTE_SCORES = True
INCLUDE_ECON = False

K_ANALYSIS = 3
SILHOUETTE_K_RANGE = range(2, 7)
CLEAN_OUTPUT = True
VERBOSE = False

# Column names
COL_PID        = "ParticipantID"
COL_ATT        = "Attitude score"
COL_BEH        = "Behavior Score"
COL_ECON       = "Economic score"
COL_SCENARIO   = "Scenario"
COL_RATE_LAB   = "Lab_Rating"
COL_RATE_PREM  = "Premium_Rating"
COL_RATE_BASIC = "Basic_Rating"

#
# Scenario-per-tuna level columns
COL_PRICE_LAB  = "Price_Lab"
COL_PRICE_PREM = "Price_Premium"
COL_PRICE_BASIC= "Price_Basic"
COL_NUTR_LAB   = "Nutrition_Lab"
COL_NUTR_PREM  = "Nutrition_Premium"
COL_NUTR_BASIC = "Nutrition_Basic"
COL_SUST_LAB   = "Sustainability_Lab"
COL_SUST_PREM  = "Sustainability_Premium"
COL_SUST_BASIC = "Sustainability_Basic"

# Taste (new factor)
COL_TASTE_LAB   = "Taste_Lab"
COL_TASTE_PREM  = "Taste_Premium"
COL_TASTE_BASIC = "Taste_Basic"
COL_TASTE_LVL   = "TasteLvl"

# Proxies used in analyses/plots
COL_PRICE_LVL  = "PriceLvl"
COL_NUTR_LVL   = "NutriLvl"
COL_SUST_LVL   = "SustainLvl"

DEMOG_COLS = ["Age", "Gender", "Education", "Marital", "HouseholdSize", "Income", "Employment", "Urban_Rural"]

# Qualtrics items (only if COMPUTE_SCORES=True)
ATT_ITEMS  = ["Q2_1","Q3_1","Q4_1","Q5_1","Q6_1"]
BEH_ITEMS  = ["Q8_1","Q9_1","Q10_1","Q11_1","Q12_1","Q13_1","Q14_1"]
ECON_ITEMS = ["Q15_1","Q16_1","Q17_1","Q18_1","Q19_1","Q20_1"]

# -------------------------
# Utilities
# -------------------------

