from fastapi.testclient import TestClient

from codex_monitor.api import app


def test_health_endpoint_is_explicitly_read_only():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["read_only"] is True
