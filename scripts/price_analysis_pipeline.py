import os
import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt


def _extract_price_long_from_raw(raw_path: str) -> pd.DataFrame:
    raw = pd.read_excel(raw_path, sheet_name='Exploring Consumer Preferences ')
    num = raw.apply(lambda c: pd.to_numeric(c, errors='coerce'))

    # Q-range -> actual USD mapping (basic, premium, lab)
    range_price_map = {
        (42, 47): {'Basic': 4.0, 'Premium': 6.5, 'Lab': 7.5},
        (48, 53): {'Basic': 5.0, 'Premium': 5.0, 'Lab': 6.5},
        (54, 59): {'Basic': 4.5, 'Premium': 6.5, 'Lab': 6.5},
        (60, 65): {'Basic': 4.2, 'Premium': 7.0, 'Lab': 6.0},
        (66, 71): {'Basic': 5.5, 'Premium': 5.5, 'Lab': 4.5},
    }

    def q_prices(q: int):
        for (a, b), m in range_price_map.items():
            if a <= q <= b:
                return m
        return None

    rows = []
    for idx, row in num.iterrows():
        active_q = None
        for q in range(42, 72):
            cols = [f'Q{q}_1', f'Q{q}_2', f'Q{q}_3']
            if row[cols].notna().any():
                active_q = q
                break
        if active_q is None:
            continue

        m = q_prices(active_q)
        if m is None:
            continue

        rid = raw.loc[idx, 'ResponseId'] if 'ResponseId' in raw.columns else idx
        rows += [
            {'ResponseId': rid, 'question': active_q, 'alt': 'Lab', 'rating': row[f'Q{active_q}_1'], 'price_usd': m['Lab']},
            {'ResponseId': rid, 'question': active_q, 'alt': 'Premium', 'rating': row[f'Q{active_q}_2'], 'price_usd': m['Premium']},
            {'ResponseId': rid, 'question': active_q, 'alt': 'Basic', 'rating': row[f'Q{active_q}_3'], 'price_usd': m['Basic']},
        ]

    long = pd.DataFrame(rows)
    long['rating'] = pd.to_numeric(long['rating'], errors='coerce')
    long = long.dropna(subset=['rating', 'price_usd']).copy()
    return long


