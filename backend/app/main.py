
from datetime import datetime, timezone
import json
import os
import secrets
from typing import Any, Generator, Protocol, cast

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://discipulus-ai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.auth import create_access_token, get_user_id_from_token
from app.database import SessionLocal
from app.models import (
    Assessment,
    Attempt,
    AssessmentReview,
    GeneratedAssessmentQuestion,
    Chapter,
    Question,
    Subject,
    User,
)
from app.security import hash_password, verify_password
from app.services.gemini_service import (
    BloomLevel,
    generate_questions,
    evaluate_written_answer,
)
from app.ml import predictor as _predictor


# ---------------------------------------------------------------------
# ML predictor typing
# ---------------------------------------------------------------------

class _PerformancePredictor(Protocol):
    def __call__(
        self,
        current_percentage: float,
        previous_percentage: float,
        attempt_count: int,
    ) -> dict[str, Any]: ...


predict_performance: _PerformancePredictor = cast(
    _PerformancePredictor,
    getattr(_predictor, "predict_performance"),
)


# ---------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------

class AnswerSubmission(BaseModel):
    question_id: int = Field(gt=0)
    selected_option: str = Field(pattern="^[A-D]$")


class AssessmentSubmission(BaseModel):
    chapter_id: int = Field(gt=0)
    answers: list[AnswerSubmission] = Field(min_length=1)


class DynamicQuestionRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=10)
    topic: str | None = Field(default=None, min_length=2, max_length=200)
    bloom_levels: list[BloomLevel] | None = None
    include_written: bool = True


class GeneratedAnswerSubmission(BaseModel):
    question_id: int = Field(gt=0)
    answer: str = Field(default="", max_length=12000)


class GeneratedAssessmentSubmission(BaseModel):
    assessment_id: int = Field(gt=0)
    answers: list[GeneratedAnswerSubmission] = Field(min_length=1, max_length=10)


class UserRegistration(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    class_level: int = Field(ge=11, le=12)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)
    # Required only when creating a new account via Google sign-up.
    class_level: int | None = Field(default=None, ge=11, le=12)


# ---------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------

app = FastAPI(
    title="Discipulus-AI API",
    description=(
        "Personalized learning platform for Class XI and XII PCMB students"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# Database and authentication dependencies
# ---------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """Create a database session and close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the active student associated with a valid bearer token."""
    user_id = get_user_id_from_token(credentials.credentials)
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student account not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ---------------------------------------------------------------------
# General and health endpoints
# ---------------------------------------------------------------------

@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to Discipulus-AI API",
        "docs": "/docs",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "application": "Discipulus-AI",
    }


# ---------------------------------------------------------------------
# Student registration and login
# ---------------------------------------------------------------------

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_student(
    registration: UserRegistration,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    email = str(registration.email).strip().lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        full_name=registration.full_name.strip(),
        email=email,
        password_hash=hash_password(registration.password),
        class_level=registration.class_level,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None

    return {
        "message": "Registration successful",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "class_level": user.class_level,
        },
    }


@app.post("/api/auth/login")
def login_student(
    credentials: UserLogin,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    email = str(credentials.email).strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    # Use the same response for an unknown email or wrong password.
    if (
        user is None
        or not verify_password(
            credentials.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive",
        )

    token = create_access_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 1800,
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "class_level": user.class_level,
        },
    }


@app.post("/api/auth/google")
def google_login(
    request: GoogleLoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verify a Google ID token and sign in or create a student account."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google sign-in is not configured on the server.",
        )

    try:
        verify_google_token = cast(
            Any,
            google_id_token.verify_oauth2_token,
        )
        claims: dict[str, Any] = cast(dict[str, Any], verify_google_token(
            request.id_token,
            google_requests.Request(),
            client_id,
        ))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential is invalid or expired. Please try again.",
        ) from None

    email = str(claims.get("email", "")).strip().lower()
    full_name = str(claims.get("name", "")).strip()
    email_verified = claims.get("email_verified") is True

    if not email or not email_verified or not full_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google must provide a verified email and profile name.",
        )

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        # Do not silently assign a class when someone clicks Sign in.
        # New Google users must use the sign-up screen and select a class.
        if request.class_level is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No account exists for this Google email. Please choose Create one and select your class to sign up.",
            )

        user = User(
            full_name=full_name[:120],
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            class_level=request.class_level,
        )
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not create the student account. Please retry.",
                ) from None

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This student account is inactive.",
        )

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 1800,
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "class_level": user.class_level,
        },
    }


