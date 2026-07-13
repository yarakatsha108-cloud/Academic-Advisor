"""
Stage 4: Final clustering.

- Re-fit KMeans at the best K found in stage 3 (by silhouette score).
- random_state=42 and n_init=10 match stage 3 exactly so the model here
  is reproducible and comparable to what was evaluated there.
- Cluster labels are attached back to the full data_unified.csv (not
  just the scaled array) so descriptive/validation columns stay next to
  each student's cluster for stage 5's interpretation step.
"""

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")

import pickle
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Best K from stage 3's silhouette search. Note: on this dataset K=2 wins
# by silhouette score, but the margin over K=3/K=7 is small (0.138 vs
# 0.11-0.065) and all scores are low (<0.14), meaning cluster structure
# in this feature space is weak overall - the students don't separate
# into sharply distinct groups. Worth re-checking against domain
# expectations (e.g. does a 2-way split actually differentiate majors
# usefully) rather than trusting silhouette blindly.
BEST_K = 3

X_scaled = np.load("X_scaled.npy")
df = pd.read_csv("data_unified.csv", encoding="utf-8-sig")

print("=== CHECKPOINT: inputs loaded ===")
print("X_scaled shape:", X_scaled.shape)
print("data_unified shape:", df.shape)
assert len(df) == X_scaled.shape[0], "Row count mismatch between CSV and scaled array"

kmeans = KMeans(n_clusters=BEST_K, random_state=42, n_init=10)
labels = kmeans.fit_predict(X_scaled)
score = silhouette_score(X_scaled, labels)

print(f"\n=== CHECKPOINT: KMeans fit with K={BEST_K} ===")
print("inertia:", round(kmeans.inertia_, 2))
print("silhouette:", round(score, 4))
print("cluster sizes:\n", pd.Series(labels).value_counts().sort_index())

df["cluster"] = labels

print("\n=== CHECKPOINT: cluster column attached ===")
print("shape:", df.shape)
print("nulls:", int(df.isnull().sum().sum()))

df.to_csv("data_with_clusters.csv", index=False, encoding="utf-8-sig")
with open("kmeans_model.pkl", "wb") as f:
    pickle.dump(kmeans, f)

print("\nSaved data_with_clusters.csv, kmeans_model.pkl")
