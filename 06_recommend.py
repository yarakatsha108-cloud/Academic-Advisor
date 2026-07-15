"""
Stage 6: Recommend majors for a new student using the saved clustering model.

- Loads scaler.pkl / kmeans_model.pkl / feature_columns.pkl (all produced by
  02_scale.py and 04_clustering.py) so inference reuses the exact same
  transform and model that were fit on the training data - no refitting.
- academic_branch ("الفرع الدراسي") is deliberately NOT one of the 30
  clustering features (see 01_clean_encode.py) - it's applied here only as
  a post-cluster filter, same as that file's original design note.
- FRIENDLY_ORDER below spells out the 30 clustering columns as readable
  English names, in the exact order clustering_columns was built in
  02_scale.py. Zipping it against feature_columns.pkl means the Arabic
  survey text is never retyped by hand here (a transcription slip would
  silently misalign a feature) - the pickle stays the single source of
  truth for column identity/order, this file only names the positions.
"""

import pickle
import sys

import pandas as pd

# The report below prints arrows/checkmarks/emoji that don't exist in
# Windows' legacy console code pages (e.g. cp1256) - force UTF-8 stdout so
# `python 06_recommend.py` doesn't crash mid-report on a non-UTF-8 terminal.
sys.stdout.reconfigure(encoding="utf-8")

with open("scaler.pkl", "rb") as f:
    scaler = pickle.load(f)
with open("kmeans_model.pkl", "rb") as f:
    kmeans = pickle.load(f)
with open("feature_columns.pkl", "rb") as f:
    FEATURE_COLUMNS = pickle.load(f)

FRIENDLY_ORDER = [
    "age",
    "interest_programming",
    "interest_math",
    "interest_physics_engineering",
    "interest_medicine",
    "interest_chemistry_biology",
    "interest_languages",
    "interest_humanities",
    "interest_economics",
    "interest_arts",
    "interest_law",
    "prefer_theoretical",
    "enjoy_complex_problems",
    "prefer_people_over_computer",
    "handle_academic_pressure",
    "prefer_job_stability",
    "priority_income",
    "priority_social_status",
    "priority_passion",
    "priority_job_stability",
    "willing_compromise_encoded",
    "willing_follow_parents_encoded",
    "family_financial_encoded",
    "math_grade",
    "physics_grade",
    "chemistry_grade",
    "arabic_grade",
    "foreign_language_grade",
    "can_study_outside_city",
    "can_study_private_university_encoded",
]
assert len(FRIENDLY_ORDER) == len(FEATURE_COLUMNS) == 30, (
    "FRIENDLY_ORDER must name every clustering column, in the same order "
    "as feature_columns.pkl"
)
FRIENDLY_TO_COLUMN = dict(zip(FRIENDLY_ORDER, FEATURE_COLUMNS))

CLUSTER_NAMES = {
    0: "Undecided Scientific",
    1: "Confident Scientific",
    2: "Humanities",
}

CLUSTER_CANDIDATES = {
    0: ["Medicine", "Engineering", "Computer Science", "Law"],
    1: ["Medicine", "Engineering", "Computer Science"],
    2: ["Law", "Humanities", "Economics", "Arts"],
}

# (requirement label, threshold) - checked against science_avg or math_grade
# below. Law/Humanities/Arts have no grade requirement and are absent here.
GRADE_REQUIREMENTS = {
    "Medicine": ("science_avg (math+physics+chemistry)/3", 80),
    "Engineering": ("science_avg (math+physics+chemistry)/3", 75),
    "Computer Science": ("math grade", 70),
    "Economics": ("math grade", 60),
}

# A grade up to this many points below the threshold is "borderline" -
# still counted as MATCHED, just flagged, rather than dropped outright.
BORDERLINE_MARGIN = 5

# Beyond the borderline margin but within this many points of the
# threshold, a grade-only miss becomes an ASPIRATION major instead of
# being dropped outright (a hard constraint miss - branch/private - is
# never an aspiration major, regardless of grade).
ASPIRATION_MARGIN = 15

# Short display label for each grade-requirement metric (GRADE_REQUIREMENTS
# keys use the full formula for the "excluded" reason text; the aspiration
# report is more compact).
SHORT_METRIC_LABEL = {
    "science_avg (math+physics+chemistry)/3": "science_avg",
    "math grade": "math grade",
}

BRANCH_NAMES = {1: "Scientific", 2: "Literary", 3: "Commercial", 4: "Vocational", 5: "Industrial"}


