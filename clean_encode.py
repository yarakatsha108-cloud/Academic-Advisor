import pandas as pd

RAW_CSV = "استبيان_اختيار_التخصص_الجامعي_لطلاب_الصف_الثالث_الثانوي_Responses.csv"
OUT_CSV = "data_unified.csv"

df = pd.read_csv(RAW_CSV, encoding="utf-8")

print("=== CHECKPOINT: raw load ===")
print("shape:", df.shape)
print("nulls:", int(df.isnull().sum().sum()))
print("duplicates:", int(df.duplicated().sum()))

df = df.drop(columns=["Timestamp"])
print("\n=== CHECKPOINT: after dropping Timestamp ===")
print("shape:", df.shape)


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

branch_col = "الفرع الدراسي"
print(f"\n=== CHECKPOINT: {branch_col} value counts (descriptive only, not scaled/clustered) ===")
print(df[branch_col].value_counts().sort_index())

print("\n=== CHECKPOINT: final verification ===")
print("shape:", df.shape)
print("nulls:", int(df.isnull().sum().sum()))
print("duplicates:", int(df.duplicated().sum()))
assert df.isnull().sum().sum() == 0, "Nulls remain after cleaning"
assert df.duplicated().sum() == 0, "Duplicate rows remain after cleaning"

df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\nSaved unified dataset -> {OUT_CSV}")
