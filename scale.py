"""
Stage 2: Scale the clustering feature block.

- Load data_unified.csv (output of clean_encode.py).
- Apply StandardScaler ONLY to the 20 clustering feature columns -
  descriptive columns (gender, academic_branch, city) and validation
  columns (major choices, parents' preference, etc.) must stay untouched
  since they are not distance-based inputs to KMeans, only used for
  interpretation afterwards.
- Persist the fitted scaler so the exact same transform can be reapplied
  to a new student's answers at inference time without refitting.

- Reduced from the original 30-feature set to 20 following the ANOVA
  F-score + PCA-importance weak-feature ranking in
  clustering_experiment.py (see clustering_experiment_feature_ranking.csv).
  Of the 10 weakest features identified there:
    - 5 are dropped from the system entirely (see clean_encode.py /
      recommend.py / api.py): age, willing_compromise, willing_
      follow_parents, family_financial_status, prefer_job_stability.
    - 5 are kept, but moved OUT of the clustering vector and into
      explicit recommend_majors() parameters instead, since each drives
      its own rule there (interest_programming, interest_languages,
      prefer_people_over_computer, can_study_outside_city,
      can_study_private_university_encoded).
"""

import pandas as pd
import numpy as np
import pickle
from sklearn.preprocessing import StandardScaler

IN_CSV = "data_unified.csv"

df = pd.read_csv(IN_CSV, encoding="utf-8-sig")

print("=== CHECKPOINT: loaded data_unified.csv ===")
print("shape:", df.shape)
print("nulls:", int(df.isnull().sum().sum()))

# The 20 clustering feature columns (see the reduction note in the module
# docstring above). Dropped relative to the original 30: age; interest in
# programming/languages; prefer_people_over_computer; prefer_job_stability;
# willing_compromise/willing_follow_parents/family_financial (all three
# "_encoded"); can_study_outside_city; can_study_private_university_encoded.
clustering_columns = [
    # interests (Likert 1-5)
    "اهتمامي بالرياضيات والمنطق",
    "اهتمامي بالفيزياء والهندسة",
    "اهتمامي بالطب والعلوم الصحية",
    "اهتمامي بالكيمياء والأحياء",
    "اهتمامي بالعلوم الإنسانية (فلسفة، علم نفس، اجتماع)",
    "اهتمامي بالاقتصاد وإدارة الأعمال",
    "اهتمامي بالفنون (رسم، موسيقى، تصميم)",
    "اهتمامي بالقانون والحقوق",
    # personality (Likert 1-5)
    "أفضل الدراسة النظرية على العملية",
    "أستمتع بحل المسائل المعقدة",
    "أتحمل ضغط الدراسة العالي إذا كان التخصص أحبه",
    # priority ranking (1-4)
    "ترتيب أهمية الدخل الجيد بالنسبة لي",
    "ترتيب أهمية المكانة الاجتماعية",
    "ترتيب أهمية العمل في مجال أحبه",
    "ترتيب أهمية الاستقرار الوظيفي",
    # grades (0-100)
    "علامة الرياضيات (0–100)",
    "علامة الفيزياء (0–100)",
    "علامة الكيمياء (0–100)",
    "علامة اللغة العربية (0–100)",
    "علامة اللغة الأجنبية (0–100)",
]

assert len(clustering_columns) == 20, (
    f"Expected 20 clustering columns, got {len(clustering_columns)}"
)
missing = [c for c in clustering_columns if c not in df.columns]
assert not missing, f"Missing expected columns: {missing}"

X = df[clustering_columns].copy()

print("\n=== CHECKPOINT: clustering feature block selected ===")
print("shape:", X.shape)
print("nulls:", int(X.isnull().sum().sum()))

# Fit StandardScaler so every feature contributes proportionally to
# Euclidean distance in KMeans - without this, "grade 0-100" would
# dominate over a Likert "1-5" scale purely due to magnitude, not
# actual signal.
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

print("\n=== CHECKPOINT: after StandardScaler ===")
print("scaled array shape:", X_scaled.shape)
print("mean (should be ~0):", np.round(X_scaled.mean(axis=0), 3)[:5], "...")
print("std (should be ~1):", np.round(X_scaled.std(axis=0), 3)[:5], "...")

with open("scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)

np.save("X_scaled.npy", X_scaled)

with open("feature_columns.pkl", "wb") as f:
    pickle.dump(clustering_columns, f)

print("\nSaved scaler.pkl, X_scaled.npy, feature_columns.pkl")