def run_price_only_outputs(raw_path: str, out_dir: str = 'out', plots_dir: str = 'out/plots') -> None:
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)

    long = _extract_price_long_from_raw(raw_path)

    # price-level coding for backward-compatible visuals
    price_rank_map = {4.0: 1, 4.2: 1, 4.5: 1, 5.0: 2, 5.5: 2, 6.0: 3, 6.5: 3, 7.0: 3, 7.5: 3}
    long_rank = long.copy()
    long_rank['price_level'] = long_rank['price_usd'].map(price_rank_map)

    # Segment assignment (same approach as before using alt ratings by respondent)
    pivot = long_rank.pivot_table(index=['ResponseId', 'question'], columns='alt', values='rating').reset_index()
    pivot = pivot.dropna(subset=['Lab', 'Premium', 'Basic'])

    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans

    X = StandardScaler().fit_transform(pivot[['Lab', 'Premium', 'Basic']])
    km = KMeans(n_clusters=4, random_state=42, n_init=30)
    pivot['cluster4'] = km.fit_predict(X)
    cent = pivot.groupby('cluster4')[['Lab', 'Premium', 'Basic']].mean()
    labels = {}
    for c, r in cent.iterrows():
        vals = r.to_dict()
        mx = max(vals, key=vals.get)
        if vals['Lab'] < 2.5 and vals['Premium'] < 2.5 and vals['Basic'] < 2.5:
            labels[c] = 'Low-interest all'
        elif mx == 'Premium' and vals['Premium'] > 6:
            labels[c] = 'Premium-first'
        elif mx == 'Lab' and vals['Lab'] > 5:
            labels[c] = 'Lab+Premium positive'
        elif mx == 'Basic' and vals['Basic'] > 5.5:
            labels[c] = 'Basic-first'
        else:
            labels[c] = 'Mixed'

    pivot['segment'] = pivot['cluster4'].map(labels)
    seg_map = pivot[['ResponseId', 'question', 'segment']]
    long_rank = long_rank.merge(seg_map, on=['ResponseId', 'question'], how='left')

    # ---------------- Data exports ----------------
    long_rank.to_csv(os.path.join(out_dir, 'tuna_price_only_long.csv'), index=False)
    long.to_csv(os.path.join(out_dir, 'tuna_price_actual_usd_long.csv'), index=False)

    # Price-only model with coded level + alt FE
    X1 = pd.get_dummies(long_rank[['price_level', 'alt']], columns=['alt'], drop_first=True)
    X1 = sm.add_constant(X1.astype(float))
    m1 = sm.OLS(long_rank['rating'].astype(float), X1).fit()

    seg_rows = []
    for s, g in long_rank.groupby('segment'):
        Xg = pd.get_dummies(g[['price_level', 'alt']], columns=['alt'], drop_first=True)
        Xg = sm.add_constant(Xg.astype(float))
        mg = sm.OLS(g['rating'].astype(float), Xg).fit()
        seg_rows.append({'segment': s, 'n': len(g), 'price_coef': mg.params.get('price_level', np.nan), 'r2': mg.rsquared})
    seg_df = pd.DataFrame(seg_rows).sort_values('n', ascending=False)
    seg_df.to_csv(os.path.join(out_dir, 'tuna_price_only_segment_price_effect.csv'), index=False)

    # Actual-USD model + coefficients
    Xu = pd.get_dummies(long[['price_usd', 'alt']], columns=['alt'], drop_first=True)
    Xu = sm.add_constant(Xu.astype(float))
    mu = sm.OLS(long['rating'].astype(float), Xu).fit()
    pd.DataFrame({'term': mu.params.index, 'coef': mu.params.values}).to_csv(
        os.path.join(out_dir, 'tuna_price_actual_usd_model_coefficients.csv'), index=False
    )

    # summaries (WTP naming)
    by_price_rank = long_rank.groupby('price_level', as_index=False)['rating'].mean().rename(columns={'rating': 'willingness_to_purchase'})
    by_alt_rank = long_rank.groupby(['alt', 'price_level'], as_index=False)['rating'].mean().rename(columns={'rating': 'willingness_to_purchase'})
    by_price_usd = long.groupby('price_usd', as_index=False)['rating'].mean().rename(columns={'rating': 'willingness_to_purchase'})
    by_alt_usd = long.groupby(['alt', 'price_usd'], as_index=False)['rating'].mean().rename(columns={'rating': 'willingness_to_purchase'})

    by_price_rank.to_csv(os.path.join(out_dir, 'tuna_price_only_summary_by_price_wtp.csv'), index=False)
    by_alt_rank.to_csv(os.path.join(out_dir, 'tuna_price_only_summary_by_alt_price_wtp.csv'), index=False)
    by_price_usd.to_csv(os.path.join(out_dir, 'tuna_price_actual_usd_summary_by_price_wtp.csv'), index=False)
    by_alt_usd.to_csv(os.path.join(out_dir, 'tuna_price_actual_usd_summary_by_alt_price_wtp.csv'), index=False)

    with open(os.path.join(out_dir, 'tuna_price_only_summary.txt'), 'w', encoding='utf-8') as f:
        f.write('Price-only model: willingness_to_purchase ~ price_level + alt FE\n')
        f.write(m1.params.round(4).to_string())
        f.write(f'\nR2: {m1.rsquared:.4f}\n')

    with open(os.path.join(out_dir, 'tuna_price_actual_usd_summary.txt'), 'w', encoding='utf-8') as f:
        f.write('Model: willingness_to_purchase ~ price_usd + alt FE\n')
        f.write(mu.params.round(4).to_string())
        f.write(f'\nR2: {mu.rsquared:.4f}\n')
        if 'price_usd' in mu.params:
            f.write(f"\nPrice coefficient (per +$1): {mu.params['price_usd']:.4f}\n")

    # ---------------- Plots ----------------
    plt.style.use('ggplot')

    # 1 price-level overall
    plt.figure(figsize=(6, 4))
    t = by_price_rank.sort_values('price_level')
    plt.plot(t['price_level'], t['willingness_to_purchase'], marker='o', linewidth=2.4)
    plt.title('Overall Price Level vs Willingness to Purchase')
    plt.xlabel('Price level (1=lowest, 3=highest)')
    plt.ylabel('Willingness to Purchase')
    plt.ylim(1, 7)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '01_overall_price_effect.png'), dpi=220)
    plt.close()

    # 2 price-level by alt
    plt.figure(figsize=(7, 4.5))
    for alt in ['Basic', 'Premium', 'Lab']:
        d = by_alt_rank[by_alt_rank['alt'] == alt]
        if len(d):
            plt.plot(d['price_level'], d['willingness_to_purchase'], marker='o', linewidth=2.1, label=alt)
    plt.title('Price Level vs Willingness to Purchase by Product Type')
    plt.xlabel('Price level (1=lowest, 3=highest)')
    plt.ylabel('Willingness to Purchase')
    plt.ylim(1, 7)
    plt.legend(title='Alternative')
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '02_price_effect_by_alternative.png'), dpi=220)
    plt.close()

    # 3 segment coefficients
    if not seg_df.empty:
        s = seg_df.sort_values('price_coef')
        colors = ['#c0392b' if v < 0 else '#2980b9' for v in s['price_coef']]
        plt.figure(figsize=(7, 4.5))
        plt.barh(s['segment'], s['price_coef'], color=colors)
        plt.axvline(0, color='black', linewidth=1)
        plt.title('Price Sensitivity by Segment (Price Coefficient)')
        plt.xlabel('Price coefficient (negative = dislikes higher price)')
        plt.ylabel('Segment')
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, '03_segment_price_coefficients.png'), dpi=220)
        plt.close()

    # 4 heatmap alt x rank
    piv = by_alt_rank.pivot(index='alt', columns='price_level', values='willingness_to_purchase')
    arr = piv.values
    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    im = ax.imshow(arr, cmap='YlGnBu', vmin=1, vmax=7, aspect='auto')
    ax.set_xticks(np.arange(piv.shape[1]))
    ax.set_xticklabels(list(piv.columns))
    ax.set_yticks(np.arange(piv.shape[0]))
    ax.set_yticklabels(list(piv.index))
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, f'{arr[i, j]:.2f}', ha='center', va='center', color='black', fontsize=9)
    ax.set_title('Willingness to Purchase Heatmap (Alternative × Price Level)')
    ax.set_xlabel('Price level')
    ax.set_ylabel('Alternative')
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '04_alt_price_heatmap.png'), dpi=220)
    plt.close()

    # USD plots
    plt.figure(figsize=(6.2, 4.2))
    t = by_price_usd.sort_values('price_usd')
    plt.plot(t['price_usd'], t['willingness_to_purchase'], marker='o', linewidth=2.3)
    plt.title('Willingness to Purchase vs Actual Price (USD)')
    plt.xlabel('Price (USD)')
    plt.ylabel('Willingness to Purchase')
    plt.ylim(1, 7)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '01_mean_rating_vs_price_usd.png'), dpi=220)
    plt.close()

    plt.figure(figsize=(7.2, 4.6))
    for alt in ['Basic', 'Premium', 'Lab']:
        d = by_alt_usd[by_alt_usd['alt'] == alt]
        if len(d):
            plt.plot(d['price_usd'], d['willingness_to_purchase'], marker='o', linewidth=2.1, label=alt)
    plt.title('Willingness to Purchase vs Actual Price by Product Type')
    plt.xlabel('Price (USD)')
    plt.ylabel('Willingness to Purchase')
    plt.ylim(1, 7)
    plt.legend(title='Alternative')
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '02_mean_rating_vs_price_by_alt_usd.png'), dpi=220)
    plt.close()

    # with slope annotations
    slopes = {}
    for alt, g in long.groupby('alt'):
        Xm = sm.add_constant(g['price_usd'].astype(float))
        ym = g['rating'].astype(float)
        mm = sm.OLS(ym, Xm).fit()
        slopes[alt] = mm.params['price_usd']

    plt.figure(figsize=(8, 5))
    colors = {'Basic': '#1f77b4', 'Premium': '#2ca02c', 'Lab': '#d62728'}
    for alt in ['Basic', 'Premium', 'Lab']:
        d = by_alt_usd[by_alt_usd['alt'] == alt]
        if len(d):
            plt.plot(d['price_usd'], d['willingness_to_purchase'], marker='o', linewidth=2.4,
                     color=colors.get(alt), label=f"{alt} (slope {slopes[alt]:.3f}/$)")
    plt.title('Willingness to Purchase vs Actual Price (USD) by Product Type')
    plt.xlabel('Price (USD)')
    plt.ylabel('Willingness to Purchase')
    plt.ylim(1, 7)
    plt.legend(title='Product + price slope', loc='best')
    plt.grid(True, alpha=0.35)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '03_mean_rating_vs_price_by_alt_with_slopes.png'), dpi=240)
    plt.close()

    pd.DataFrame({'alt': list(slopes.keys()), 'slope_rating_per_usd': [slopes[k] for k in slopes]}).to_csv(
        os.path.join(plots_dir, '03_price_slopes_by_alt.csv'), index=False
    )


