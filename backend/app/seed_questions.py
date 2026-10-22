
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Chapter, Question


SAMPLE_QUESTIONS = [
    {
        "prompt": "Which of the following is a fundamental SI unit?",
        "option_a": "Newton",
        "option_b": "Joule",
        "option_c": "Kilogram",
        "option_d": "Watt",
        "correct_option": "C",
        "explanation": "The kilogram is an SI base unit of mass. "
        "Newton, joule, and watt are derived SI units.",
        "difficulty": "easy",
    },
    {
        "prompt": "What is the SI unit of length?",
        "option_a": "Centimetre",
        "option_b": "Metre",
        "option_c": "Kilometre",
        "option_d": "Millimetre",
        "correct_option": "B",
        "explanation": "The metre (m) is the SI base unit of length.",
        "difficulty": "easy",
    },
    {
        "prompt": "Which instrument is commonly used to measure the "
        "diameter of a thin wire accurately?",
        "option_a": "Stopwatch",
        "option_b": "Metre scale only",
        "option_c": "Ammeter",
        "option_d": "Screw gauge",
        "correct_option": "D",
        "explanation": "A screw gauge can measure small diameters "
        "with greater precision than an ordinary metre scale.",
        "difficulty": "medium",
    },
]


def seed_questions() -> None:
    with SessionLocal() as db:
        chapter = db.scalar(
            select(Chapter)
            .join(Chapter.subject)
            .where(
                Chapter.id == 1,
                Chapter.subject.has(
                    name="Physics",
                    class_level=11,
                ),
            )
        )

        if chapter is None:
            raise ValueError(
                "Class 11 Physics chapter with ID 1 was not found."
            )

        for item in SAMPLE_QUESTIONS:
            existing = db.scalar(
                select(Question).where(
                    Question.chapter_id == chapter.id,
                    Question.prompt == item["prompt"],
                )
            )

            if existing is None:
                db.add(
                    Question(
                        chapter_id=chapter.id,
                        **item,
                    )
                )

        db.commit()
        print("Sample questions seeded successfully.")


if __name__ == "__main__":
    seed_questions()
