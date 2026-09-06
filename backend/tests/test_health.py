from fastapi.testclient import TestClient

from refyne.main import app


def test_health_reports_service_status() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "refyne"