def run_actual_price_glm_outputs(raw_path: str, out_dir: str = 'out', plots_dir: str = 'out/plots') -> None:
    """Actual-USD-only GLM pipeline outputs (clean set; no 0~3 price_level artifacts)."""
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)

    long = _extract_price_long_from_raw(raw_path).copy()

    # sustainability groups from original survey items
    raw = pd.read_excel(raw_path, sheet_name='Exploring Consumer Preferences ')
    num = raw.apply(lambda c: pd.to_numeric(c, errors='coerce'))

    # respondent-level active question
    q_by_idx = {}
    for idx, row in num.iterrows():
        active_q = None
        for q in range(42, 72):
            cols = [f'Q{q}_1', f'Q{q}_2', f'Q{q}_3']
            if row[cols].notna().any():
                active_q = q
                break
        q_by_idx[idx] = active_q

    rid_col = 'ResponseId' if 'ResponseId' in raw.columns else None
    resp = pd.DataFrame({
        'row_index': list(q_by_idx.keys()),
        'question': list(q_by_idx.values()),
    })
    if rid_col:
        resp['ResponseId'] = raw.loc[resp['row_index'], rid_col].values
    else:
        resp['ResponseId'] = resp['row_index']

    active_cols = [c for c in ['Q2_1', 'Q4_1', 'Q5_1'] if c in num.columns]
    support_cols = [c for c in ['Q8_1', 'Q9_1', 'Q10_1', 'Q11_1', 'Q14_1'] if c in num.columns]
    resp['active_score'] = num.loc[resp['row_index'], active_cols].mean(axis=1).values if active_cols else np.nan
    resp['support_score'] = num.loc[resp['row_index'], support_cols].mean(axis=1).values if support_cols else np.nan

    support_q33 = resp['support_score'].quantile(0.33)
    active_q50 = resp['active_score'].median()

    def classify(r):
        if pd.isna(r['support_score']) or pd.isna(r['active_score']):
            return 'Unknown'
        if r['support_score'] <= support_q33:
            return 'Unsupportive'
        if r['active_score'] >= active_q50:
            return 'Supportive & Active'
        return 'Supportive but Inactive'

    resp['sustain_group'] = resp.apply(classify, axis=1)
    resp = resp[resp['sustain_group'] != 'Unknown'][['ResponseId', 'question', 'sustain_group']].copy()
    long = long.merge(resp, on=['ResponseId', 'question'], how='left').dropna(subset=['sustain_group'])

    # GLM with robust SE (actual USD)
    long['alt'] = pd.Categorical(long['alt'], categories=['Lab', 'Premium', 'Basic'], ordered=True)
    long['sustain_group'] = pd.Categorical(long['sustain_group'],
                                           categories=['Supportive & Active', 'Supportive but Inactive', 'Unsupportive'],
                                           ordered=True)

    # RAW 9-line figure (no model smoothing)
    colors = {'Lab': '#d62728', 'Premium': '#2ca02c', 'Basic': '#1f77b4'}
    linestyles = {'Supportive & Active': 'solid', 'Supportive but Inactive': (0, (1, 2)), 'Unsupportive': (0, (5, 2))}

    raw9 = long.groupby(['sustain_group', 'alt', 'price_usd'], as_index=False)['rating'].mean().rename(columns={'rating': 'mean_wtp'})
    raw9.to_csv(os.path.join(plots_dir, 'tuna_raw_9line_values.csv'), index=False)

    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 6))
    for grp in ['Supportive & Active', 'Supportive but Inactive', 'Unsupportive']:
        for alt in ['Lab', 'Premium', 'Basic']:
            d = raw9[(raw9['sustain_group'] == grp) & (raw9['alt'] == alt)].sort_values('price_usd')
            if d.empty:
                continue
            ax.plot(d['price_usd'], d['mean_wtp'], color=colors[alt], linestyle=linestyles[grp], marker='o', linewidth=2,
                    label=f'{alt} | {grp}')

    ax.set_title('Raw Mean WTP vs Actual Price by Product × Sustainability Group (9 lines)')
    ax.set_xlabel('Price (USD)')
    ax.set_ylabel('Mean willingness to purchase')
    ax.set_ylim(1, 7)
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=True)
    ax.grid(True, alpha=0.35)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'tuna_raw_9line_actual_usd.png'), dpi=260)
    plt.close()

    formula = 'rating ~ C(alt, Treatment(reference="Lab")) * C(sustain_group, Treatment(reference="Supportive & Active")) + price_usd'
    m = smf.glm(formula=formula, data=long, family=sm.families.Gaussian()).fit(cov_type='HC3')

    coef = pd.DataFrame({
        'term': m.params.index,
        'beta': m.params.values,
        'se_robust': m.bse.values,
        'z_or_t': m.tvalues.values,
        'p_value': m.pvalues.values,
        'ci_low_95': m.conf_int()[0].values,
        'ci_high_95': m.conf_int()[1].values,
    })
    coef.to_csv(os.path.join(out_dir, 'tuna_glm_actual_price_coefficients_robust.csv'), index=False)
    long.to_csv(os.path.join(out_dir, 'tuna_long_with_actual_usd_and_groups.csv'), index=False)

    # Predicted 9-line chart (actual observed support only) + anti-overlap labels
    grid_rows = []
    for grp in ['Supportive & Active', 'Supportive but Inactive', 'Unsupportive']:
        for alt in ['Lab', 'Premium', 'Basic']:
            for p in sorted(long.loc[long['alt'] == alt, 'price_usd'].dropna().unique()):
                grid_rows.append({'alt': alt, 'sustain_group': grp, 'price_usd': p})
    grid = pd.DataFrame(grid_rows)
    grid['alt'] = pd.Categorical(grid['alt'], categories=['Lab', 'Premium', 'Basic'], ordered=True)
    grid['sustain_group'] = pd.Categorical(grid['sustain_group'],
                                           categories=['Supportive & Active', 'Supportive but Inactive', 'Unsupportive'],
                                           ordered=True)
    pr = m.get_prediction(grid).summary_frame(alpha=0.05)
    grid['pred'] = pr['mean'].values

    colors = {'Lab': '#d62728', 'Premium': '#2ca02c', 'Basic': '#1f77b4'}
    linestyles = {'Supportive & Active': 'solid', 'Supportive but Inactive': (0, (1, 2)), 'Unsupportive': (0, (5, 2))}

    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 6))
    for grp in ['Supportive & Active', 'Supportive but Inactive', 'Unsupportive']:
        for alt in ['Lab', 'Premium', 'Basic']:
            d = grid[(grid['sustain_group'] == grp) & (grid['alt'] == alt)].sort_values('price_usd')
            ax.plot(d['price_usd'], d['pred'], color=colors[alt], linestyle=linestyles[grp], marker='o', linewidth=2,
                    label=f'{alt} | {grp}')

    labels = []
    for grp in ['Supportive & Active', 'Supportive but Inactive', 'Unsupportive']:
        for alt in ['Lab', 'Premium', 'Basic']:
            d = grid[(grid['sustain_group'] == grp) & (grid['alt'] == alt)]
            for x, y in zip(d['price_usd'], d['pred']):
                txt_color = '#111111' if alt == 'Basic' else colors[alt]
                labels.append({'x': float(x), 'y': float(y), 'text': f'{y:.2f}', 'color': txt_color, 'line_color': colors[alt]})
    labels = pd.DataFrame(labels)
    for x, g in labels.groupby('x'):
        gg = g.sort_values('y').copy()
        y_pos = (gg['y'] + 0.05).tolist()
        for i in range(1, len(y_pos)):
            if y_pos[i] - y_pos[i - 1] < 0.12:
                y_pos[i] = y_pos[i - 1] + 0.12
        for (_, r), yl in zip(gg.iterrows(), y_pos):
            if abs(yl - r['y']) > 0.075:
                ax.plot([x, x], [r['y'] + 0.015, yl - 0.015], color=r['line_color'], alpha=0.35, linewidth=0.8)
            ax.text(x, yl, r['text'], fontsize=6.5, color=r['color'], alpha=0.9, ha='center', va='bottom')

    ax.set_title('GLM Predicted WTP by Product × Sustainability Group')
    ax.set_xlabel('Price (USD)')
    ax.set_ylabel('Predicted willingness to purchase')
    ax.set_ylim(1, 7)
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=True, title='slope : -0.323/$')
    ax.grid(True, alpha=0.35)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'tuna_glm_predicted_9line_actual_usd.png'), dpi=260)
    plt.close()

    # 9-line slope version (legend includes per-line slope by product × cluster)
    line_slope_rows = []
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    for grp in ['Supportive & Active', 'Supportive but Inactive', 'Unsupportive']:
        for alt in ['Lab', 'Premium', 'Basic']:
            d = grid[(grid['sustain_group'] == grp) & (grid['alt'] == alt)].sort_values('price_usd')
            if d.empty:
                continue
            Xm = sm.add_constant(d['price_usd'].astype(float))
            mm = sm.OLS(d['pred'].astype(float), Xm).fit()
            slope = float(mm.params['price_usd'])
            line_slope_rows.append({'alt': alt, 'sustain_group': grp, 'slope_rating_per_usd': slope})

            ax.plot(
                d['price_usd'], d['pred'], color=colors[alt], linestyle=linestyles[grp], marker='o', linewidth=2.2,
                label=f'{alt} | {grp} (slope {slope:.3f}/$)'
            )

    ax.set_title('GLM Predicted WTP vs Actual Price by Product × Sustainability Group')
    ax.set_xlabel('Price (USD)')
    ax.set_ylabel('Predicted willingness to purchase')
    ax.set_ylim(1, 7)
    ax.grid(True, alpha=0.35)
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), frameon=True, title='9 lines + slope')
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'tuna_glm_predicted_9line_with_slopes.png'), dpi=260)
    plt.close()

    pd.DataFrame(line_slope_rows).to_csv(os.path.join(plots_dir, 'tuna_glm_9line_slopes.csv'), index=False)

    # Product-wise slope figure (kept for paper continuity)
    by_alt_usd = long.groupby(['alt', 'price_usd'], as_index=False)['rating'].mean().rename(columns={'rating': 'willingness_to_purchase'})
    slopes = {}
    for alt, g in long.groupby('alt'):
        Xm = sm.add_constant(g['price_usd'].astype(float))
        ym = g['rating'].astype(float)
        mm = sm.OLS(ym, Xm).fit()
        slopes[alt] = mm.params['price_usd']

    plt.figure(figsize=(10, 6))
    c2 = {'Basic': '#1f77b4', 'Premium': '#2ca02c', 'Lab': '#d62728'}
    for alt in ['Basic', 'Premium', 'Lab']:
        d = by_alt_usd[by_alt_usd['alt'] == alt].sort_values('price_usd')
        if len(d):
            plt.plot(
                d['price_usd'], d['willingness_to_purchase'], marker='o', linewidth=2.6,
                color=c2.get(alt), label=f"{alt} (slope {slopes[alt]:.3f}/$)"
            )
    plt.title('Willingness to Purchase vs Actual Price (USD) by Product Type')
    plt.xlabel('Price (USD)')
    plt.ylabel('Willingness to Purchase')
    plt.ylim(1, 7)
    plt.legend(title='Product + price slope', loc='upper right')
    plt.grid(True, alpha=0.35)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, '03_mean_rating_vs_price_by_alt_with_slopes.png'), dpi=240)
    plt.close()

    pd.DataFrame({'alt': list(slopes.keys()), 'slope_rating_per_usd': [slopes[k] for k in slopes]}).to_csv(
        os.path.join(plots_dir, '03_price_slopes_by_alt.csv'), index=False
    )

    with open(os.path.join(out_dir, 'tuna_glm_actual_price_summary.txt'), 'w', encoding='utf-8') as f:
        f.write('GLM method summary (actual USD price)\n')
        f.write('=====================================\n')
        f.write(f'N rows: {len(long)}\n')
        f.write('Formula:\n' + formula + '\n\n')
        f.write('\nProduct-wise OLS price slopes (rating per +$1):\n')
        for k in ['Basic', 'Premium', 'Lab']:
            if k in slopes:
                f.write(f'  {k}: {slopes[k]:.4f}\n')
        f.write('\n')
        f.write(coef.round(4).to_string(index=False))


if __name__ == '__main__':
    # Safe standalone run
    RAW_DEFAULT = r'data/raw/Exploring Consumer Preferences and Willingness to Pay for Sustainable and Lab-Grown Tuna_September 2, 2025_15.40 2 copy.xlsx'
    run_actual_price_glm_outputs(RAW_DEFAULT, out_dir='out', plots_dir='out/plots')
