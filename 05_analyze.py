"""
Stage 5: Analyze and interpret clusters.

- Mean profile per cluster uses the 30 raw/_encoded clustering columns
  (not the scaled array) so numbers are human-readable (e.g. actual
  grades 0-100, actual Likert 1-5) rather than z-scores.
- Top-3 validation values per cluster come from data_with_clusters.csv's
  first_choice_major / expected_actual_major columns - these were never
  used for clustering, only to sanity-check whether clusters correspond
  to distinct major preferences afterward.
- PCA is fit on the scaled array (X_scaled.npy), matching what KMeans
  actually clustered on, so the 2D plot reflects real cluster geometry
  rather than an arbitrary raw-feature projection.
- The heatmap also uses scaled (z-score) values, not raw ones - grades
  (0-100) and Likert (1-5) on the same color scale would visually drown
  out the Likert columns if plotted in raw units.
- Gender is printed per cluster as a note only (imbalance: 259 female /
  31 male overall) since it was never a clustering feature but the user
  asked for the imbalance to be surfaced during analysis.
"""

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")

import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA

df = pd.read_csv("data_with_clusters.csv", encoding="utf-8-sig")
X_scaled = np.load("X_scaled.npy")
with open("feature_columns.pkl", "rb") as f:
    feature_columns = pickle.load(f)

print("=== CHECKPOINT: inputs loaded ===")
print("data shape:", df.shape)
print("X_scaled shape:", X_scaled.shape)
print("nulls:", int(df.isnull().sum().sum()))
assert len(df) == X_scaled.shape[0], "Row count mismatch between CSV and scaled array"

# --- Mean profile per cluster (raw/_encoded units, human-readable) ---
print("\n=== Mean profile per cluster (30 clustering features) ===")
profile = df.groupby("cluster")[feature_columns].mean().round(2)
print(profile.to_string())

# --- Major code -> English name mapping ---
# Applied to validation columns before any printing/plotting so every
# downstream Top-3 print and chart shows readable major names instead
# of the raw Google Forms numeric codes.
MAJOR_MAP = {
    0: "Unknown",
    1: "Medicine",
    2: "Engineering",
    3: "Computer Science",
    4: "Economics",
    5: "Law",
    6: "Humanities",
    7: "Arts",
    8: "Other",
}

# --- Top-3 validation values per cluster ---
# These columns were withheld from clustering entirely; used only here to
# check whether clusters line up with real major preferences.
validation_cols = {
    "first_choice_major": "التخصص الأول الذي أرغب به",
    "expected_actual_major": "ما هو التخصص الذي تتوقع أن تختاره فعليًا؟",
}

for label, col in validation_cols.items():
    print(f"\n=== Top 3 '{label}' ({col}) per cluster ===")
    mapped = df[col].map(MAJOR_MAP)
    for cluster_id, group in mapped.groupby(df["cluster"]):
        top3 = group.value_counts().head(3)
        print(f"\nCluster {cluster_id} (n={len(group)}):")
        print(top3.to_string())

# --- Gender note (not a clustering feature - surfaced per project notes) ---
gender_col = "الجنس"
print(f"\n=== Gender distribution note (not used in clustering) ===")
print("overall:\n", df[gender_col].value_counts().to_string())
print("\nper cluster:\n", df.groupby("cluster")[gender_col].value_counts().unstack(fill_value=0).to_string())

# --- PCA scatter colored by cluster ---
# Fit on the same scaled array KMeans clustered on, so the 2D projection
# reflects actual cluster geometry rather than an arbitrary raw subspace.
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled)

print("\n=== CHECKPOINT: PCA fit ===")
print("explained variance ratio:", np.round(pca.explained_variance_ratio_, 4))

plt.figure(figsize=(8, 6))
scatter = plt.scatter(X_pca[:, 0], X_pca[:, 1], c=df["cluster"], cmap="viridis", alpha=0.7)
plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% var)")
plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% var)")
plt.title("Clusters projected onto first 2 principal components")
plt.legend(*scatter.legend_elements(), title="Cluster")
plt.tight_layout()
plt.savefig("pca_clusters.png", dpi=150)
print("\nSaved pca_clusters.png")

