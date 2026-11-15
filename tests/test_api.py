from fastapi.testclient import TestClient
import pytest

from codex_monitor import api
from codex_monitor.api import app
from codex_monitor.config import Settings
from codex_monitor.parser import SessionMonitor


@pytest.fixture(autouse=True)
def isolated_monitor(tmp_path, monkeypatch):
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monkeypatch.setattr(api, "monitor", monitor)
    monkeypatch.setattr(api, "settings", monitor.settings)
    return monitor


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


def test_api_serializes_unknown_usage_without_claiming_zero(isolated_monitor, tmp_path):
    from codex_monitor.parser import FileCursor, ThreadState

    state = ThreadState(tmp_path / "memory.jsonl", "unknown")
    isolated_monitor.files[state.path] = FileCursor(state=state)
    with TestClient(app) as client:
        detail = client.get("/api/threads/unknown")
        dashboard = client.get("/api/dashboard")
    assert detail.status_code == dashboard.status_code == 200
    body = detail.json()
    assert body["usage"]["input_tokens"] is None
    assert body["wci"] is None
    assert body["health"]["score"] is None
    assert dashboard.json()["active_thread"]["health"]["label"] == "INDISPONÍVEL"
