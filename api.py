"""
FastAPI wrapper around the recommendation logic in recommend.py.

- recommend.py's module-level code loads scaler.pkl / kmeans_model.pkl /
  feature_columns.pkl once, at import time. Because that import happens
  here at process startup (module scope, not inside the endpoint), those
  artifacts are loaded once per server process, not once per request.
- recommend.py's Student A/B/C demo is guarded by
  `if __name__ == "__main__"`, so importing it here does not print that
  report to the API server's console.
- ADDED: youtube_suggestions and study_schedule fields, mirroring the two
  advisory add-ons recommend.py now returns from recommend_majors().

- StudentRequest was reduced alongside the 30->20 clustering feature cut
  in scale.py/recommend.py: age, willing_compromise_encoded,
  willing_follow_parents_encoded, family_financial_encoded, and
  prefer_job_stability are gone entirely (no rule anywhere used them).
  interest_programming, interest_languages, prefer_people_over_computer,
  can_study_outside_city, and can_study_private_university_encoded are
  still request fields (the student still answers these questions), but
  are now popped out and passed to recommend_majors() as separate
  parameters instead of being folded into student_answers, since they
  drive priority-boost/soft-note rules rather than clustering.
- ADDED: priority_boosts and notes fields, mirroring recommend_majors()'s
  new priority-boost tie-breakers and soft outside-city note.
"""

from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from recommend import recommend_majors, FRIENDLY_TO_COLUMN

app = FastAPI(title="Major Recommendation API")

# allow_credentials=False because allow_origins=["*"] + allow_credentials=True
# is rejected by browsers (and by Starlette) - this API takes no cookies/auth
# header, so there's nothing that needs the credentialed mode anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudentRequest(BaseModel):
    academic_branch: int = Field(..., description="1=scientific, 2=literary, 4=vocational, 5=industrial")

    # --- 20 clustering features (see scale.py / recommend.py) ---
    interest_math: int = Field(..., ge=1, le=5)
    interest_physics_engineering: int = Field(..., ge=1, le=5)
    interest_medicine: int = Field(..., ge=1, le=5)
    interest_chemistry_biology: int = Field(..., ge=1, le=5)
    interest_humanities: int = Field(..., ge=1, le=5)
    interest_economics: int = Field(..., ge=1, le=5)
    interest_arts: int = Field(..., ge=1, le=5)
    interest_law: int = Field(..., ge=1, le=5)
    prefer_theoretical: int = Field(..., ge=1, le=5)
    enjoy_complex_problems: int = Field(..., ge=1, le=5)
    handle_academic_pressure: int = Field(..., ge=1, le=5)
    priority_income: int = Field(..., ge=1, le=4)
    priority_social_status: int = Field(..., ge=1, le=4)
    priority_passion: int = Field(..., ge=1, le=4)
    priority_job_stability: int = Field(..., ge=1, le=4)
    math_grade: float = Field(..., ge=0, le=100)
    physics_grade: float = Field(..., ge=0, le=100)
    chemistry_grade: float = Field(..., ge=0, le=100)
    arabic_grade: float = Field(..., ge=0, le=100)
    foreign_language_grade: float = Field(..., ge=0, le=100)

    # --- 5 signals: still answered, but passed to recommend_majors() as
    # separate parameters rather than folded into student_answers/clustering ---
    interest_programming: int = Field(..., ge=1, le=5)
    interest_languages: int = Field(..., ge=1, le=5)
    prefer_people_over_computer: int = Field(..., ge=1, le=5)
    can_study_outside_city: int = Field(..., ge=0, le=1)
    can_study_private_university_encoded: float

    exam_stage: Literal["mid_year", "supplementary_round_available", "final"] = Field(
        "mid_year",
        description=(
            "'mid_year'/'supplementary_round_available': grades can still change, so "
            "aspiration_majors + youtube_suggestions + study_schedule are computed normally. "
            "'final': grades are locked - would-be aspiration majors are excluded outright, "
            "and youtube_suggestions/study_schedule are suppressed (nothing left to advise on)."
        ),
    )


class AspirationMajor(BaseModel):
    major: str
    gap: float
    metric: str
    required: float


class PriorityBoost(BaseModel):
    major: str
    reason: str


class Evaluation(BaseModel):
    major: str
    status: str
    reason: str


class YoutubeTeacher(BaseModel):
    teacher: str
    note: str
    youtube: Optional[str] = None


class ScheduleBlock(BaseModel):
    time: str
    subject: str
    hours: float
    focus: str


class AttentionSubject(BaseModel):
    grade: float
    reason: str  # "below_threshold" | "aspiration_target" | "both"


class StudySchedule(BaseModel):
    mode: str  # "corrective" | "maintenance"
    attention_subjects: dict[str, AttentionSubject]
    schedule: dict[str, list[ScheduleBlock]]
    weekly_hours_by_subject: dict[str, float]
    assumptions: str


class RecommendResponse(BaseModel):
    cluster_id: int
    cluster_name: str
    exam_stage: str
    science_avg: float
    matched_majors: list[str]
    aspiration_majors: list[AspirationMajor]
    evaluations: list[Evaluation]
    priority_boosts: list[PriorityBoost]
    notes: list[str]
    youtube_suggestions: dict[str, list[YoutubeTeacher]]
    study_schedule: StudySchedule


@app.get("/health")
def health():
    return {"status": "ok"}


# The 5 signal fields are still part of StudentRequest (the student still
# answers these questions) but are popped out here and passed to
# recommend_majors() as separate parameters instead of being folded into
# student_answers - see the module docstring.
_SIGNAL_FIELDS = (
    "can_study_private_university_encoded",
    "can_study_outside_city",
    "interest_programming",
    "interest_languages",
    "prefer_people_over_computer",
)


@app.post("/recommend", response_model=RecommendResponse)
def recommend(student: StudentRequest):
    payload = student.model_dump()
    academic_branch = payload.pop("academic_branch")
    exam_stage = payload.pop("exam_stage")
    signals = {field: payload.pop(field) for field in _SIGNAL_FIELDS}

    student_answers = {FRIENDLY_TO_COLUMN[name]: value for name, value in payload.items()}

    result = recommend_majors(student_answers, academic_branch, **signals, exam_stage=exam_stage)

    return RecommendResponse(
        cluster_id=result["cluster"],
        exam_stage=result["exam_stage"],
        cluster_name=result["cluster_name"],
        science_avg=result["science_avg"],
        matched_majors=result["matched_majors"],
        aspiration_majors=[
            AspirationMajor(
                major=item["major"],
                gap=item["gap"],
                metric=item["metric_label"],
                required=item["threshold"],
            )
            for item in result["aspiration_majors"]
        ],
        evaluations=[
            Evaluation(major=major, status=status, reason=reason)
            for major, status, reason in result["evaluations"]
        ],
        priority_boosts=[PriorityBoost(**b) for b in result["priority_boosts"]],
        notes=result["notes"],
        youtube_suggestions={
            subject: [YoutubeTeacher(**t) for t in teachers]
            for subject, teachers in result["youtube_suggestions"].items()
        },
        study_schedule=StudySchedule(
            mode=result["study_schedule"]["mode"],
            attention_subjects={
                subj: AttentionSubject(**info)
                for subj, info in result["study_schedule"]["attention_subjects"].items()
            },
            schedule=result["study_schedule"]["schedule"],
            weekly_hours_by_subject=result["study_schedule"]["weekly_hours_by_subject"],
            assumptions=result["study_schedule"]["assumptions"],
        ),
    )


# --- Run locally ---
# pip install fastapi uvicorn
# uvicorn api:app --reload --port 8000
