from fastapi.testclient import TestClient

from codex_monitor.api import app


def test_health_endpoint_is_explicitly_read_only():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["read_only"] is True


def test_rate_timeline_endpoint_accepts_only_supported_ranges():
    with TestClient(app) as client:
        response = client.get("/api/rate-limits/timeline?range=5h")
        rejected = client.get("/api/rate-limits/timeline?range=invalid")
    assert response.status_code == 200
    assert response.json()["range"] == "5h"
    assert rejected.status_code == 422
