
from typing import TypedDict

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Subject


class SubjectData(TypedDict):
    name: str
    class_level: int


SUBJECTS: list[SubjectData] = [
    {"name": "Physics", "class_level": 11},
    {"name": "Chemistry", "class_level": 11},
    {"name": "Mathematics", "class_level": 11},
    {"name": "Biology", "class_level": 11},
    {"name": "Physics", "class_level": 12},
    {"name": "Chemistry", "class_level": 12},
    {"name": "Mathematics", "class_level": 12},
    {"name": "Biology", "class_level": 12},
]


def seed_subjects() -> None:
    with SessionLocal() as db:
        for item in SUBJECTS:
            existing = db.scalar(
                select(Subject).where(
                    Subject.name == item["name"],
                    Subject.class_level == item["class_level"],
                )
            )

            if existing is None:
                db.add(Subject(**item))

        db.commit()
        print("Subject seeding completed successfully.")


if __name__ == "__main__":
    seed_subjects()
