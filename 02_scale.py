"""
Stage 2: Scale the clustering feature block.

- Load data_unified.csv (output of 01_clean_encode.py).
- Apply StandardScaler ONLY to the 30 clustering feature columns -
  descriptive columns (gender, academic_branch, city) and validation
  columns (major choices, parents' preference, etc.) must stay untouched
  since they are not distance-based inputs to KMeans, only used for
  interpretation afterwards.
- Persist the fitted scaler so the exact same transform can be reapplied
  to a new student's answers at inference time without refitting.
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

# The 30 clustering feature columns. For the 3 ordinal constraint columns
# we use the _encoded version (0, 0.5, 1) produced in stage 1, not the
# raw {0,1,2} codes, so "somewhat" is evenly spaced between "no" and "yes".
clustering_columns = [
    # age
    "العمر(رقم_عدد صحيح)",
    # interests (Likert 1-5)
    "اهتمامي بالبرمجة والتقنية",
    "اهتمامي بالرياضيات والمنطق",
    "اهتمامي بالفيزياء والهندسة",
    "اهتمامي بالطب والعلوم الصحية",
    "اهتمامي بالكيمياء والأحياء",
    "اهتمامي باللغات والآداب",
    "اهتمامي بالعلوم الإنسانية (فلسفة، علم نفس، اجتماع)",
    "اهتمامي بالاقتصاد وإدارة الأعمال",
    "اهتمامي بالفنون (رسم، موسيقى، تصميم)",
    "اهتمامي بالقانون والحقوق",
    # personality (Likert 1-5)
    "أفضل الدراسة النظرية على العملية",
    "أستمتع بحل المسائل المعقدة",
    "أفضل العمل مع الناس أكثر من العمل مع الحاسوب",
    "أتحمل ضغط الدراسة العالي إذا كان التخصص أحبه",
    "أميل للاستقرار الوظيفي أكثر من المغامرة",
    # priority ranking (1-4)
    "ترتيب أهمية الدخل الجيد بالنسبة لي",
    "ترتيب أهمية المكانة الاجتماعية",
    "ترتيب أهمية العمل في مجال أحبه",
    "ترتيب أهمية الاستقرار الوظيفي",
    # constraints
    "هل أنت مستعد للتنازل عن رغبتك الأولى إذا كان هناك تخصص قريب منها_encoded",
    "هل أنت مستعد لتحقيق رغبة الأهل على حساب رغبتك الشخصية؟_encoded",
    "القدرة المادية للعائلة_encoded",
    # grades (0-100)
    "علامة الرياضيات (0–100)",
    "علامة الفيزياء (0–100)",
    "علامة الكيمياء (0–100)",
    "علامة اللغة العربية (0–100)",
    "علامة اللغة الأجنبية (0–100)",
    # constraints (cont'd)
    "هل يمكنك الدراسة خارج مدينتك؟",
    "هل يمكنك الدراسة في جامعة خاصة؟_encoded",
]

assert len(clustering_columns) == 30, (
    f"Expected 30 clustering columns, got {len(clustering_columns)}"
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
