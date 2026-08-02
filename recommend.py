"""
Recommend majors for a new student using the saved clustering model.

- Loads scaler.pkl / kmeans_model.pkl / feature_columns.pkl (all produced by
  scale.py and clustering.py) so inference reuses the exact same
  transform and model that were fit on the training data - no refitting.
- academic_branch ("الفرع الدراسي") is deliberately NOT one of the 20
  clustering features (see clean_encode.py) - it's applied here only as
  a post-cluster filter, same as that file's original design note.
- FRIENDLY_ORDER below spells out the 20 clustering columns as readable
  English names, in the exact order clustering_columns was built in
  scale.py. Zipping it against feature_columns.pkl means the Arabic
  survey text is never retyped by hand here (a transcription slip would
  silently misalign a feature) - the pickle stays the single source of
  truth for column identity/order, this file only names the positions.

- Reduced from 30 to 20 clustering features (see scale.py's docstring
  for the weak-feature-ranking methodology). 5 of the 10 dropped features
  were removed from the system entirely (age, willing_compromise,
  willing_follow_parents, family_financial, prefer_job_stability - no
  rule anywhere depends on them). The other 5 still drive real logic, so
  they're now explicit recommend_majors() parameters instead of clustering
  inputs: can_study_private_university_encoded (hard Arts eligibility
  gate - unchanged), can_study_outside_city (soft advisory note),
  interest_programming/interest_languages/prefer_people_over_computer
  (priority-boost tie-breakers within a cluster's candidate majors). See
  the "Priority-boost tie-breakers" section below.

- ADDED: youtube_suggestions (curated teacher/channel suggestions) and
  study_schedule (a weighted weekly study-time planner) - both advisory
  add-ons layered on top of the matched/aspiration major logic, not part
  of the clustering or grade-requirement decisions themselves. Both are
  driven by identify_subjects_needing_attention(), which flags a subject
  either for a low raw grade (< WEAK_GRADE_THRESHOLD) or for feeding an
  aspiration major's metric (e.g. physics=65 isn't "weak" on its own, but
  if it's part of a science_avg blocking a Medicine aspiration, it still
  gets flagged). If a student has neither - nothing below threshold, no
  aspiration major to close - study_schedule falls back to a light
  "maintenance" plan instead of forcing a full corrective one on someone
  who doesn't need it, and youtube_suggestions is empty.
"""

import math
import pickle
import sys

import pandas as pd

# The report below prints arrows/checkmarks/emoji that don't exist in
# Windows' legacy console code pages (e.g. cp1256) - force UTF-8 stdout so
# `python recommend.py` doesn't crash mid-report on a non-UTF-8 terminal.
sys.stdout.reconfigure(encoding="utf-8")

with open("scaler.pkl", "rb") as f:
    scaler = pickle.load(f)
with open("kmeans_model.pkl", "rb") as f:
    kmeans = pickle.load(f)
with open("feature_columns.pkl", "rb") as f:
    FEATURE_COLUMNS = pickle.load(f)

FRIENDLY_ORDER = [
    "interest_math",
    "interest_physics_engineering",
    "interest_medicine",
    "interest_chemistry_biology",
    "interest_humanities",
    "interest_economics",
    "interest_arts",
    "interest_law",
    "prefer_theoretical",
    "enjoy_complex_problems",
    "handle_academic_pressure",
    "priority_income",
    "priority_social_status",
    "priority_passion",
    "priority_job_stability",
    "math_grade",
    "physics_grade",
    "chemistry_grade",
    "arabic_grade",
    "foreign_language_grade",
]
assert len(FRIENDLY_ORDER) == len(FEATURE_COLUMNS) == 20, (
    "FRIENDLY_ORDER must name every clustering column, in the same order "
    "as feature_columns.pkl"
)
FRIENDLY_TO_COLUMN = dict(zip(FRIENDLY_ORDER, FEATURE_COLUMNS))

# Verified against the 20-feature refit's cluster_heatmap.png/profile means
# (analyze.py) - cluster IDs are arbitrary per-refit and are NOT the same
# mapping as the old 30-feature model (there, 0/2 were swapped).
CLUSTER_NAMES = {
    0: "Humanities",
    1: "Confident Scientific",
    2: "Undecided Scientific",
}

