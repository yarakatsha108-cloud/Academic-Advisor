"""
Stage 7: FastAPI wrapper around the recommendation logic in 06_recommend.py.

- "06_recommend" is not a valid Python identifier (leading digit), so it
  can't be reached with a plain `import 06_recommend` statement - it's
  loaded via importlib instead, from this file's own directory so it
  works regardless of the process's current working directory.
- 06_recommend.py's module-level code loads scaler.pkl / kmeans_model.pkl /
  feature_columns.pkl once, at import time. Because that import happens
  here at process startup (module scope, not inside the endpoint), those
  artifacts are loaded once per server process, not once per request.
- 06_recommend.py's Student A/B/C demo is guarded by
  `if __name__ == "__main__"`, so importing it here does not print that
  report to the API server's console.
"""

import importlib.util
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

_MODULE_PATH = Path(__file__).parent / "06_recommend.py"
_spec = importlib.util.spec_from_file_location("recommend_module", _MODULE_PATH)
recommend_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recommend_module)

recommend_majors = recommend_module.recommend_majors
FRIENDLY_TO_COLUMN = recommend_module.FRIENDLY_TO_COLUMN

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
    age: int
    academic_branch: int = Field(..., description="1=scientific, 2=literary, 4=vocational, 5=industrial")
    interest_programming: int = Field(..., ge=1, le=5)
    interest_math: int = Field(..., ge=1, le=5)
    interest_physics_engineering: int = Field(..., ge=1, le=5)
    interest_medicine: int = Field(..., ge=1, le=5)
    interest_chemistry_biology: int = Field(..., ge=1, le=5)
    interest_languages: int = Field(..., ge=1, le=5)
    interest_humanities: int = Field(..., ge=1, le=5)
    interest_economics: int = Field(..., ge=1, le=5)
    interest_arts: int = Field(..., ge=1, le=5)
    interest_law: int = Field(..., ge=1, le=5)
    prefer_theoretical: int = Field(..., ge=1, le=5)
    enjoy_complex_problems: int = Field(..., ge=1, le=5)
    prefer_people_over_computer: int = Field(..., ge=1, le=5)
    handle_academic_pressure: int = Field(..., ge=1, le=5)
    prefer_job_stability: int = Field(..., ge=1, le=5)
    priority_income: int = Field(..., ge=1, le=4)
    priority_social_status: int = Field(..., ge=1, le=4)
    priority_passion: int = Field(..., ge=1, le=4)
    priority_job_stability: int = Field(..., ge=1, le=4)
    willing_compromise_encoded: float
    willing_follow_parents_encoded: float
    family_financial_encoded: int = Field(..., ge=0, le=1)
    math_grade: float = Field(..., ge=0, le=100)
    physics_grade: float = Field(..., ge=0, le=100)
    chemistry_grade: float = Field(..., ge=0, le=100)
    arabic_grade: float = Field(..., ge=0, le=100)
    foreign_language_grade: float = Field(..., ge=0, le=100)
    can_study_outside_city: int = Field(..., ge=0, le=1)
    can_study_private_university_encoded: float


class AspirationMajor(BaseModel):
    major: str
    gap: float
    metric: str
    required: float


class Evaluation(BaseModel):
    major: str
    status: str
    reason: str


class RecommendResponse(BaseModel):
    cluster_id: int
    cluster_name: str
    science_avg: float
    matched_majors: list[str]
    aspiration_majors: list[AspirationMajor]
    evaluations: list[Evaluation]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(student: StudentRequest):
    payload = student.model_dump()
    academic_branch = payload.pop("academic_branch")

    student_answers = {FRIENDLY_TO_COLUMN[name]: value for name, value in payload.items()}

    result = recommend_majors(student_answers, academic_branch)

    return RecommendResponse(
        cluster_id=result["cluster"],
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
    )


# --- Run locally ---
# pip install fastapi uvicorn
# uvicorn 07_api:app --reload --port 8000
