
"""
Train a demonstration student-performance classifier.

IMPORTANT:
The training data is synthetic and intended only to demonstrate
the ML pipeline. It is not validated educational assessment data.
"""

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# Resolve paths relative to this file.
ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = ML_DIR / "learning_model.joblib"

RANDOM_STATE = 42

FEATURE_NAMES = [
    "current_percentage",
    "previous_percentage",
    "attempt_count",
    "improvement",
]

CLASS_NAMES = [
    "Needs Revision",
    "Developing",
    "Proficient",
]


def create_synthetic_dataset():
    """Create reproducible synthetic data for the demonstration."""

    rng = np.random.default_rng(RANDOM_STATE)
    sample_count = 1200

    current = rng.uniform(0, 100, sample_count)
    previous = rng.uniform(0, 100, sample_count)
    attempts = rng.integers(1, 11, sample_count)

    improvement = current - previous

    # Demonstration-only labels based on current performance.
    # These labels are not ground truth from real students.
    labels = np.where(
        current < 40,
        "Needs Revision",
        np.where(current < 70, "Developing", "Proficient"),
    )

    X = np.column_stack(
        [current, previous, attempts, improvement]
    )

    return X, labels


def main():
    X, y = create_synthetic_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=150,
                    max_depth=8,
                    random_state=RANDOM_STATE,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    print("\n=== Demonstration Model Evaluation ===")
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    print(f"Test accuracy: {accuracy_score(y_test, predictions):.3f}")
    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=CLASS_NAMES,
            zero_division=0,
        )
    )

    joblib.dump(
        {
            "model": model,
            "feature_names": FEATURE_NAMES,
            "class_names": CLASS_NAMES,
            "data_type": "synthetic_demonstration",
        },
        MODEL_PATH,
    )

    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
