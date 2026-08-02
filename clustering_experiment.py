"""
Clustering experiment: compare K=2..5 on the full 30-feature set vs. a
reduced feature set after dropping weak/low-contributing features.

This script is fully separate from the production pipeline
(clean_encode.py -> scale.py -> find_k.py -> clustering.py ->
analyze.py). It only reads their outputs (data_unified.csv,
feature_columns.pkl) and writes its own output files
(clustering_experiment_results.csv, clustering_experiment_silhouette.png).
It does not touch X_scaled.npy, scaler.pkl, kmeans_model.pkl,
data_with_clusters.csv, or any production .png.

Weak-feature identification uses a reference clustering at K=3 (the
production default) and combines two independent signals:
  1. ANOVA F-score (sklearn f_classif) of each feature against the
     reference cluster labels - how much each feature's mean differs
     across clusters relative to its within-cluster variance.
  2. PCA loading weight - each feature's contribution to the first 3
     principal components, weighted by each component's explained
     variance ratio.
Features ranked weakest on both signals are dropped for the "reduced"
feature set.
"""

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")

import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_selection import f_classif
from sklearn.decomposition import PCA

RANDOM_STATE = 42
N_INIT = 10
K_VALUES = [2, 3, 4, 5]
REFERENCE_K_FOR_FEATURE_SELECTION = 3
NUM_FEATURES_TO_DROP = 10  # drop the weakest ~1/3 of the 30 features

DATA_CSV = "data_unified.csv"
FEATURE_COLUMNS_PKL = "feature_columns.pkl"

FIRST_CHOICE_COL = "التخصص الأول الذي أرغب به"
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
    "هل أنت مستعد للتنازل عن رغبتك الأولى إذا كان هناك تخصص قريب منها_encoded": "Willing to compromise first choice",
    "هل أنت مستعد لتحقيق رغبة الأهل على حساب رغبتك الشخصية؟_encoded": "Willing to follow parents' choice",
    "القدرة المادية للعائلة_encoded": "Family financial status",
    "علامة الرياضيات (0–100)": "Math grade",
    "علامة الفيزياء (0–100)": "Physics grade",
    "علامة الكيمياء (0–100)": "Chemistry grade",
    "علامة اللغة العربية (0–100)": "Arabic grade",
    "علامة اللغة الأجنبية (0–100)": "Foreign language grade",
    "هل يمكنك الدراسة خارج مدينتك؟": "Can study outside city",
    "هل يمكنك الدراسة في جامعة خاصة؟_encoded": "Can study in private university",
}


def en(col):
    return FEATURE_LABELS_EN.get(col, col)


def fit_kmeans(X_scaled, k):
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=N_INIT)
    labels = km.fit_predict(X_scaled)
    score = silhouette_score(X_scaled, labels)
    return km, labels, score


def print_cluster_profile(df, feature_cols, labels, X_scaled, top_n=5):
    """Print cluster sizes and a brief profile: top-N most distinguishing
    features per cluster (by ANOVA F-score for this specific run) plus the
    most common first-choice major (mode) per cluster."""
    sizes = pd.Series(labels).value_counts().sort_index()
    print("Cluster sizes:")
    print(sizes.to_string())

    f_scores, _ = f_classif(X_scaled, labels)
    top_idx = np.argsort(f_scores)[::-1][:top_n]
    top_features = [feature_cols[i] for i in top_idx]

    raw_profile = df.groupby(labels)[feature_cols].mean().round(2)

    print(f"\nTop {top_n} distinguishing features (highest ANOVA F-score) and cluster means:")
    print(raw_profile[top_features].rename(columns=en).to_string())

    if FIRST_CHOICE_COL in df.columns:
        mapped = df[FIRST_CHOICE_COL].map(MAJOR_MAP)
        modes = mapped.groupby(labels).agg(lambda s: s.value_counts().idxmax())
        print("\nMost common first-choice major per cluster (validation only, not a clustering feature):")
        print(modes.to_string())


def run_k_sweep(df, feature_cols, X_scaled, label):
    print(f"\n{'=' * 70}")
    print(f"FEATURE SET: {label}  ({len(feature_cols)} features)")
    print(f"{'=' * 70}")
    results = []
    for k in K_VALUES:
        print(f"\n--- K={k} | {label} ---")
        km, labels, score = fit_kmeans(X_scaled, k)
        print(f"Silhouette score: {score:.4f}")
        print_cluster_profile(df, feature_cols, labels, X_scaled)
        sizes = pd.Series(labels).value_counts().sort_index()
        results.append({
            "K": k,
            "feature_set": label,
            "n_features": len(feature_cols),
            "silhouette": round(score, 4),
            "cluster_sizes": ", ".join(str(v) for v in sizes.values),
        })
    return results


