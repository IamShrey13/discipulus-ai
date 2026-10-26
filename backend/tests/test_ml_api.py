from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200


def test_bloom_profile_requires_authentication():
    response = client.get("/api/ml/bloom-profile")

    assert response.status_code in (401, 403)


def test_performance_endpoint_requires_authentication():
    response = client.get("/api/ml/performance")

    assert response.status_code in (401, 403)


def test_chapter_questions_require_authentication():
    response = client.get("/api/chapters/1/questions")

    assert response.status_code in (401, 403)


def test_attempt_review_requires_authentication():
    response = client.get("/api/attempts/1/review")

    assert response.status_code in (401, 403)


def test_my_attempts_require_authentication():
    response = client.get("/api/attempts/me")

    assert response.status_code in (401, 403)