def recommend_majors(student_answers, academic_branch):
    """
    student_answers: dict mapping each of the 30 clustering feature column
    names (feature_columns.pkl) to the student's raw answer - same units/
    encoding the model was trained on (e.g. "_encoded" columns as
    {0, 0.5, 1}, grades as 0-100).
    academic_branch: raw "الفرع الدراسي" code (1/2/3/4/5).

    Returns a dict with the assigned cluster and the cluster's candidates
    split into:
      - matched_majors: pass every grade and constraint check (borderline
        grades - within BORDERLINE_MARGIN of the threshold - still count
        as matched).
      - aspiration_majors: excluded ONLY by a grade gap between
        BORDERLINE_MARGIN and ASPIRATION_MARGIN points (a branch/private
        constraint miss is never an aspiration major, no matter the grade).
    `evaluations` carries the full per-candidate trace (including majors
    dropped entirely, gap > ASPIRATION_MARGIN or a hard constraint) for
    debugging/transparency.
    """
    missing = [c for c in FEATURE_COLUMNS if c not in student_answers]
    if missing:
        raise ValueError(f"Missing required feature(s): {missing}")

    row = pd.DataFrame([[student_answers[c] for c in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    row_scaled = scaler.transform(row)
    cluster_id = int(kmeans.predict(row_scaled)[0])

    math_grade = student_answers[FRIENDLY_TO_COLUMN["math_grade"]]
    physics_grade = student_answers[FRIENDLY_TO_COLUMN["physics_grade"]]
    chemistry_grade = student_answers[FRIENDLY_TO_COLUMN["chemistry_grade"]]
    science_avg = (math_grade + physics_grade + chemistry_grade) / 3
    can_study_private = student_answers[FRIENDLY_TO_COLUMN["can_study_private_university_encoded"]]

    metric_values = {
        "science_avg (math+physics+chemistry)/3": science_avg,
        "math grade": math_grade,
    }

    matched_majors = []
    aspiration_majors = []
    evaluations = []

    for major in CLUSTER_CANDIDATES[cluster_id]:
        # Hard eligibility constraints are checked first: a branch/private
        # miss disqualifies a major outright, so it can never be an
        # aspiration major regardless of how close the grades are.
        if major == "Arts" and can_study_private == 0:
            evaluations.append(
                (major, "excluded", "Arts is only offered privately; student cannot study privately")
            )
            continue

        if academic_branch == 2 and major in ("Medicine", "Engineering", "Computer Science"):
            evaluations.append((major, "excluded", "Literary branch excludes this major"))
            continue

        if academic_branch in (4, 5) and major == "Medicine":
            branch_name = BRANCH_NAMES.get(academic_branch, academic_branch)
            evaluations.append((major, "excluded", f"{branch_name} branch excludes Medicine"))
            continue

        if major not in GRADE_REQUIREMENTS:
            matched_majors.append(major)
            evaluations.append((major, "matched", "no grade requirement"))
            continue

        label, threshold = GRADE_REQUIREMENTS[major]
        value = metric_values[label]
        gap = threshold - value

        if gap <= 0:
            matched_majors.append(major)
            evaluations.append((major, "matched", f"{label} = {value:.1f}, meets required {threshold}"))
        elif gap <= BORDERLINE_MARGIN:
            matched_majors.append(major)
            evaluations.append(
                (major, "matched", f"borderline - {label} = {value:.1f}, required {threshold}")
            )
        elif gap < ASPIRATION_MARGIN:
            aspiration_majors.append(
                {
                    "major": major,
                    "metric_label": SHORT_METRIC_LABEL[label],
                    "current": round(value, 1),
                    "threshold": threshold,
                    "gap": round(gap, 1),
                }
            )
            evaluations.append(
                (major, "aspiration", f"{label} = {value:.1f}, needs {threshold} (+{gap:.1f})")
            )
        else:
            evaluations.append(
                (major, "excluded", f"{label} = {value:.1f}, far below required {threshold} (+{gap:.1f})")
            )

    aspiration_majors.sort(key=lambda item: item["gap"])

    return {
        "cluster": cluster_id,
        "cluster_name": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
        "science_avg": round(science_avg, 1),
        "math_grade": math_grade,
        "matched_majors": matched_majors,
        "aspiration_majors": aspiration_majors,
        "evaluations": evaluations,
    }


# --- Demo student builder ---
# Fills in the 27 clustering answers a demo persona doesn't care about with
# neutral midpoint defaults, so each example below only needs to set the
# handful of fields that actually define that persona.
DEFAULT_STUDENT = {
    "age": 18,
    "interest_programming": 3,
    "interest_math": 3,
    "interest_physics_engineering": 3,
    "interest_medicine": 3,
    "interest_chemistry_biology": 3,
    "interest_languages": 3,
    "interest_humanities": 3,
    "interest_economics": 3,
    "interest_arts": 3,
    "interest_law": 3,
    "prefer_theoretical": 3,
    "enjoy_complex_problems": 3,
    "prefer_people_over_computer": 3,
    "handle_academic_pressure": 3,
    "prefer_job_stability": 3,
    "priority_income": 2,
    "priority_social_status": 2,
    "priority_passion": 2,
    "priority_job_stability": 2,
    "willing_compromise_encoded": 0.5,
    "willing_follow_parents_encoded": 0.5,
    "family_financial_encoded": 1,
    "math_grade": 70,
    "physics_grade": 70,
    "chemistry_grade": 70,
    "arabic_grade": 70,
    "foreign_language_grade": 70,
    "can_study_outside_city": 1,
    "can_study_private_university_encoded": 1.0,
}
assert set(DEFAULT_STUDENT) == set(FRIENDLY_TO_COLUMN)


def make_student(academic_branch, **overrides):
    unknown = set(overrides) - set(DEFAULT_STUDENT)
    if unknown:
        raise ValueError(f"Unknown student attribute(s): {sorted(unknown)}")
    profile = {**DEFAULT_STUDENT, **overrides}
    answers = {FRIENDLY_TO_COLUMN[name]: value for name, value in profile.items()}
    return answers, academic_branch, profile


def print_report(label, profile, academic_branch, result):
    print(f"\n=== {label} ===")
    print("Profile:")
    print(f"  academic_branch: {BRANCH_NAMES.get(academic_branch, academic_branch)}")
    print(f"  grades -> math: {profile['math_grade']}, physics: {profile['physics_grade']}, "
          f"chemistry: {profile['chemistry_grade']}")
    print(f"  key interests (1-5) -> medicine: {profile['interest_medicine']}, "
          f"programming: {profile['interest_programming']}, humanities: {profile['interest_humanities']}, "
          f"law: {profile['interest_law']}")
    print(f"  can_study_private_university_encoded: {profile['can_study_private_university_encoded']}")

    print(f"\nAssigned cluster: {result['cluster']} ({result['cluster_name']})")
    print(f"science_avg = {result['science_avg']}, math_grade = {result['math_grade']}")

    print("\nCandidate evaluation:")
    for major, status, reason in result["evaluations"]:
        print(f"  [{status:10}] {major:<17} - {reason}")

    print("\nMATCHED MAJORS (ready to apply):")
    if result["matched_majors"]:
        for major in result["matched_majors"]:
            print(f"  → {major:<17} ✓")
    else:
        print("  (none)")

    print("\nASPIRATION MAJORS (strong fit, improve grades):")
    if result["aspiration_majors"]:
        for item in result["aspiration_majors"]:
            print(
                f"  → {item['major']:<17} !!!!  {item['metric_label']} {item['current']}, "
                f"need {item['threshold']} (+{item['gap']} needed)"
            )
    else:
        print("  (none)")


if __name__ == "__main__":
    # Demo only - runs when this file is executed directly (`python
    # 06_recommend.py`), not when other modules (e.g. 07_api.py) import
    # recommend_majors()/make_student() from it.

    # --- Student A: high science grades, high medicine interest, scientific branch ---
    a_answers, a_branch, a_profile = make_student(
        academic_branch=1,
        math_grade=92,
        physics_grade=90,
        chemistry_grade=88,
        interest_medicine=5,
        interest_chemistry_biology=5,
        interest_physics_engineering=4,
        enjoy_complex_problems=5,
        handle_academic_pressure=5,
    )

    # --- Student B: low science grades, high humanities interest, literary branch ---
    b_answers, b_branch, b_profile = make_student(
        academic_branch=2,
        math_grade=45,
        physics_grade=40,
        chemistry_grade=48,
        arabic_grade=85,
        foreign_language_grade=80,
        interest_humanities=5,
        interest_languages=4,
        interest_law=4,
        interest_programming=1,
        interest_physics_engineering=1,
        prefer_people_over_computer=5,
    )

    # --- Student C: medium grades, high CS interest, scientific branch ---
    c_answers, c_branch, c_profile = make_student(
        academic_branch=1,
        math_grade=68,
        physics_grade=65,
        chemistry_grade=67,
        interest_programming=4,
        interest_math=4,
        can_study_private_university_encoded=1.0,
    )

    for label, answers, branch, profile in [
        ("Student A", a_answers, a_branch, a_profile),
        ("Student B", b_answers, b_branch, b_profile),
        ("Student C", c_answers, c_branch, c_profile),
    ]:
        result = recommend_majors(answers, branch)
        print_report(label, profile, branch, result)