# ---------------------------------------------------------------------
# Subjects and chapters
# ---------------------------------------------------------------------

@app.get("/api/subjects")
def get_subjects(
    class_level: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    if class_level not in (11, 12):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="class_level must be 11 or 12",
        )

    subjects = (
        db.query(Subject)
        .filter(Subject.class_level == class_level)
        .order_by(Subject.id)
        .all()
    )

    return [
        {
            "id": subject.id,
            "name": subject.name,
            "class_level": subject.class_level,
        }
        for subject in subjects
    ]


@app.get("/api/chapters")
def get_chapters(
    subject_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    subject = db.get(Subject, subject_id)

    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    chapters = (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id)
        .order_by(Chapter.chapter_number)
        .all()
    )

    return [
        {
            "id": chapter.id,
            "title": chapter.title,
            "chapter_number": chapter.chapter_number,
            "subject_id": chapter.subject_id,
        }
        for chapter in chapters
    ]


@app.post("/api/chapters/{chapter_id}/generate-questions")
def generate_chapter_questions(
    chapter_id: int,
    request: DynamicQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Generate questions and persist their private answer key for later evaluation.
    Correct answers and marking rubrics are never returned before submission.
    """
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    subject = db.get(Subject, chapter.subject_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The subject for this chapter was not found",
        )

    if subject.class_level != current_user.class_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This chapter is not available for your class level",
        )

    try:
        questions = generate_questions(
            class_level=current_user.class_level,
            subject=subject.name,
            chapter=chapter.title,
            topic=(request.topic or chapter.title).strip(),
            count=request.count,
            bloom_levels=request.bloom_levels,
            include_written=request.include_written,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Do not expose API keys or provider internals to the client.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Question generation is temporarily unavailable. "
                "Please retry shortly."
            ),
        ) from exc

    assessment = Assessment(
        student_id=current_user.id, chapter_id=chapter.id,
        title=f"AI Assessment: {chapter.title} — {(request.topic or chapter.title).strip()}",
    )
    try:
        db.add(assessment)
        db.flush()
        public_questions: list[dict[str, Any]] = []
        for index, question in enumerate(questions, start=1):
            saved = GeneratedAssessmentQuestion(
                assessment_id=assessment.id, question_order=index,
                question_type=question.question_type, prompt=question.question,
                options_json=json.dumps(question.options),
                correct_option=question.correct_option,
                expected_answer=question.expected_answer,
                rubric_json=json.dumps(question.marking_rubric),
                explanation=question.explanation, topic=question.topic,
                bloom_level=question.bloom_level, difficulty=question.difficulty,
            )
            db.add(saved)
            db.flush()
            public_questions.append({
                "id": saved.id, "temporary_id": saved.id,
                "question_type": question.question_type, "question": question.question,
                "topic": question.topic, "bloom_level": question.bloom_level,
                "difficulty": question.difficulty, "options": question.options,
            })
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "assessment_id": assessment.id, "chapter_id": chapter.id,
        "chapter": chapter.title, "topic": (request.topic or chapter.title).strip(),
        "subject": subject.name, "class_level": current_user.class_level,
        "count": len(public_questions), "questions": public_questions,
    }


@app.get("/api/chapters/{chapter_id}/questions")
def get_chapter_questions(
    chapter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    chapter = db.get(Chapter, chapter_id)

    if chapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    questions = (
        db.query(Question)
        .filter(Question.chapter_id == chapter_id)
        .order_by(Question.id)
        .all()
    )

    # Do not expose correct answers in the question-fetch endpoint.
    return [
        {
            "id": question.id,
            "chapter_id": question.chapter_id,
            "prompt": question.prompt,
            "option_a": question.option_a,
            "option_b": question.option_b,
            "option_c": question.option_c,
            "option_d": question.option_d,
            "difficulty": question.difficulty,
        }
        for question in questions
    ]


# ---------------------------------------------------------------------
# Assessment submission
# ---------------------------------------------------------------------

@app.post("/api/assessments/submit")
def submit_assessment(
    submission: AssessmentSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    chapter = db.get(Chapter, submission.chapter_id)

    if chapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    question_ids = [
        answer.question_id for answer in submission.answers
    ]

    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate question IDs are not allowed",
        )

    questions = (
        db.query(Question)
        .filter(
            Question.chapter_id == submission.chapter_id,
            Question.id.in_(question_ids),
        )
        .all()
    )

    question_map = {
        question.id: question for question in questions
    }

    if len(question_map) != len(question_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more questions do not belong to this chapter",
        )

    score = 0
    results: list[dict[str, Any]] = []

    for answer in submission.answers:
        question = question_map[answer.question_id]
        is_correct = (
            answer.selected_option == question.correct_option
        )

        if is_correct:
            score += 1

        results.append(
            {
                "question_id": question.id,
                "selected_option": answer.selected_option,
                "is_correct": is_correct,
                "correct_option": question.correct_option,
                "explanation": question.explanation,
            }
        )

    total_questions = len(submission.answers)
    percentage = round(
        (score / total_questions) * 100,
        2,
    )

    assessment = Assessment(
        student_id=current_user.id,
        chapter_id=chapter.id,
        title=f"Chapter {chapter.chapter_number}: {chapter.title}",
    )

    try:
        db.add(assessment)
        db.flush()

        attempt = Attempt(
            student_id=current_user.id,
            assessment_id=assessment.id,
            score=score,
            total_questions=total_questions,
            submitted_at=datetime.now(timezone.utc),
        )

        db.add(attempt)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "chapter_id": submission.chapter_id,
        "score": score,
        "total_questions": total_questions,
        "percentage": percentage,
        "results": results,
    }


# ---------------------------------------------------------------------
# AI-generated assessment submission and detailed review
# ---------------------------------------------------------------------

@app.post("/api/assessments/submit-generated")
def submit_generated_assessment(
    submission: GeneratedAssessmentSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    assessment = db.get(Assessment, submission.assessment_id)
    if assessment is None or assessment.student_id != current_user.id:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    if db.scalar(select(Attempt).where(Attempt.assessment_id == assessment.id)) is not None:
        raise HTTPException(status_code=409, detail="This assessment has already been submitted.")
    saved_questions = (db.query(GeneratedAssessmentQuestion)
        .filter(GeneratedAssessmentQuestion.assessment_id == assessment.id)
        .order_by(GeneratedAssessmentQuestion.question_order).all())
    if not saved_questions:
        raise HTTPException(status_code=400, detail="This assessment has no questions.")
    answers_by_id = {item.question_id: item.answer.strip() for item in submission.answers}
    valid_ids = {item.id for item in saved_questions}
    if len(answers_by_id) != len(submission.answers) or set(answers_by_id) != valid_ids:
        raise HTTPException(status_code=400, detail="Submit exactly one answer for each question in this assessment.")
    chapter = db.get(Chapter, assessment.chapter_id)
    subject = db.get(Subject, chapter.subject_id) if chapter else None
    if chapter is None or subject is None:
        raise HTTPException(status_code=404, detail="Assessment chapter or subject not found.")

    results: list[dict[str, Any]] = []
    earned = 0.0
    maximum = 0.0
    correct_count = 0
    try:
        for question in saved_questions:
            student_answer = answers_by_id[question.id]
            options: list[Any] = cast(list[Any], json.loads(question.options_json or "[]"))
            rubric: list[Any] = cast(list[Any], json.loads(question.rubric_json or "[]"))
            if question.question_type == "mcq":
                max_points = 1.0
                selected = student_answer.upper()
                is_correct = selected == question.correct_option
                points = 1.0 if is_correct else 0.0
                correct_count += int(is_correct)
                correct_answer = (
                    options[ord(question.correct_option) - ord("A")]
                    if question.correct_option and len(options) >= 4 else question.correct_option
                )
                item = {
                    "question_id": question.id, "question_type": "mcq", "question": question.prompt,
                    "student_answer": selected, "selected_option": selected, "is_correct": is_correct,
                    "score_awarded": points, "max_score": max_points,
                    "correct_option": question.correct_option, "correct_answer": correct_answer,
                    "expected_answer": question.expected_answer,
                    "feedback": "Correct answer." if is_correct else "Review the explanation and compare it with your selected option.",
                    "explanation": question.explanation,
                }
            else:
                max_points = float(max(1, len(rubric)))
                evaluation = evaluate_written_answer(
                    class_level=current_user.class_level, subject=subject.name, chapter=chapter.title,
                    question=question.prompt, student_answer=student_answer,
                    expected_answer=question.expected_answer, marking_rubric=rubric,
                )
                points = min(max_points, max(0.0, float(evaluation.score)))
                is_correct = points >= max_points
                correct_count += int(is_correct)
                item = {
                    "question_id": question.id, "question_type": "written", "question": question.prompt,
                    "student_answer": student_answer, "selected_option": None, "is_correct": is_correct,
                    "score_awarded": round(points, 2), "max_score": max_points,
                    "correct_option": None, "correct_answer": evaluation.correct_answer or question.expected_answer,
                    "expected_answer": question.expected_answer, "feedback": evaluation.feedback,
                    "strengths": evaluation.strengths, "improvements": evaluation.improvements,
                    "explanation": question.explanation,
                }
            earned += points
            maximum += max_points
            results.append(item)
        percentage = round((earned / maximum) * 100, 2) if maximum else 0.0
        attempt = Attempt(
            student_id=current_user.id, assessment_id=assessment.id,
            score=round(earned), total_questions=round(maximum),
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(attempt)
        db.flush()
        overall_feedback = (
            "Excellent work. Keep challenging yourself." if percentage >= 85 else
            "Good progress. Review the feedback for each question and practise the areas you missed." if percentage >= 60 else
            "Use the corrections below to revise the key concepts, then try another assessment."
        )
        review = AssessmentReview(
            attempt_id=attempt.id, score_awarded=earned, max_score=maximum,
            percentage=percentage, results_json=json.dumps(results),
            overall_feedback=overall_feedback,
        )
        db.add(review)
        db.commit()
        db.refresh(attempt)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Evaluation could not be completed. Your assessment was not submitted; please retry.") from exc
    return {
        "attempt_id": attempt.id, "assessment_id": assessment.id,
        "chapter_id": assessment.chapter_id, "score": round(earned, 2),
        "total_score": round(maximum, 2), "total_questions": len(saved_questions),
        "percentage": percentage, "overall_feedback": overall_feedback, "results": results,
    }


@app.get("/api/attempts/{attempt_id}/review")
def get_attempt_review(
    attempt_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        raise HTTPException(status_code=404, detail="Assessment attempt not found.")
    review = db.scalar(select(AssessmentReview).where(AssessmentReview.attempt_id == attempt.id))
    assessment = db.get(Assessment, attempt.assessment_id)
    if review is None or assessment is None:
        raise HTTPException(status_code=404, detail="Detailed feedback is not available for this attempt.")
    return {
        "attempt_id": attempt.id, "assessment_id": assessment.id, "chapter_id": assessment.chapter_id,
        "title": assessment.title, "score": review.score_awarded, "total_score": review.max_score,
        "total_questions": attempt.total_questions, "percentage": review.percentage,
        "overall_feedback": review.overall_feedback,
        "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "results": json.loads(review.results_json),
    }


# ---------------------------------------------------------------------
# Authenticated student's assessment history
# ---------------------------------------------------------------------

@app.get("/api/attempts/me")
def get_my_attempts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    statement = (
        select(Attempt, Assessment)
        .join(
            Assessment,
            Attempt.assessment_id == Assessment.id,
        )
        .where(Attempt.student_id == current_user.id)
        .order_by(
            Attempt.submitted_at.desc(),
            Attempt.id.desc(),
        )
    )

    rows = db.execute(statement).all()
    history: list[dict[str, Any]] = []

    for attempt, assessment in rows:
        review = db.scalar(select(AssessmentReview).where(AssessmentReview.attempt_id == attempt.id))
        percentage = (
            review.percentage if review is not None else
            round((attempt.score / attempt.total_questions) * 100, 2)
            if attempt.total_questions > 0 else 0.0
        )
        history.append({
            "attempt_id": attempt.id, "assessment_id": assessment.id,
            "chapter_id": assessment.chapter_id, "title": assessment.title,
            "score": review.score_awarded if review is not None else attempt.score,
            "total_questions": review.max_score if review is not None else attempt.total_questions,
            "percentage": percentage, "has_detailed_feedback": review is not None,
            "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        })

    return history


# ---------------------------------------------------------------------
# Bloom's Taxonomy dashboard analytics
# ---------------------------------------------------------------------

@app.get("/api/ml/bloom-profile")
def get_bloom_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Aggregate the authenticated student's saved generated-assessment marks
    by Bloom level. No external AI call is made for these calculations.
    """
    levels = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
    totals: dict[str, dict[str, float | int]] = {
        level: {"earned": 0.0, "possible": 0.0, "questions": 0}
        for level in levels
    }

    rows: list[Any] = list(db.execute(
        select(Attempt, AssessmentReview, Assessment)
        .join(AssessmentReview, AssessmentReview.attempt_id == Attempt.id)
        .join(Assessment, Assessment.id == Attempt.assessment_id)
        .where(Attempt.student_id == current_user.id)
        .order_by(Attempt.submitted_at.desc(), Attempt.id.desc())
    ).all())

    for _attempt, review, assessment in rows:
        try:
            raw_results: Any = json.loads(review.results_json or "[]")
            if not isinstance(raw_results, list):
                continue
            results: list[Any] = raw_results
        except (TypeError, json.JSONDecodeError):
            continue
        question_ids = [
            int(item["question_id"])
            for item in results
            if isinstance(item, dict) and str(item.get("question_id", "")).isdigit()
        ]
        if not question_ids:
            continue
        question_rows: list[GeneratedAssessmentQuestion] = list(db.execute(
            select(GeneratedAssessmentQuestion)
            .where(
                GeneratedAssessmentQuestion.assessment_id == assessment.id,
                GeneratedAssessmentQuestion.id.in_(question_ids),
            )
        ).scalars().all())
        question_by_id: dict[int, GeneratedAssessmentQuestion] = {question.id: question for question in question_rows}

        for item in results:
            if not isinstance(item, dict):
                continue
            try:
                question_id = int(item.get("question_id"))
            except (TypeError, ValueError):
                continue
            question = question_by_id.get(question_id)
            if question is None:
                # Older stored attempts may not have generated-question metadata.
                continue
            level = question.bloom_level.title()
            if level not in totals:
                continue
            earned = max(0.0, float(item.get("score_awarded") or 0))
            possible = max(0.0, float(item.get("max_score") or 0))
            if possible <= 0:
                continue
            totals[level]["earned"] = float(totals[level]["earned"]) + earned
            totals[level]["possible"] = float(totals[level]["possible"]) + possible
            totals[level]["questions"] = int(totals[level]["questions"]) + 1

    response_levels: list[dict[str, Any]] = []
    for level in levels:
        item = totals[level]
        possible = float(item["possible"])
        earned = float(item["earned"])
        response_levels.append({
            "level": level,
            "score": round((earned / possible) * 100, 1) if possible > 0 else None,
            "earned_marks": round(earned, 2),
            "possible_marks": round(possible, 2),
            "question_count": int(item["questions"]),
        })

    scored_levels: list[dict[str, Any]] = [
        item for item in response_levels if item.get("score") is not None
    ]
    recommendations: list[str] = []
    if not scored_levels:
        recommendations.append(
            "Complete an AI-generated assessment to start building your Bloom's Taxonomy profile."
        )
    else:
        weakest = sorted(scored_levels, key=lambda item: float(item["score"]))[:2]
        for item in weakest:
            score = float(item["score"])
            if score < 50:
                advice = "prioritize focused revision and worked examples"
            elif score < 75:
                advice = "practise more questions and explain your reasoning"
            else:
                advice = "maintain this skill with mixed-difficulty practice"
            recommendations.append(
                f"{item['level']}: {score:.1f}% — {advice}."
            )

    return {
        "levels": response_levels,
        "recommendations": recommendations,
        "data_points": sum(int(item["question_count"]) for item in response_levels),
    }


# ---------------------------------------------------------------------
# ML-based performance classification
# ---------------------------------------------------------------------

@app.get("/api/ml/performance")
def get_ml_performance(
    chapter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Classify the student's performance using their chapter history.

    The current demonstration model uses synthetic training data and
    is not educationally validated.
    """
    if chapter_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chapter_id must be a positive integer",
        )

    statement = (
        select(Attempt, Assessment)
        .join(
            Assessment,
            Attempt.assessment_id == Assessment.id,
        )
        .where(
            Attempt.student_id == current_user.id,
            Assessment.chapter_id == chapter_id,
        )
        .order_by(
            Attempt.submitted_at.desc(),
            Attempt.id.desc(),
        )
    )

    rows = db.execute(statement).all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assessment attempts found for this chapter",
        )

    # Ignore attempts with no questions when calculating performance.
    valid_attempts = [
        (attempt, assessment)
        for attempt, assessment in rows
        if attempt.total_questions > 0
    ]

    if len(valid_attempts) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Complete at least two valid assessment attempts "
                "for this chapter to generate a performance prediction"
            ),
        )

    latest_attempt, _ = valid_attempts[0]
    previous_attempt, _ = valid_attempts[1]

    current_percentage = (
        latest_attempt.score / latest_attempt.total_questions
    ) * 100

    previous_percentage = (
        previous_attempt.score / previous_attempt.total_questions
    ) * 100

    try:
        prediction = predict_performance(
            current_percentage=round(current_percentage, 2),
            previous_percentage=round(previous_percentage, 2),
            attempt_count=len(valid_attempts),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "student_id": current_user.id,
        "chapter_id": chapter_id,
        **prediction,
    }