# --- Cluster profile heatmap (scaled/z-score units) ---
# Using z-scores (not raw units) puts a 0-100 grade and a 1-5 Likert
# column on a comparable color scale, so no single feature dominates
# the heatmap purely due to magnitude.
scaled_df = pd.DataFrame(X_scaled, columns=feature_columns)
scaled_df["cluster"] = df["cluster"].values
scaled_profile = scaled_df.groupby("cluster").mean()

# English labels for the Arabic feature columns, kept as a dict (not a
# positional list) so the mapping is correct regardless of column order.
FEATURE_LABELS_EN = {
    "العمر(رقم_عدد صحيح)": "Age",
    "اهتمامي بالبرمجة والتقنية": "Interest: Programming/Tech",
    "اهتمامي بالرياضيات والمنطق": "Interest: Math/Logic",
    "اهتمامي بالفيزياء والهندسة": "Interest: Physics/Engineering",
    "اهتمامي بالطب والعلوم الصحية": "Interest: Medicine/Health",
    "اهتمامي بالكيمياء والأحياء": "Interest: Chemistry/Biology",
    "اهتمامي باللغات والآداب": "Interest: Languages/Literature",
    "اهتمامي بالعلوم الإنسانية (فلسفة، علم نفس، اجتماع)": "Interest: Humanities",
    "اهتمامي بالاقتصاد وإدارة الأعمال": "Interest: Economics/Business",
    "اهتمامي بالفنون (رسم، موسيقى، تصميم)": "Interest: Arts",
    "اهتمامي بالقانون والحقوق": "Interest: Law",
    "أفضل الدراسة النظرية على العملية": "Prefer theoretical study",
    "أستمتع بحل المسائل المعقدة": "Enjoy solving complex problems",
    "أفضل العمل مع الناس أكثر من العمل مع الحاسوب": "Prefer working with people over computers",
    "أتحمل ضغط الدراسة العالي إذا كان التخصص أحبه": "Handle high academic pressure",
    "أميل للاستقرار الوظيفي أكثر من المغامرة": "Prefer job stability over risk",
    "ترتيب أهمية الدخل الجيد بالنسبة لي": "Priority: Income",
    "ترتيب أهمية المكانة الاجتماعية": "Priority: Social status",
    "ترتيب أهمية العمل في مجال أحبه": "Priority: Work in field I love",
    "ترتيب أهمية الاستقرار الوظيفي": "Priority: Job stability",
    "هل أنت مستعد للتنازل عن رغبتك الأولى إذا كان هناك تخصص قريب منها_encoded": "Willing to compromise first choice (encoded)",
    "هل أنت مستعد لتحقيق رغبة الأهل على حساب رغبتك الشخصية؟_encoded": "Willing to follow parents choice (encoded)",
    "القدرة المادية للعائلة_encoded": "Family financial status (encoded)",
    "علامة الرياضيات (0–100)": "Math grade",
    "علامة الفيزياء (0–100)": "Physics grade",
    "علامة الكيمياء (0–100)": "Chemistry grade",
    "علامة اللغة العربية (0–100)": "Arabic grade",
    "علامة اللغة الأجنبية (0–100)": "Foreign language grade",
    "هل يمكنك الدراسة خارج مدينتك؟": "Can study outside city",
    "هل يمكنك الدراسة في جامعة خاصة؟_encoded": "Can study in private university (encoded)",
}

# Descriptive cluster names derived from the mean profile above (cluster 0:
# high grades but low STEM interest/first-choice split; cluster 1: highest
# STEM interest+grades; cluster 2: lowest STEM grades, highest humanities/
# arts/law interest) - used only as chart labels, not stored back to data.
CLUSTER_NAMES = {
    0: "Undecided Scientific",
    1: "Confident Scientific",
    2: "Humanities",
}

heatmap_data = scaled_profile.T
heatmap_data.index = [FEATURE_LABELS_EN[c] for c in heatmap_data.index]
heatmap_data.columns = [CLUSTER_NAMES[c] for c in heatmap_data.columns]

plt.figure(figsize=(14, 10))
sns.heatmap(heatmap_data, cmap="coolwarm", center=0, annot=True, fmt=".2f", cbar_kws={"label": "z-score"})
plt.title("Cluster profiles (standardized feature means)")
plt.xlabel("Cluster")
plt.tight_layout()
plt.savefig("cluster_heatmap.png", dpi=200)
print("Saved cluster_heatmap.png")
