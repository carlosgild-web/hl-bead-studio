"""Phase 0 smoke test: the mock SAP starts and answers its health probe."""

from fastapi.testclient import TestClient

from app import __version__
from app.main import app


def test_health_reports_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "sap-mock", "version": __version__}
