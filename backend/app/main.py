from app.auth import create_access_token

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import User
from app.security import hash_password, verify_password

from pydantic import BaseModel, Field

from typing import Any, Generator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Subject, Chapter, Question


class AnswerSubmission(BaseModel):
    question_id: int = Field(gt=0)
    selected_option: str = Field(pattern="^[A-D]$")


class AssessmentSubmission(BaseModel):
    chapter_id: int = Field(gt=0)
    answers: list[AnswerSubmission] = Field(min_length=1)

class UserRegistration(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    class_level: int = Field(ge=11, le=12)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


app = FastAPI(
    title="Discipulus-AI API",
    description="Personalized learning platform for Class XI and XII PCMB students",
    version="0.1.0",
)

# Allow requests from the local frontend during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/auth/register", status_code=201)
def register_student(
    registration: UserRegistration,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # Normalize the email address.
    email = str(registration.email).strip().lower()

    # Reject an existing email.
    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    # Hash the password before storing it.
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
            status_code=409,
            detail="An account with this email already exists",
        ) from None

    # Never return the password or password hash.
    return {
        "message": "Registration successful",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "class_level": user.class_level,
        },
    }


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


@app.get("/api/subjects")
def get_subjects(
    class_level: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    if class_level not in (11, 12):
        raise HTTPException(
            status_code=400,
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
            status_code=404,
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


@app.get("/api/chapters/{chapter_id}/questions")
def get_chapter_questions(
    chapter_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    chapter = db.get(Chapter, chapter_id)

    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail="Chapter not found",
        )

    questions = (
        db.query(Question)
        .filter(Question.chapter_id == chapter_id)
        .order_by(Question.id)
        .all()
    )

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


@app.post("/api/assessments/submit")
def submit_assessment(
    submission: AssessmentSubmission,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    chapter = db.get(Chapter, submission.chapter_id)

    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail="Chapter not found",
        )

    # Prevent duplicate question IDs in one submission.
    question_ids = [answer.question_id for answer in submission.answers]

    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(
            status_code=400,
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

    question_map = {question.id: question for question in questions}

    if len(question_map) != len(question_ids):
        raise HTTPException(
            status_code=400,
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
    percentage = round((score / total_questions) * 100, 2)

    return {
        "chapter_id": submission.chapter_id,
        "score": score,
        "total_questions": total_questions,
        "percentage": percentage,
        "results": results,
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
            status_code=401,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
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