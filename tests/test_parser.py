import json
from pathlib import Path

from codex_monitor.config import Settings
from codex_monitor.parser import SessionMonitor


def line(event):
    return (json.dumps(event) + "\n").encode()


def event(kind, payload, timestamp="2026-09-14T12:00:00Z"):
    return {"type": kind, "timestamp": timestamp, "payload": payload}


def write_session(root: Path, name="thread.jsonl") -> Path:
    folder = root / "2026" / "09" / "14"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


def token_event(total_input=1_000, cached=800, output=100, last_input=500, rate=10):
    return event("event_msg", {
        "type": "token_count",
        "info": {
            "total_token_usage": {"input_tokens": total_input, "cached_input_tokens": cached, "output_tokens": output, "reasoning_output_tokens": 30, "total_tokens": total_input + output},
            "last_token_usage": {"input_tokens": last_input, "cached_input_tokens": min(cached, last_input), "output_tokens": output, "reasoning_output_tokens": 30, "total_tokens": last_input + output},
            "model_context_window": 2_000,
        },
        "rate_limits": {"primary": {"used_percent": rate, "window_minutes": 300, "resets_at": 100}, "secondary": {"used_percent": 5, "window_minutes": 10080, "resets_at": 200}},
    })


def test_different_events_missing_fields_and_accumulators(tmp_path):
    path = write_session(tmp_path)
    data = b"".join([
        line(event("session_meta", {"id": "abc", "timestamp": "2026-09-14T11:00:00Z"})),
        line(event("turn_context", {"model": "gpt-test", "effort": "high"})),
        line(event("event_msg", {"type": "user_message", "message": "Meu prompt privado para o projeto"})),
        line(event("response_item", {"type": "custom_tool_call", "call_id": "call-1"})),
        line(event("response_item", {"type": "custom_tool_call", "call_id": "call-1"})),
        line(event("event_msg", {"type": "context_compacted"})),
        line(token_event()),
        line(event("unknown", {})),
    ])
    path.write_bytes(data)
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()
    thread = monitor.thread("abc")
    assert thread is not None
    assert thread["model"] == "gpt-test"
    assert thread["tool_calls"] == 1
    assert thread["compactions"] == 1
    assert thread["usage"]["uncached_input_tokens"] == 200
    assert thread["context_pressure"] == 25
    assert thread["title"].startswith("Meu prompt privado")


def test_incremental_read_and_no_double_count(tmp_path):
    path = write_session(tmp_path)
    path.write_bytes(line(event("session_meta", {"id": "incremental"})) + line(token_event()))
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan(); monitor.scan()
    assert len(monitor.thread("incremental")["evolution"]) == 1
    with path.open("ab") as handle:
        handle.write(line(token_event(2_000, 1_600, 200, 700)))
    monitor.scan()
    result = monitor.thread("incremental")
    assert result["usage"]["input_tokens"] == 2_000
    assert len(result["evolution"]) == 2


def test_incomplete_line_waits_until_completed(tmp_path):
    path = write_session(tmp_path)
    valid = line(event("session_meta", {"id": "partial"}))
    path.write_bytes(valid + b'{"type":"event_msg"')
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()
    assert monitor.thread("partial")["parser"]["invalid_lines"] == 0
    with path.open("ab") as handle:
        handle.write(b',"payload":{"type":"unknown"}}\nnot json\n')
    monitor.scan()
    assert monitor.thread("partial")["parser"]["invalid_lines"] == 1


def test_truncation_rebuilds_file_state(tmp_path):
    path = write_session(tmp_path)
    path.write_bytes(line(event("session_meta", {"id": "old"})) + line(token_event()))
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path)); monitor.scan()
    path.write_bytes(line(event("session_meta", {"id": "new"})))
    monitor.scan()
    assert monitor.thread("old") is None
    assert monitor.thread("new") is not None


def test_rate_limit_reset_and_multiple_threads(tmp_path):
    first = write_session(tmp_path, "one.jsonl")
    second = write_session(tmp_path, "two.jsonl")
    first.write_bytes(line(event("session_meta", {"id": "one"})) + line(token_event(rate=90)))
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path)); monitor.scan()
    second.write_bytes(line(event("session_meta", {"id": "two"}, "2026-09-14T13:00:00Z")) + line(token_event(rate=5) | {"timestamp": "2026-09-14T13:01:00Z"}))
    raw = second.read_text()
    raw = raw.replace('"resets_at": 100', '"resets_at": 300')
    second.write_text(raw)
    monitor.scan()
    dashboard = monitor.dashboard()
    assert len(dashboard["threads"]) == 2
    assert dashboard["rate_limit_resets_detected"] == 1
    assert dashboard["rate_limits"]["primary"]["used_percent"] == 5