def main():
    with open(FEATURE_COLUMNS_PKL, "rb") as f:
        feature_columns = pickle.load(f)

    df = pd.read_csv(DATA_CSV, encoding="utf-8-sig")

    print("=== CHECKPOINT: inputs loaded ===")
    print("data shape:", df.shape)
    print("clustering features:", len(feature_columns))

    # --- Full feature set: scale and sweep K=2..5 ---
    X_full_raw = df[feature_columns].copy()
    scaler_full = StandardScaler()
    X_full_scaled = scaler_full.fit_transform(X_full_raw)

    full_results = run_k_sweep(df, feature_columns, X_full_scaled, "Full (30 features)")

    # --- Weak feature identification ---
    print(f"\n{'=' * 70}")
    print(f"WEAK FEATURE IDENTIFICATION (reference K={REFERENCE_K_FOR_FEATURE_SELECTION})")
    print(f"{'=' * 70}")

    ref_km, ref_labels, ref_score = fit_kmeans(X_full_scaled, REFERENCE_K_FOR_FEATURE_SELECTION)
    print(f"Reference clustering silhouette (K={REFERENCE_K_FOR_FEATURE_SELECTION}): {ref_score:.4f}")

    f_scores, p_values = f_classif(X_full_scaled, ref_labels)

    pca = PCA(n_components=3, random_state=RANDOM_STATE)
    pca.fit(X_full_scaled)
    # Weighted absolute loading across the first 3 PCs, weighted by each
    # component's explained variance ratio.
    pca_importance = np.abs(pca.components_).T @ pca.explained_variance_ratio_

    n_classes = len(np.unique(ref_labels))
    n_samples = X_full_scaled.shape[0]
    df_between = n_classes - 1
    df_within = n_samples - n_classes
    eta_squared = (f_scores * df_between) / (f_scores * df_between + df_within)

    ranking = pd.DataFrame({
        "feature": [en(c) for c in feature_columns],
        "anova_f_score": f_scores,
        "anova_p_value": p_values,
        "eta_squared": eta_squared,
        "pca_importance": pca_importance,
    })
    ranking["f_rank"] = ranking["anova_f_score"].rank(ascending=True)  # 1 = weakest
    ranking["pca_rank"] = ranking["pca_importance"].rank(ascending=True)  # 1 = weakest
    ranking["combined_weak_rank"] = (ranking["f_rank"] + ranking["pca_rank"]) / 2
    ranking = ranking.sort_values("combined_weak_rank").reset_index(drop=True)

    print(f"\nFeature ranking (weakest first) - explained variance ratio of top 3 PCs: "
          f"{np.round(pca.explained_variance_ratio_, 4)}")
    print(ranking.drop(columns=["f_rank", "pca_rank"]).to_string(index=False))

    weak_features_en = ranking["feature"].head(NUM_FEATURES_TO_DROP).tolist()
    en_to_original = {en(c): c for c in feature_columns}
    weak_features = [en_to_original[f] for f in weak_features_en]

    print(f"\nDropping {NUM_FEATURES_TO_DROP} weakest features:")
    for f in weak_features_en:
        print(f"  - {f}")

    reduced_feature_columns = [c for c in feature_columns if c not in weak_features]

    # --- Reduced feature set: re-scale (fresh StandardScaler) and sweep K=2..5 ---
    X_reduced_raw = df[reduced_feature_columns].copy()
    scaler_reduced = StandardScaler()
    X_reduced_scaled = scaler_reduced.fit_transform(X_reduced_raw)

    reduced_label = f"Reduced ({len(reduced_feature_columns)} features)"
    reduced_results = run_k_sweep(df, reduced_feature_columns, X_reduced_scaled, reduced_label)

    # --- Comparison table across all 8 runs ---
    all_results = full_results + reduced_results
    comparison = pd.DataFrame(all_results)

    full_silhouette_by_k = {r["K"]: r["silhouette"] for r in full_results}

    def make_note(row):
        if row["feature_set"].startswith("Full"):
            note = "Production default" if row["K"] == 3 else "Baseline (full feature set)"
        else:
            delta = row["silhouette"] - full_silhouette_by_k[row["K"]]
            direction = "improved" if delta > 0 else ("worsened" if delta < 0 else "unchanged")
            note = f"Silhouette {direction} vs. full set ({delta:+.4f})"
        return note

    comparison["note"] = comparison.apply(make_note, axis=1)

    print(f"\n{'=' * 70}")
    print("COMPARISON TABLE - ALL 8 RUNS")
    print(f"{'=' * 70}")
    print(comparison.to_string(index=False))

    comparison.to_csv("clustering_experiment_results.csv", index=False, encoding="utf-8-sig")
    print("\nSaved clustering_experiment_results.csv")

    ranking.drop(columns=["f_rank", "pca_rank"]).to_csv(
        "clustering_experiment_feature_ranking.csv", index=False, encoding="utf-8-sig"
    )
    print("Saved clustering_experiment_feature_ranking.csv")

    # --- Silhouette comparison plot ---
    plt.figure(figsize=(8, 5))
    full_sil = [r["silhouette"] for r in full_results]
    reduced_sil = [r["silhouette"] for r in reduced_results]
    plt.plot(K_VALUES, full_sil, marker="o", label="Full (30 features)")
    plt.plot(K_VALUES, reduced_sil, marker="o", label=reduced_label)
    plt.xlabel("K")
    plt.ylabel("Silhouette score")
    plt.title("Silhouette score by K: full vs. reduced feature set")
    plt.xticks(K_VALUES)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("clustering_experiment_silhouette.png", dpi=150)
    print("Saved clustering_experiment_silhouette.png")


if __name__ == "__main__":
    main()