CLUSTER_CANDIDATES = {
    2: ["Medicine", "Engineering", "Computer Science", "Law"],
    1: ["Medicine", "Engineering", "Computer Science"],
    0: ["Law", "Humanities", "Economics", "Arts"],
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

# Reverse of SHORT_METRIC_LABEL, but pointing to which raw subject columns
# feed each aspiration-major metric. Used to flag "this subject is holding
# back an aspiration major" even when the subject's own grade is above
# WEAK_GRADE_THRESHOLD - e.g. physics=65 isn't "weak" on its own, but if
# it's part of a science_avg that's blocking an aspiration major, it's
# still worth flagging.
SHORT_METRIC_TO_SUBJECTS = {
    "science_avg": {"math_grade", "physics_grade", "chemistry_grade"},
    "math grade": {"math_grade"},
}

BRANCH_NAMES = {1: "Scientific", 2: "Literary", 3: "Commercial", 4: "Vocational", 5: "Industrial"}

# exam_stage controls whether "improve your grade" advice makes sense at
# all. aspiration_majors/youtube_suggestions/study_schedule all implicitly
# assume the student's grades can still change - true mid-year, and true
# right after "الدور الأول" if a "دور تكميلي" (supplementary/makeup round)
# is still available for a weak subject. Once grades are genuinely final
# (no more rounds), that framing is actively misleading - a gap the
# student can no longer close shouldn't be shown as something to work
# toward, and there's nothing left to suggest a study plan or teacher for.
EXAM_STAGES = {"mid_year", "supplementary_round_available", "final"}
IMPROVABLE_STAGES = {"mid_year", "supplementary_round_available"}


# =====================================================================
# YouTube teacher suggestions for weak subjects
# =====================================================================
# WEAK_GRADE_THRESHOLD is deliberately separate from GRADE_REQUIREMENTS
# above (which range 60-80 and gate specific majors). This is a general
# "could use extra support" flag used only for advice, not for excluding
# or matching any major.
WEAK_GRADE_THRESHOLD = 65

SUBJECT_DISPLAY_NAMES = {
    "math_grade": "Math",
    "physics_grade": "Physics",
    "chemistry_grade": "Chemistry",
    "arabic_grade": "Arabic",
    "foreign_language_grade": "Foreign language",
}

# Curated via web search (not a live API call, and not manually clicked
# through one by one) for teachers/channels covering the Syrian bakalorya
# curriculum specifically, since most "best chemistry teacher on YouTube"
# results skew Egyptian and don't match the Syrian syllabus. Treat this as
# a starting point to spot-check periodically - channel names/links can
# go stale, and a research pass should be re-run occasionally rather than
# trusting this list indefinitely.
YOUTUBE_SUGGESTIONS = {
    "math_grade": [
        {"teacher": "فارس جقل", "note": "شرح منهاج الرياضيات كامل لبكالوريا سوريا (يوتيوب + تلغرام)"},
        {"teacher": "خالد العبدالله", "note": "رياضيات بكالوريا وجامعة، منهاج سوري",
         "youtube": "https://www.youtube.com/@خالدالعبدالله-٣6م"},
    ],
    "physics_grade": [
        {"teacher": "مؤيد بكر - أكاديمية الفيزياء الإلكترونية", "note": "فيزياء بكالوريا، منهاج سوري",
         "youtube": "https://www.youtube.com/channel/UCENwdX2QOUBVXC2OCYmc1Rg"},
        {"teacher": "حسام المسالمة", "note": "شرح فيزياء", "youtube": "https://www.youtube.com/@HousamMasalma"},
    ],
    "chemistry_grade": [
        {"teacher": "أسامة الحصري - كيمياء بكالوريا", "note": "منهاج سوري، أوراق عمل وحلول دورات",
         "youtube": "https://www.youtube.com/@-.3613"},
        {"teacher": "فارس جقل", "note": "كيمياء بكالوريا حديث - منهاج سوري"},
    ],
    "arabic_grade": [
        {"teacher": "عمر سويد", "note": "منهاج اللغة العربية للثالث الثانوي، الفرعين العلمي والأدبي، سوريا"},
        {"teacher": "رامي تكريتي", "note": "قواعد اللغة العربية لطلاب البكالوريا، الفرعين"},
    ],
    "foreign_language_grade": [
        {"teacher": "طارق شريف - البوابة التعليمية", "note": "قواعد اللغة الإنكليزية لبكالوريا سوريا، الفرعين"},
        {"teacher": "د. فادي العيسى", "note": "منصة سورية غير ربحية متخصصة بتعليم الإنكليزي"},
    ],
}


def identify_weak_subjects(student_answers):
    """Returns {subject_key: grade} for every one of the 5 core grade
    subjects below WEAK_GRADE_THRESHOLD, with NO regard to which majors
    the student is chasing. This alone used to drive youtube_suggestions
    and the study schedule, which produced two bad results in practice:
    a student sitting at 65-68 in math/physics/chemistry - exactly what's
    blocking their Medicine/Engineering ASPIRATION majors - got flagged
    as having nothing to work on, because 65-68 isn't "generically weak".
    See identify_subjects_needing_attention() below for the fix; this
    function is kept only as one input to that combined check."""
    grades = {
        subj: student_answers[FRIENDLY_TO_COLUMN[subj]]
        for subj in SUBJECT_DISPLAY_NAMES
    }
    return {subj: grade for subj, grade in grades.items() if grade < WEAK_GRADE_THRESHOLD}


def identify_subjects_needing_attention(student_answers, aspiration_majors):
    """Combines two independent reasons a subject deserves youtube
    suggestions / extra schedule weight:
      - "below_threshold": grade < WEAK_GRADE_THRESHOLD, regardless of
        whether any major needs it (generic "could use support").
      - "aspiration_target": the subject feeds the metric of an
        aspiration_major (e.g. math/physics/chemistry for a science_avg-
        gated aspiration like Medicine/Engineering), even if the grade
        itself is >= WEAK_GRADE_THRESHOLD - it's still what's standing
        between the student and that major.
    A subject hit by both gets reason "both". Returns
    {subject_key: {"grade": float, "reason": str}}; empty dict means the
    student has nothing below the generic threshold AND every candidate
    major is already matched (no aspiration gap to close) - genuinely
    nothing to recommend.
    """
    grades = {
        subj: student_answers[FRIENDLY_TO_COLUMN[subj]]
        for subj in SUBJECT_DISPLAY_NAMES
    }
    attention = {}
    for subj, grade in grades.items():
        if grade < WEAK_GRADE_THRESHOLD:
            attention[subj] = {"grade": grade, "reason": "below_threshold"}
    for item in aspiration_majors:
        for subj in SHORT_METRIC_TO_SUBJECTS.get(item["metric_label"], set()):
            if subj not in attention:
                attention[subj] = {"grade": grades[subj], "reason": "aspiration_target"}
            elif attention[subj]["reason"] == "below_threshold":
                # Only upgrade to "both" the first time - if a LATER
                # aspiration major (e.g. Medicine after Engineering, both
                # science_avg-gated) touches the same subject again, it's
                # already "aspiration_target"/"both" and must not be
                # re-processed, or two aspiration majors sharing a metric
                # would incorrectly look like "both" reasons.
                attention[subj]["reason"] = "both"
    return attention


def build_youtube_suggestions(attention_subjects):
    """attention_subjects: dict from identify_subjects_needing_attention().
    Returns a dict keyed by display subject name -> list of curated
    teacher suggestions, only for subjects actually in that dict (empty
    dict if the student has nothing to work on)."""
    return {
        SUBJECT_DISPLAY_NAMES[subj]: YOUTUBE_SUGGESTIONS.get(subj, [])
        for subj in attention_subjects
    }


# =====================================================================
# Weekly study schedule generator
# =====================================================================
# Assumptions (documented here since they are not derivable from the
# survey data - they're a reasonable default, meant to be adjustable):
#   - Syrian school week: Sunday-Thursday are school days (one evening
#     review block each), Friday-Saturday is the weekend (two longer
#     blocks each, for new material + practice).
#   - Total weekly study capacity in this plan: 9 blocks x 2h = 18h.
#   - Every one of the 5 core subjects gets at least 1 weekly block, even
#     if not weak, so review doesn't fully drop off; weak subjects get
#     extra blocks proportional to how far below WEAK_GRADE_THRESHOLD
#     they are.
SCHOOL_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
WEEKEND_DAYS = ["Friday", "Saturday"]
SCHOOL_DAY_BLOCKS = [("17:00-19:00", 2.0)]
WEEKEND_DAY_BLOCKS = [("10:00-12:00", 2.0), ("16:00-18:00", 2.0)]

# When identify_subjects_needing_attention() returns empty (no subject
# below WEAK_GRADE_THRESHOLD, no aspiration major to close a gap for) -
# a fully-matched, no-weak-grade student like "Student A" - a full 9-block/
# 18h corrective plan is the wrong output. These two light weekend blocks
# replace it: general review, not subject-targeted, clearly optional.
MAINTENANCE_BLOCKS = [("Friday", "10:00-12:00", 2.0), ("Saturday", "10:00-12:00", 2.0)]


def _compute_subject_weights(grades, attention_subjects):
    # Baseline weight 1 for every subject. +deficit/10 for subjects below
    # WEAK_GRADE_THRESHOLD (weakest pull proportionally more blocks). A
    # flat +1.0 bonus for subjects flagged "aspiration_target"/"both" -
    # i.e. subjects standing between the student and an aspiration major,
    # even if the grade itself isn't "weak" (e.g. physics=65 blocking an
    # 80-average Medicine aspiration still needs priority).
    weights = {}
    for subj, grade in grades.items():
        w = 1.0 + max(0.0, WEAK_GRADE_THRESHOLD - grade) / 10.0
        info = attention_subjects.get(subj)
        if info and info["reason"] in ("aspiration_target", "both"):
            w += 1.0
        weights[subj] = w
    return weights


def _allocate_blocks(weights, total_blocks):
    """Largest-remainder apportionment of total_blocks across subjects,
    weighted by `weights`, with every subject guaranteed >= 1 block."""
    subjects = list(weights.keys())
    n = len(subjects)
    assert total_blocks >= n, "need at least 1 block per subject"
    total_weight = sum(weights.values())
    raw = {s: weights[s] / total_weight * total_blocks for s in subjects}
    alloc = {s: max(1, math.floor(raw[s])) for s in subjects}

    diff = total_blocks - sum(alloc.values())
    if diff > 0:
        order = sorted(subjects, key=lambda s: (raw[s] - math.floor(raw[s])), reverse=True)
        i = 0
        while diff > 0:
            alloc[order[i % n]] += 1
            diff -= 1
            i += 1
    elif diff < 0:
        order = sorted(subjects, key=lambda s: weights[s])
        i = 0
        while diff < 0:
            s = order[i % n]
            if alloc[s] > 1:
                alloc[s] -= 1
                diff += 1
            i += 1
    return alloc


def build_weekly_schedule(student_answers, attention_subjects):
    """Builds a day-by-day weekly study schedule, weighted toward
    attention_subjects (see identify_subjects_needing_attention). If
    attention_subjects is empty - nothing below WEAK_GRADE_THRESHOLD and
    every candidate major already matched - returns a light 2-block
    "maintenance" plan instead of forcing the full 9-block corrective one
    on a student who doesn't need it."""
    if not attention_subjects:
        schedule_by_day = {day: [] for day in SCHOOL_DAYS + WEEKEND_DAYS}
        for day, time_range, hours in MAINTENANCE_BLOCKS:
            schedule_by_day[day].append({
                "time": time_range,
                "subject": "General review",
                "hours": hours,
                "focus": "مراجعة عامة اختيارية - لا توجد مادة ضعيفة ولا تخصص طموح يحتاج تحسين حالياً",
            })
        return {
            "mode": "maintenance",
            "attention_subjects": {},
            "schedule": schedule_by_day,
            "weekly_hours_by_subject": {},
            "assumptions": (
                "كل العلامات فوق الحد الأدنى وكل التخصصات المرشّحة matched بدون aspiration - "
                "جدول مراجعة خفيف اختياري (4 ساعات/أسبوع، عطلة فقط) بدل خطة تصحيحية مكثفة."
            ),
        }

    grades = {
        subj: student_answers[FRIENDLY_TO_COLUMN[subj]]
        for subj in SUBJECT_DISPLAY_NAMES
    }
    weights = _compute_subject_weights(grades, attention_subjects)

    slots = [(day, t, h) for day in SCHOOL_DAYS for t, h in SCHOOL_DAY_BLOCKS]
    slots += [(day, t, h) for day in WEEKEND_DAYS for t, h in WEEKEND_DAY_BLOCKS]
    total_blocks = len(slots)

    alloc = _allocate_blocks(weights, total_blocks)

    # Weighted round-robin queue (highest-priority subjects appear
    # earliest/most often) rather than clumping one subject's blocks.
    queue = []
    remaining = dict(alloc)
    while sum(remaining.values()) > 0:
        for subj in sorted(remaining, key=lambda s: -weights[s]):
            if remaining[subj] > 0:
                queue.append(subj)
                remaining[subj] -= 1

    schedule_by_day = {day: [] for day in SCHOOL_DAYS + WEEKEND_DAYS}
    used_today = {day: set() for day in SCHOOL_DAYS + WEEKEND_DAYS}
    pending = list(queue)
    for day, time_range, hours in slots:
        chosen = None
        for i, subj in enumerate(pending):
            if subj not in used_today[day]:
                chosen = pending.pop(i)
                break
        if chosen is None:
            chosen = pending.pop(0)
        used_today[day].add(chosen)
        info = attention_subjects.get(chosen)
        if info is None:
            focus = "مراجعة عامة"
        elif info["reason"] == "below_threshold":
            focus = "مراجعة نظرية + حل أسئلة (علامة تحت الحد الأدنى)"
        elif info["reason"] == "aspiration_target":
            focus = "مراجعة مركّزة - مطلوبة لتخصص طموح (aspiration)"
        else:
            focus = "مراجعة مركّزة - علامة ضعيفة وتخصص طموح معاً"
        schedule_by_day[day].append({
            "time": time_range,
            "subject": SUBJECT_DISPLAY_NAMES[chosen],
            "hours": hours,
            "focus": focus,
        })

    weekly_hours_by_subject = {
        SUBJECT_DISPLAY_NAMES[subj]: count * 2.0 for subj, count in alloc.items()
    }

    return {
        "mode": "corrective",
        "attention_subjects": {
            SUBJECT_DISPLAY_NAMES[s]: info for s, info in attention_subjects.items()
        },
        "schedule": schedule_by_day,
        "weekly_hours_by_subject": weekly_hours_by_subject,
        "assumptions": (
            "Sun-Thu: 1 evening block (17:00-19:00). Fri-Sat (weekend): 2 blocks "
            "each (10:00-12:00 new material, 16:00-18:00 practice). 18h/week total; "
            f"subjects below {WEAK_GRADE_THRESHOLD} or blocking an aspiration major get extra blocks."
        ),
    }


# =====================================================================
# Priority-boost tie-breakers (STEP 2 signals: interest_programming,
# interest_languages, prefer_people_over_computer)
# =====================================================================
# These 3 signals were dropped from the clustering vector (see scale.py)
# but still carry real signal for which candidate major within a cluster's
# already-decided matched/aspiration set to emphasize first. Unlike
# academic_branch/can_study_private_university_encoded above, they are NOT
# hard eligibility gates - a high score never adds a major that failed its
# grade/branch check, and a low score never removes one. They only reorder
# (move-to-front, stable otherwise) an already-built matched/aspiration
# list, so matched_majors/aspiration_majors keep their existing shape.
PRIORITY_BOOST_THRESHOLD = 4  # Likert 1-5; ">= 4" counts as "high"


def _apply_priority_boosts(majors, interest_programming, interest_languages, prefer_people_over_computer):
    """majors: matched_majors (list[str]) or aspiration_majors (list[dict]
    with a "major" key) - both are handled since boosting only moves
    whichever item names a target major to the front. Returns
    (reordered_list, boosts_applied), where boosts_applied is
    [{"major", "reason"}, ...] for transparency - only majors actually
    present in `majors` produce an entry (boosting a major a cluster
    doesn't offer is a silent no-op)."""
    def name_of(item):
        return item["major"] if isinstance(item, dict) else item

    reordered = list(majors)
    boosts_applied = []

    def boost(major, reason):
        for i, item in enumerate(reordered):
            if name_of(item) == major:
                reordered.insert(0, reordered.pop(i))
                boosts_applied.append({"major": major, "reason": reason})
                break

    if interest_programming >= PRIORITY_BOOST_THRESHOLD:
        boost("Computer Science", f"interest_programming >= {PRIORITY_BOOST_THRESHOLD}")
    if interest_languages >= PRIORITY_BOOST_THRESHOLD:
        boost("Humanities", f"interest_languages >= {PRIORITY_BOOST_THRESHOLD}")
    if prefer_people_over_computer >= PRIORITY_BOOST_THRESHOLD:
        boost("Medicine", f"prefer_people_over_computer >= {PRIORITY_BOOST_THRESHOLD}")
        boost("Law", f"prefer_people_over_computer >= {PRIORITY_BOOST_THRESHOLD}")

    return reordered, boosts_applied


# Soft informational note (STEP 2 signal: can_study_outside_city). NOT a
# hard threshold change - Syria's "مفاضلة" admission cutoffs by governorate/
# university shift yearly, so hardcoding numbers here would go stale. Shown
# only when it's actually actionable: the student has an aspiration major
# to potentially close a grade gap on AND can study outside their city.
CAN_STUDY_OUTSIDE_CITY_NOTE = (
    "بما إنك قادر تدرس خارج مدينتك، معدلات القبول ممكن تختلف حسب الجامعة/المحافظة - "
    "راجعي نتائج المفاضلة الرسمية على mohe.gov.sy قبل ما تحسمي، خصوصاً للتخصصات القريبة من العتبة."
)


def recommend_majors(
    student_answers,
    academic_branch,
    can_study_private_university_encoded,
    can_study_outside_city,
    interest_programming,
    interest_languages,
    prefer_people_over_computer,
    exam_stage="mid_year",
):
    """
    student_answers: dict mapping each of the 20 clustering feature column
    names (feature_columns.pkl) to the student's raw answer - same units/
    encoding the model was trained on (e.g. grades as 0-100, Likert 1-5).
    academic_branch: raw "الفرع الدراسي" code (1/2/3/4/5).
    can_study_private_university_encoded: {0, 0.5, 1} - hard Arts
    eligibility gate (Arts is only offered privately in this system).
    can_study_outside_city: 0/1 - drives a soft informational note (see
    CAN_STUDY_OUTSIDE_CITY_NOTE) when the student also has an aspiration
    major; never changes eligibility or thresholds.
    interest_programming, interest_languages, prefer_people_over_computer:
    Likert 1-5 - priority-boost tie-breakers (see _apply_priority_boosts)
    that reorder, but never add/remove, matched_majors/aspiration_majors.
    exam_stage: one of EXAM_STAGES - "mid_year" (default) or
    "supplementary_round_available" both mean the grades can still
    change, so aspiration_majors/youtube_suggestions/study_schedule work
    as usual. "final" means the grades are locked (no more rounds): any
    major that would have been an aspiration is instead excluded outright
    (no false "you can still improve" signal), and youtube_suggestions/
    study_schedule are both suppressed - there's genuinely nothing left
    to advise on.

    Returns a dict with the assigned cluster and the cluster's candidates
    split into:
      - matched_majors: pass every grade and constraint check (borderline
        grades - within BORDERLINE_MARGIN of the threshold - still count
        as matched), reordered by _apply_priority_boosts.
      - aspiration_majors: excluded ONLY by a grade gap between
        BORDERLINE_MARGIN and ASPIRATION_MARGIN points (a branch/private
        constraint miss is never an aspiration major, no matter the grade),
        AND only when exam_stage is still improvable - always empty when
        exam_stage="final". Also reordered by _apply_priority_boosts.
    `evaluations` carries the full per-candidate trace (including majors
    dropped entirely, gap > ASPIRATION_MARGIN or a hard constraint) for
    debugging/transparency. `priority_boosts` records which boosts actually
    fired. `notes` carries the soft outside-city note when applicable
    (otherwise an empty list).

    Also returns two advisory add-ons, independent of the major logic
    above: `youtube_suggestions` and `study_schedule`, both driven by
    identify_subjects_needing_attention() (see module docstring) - a
    subject below WEAK_GRADE_THRESHOLD OR feeding an aspiration major's
    metric gets flagged; if neither applies to anything, youtube_suggestions
    is empty and study_schedule falls back to a light maintenance plan.
    Both are also suppressed entirely when exam_stage="final".
    """
    if exam_stage not in EXAM_STAGES:
        raise ValueError(f"exam_stage must be one of {sorted(EXAM_STAGES)}, got {exam_stage!r}")

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
    can_study_private = can_study_private_university_encoded

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
        elif gap < ASPIRATION_MARGIN and exam_stage in IMPROVABLE_STAGES:
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
        elif gap < ASPIRATION_MARGIN:
            # exam_stage == "final": would have been an aspiration major,
            # but there's no round left to close a {gap:.1f}-point gap, so
            # it's excluded outright rather than shown as still reachable.
            evaluations.append(
                (major, "excluded",
                 f"{label} = {value:.1f}, below required {threshold} (+{gap:.1f}) - "
                 "grades are final, no further improvement possible")
            )
        else:
            evaluations.append(
                (major, "excluded", f"{label} = {value:.1f}, far below required {threshold} (+{gap:.1f})")
            )

    aspiration_majors.sort(key=lambda item: item["gap"])

    # Priority-boost tie-breakers: reorder (never add/remove) matched and
    # aspiration majors using the 3 interest/preference signals. Applied
    # AFTER both lists are fully built, per the module docstring.
    matched_majors, matched_boosts = _apply_priority_boosts(
        matched_majors, interest_programming, interest_languages, prefer_people_over_computer
    )
    aspiration_majors, aspiration_boosts = _apply_priority_boosts(
        aspiration_majors, interest_programming, interest_languages, prefer_people_over_computer
    )
    priority_boosts = matched_boosts + aspiration_boosts

    # Soft outside-city note: only when there's actually an aspiration gap
    # the student might close by looking beyond their own city/university,
    # never a hard threshold change (see CAN_STUDY_OUTSIDE_CITY_NOTE above).
    notes = []
    if aspiration_majors and can_study_outside_city == 1:
        notes.append(CAN_STUDY_OUTSIDE_CITY_NOTE)

    if exam_stage in IMPROVABLE_STAGES:
        # Computed AFTER aspiration_majors so a subject can be flagged for
        # advice either because its own grade is weak, or because it's
        # what's standing between the student and an aspiration major.
        attention_subjects = identify_subjects_needing_attention(student_answers, aspiration_majors)
        youtube_suggestions = build_youtube_suggestions(attention_subjects)
        study_schedule = build_weekly_schedule(student_answers, attention_subjects)
    else:
        # exam_stage == "final" - aspiration_majors is always empty here
        # (see the loop above), and there's nothing left to advise on:
        # no teacher suggestions, no study plan.
        youtube_suggestions = {}
        study_schedule = {
            "mode": "not_applicable",
            "attention_subjects": {},
            "schedule": {},
            "weekly_hours_by_subject": {},
            "assumptions": (
                "العلامات نهائية (لا يوجد دور تكميلي متاح) - لا داعي لخطة دراسة أو "
                "اقتراحات تحسين؛ التوصية مبنية على العلامات كما هي فقط."
            ),
        }

    return {
        "cluster": cluster_id,
        "cluster_name": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
        "science_avg": round(science_avg, 1),
        "math_grade": math_grade,
        "matched_majors": matched_majors,
        "aspiration_majors": aspiration_majors,
        "evaluations": evaluations,
        "priority_boosts": priority_boosts,
        "notes": notes,
        "youtube_suggestions": youtube_suggestions,
        "study_schedule": study_schedule,
        "exam_stage": exam_stage,
    }


# --- Demo student builder ---
# Fills in the 20 clustering answers a demo persona doesn't care about with
# neutral midpoint defaults, so each example below only needs to set the
# handful of fields that actually define that persona. The 5 STEP-2 signal
# parameters (moved out of the clustering vector - see module docstring)
# get their own default set, DEFAULT_SIGNALS, since they're no longer part
# of student_answers - they're passed to recommend_majors() separately.
DEFAULT_STUDENT = {
    "interest_math": 3,
    "interest_physics_engineering": 3,
    "interest_medicine": 3,
    "interest_chemistry_biology": 3,
    "interest_humanities": 3,
    "interest_economics": 3,
    "interest_arts": 3,
    "interest_law": 3,
    "prefer_theoretical": 3,
    "enjoy_complex_problems": 3,
    "handle_academic_pressure": 3,
    "priority_income": 2,
    "priority_social_status": 2,
    "priority_passion": 2,
    "priority_job_stability": 2,
    "math_grade": 70,
    "physics_grade": 70,
    "chemistry_grade": 70,
    "arabic_grade": 70,
    "foreign_language_grade": 70,
}
assert set(DEFAULT_STUDENT) == set(FRIENDLY_TO_COLUMN)

DEFAULT_SIGNALS = {
    "can_study_private_university_encoded": 1.0,
    "can_study_outside_city": 1,
    "interest_programming": 3,
    "interest_languages": 3,
    "prefer_people_over_computer": 3,
}


def make_student(academic_branch, **overrides):
    unknown = set(overrides) - set(DEFAULT_STUDENT) - set(DEFAULT_SIGNALS)
    if unknown:
        raise ValueError(f"Unknown student attribute(s): {sorted(unknown)}")
    clustering_overrides = {k: v for k, v in overrides.items() if k in DEFAULT_STUDENT}
    signal_overrides = {k: v for k, v in overrides.items() if k in DEFAULT_SIGNALS}
    profile = {**DEFAULT_STUDENT, **clustering_overrides}
    signals = {**DEFAULT_SIGNALS, **signal_overrides}
    answers = {FRIENDLY_TO_COLUMN[name]: value for name, value in profile.items()}
    full_profile = {**profile, **signals}
    return answers, academic_branch, signals, full_profile


def print_report(label, profile, academic_branch, result):
    print(f"\n=== {label} ===")
    print("Profile:")
    print(f"  academic_branch: {BRANCH_NAMES.get(academic_branch, academic_branch)}")
    print(f"  grades -> math: {profile['math_grade']}, physics: {profile['physics_grade']}, "
          f"chemistry: {profile['chemistry_grade']}")
    print(f"  key interests (1-5) -> medicine: {profile['interest_medicine']}, "
          f"programming: {profile['interest_programming']}, humanities: {profile['interest_humanities']}, "
          f"law: {profile['interest_law']}, prefer_people_over_computer: {profile['prefer_people_over_computer']}")
    print(f"  can_study_private_university_encoded: {profile['can_study_private_university_encoded']}, "
          f"can_study_outside_city: {profile['can_study_outside_city']}")

    print(f"\nAssigned cluster: {result['cluster']} ({result['cluster_name']})  |  exam_stage: {result['exam_stage']}")
    print(f"science_avg = {result['science_avg']}, math_grade = {result['math_grade']}")

    print("\nCandidate evaluation:")
    for major, status, reason in result["evaluations"]:
        print(f"  [{status:10}] {major:<17} - {reason}")

    print("\nMATCHED MAJORS (ready to apply):")
    if result["matched_majors"]:
        for major in result["matched_majors"]:
            print(f"  -> {major:<17} [OK]")
    else:
        print("  (none)")

    print("\nASPIRATION MAJORS (strong fit, improve grades):")
    if result["aspiration_majors"]:
        for item in result["aspiration_majors"]:
            print(
                f"  -> {item['major']:<17} !!!!  {item['metric_label']} {item['current']}, "
                f"need {item['threshold']} (+{item['gap']} needed)"
            )
    else:
        print("  (none)")

    print("\nPRIORITY BOOSTS (interest_programming/interest_languages/prefer_people_over_computer tie-breakers):")
    if result["priority_boosts"]:
        for boost in result["priority_boosts"]:
            print(f"  -> {boost['major']:<17} boosted ({boost['reason']})")
    else:
        print("  (none)")

    print("\nNOTES:")
    if result["notes"]:
        for note in result["notes"]:
            print(f"  - {note}")
    else:
        print("  (none)")

    print("\nYOUTUBE SUGGESTIONS (weak subjects + subjects blocking an aspiration major):")
    if result["youtube_suggestions"]:
        for subject, teachers in result["youtube_suggestions"].items():
            print(f"  {subject}:")
            for t in teachers:
                link = f" -> {t['youtube']}" if "youtube" in t else " (search on YouTube)"
                print(f"    - {t['teacher']}: {t['note']}{link}")
    elif result["study_schedule"]["mode"] == "not_applicable":
        print("  (none - exam_stage=final, grades are locked, nothing left to advise on)")
    else:
        print("  (none - no weak subject and no aspiration major to close)")

    print(f"\nSTUDY SCHEDULE (weekly, mode={result['study_schedule']['mode']}):")
    sched = result["study_schedule"]
    print(f"  assumptions: {sched['assumptions']}")
    if sched["weekly_hours_by_subject"]:
        print(f"  weekly hours by subject: {sched['weekly_hours_by_subject']}")
    for day, blocks in sched["schedule"].items():
        line = ", ".join(f"{b['time']} {b['subject']}" for b in blocks)
        print(f"    {day}: {line}")


if __name__ == "__main__":
    # Demo only - runs when this file is executed directly (`python
    # recommend.py`), not when other modules (e.g. api.py) import
    # recommend_majors()/make_student() from it.

    # --- Student A: high science grades, high medicine interest, scientific
    # branch. prefer_people_over_computer=5 demonstrates the Medicine boost
    # (it fires - visible in PRIORITY BOOSTS - but Medicine is already first
    # in the Confident Scientific candidate order, so matched_majors order
    # itself doesn't visibly change; see Student C for a visible reorder). ---
    a_answers, a_branch, a_signals, a_profile = make_student(
        academic_branch=1,
        math_grade=92,
        physics_grade=90,
        chemistry_grade=88,
        interest_medicine=5,
        interest_chemistry_biology=5,
        interest_physics_engineering=4,
        enjoy_complex_problems=5,
        handle_academic_pressure=5,
        prefer_people_over_computer=5,
    )

    # --- Student B: low science grades, high humanities interest, literary
    # branch. interest_languages=4 demonstrates a VISIBLE boost: Humanities
    # moves ahead of Law in matched_majors. math_grade=50 (Economics needs
    # 60, gap=10, within ASPIRATION_MARGIN) plus can_study_outside_city=1
    # demonstrates the soft outside-city note. ---
    b_answers, b_branch, b_signals, b_profile = make_student(
        academic_branch=2,
        math_grade=50,
        physics_grade=40,
        chemistry_grade=48,
        arabic_grade=85,
        foreign_language_grade=80,
        interest_humanities=5,
        interest_law=4,
        interest_physics_engineering=1,
        interest_languages=4,
        can_study_outside_city=1,
    )

    # --- Student C: medium grades, high CS interest, scientific branch.
    # interest_programming=4 demonstrates a VISIBLE boost: Computer Science
    # moves to the front of matched_majors, ahead of Medicine/Engineering.
    # can_study_outside_city=0 shows aspiration majors WITHOUT the soft note
    # (contrast with Student B). exam_stage="mid_year" (default) - still
    # improvable, so Medicine/Engineering show up as aspiration_majors with
    # youtube/schedule help. ---
    c_answers, c_branch, c_signals, c_profile = make_student(
        academic_branch=1,
        math_grade=68,
        physics_grade=65,
        chemistry_grade=67,
        interest_math=4,
        interest_programming=4,
        can_study_private_university_encoded=1.0,
        can_study_outside_city=0,
    )

    # --- Student D: SAME profile as Student C, but exam_stage="final" -
    # grades are locked (no supplementary round left). Medicine/Engineering
    # should now show up EXCLUDED (not aspiration), and youtube_suggestions/
    # study_schedule should both be empty/not_applicable - nothing left to
    # advise on for a grade that can no longer change. The Computer Science
    # boost still applies (it's independent of exam_stage).
    d_answers, d_branch, d_signals, d_profile = c_answers, c_branch, c_signals, c_profile

    for label, answers, branch, signals, profile, exam_stage in [
        ("Student A", a_answers, a_branch, a_signals, a_profile, "mid_year"),
        ("Student B", b_answers, b_branch, b_signals, b_profile, "mid_year"),
        ("Student C", c_answers, c_branch, c_signals, c_profile, "mid_year"),
        ("Student D (= C, but exam_stage=final)", d_answers, d_branch, d_signals, d_profile, "final"),
    ]:
        result = recommend_majors(answers, branch, **signals, exam_stage=exam_stage)
        print_report(label, profile, branch, result)
