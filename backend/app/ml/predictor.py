
from pathlib import Path

import joblib
import numpy as np


MODEL_PATH = Path(__file__).resolve().parent / "learning_model.joblib"

# Load the trained model once when this module is imported.
saved_artifact = joblib.load(MODEL_PATH)

model = saved_artifact["model"]
class_names = saved_artifact["class_names"]


def predict_performance(
    current_percentage: float,
    previous_percentage: float,
    attempt_count: int,
) -> dict:
    """Predict a demonstration performance category."""

    if not 0 <= current_percentage <= 100:
        raise ValueError("Current percentage must be between 0 and 100.")

    if not 0 <= previous_percentage <= 100:
        raise ValueError("Previous percentage must be between 0 and 100.")

    if attempt_count < 1:
        raise ValueError("Attempt count must be at least 1.")

    improvement = current_percentage - previous_percentage

    features = np.array(
        [[
            current_percentage,
            previous_percentage,
            attempt_count,
            improvement,
        ]],
        dtype=float,
    )

    prediction = str(model.predict(features)[0])

    probabilities = model.predict_proba(features)[0]
    confidence = float(np.max(probabilities))

    return {
        "performance_level": prediction,
        "confidence": round(confidence, 4),
        "current_percentage": current_percentage,
        "previous_percentage": previous_percentage,
        "improvement": round(improvement, 2),
        "attempt_count": attempt_count,
        "data_type": "synthetic_demonstration",
        "is_educationally_validated": False,
    }
