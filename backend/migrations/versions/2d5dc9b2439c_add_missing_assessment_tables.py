
"""add missing assessment tables

Revision ID: 2d5dc9b2439c
Revises: 2591dda273c7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d5dc9b2439c"
down_revision: Union[str, Sequence[str], None] = "2591dda273c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generated_assessment_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("question_order", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(length=20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("correct_option", sa.String(length=1), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("rubric_json", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("bloom_level", sa.String(length=30), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_generated_assessment_questions_id",
        "generated_assessment_questions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_generated_assessment_questions_assessment_id",
        "generated_assessment_questions",
        ["assessment_id"],
        unique=False,
    )

    op.create_table(
        "assessment_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("score_awarded", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("results_json", sa.Text(), nullable=False),
        sa.Column(
            "overall_feedback",
            sa.Text(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_assessment_reviews_id",
        "assessment_reviews",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_assessment_reviews_attempt_id",
        "assessment_reviews",
        ["attempt_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("assessment_reviews")
    op.drop_table("generated_assessment_questions")
