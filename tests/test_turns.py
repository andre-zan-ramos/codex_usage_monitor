from codex_monitor.parser import ThreadState
from codex_monitor.config import Settings
from pathlib import Path


def send(s, kind, **p):
    s.ingest({"type": kind, "timestamp": "2026-11-15T12:00:00Z", "payload": p})


def start(s, ident="a"):
    send(s, "event_msg", type="task_started", turn_id=ident)
    send(s, "turn_context", turn_id=ident, model="model", effort="high")


def snap(s, n, **extra):
    send(s, "event_msg", type="token_count", info={"total_token_usage": {"input_tokens": n, "cached_input_tokens": n // 2, "output_tokens": n // 10, "reasoning_output_tokens": n // 20, **extra}})


def result(s):
    return s.as_dict(Settings(), True)


def test_turn_deltas_duplicates_and_boundaries():
    s = ThreadState(Path("log"), "id")
    start(s); snap(s, 100); snap(s, 200); snap(s, 200)
    send(s, "event_msg", type="task_complete", turn_id="a", error="private")
    snap(s, 250)
    start(s, "b"); snap(s, 300); snap(s, 400)
    r = result(s)
    assert [t["usage"]["input_tokens"] for t in r["turns"]] == [100, 100]
    assert r["turns"][0]["usage"]["uncached_input_tokens"] == 50
    assert r["turns"][0]["usage"]["output_tokens"] == 10
    assert r["turns"][0]["usage"]["reasoning_output_tokens"] == 5
    assert r["turns"][0]["intervals"] == 1
    assert r["turns"][0]["state"] == "encerramento_observado"
    assert len(r["unassigned_usage"]) == 3
    assert "private" not in str(r)


def test_partial_regression_metadata_and_mismatch():
    s = ThreadState(Path("log"), "id")
    start(s); snap(s, 100); snap(s, 200, output_tokens=None)
    snap(s, 300)
    send(s, "turn_context", turn_id="a", model="other", effort="low")
    snap(s, 50); snap(s, 100)
    t = result(s)["turns"][0]
    assert t["metadata_changed"]
    assert t["usage"]["output_tokens"] is None
    assert t["usage"]["input_tokens"] == 250
    send(s, "turn_context", turn_id="wrong")
    snap(s, 200)
    assert result(s)["unassigned_usage"][-1]["reason"] == "limite_ou_associacao_insegura"


def test_old_logs_missing_totals_overlap_and_invalid_values():
    s = ThreadState(Path("log"), "id")
    snap(s, 100); snap(s, 200)
    assert result(s)["turns"] == []
    start(s); snap(s, 300)
    send(s, "event_msg", type="token_count", info={"last_token_usage": {"input_tokens": 20}})
    snap(s, 400); snap(s, 500, output_tokens=-2)
    assert result(s)["turns"][0]["usage"]["output_tokens"] is None
    start(s, "overlap"); snap(s, 600); snap(s, 700)
    assert result(s)["turns"][1]["ambiguous"]
    assert result(s)["turns"][1]["intervals"] == 0


def test_incremental_api_turns(tmp_path, monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from codex_monitor import api
    from codex_monitor.parser import SessionMonitor
    folder = tmp_path / "2026/11/15"
    folder.mkdir(parents=True)
    path = folder / "thread.jsonl"
    events = [{"type": "session_meta", "payload": {"id": "id"}},
              {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "a"}},
              {"type": "turn_context", "payload": {"turn_id": "a"}},
              {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 0}}}}]
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monkeypatch.setattr(api, "monitor", monitor)
    with TestClient(api.app) as client:
        assert client.get("/api/threads/id").json()["turns"][0]["intervals"] == 0
        with path.open("a", encoding="utf-8") as f:
            e = events[-1]
            e["payload"]["info"]["total_token_usage"]["input_tokens"] = 10
            f.write(json.dumps(e) + "\n")
        first = client.get("/api/threads/id").json()
        assert first["turns"][0]["usage"]["input_tokens"] == 10
        assert client.get("/api/threads/id").json() == first


def test_repeated_boundary_establishes_baseline_without_consumption():
    s = ThreadState(Path("log"), "id")
    start(s); snap(s, 100); snap(s, 200)
    send(s, "event_msg", type="task_complete", turn_id="a")
    start(s, "b"); snap(s, 200); snap(s, 300)
    t = result(s)["turns"][1]
    assert t["usage"]["input_tokens"] == 100
    assert t["intervals"] == 1
