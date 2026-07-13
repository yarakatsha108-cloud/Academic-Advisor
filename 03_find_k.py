"""
Stage 3: Choose K for KMeans.

- Load the scaled feature array from stage 2 (not the raw CSV) so the
  distance metric KMeans/silhouette use matches what will actually be
  clustered in stage 4.
- Try K = 2..10. We start at 2 (K=1 has no silhouette score - it's
  undefined for a single cluster) and cap at 10 since going higher on
  only 290 students risks clusters too small to interpret meaningfully.
- Silhouette score (not inertia alone) picks the final K: inertia keeps
  dropping as K grows (it always prefers more clusters), while
  silhouette balances cohesion vs separation and actually penalizes
  over-splitting.
"""

import os

# Avoid a known KMeans/MKL memory-leak warning on Windows when there are
# fewer data chunks than available threads - must be set before sklearn
# is imported.
os.environ.setdefault("OMP_NUM_THREADS", "2")

import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

X_scaled = np.load("X_scaled.npy")

print("=== CHECKPOINT: loaded scaled features ===")
print("shape:", X_scaled.shape)

k_range = range(2, 11)
inertias = []
silhouette_scores = []

for k in k_range:
    # n_init=10 and a fixed random_state make this reproducible and avoid
    # a single unlucky centroid initialization skewing the comparison
    # across K values.
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    inertias.append(km.inertia_)
    score = silhouette_score(X_scaled, labels)
    silhouette_scores.append(score)
    print(f"K={k}: inertia={km.inertia_:.2f}, silhouette={score:.4f}")

best_k = list(k_range)[int(np.argmax(silhouette_scores))]
print(f"\n=== CHECKPOINT: best K by silhouette score = {best_k} ===")

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

axes[0].plot(list(k_range), inertias, marker="o")
axes[0].set_title("Elbow Method (Inertia)")
axes[0].set_xlabel("K")
axes[0].set_ylabel("Inertia")
axes[0].grid(True, alpha=0.3)

axes[1].plot(list(k_range), silhouette_scores, marker="o", color="orange")
axes[1].axvline(best_k, color="red", linestyle="--", alpha=0.6, label=f"best K={best_k}")
axes[1].set_title("Silhouette Score")
axes[1].set_xlabel("K")
axes[1].set_ylabel("Silhouette Score")
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("elbow_silhouette.png", dpi=150)
print("\nSaved elbow_silhouette.png")
