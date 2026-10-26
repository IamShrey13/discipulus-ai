-- Run this once against the existing Discipulus-AI PostgreSQL database.
-- It adds storage for generated question answer keys and detailed submitted feedback.
CREATE TABLE IF NOT EXISTS generated_assessment_questions (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_order INTEGER NOT NULL,
    question_type VARCHAR(20) NOT NULL,
    prompt TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '[]',
    correct_option VARCHAR(1),
    expected_answer TEXT NOT NULL,
    rubric_json TEXT NOT NULL DEFAULT '[]',
    explanation TEXT NOT NULL DEFAULT '',
    topic VARCHAR(200) NOT NULL DEFAULT '',
    bloom_level VARCHAR(30) NOT NULL DEFAULT 'Understand',
    difficulty VARCHAR(20) NOT NULL DEFAULT 'medium'
);
CREATE INDEX IF NOT EXISTS ix_generated_assessment_questions_id
    ON generated_assessment_questions(id);
CREATE INDEX IF NOT EXISTS ix_generated_assessment_questions_assessment_id
    ON generated_assessment_questions(assessment_id);

CREATE TABLE IF NOT EXISTS assessment_reviews (
    id SERIAL PRIMARY KEY,
    attempt_id INTEGER NOT NULL UNIQUE REFERENCES attempts(id) ON DELETE CASCADE,
    score_awarded DOUBLE PRECISION NOT NULL,
    max_score DOUBLE PRECISION NOT NULL,
    percentage DOUBLE PRECISION NOT NULL,
    results_json TEXT NOT NULL,
    overall_feedback TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_assessment_reviews_id ON assessment_reviews(id);
CREATE INDEX IF NOT EXISTS ix_assessment_reviews_attempt_id ON assessment_reviews(attempt_id);
