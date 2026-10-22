
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Subject, Chapter


CHAPTERS = {
    (11, "Physics"): [
        "Physical World and Measurement",
        "Kinematics",
        "Laws of Motion",
    ],
    (11, "Chemistry"): [
        "Some Basic Concepts of Chemistry",
        "Structure of Atom",
        "Classification of Elements",
    ],
    (11, "Mathematics"): [
        "Sets",
        "Relations and Functions",
        "Trigonometric Functions",
    ],
    (11, "Biology"): [
        "The Living World",
        "Biological Classification",
        "Plant Kingdom",
    ],
    (12, "Physics"): [
        "Electric Charges and Fields",
        "Electrostatic Potential and Capacitance",
        "Current Electricity",
    ],
    (12, "Chemistry"): [
        "Solutions",
        "Electrochemistry",
        "Chemical Kinetics",
    ],
    (12, "Mathematics"): [
        "Relations and Functions",
        "Inverse Trigonometric Functions",
        "Matrices",
    ],
    (12, "Biology"): [
        "Sexual Reproduction in Flowering Plants",
        "Human Reproduction",
        "Reproductive Health",
    ],
}


def seed_chapters():
    with SessionLocal() as db:
        for (class_level, subject_name), chapter_names in CHAPTERS.items():
            subject = db.scalar(
                select(Subject).where(
                    Subject.class_level == class_level,
                    Subject.name == subject_name,
                )
            )

            if subject is None:
                raise ValueError(
                    f"Subject not found: Class {class_level} {subject_name}"
                )

            for number, title in enumerate(chapter_names, start=1):
                existing = db.scalar(
                    select(Chapter).where(
                        Chapter.subject_id == subject.id,
                        Chapter.title == title,
                    )
                )

                if existing is None:
                    db.add(
                        Chapter(
                            subject_id=subject.id,
                            title=title,
                            chapter_number=number,
                        )
                    )

        db.commit()
        print("Chapter seeding completed successfully.")


if __name__ == "__main__":
    seed_chapters()
