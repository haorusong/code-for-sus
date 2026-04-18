"""Build out/charts_preview.html — visual gallery of all pipeline plots."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")

SECTIONS = [
    ("Health Label Analysis", [
        ("fig_healthlabel_interactions.png",  "Health Label × Price & Product Interactions",
         "Panel A (significant, p=.007): Health label eliminates price sensitivity — Sept 2025 shows "
         "classic downward slope (β=−0.201) while April 2026 is flat (β=+0.065). "
         "Panel B (descriptive, p=.138): Lab-grown WTP jumped +0.67 points with health label; "
         "Basic and Premium barely changed. Label resolves uncertainty around novel lab-grown products."),
    ]),
    ("Core Findings", [
        ("fig_moderation_simple_slopes.png",  "Moderation Effect: Sustainability × Product Type",
         "The flagship finding. High-sustainability consumers rate Lab-grown significantly higher. "
         "Lines diverge on Lab-grown, converge on Basic — the interaction is product-specific."),
        ("fig_glm_forest.png",                "GLM Model 1 — Coefficient Plot (HC3 Robust SE)",
         "All Model 1 predictors sorted by β. Red = p<.01, orange = p<.05, yellow = p<.10, grey = ns. "
         "Nutrition Level dominates; Sustainability Orientation and Product: Premium are significant."),
        ("fig_sustainability_distribution.png","Distribution of Sustainability Orientation Score",
         "Mean = 4.90 (SD ≈ 1.07), slight left skew. Tercile shading shows Low / Medium / High groups "
         "used in the moderation plot. Sufficient variance to detect moderation."),
    ]),
    ("Sample Description", [
        ("fig_age_distribution.png",           "Participant Age Distribution",
         "N = 313 participants. Spread across age groups with peak in 25–44 range."),
        ("fig_demographics_summary.png",       "Sample Demographics — Gender / Education / Income",
         "53% Male, 44% Female. Education skews higher (47% Bachelor's). "
         "Income spread across $25k–$150k. Prolific sample, sustainability-aware."),
    ]),
    ("Consumer Segmentation", [
        ("cluster_distribution.png",           "Cluster Distribution (K = 3)",
         "Three segments identified via K-means on z-scored Attitude + Behavior scores."),
        ("attitude_behavior_scatter.png",      "Attitude vs Behavior by Cluster",
         "Scatter showing how clusters map onto the attitude-behavior space. "
         "Supportive but Inactive group sits high on attitude, low on behavior — the classic gap."),
        ("ratings_by_cluster.png",             "Mean WTP by Cluster × Product",
         "Supportive & Active consumers rate Lab-grown notably higher than other segments."),
        ("cluster_profile_across_tunas.png",   "Cluster Profile Across Tuna Types",
         "Line plot shows how each segment's preference profile differs across products."),
        ("elbow_method.png",                   "Elbow Method — K Selection",
         "Within-cluster inertia by K. Elbow at K=3 supports the chosen cluster count."),
        ("hierarchical_dendrogram.png",        "Hierarchical Dendrogram (Ward Linkage)",
         "Ward linkage dendrogram confirming three-cluster structure."),
    ]),
    ("Attribute Effects", [
        ("effect_nutrition.png",               "Marginal Effect of Nutrition Level",
         "Strongest main effect (F = 42.46***). Higher nutrition → higher WTP across all products."),
        ("effect_price.png",                   "Marginal Effect of Price Level",
         "Non-significant overall (F = 0.40, ns) — expected in between-subjects design."),
        ("effect_taste.png",                   "Marginal Effect of Taste Level",
         "Marginal effect (F = 1.45, ns). Taste claims have limited impact in this sample."),
        ("counts_combined.png",                "Scenario Level Counts (Price / Nutrition / Taste)",
         "Distribution of scenario conditions across participants. Roughly balanced design."),
    ]),
    ("Price × Nutrition Interactions", [
        ("heatmap_price_nutrition_lab.png",    "Price × Nutrition Heatmap — Lab-grown",
         "Mean WTP for Lab-grown by price and nutrition level combination."),
        ("heatmap_price_nutrition_premium.png","Price × Nutrition Heatmap — Premium",
         "Mean WTP for Premium sustainable tuna by price and nutrition combination."),
        ("heatmap_price_nutrition_basic.png",  "Price × Nutrition Heatmap — Basic",
         "Mean WTP for Basic conventional tuna by price and nutrition combination."),
    ]),
]

BADGE_STYLE = {
    "Core Findings":               "#1a7f37",
    "Sample Description":          "#0969da",
    "Consumer Segmentation":       "#8250df",
    "Attribute Effects":           "#b08800",
    "Price × Nutrition Interactions": "#cf222e",
}

rows = []
for section, charts in SECTIONS:
    color = BADGE_STYLE.get(section, "#555")
    rows.append(f"""
    <div class="section-header" style="border-left:5px solid {color}">
        <span class="section-badge" style="background:{color}">{section}</span>
    </div>
    <div class="grid">""")
    for fname, title, desc in charts:
        path = f"plots/{fname}"
        rows.append(f"""
        <div class="card">
            <div class="card-title">{title}</div>
            <img src="{path}" alt="{title}" loading="lazy"
                 onclick="openModal(this.src, '{title}', `{desc}`)">
            <div class="card-desc">{desc}</div>
        </div>""")
    rows.append("    </div>")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Charts — Sustainable Tuna Study</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f6f8fa; color: #1f2328; padding: 32px 24px; }}
  h1   {{ font-size: 1.7rem; font-weight: 700; margin-bottom: 4px; }}
  .sub {{ color: #57606a; font-size: .9rem; margin-bottom: 32px; }}
  .nav {{ display:flex; gap:12px; margin-bottom:32px; flex-wrap:wrap; }}
  .nav a {{ text-decoration:none; font-size:.82rem; padding:5px 12px;
            border-radius:20px; border:1px solid #d0d7de; color:#1f2328;
            background:#fff; transition:background .15s; }}
  .nav a:hover {{ background:#eef2f7; }}

  .section-header {{ margin: 40px 0 16px; padding: 10px 16px;
                     background: #fff; border-radius: 6px;
                     box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .section-badge   {{ font-size:.78rem; font-weight:700; color:#fff;
                      padding:3px 10px; border-radius:20px; letter-spacing:.03em; }}

  .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(340px,1fr));
           gap:20px; }}
  .card {{ background:#fff; border-radius:8px; overflow:hidden;
           box-shadow:0 1px 4px rgba(0,0,0,.1); transition:box-shadow .2s; }}
  .card:hover {{ box-shadow:0 4px 14px rgba(0,0,0,.15); }}
  .card-title {{ font-size:.88rem; font-weight:700; padding:12px 14px 6px; }}
  .card img   {{ width:100%; display:block; cursor:zoom-in; border-top:1px solid #eee;
                 border-bottom:1px solid #eee; }}
  .card-desc  {{ font-size:.78rem; color:#57606a; padding:8px 14px 14px;
                 line-height:1.45; }}

  /* Modal */
  #modal {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.75);
            z-index:999; justify-content:center; align-items:center; padding:24px; }}
  #modal.open {{ display:flex; }}
  #modal-box  {{ background:#fff; border-radius:10px; max-width:900px; width:100%;
                 overflow:hidden; box-shadow:0 20px 60px rgba(0,0,0,.4); }}
  #modal-title {{ font-size:1rem; font-weight:700; padding:14px 18px;
                  border-bottom:1px solid #eee; }}
  #modal-img   {{ width:100%; display:block; }}
  #modal-desc  {{ font-size:.84rem; color:#57606a; padding:12px 18px 16px; }}
  #modal-close {{ position:absolute; top:16px; right:20px; font-size:1.6rem;
                  color:#fff; cursor:pointer; line-height:1; }}
</style>
</head>
<body>
<h1>Sustainable Tuna Study — Charts</h1>
<p class="sub">N = 313 participants · 939 observations · Between-subjects conjoint (April 2026) · Click any chart to enlarge</p>

<nav class="nav">
{"".join(f'<a href="#{s.replace(" ","_").replace("×","x")}">{s}</a>' for s,_ in SECTIONS)}
  <a href="tables_preview.html">→ GLM Tables</a>
</nav>

{"".join(rows)}

<div id="modal" onclick="closeModal(event)">
  <span id="modal-close" onclick="document.getElementById('modal').classList.remove('open')">✕</span>
  <div id="modal-box">
    <div id="modal-title"></div>
    <img id="modal-img" src="" alt="">
    <div id="modal-desc"></div>
  </div>
</div>

<script>
function openModal(src, title, desc) {{
  document.getElementById('modal-img').src   = src;
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-desc').textContent  = desc;
  document.getElementById('modal').classList.add('open');
}}
function closeModal(e) {{
  if (e.target.id === 'modal' || e.target.id === 'modal-close')
    document.getElementById('modal').classList.remove('open');
}}
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') document.getElementById('modal').classList.remove('open');
}});
</script>
</body>
</html>
"""

out = os.path.join("out", "charts_preview.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Written: {out}")
