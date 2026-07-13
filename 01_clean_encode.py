"""
Stage 1: Clean and encode the raw survey CSV.

- Drop Timestamp (not a feature, not needed for validation either).
- Remap the 3 ordinal constraint columns from Google Forms codes {0,1,2}
  to {0, 0.5, 1} so their spacing reflects "no < somewhat < yes" evenly.
  We keep the ORIGINAL column too (suffixed _encoded is the new one) so
  nothing is lost and later steps can still show human-readable raw values.
- Verify zero nulls / zero duplicates, since KMeans and StandardScaler
  downstream cannot handle NaNs and duplicate rows would double-count
  students in cluster profiles.
  
"""

import pandas as pd

RAW_CSV = "استبيان_اختيار_التخصص_الجامعي_لطلاب_الصف_الثالث_الثانوي_Responses.csv"
OUT_CSV = "data_unified.csv"

# Google Forms writes UTF-8 without a BOM issue here, but we pin the
# encoding explicitly so this doesn't silently break on another machine.
df = pd.read_csv(RAW_CSV, encoding="utf-8")

print("=== CHECKPOINT: raw load ===")
print("shape:", df.shape)
print("nulls:", int(df.isnull().sum().sum()))
print("duplicates:", int(df.duplicated().sum()))

# Timestamp has no predictive or descriptive value for major recommendation.
df = df.drop(columns=["Timestamp"])
print("\n=== CHECKPOINT: after dropping Timestamp ===")
print("shape:", df.shape)

# The 3 ordinal "willingness" columns come from Google Forms as raw
# integer codes {0,1,2}. We add an _encoded column remapped to
# {0, 0.5, 1} so "somewhat" sits exactly halfway between "no" and "yes" -
# this matters for interpretability in the cluster-profile step later,
# even though StandardScaler would normalize either encoding the same way.
ordinal_map = {0: 0.0, 1: 0.5, 2: 1.0}

ordinal_cols = [
    "هل أنت مستعد للتنازل عن رغبتك الأولى إذا كان هناك تخصص قريب منها",
    "هل أنت مستعد لتحقيق رغبة الأهل على حساب رغبتك الشخصية؟",
    "هل يمكنك الدراسة في جامعة خاصة؟",
]

for col in ordinal_cols:
    assert set(df[col].unique()).issubset({0, 1, 2}), (
        f"Unexpected values in {col}: {sorted(df[col].unique())}"
    )
    df[col + "_encoded"] = df[col].map(ordinal_map)

print("\n=== CHECKPOINT: after ordinal remap ===")
print("shape:", df.shape)
print("new columns added:", [c + "_encoded" for c in ordinal_cols])

# family_financial_status ("القدرة المادية للعائلة") is documented as
# binary 0=limited/1=good but the raw CSV actually contains Google Forms
# codes {1,2} (1=limited, 2=good, confirmed against the source form's
# option order: 144 respondents coded 1, 146 coded 2). We remap to
# {0,1} in a new _encoded column (keeping the original raw column
# too, same convention as the other ordinal columns above) so
# downstream scaling/clustering uses the documented 0/1 semantics.
financial_col = "القدرة المادية للعائلة"
financial_map = {1: 0, 2: 1}
assert set(df[financial_col].unique()).issubset(set(financial_map)), (
    f"Unexpected values in {financial_col}: {sorted(df[financial_col].unique())}"
)
df[financial_col + "_encoded"] = df[financial_col].map(financial_map)

print("\n=== CHECKPOINT: after family_financial_status remap ===")
print("shape:", df.shape)
print(f"{financial_col} raw value counts:\n{df[financial_col].value_counts().sort_index()}")
print(f"{financial_col}_encoded value counts:\n{df[financial_col + '_encoded'].value_counts().sort_index()}")

# academic_branch ("الفرع الدراسي") is NOT a clustering feature - it's a
# descriptive column reserved for a post-recommendation filter (applied
# after clustering, not part of it): scientific branch -> all majors
# available; literary branch -> exclude medicine/engineering/pharmacy/CS;
# commercial branch -> keep only economics/accounting/business/law.
# Raw codes present in this dataset are {1,2,4,5} (3 does not appear -
# confirmed via value_counts, not a data error). Per the original survey's
# option order, the full legend is:
#   1 = علمي (scientific), 2 = أدبي (literary), 3 = تجاري (commercial),
#   4 = مهني (vocational), 5 = صناعي (industrial)
# Code 3 (تجاري/commercial) simply has zero respondents in this sample.
branch_col = "الفرع الدراسي"
print(f"\n=== CHECKPOINT: {branch_col} value counts (descriptive only, not scaled/clustered) ===")
print(df[branch_col].value_counts().sort_index())

# Final integrity check before saving: KMeans/StandardScaler downstream
# require a fully numeric, null-free, duplicate-free table.
print("\n=== CHECKPOINT: final verification ===")
print("shape:", df.shape)
print("nulls:", int(df.isnull().sum().sum()))
print("duplicates:", int(df.duplicated().sum()))
assert df.isnull().sum().sum() == 0, "Nulls remain after cleaning"
assert df.duplicated().sum() == 0, "Duplicate rows remain after cleaning"

df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\nSaved unified dataset -> {OUT_CSV}")
