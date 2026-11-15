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


def test_title_falls_back_to_response_item_and_skips_injected_context(tmp_path):
    path = write_session(tmp_path)
    data = b"".join([
        line(event("session_meta", {"id": "response-title"})),
        line(event("response_item", {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "<recommended_plugins>internal</recommended_plugins>"},
        ]})),
        line(event("response_item", {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "<environment_context>internal</environment_context>"},
        ]})),
        line(event("response_item", {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "Nome real da thread vindo do pedido do usuário"},
        ]})),
    ])
    path.write_bytes(data)

    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()

    assert monitor.thread("response-title")["title"] == "Nome real da thread vindo do pedido do usuário"


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
    primary = dashboard["allowance"]["primary"]
    assert primary is not None
    assert primary["used_percent"] == 5
    assert primary["cycle"] == 1


def test_dashboard_always_includes_at_least_five_most_recent_threads(tmp_path):
    for index in range(7):
        path = write_session(tmp_path, f"thread-{index}.jsonl")
        timestamp = f"2026-09-{index + 1:02d}T12:00:00Z"
        path.write_bytes(line(event("session_meta", {"id": f"thread-{index}"}, timestamp)))

    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()

    assert [thread["id"] for thread in monitor.dashboard()["threads"]] == [
        "thread-6",
        "thread-5",
        "thread-4",
        "thread-3",
        "thread-2",
    ]


def test_title_uses_codex_session_index_and_tracks_renames(tmp_path):
    path = write_session(tmp_path)
    path.write_bytes(
        line(event("session_meta", {"id": "indexed-title"}))
        + line(event("event_msg", {"type": "user_message", "message": "Primeiro pedido muito longo"}))
    )
    index_path = tmp_path / "session_index.jsonl"
    index_path.write_text(
        json.dumps({"id": "indexed-title", "thread_name": "Nome exibido no VS Code"}) + "\n",
        encoding="utf-8",
    )
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path, session_index_file=index_path))

    monitor.scan()
    assert monitor.thread("indexed-title")["title"] == "Nome exibido no VS Code"

    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"id": "indexed-title", "thread_name": "Nome renomeado"}) + "\n")
    monitor.scan()
    assert monitor.thread("indexed-title")["title"] == "Nome renomeado"


def test_unchanged_usage_does_not_add_calls_but_refreshes_global_quota(tmp_path):
    path = write_session(tmp_path)
    path.write_bytes(line(event("session_meta", {"id": "dedup"})) + line(token_event()))
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()
    repeated = token_event(rate=20) | {"timestamp": "2026-09-14T12:01:00Z"}
    with path.open("ab") as handle:
        handle.write(line(event("response_item", {"type": "function_call", "call_id": "new-tool"})))
        handle.write(line(repeated))
    monitor.scan()
    result = monitor.thread("dedup")
    assert len(result["evolution"]) == 1
    assert result["tool_calls"] == 1
    assert result["last_activity"] == repeated["timestamp"]
    assert len(monitor.allowance.observations) == 4
    assert monitor.allowance.observations[-2].used_percent == 20
    # An identical last-call size can still represent new consumption when totals advance.
    with path.open("ab") as handle:
        handle.write(line(token_event(2_000, 1_600, 200, last_input=500)))
    monitor.scan()
    monitor.scan()
    assert len(monitor.thread("dedup")["evolution"]) == 2


def test_old_partial_logs_preserve_missing_and_explicit_zero(tmp_path):
    path = write_session(tmp_path)
    path.write_bytes(line(event("session_meta", {"id": "partial-usage"})))
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()
    result = monitor.thread("partial-usage")
    assert all(value is None for value in result["usage"].values())
    assert result["wci"] is None
    assert result["health"]["score"] is None
    usage = {"input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": None}
    with path.open("ab") as handle:
        handle.write(line(event("event_msg", {"type": "token_count", "info": {"total_token_usage": usage, "last_token_usage": usage}})))
    monitor.scan()
    result = monitor.thread("partial-usage")
    assert result["usage"]["input_tokens"] == 0
    assert result["usage"]["cached_input_tokens"] is None
    assert result["usage"]["reasoning_output_tokens"] is None
    assert result["usage"]["uncached_input_tokens"] is None
    assert result["wci"] is None
    assert result["health"]["score"] == 0
    assert result["evolution"] == []
    usage = {"input_tokens": 20, "output_tokens": 2}
    with path.open("ab") as handle:
        handle.write(line(event("event_msg", {"type": "token_count", "info": {"total_token_usage": usage, "last_token_usage": usage, "model_context_window": 100}})))
    monitor.scan()
    result = monitor.thread("partial-usage")
    assert result["context_pressure"] == 20
    assert result["evolution"][0]["wci"] is None
    assert result["evolution"][0]["cumulative_wci"] is None


def test_last_only_snapshots_are_deduplicated_and_invalid_fields_are_unknown(tmp_path):
    path = write_session(tmp_path)
    usage = {"input_tokens": 10, "cached_input_tokens": "invalid", "output_tokens": 0}
    path.write_bytes(b"".join(line(event("event_msg", {"type": "token_count", "info": {"last_token_usage": usage}}, timestamp)) for timestamp in ["2026-09-14T12:00:00Z", "2026-09-14T12:01:00Z"]))
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()
    result = monitor.threads(details=True)[0]
    assert len(result["evolution"]) == 1
    assert result["evolution"][0]["cached_input_tokens"] is None
    assert result["usage"]["input_tokens"] is None


def test_missing_metadata_and_snapshot_source_changes_do_not_create_calls(tmp_path):
    path = write_session(tmp_path)
    first = token_event()
    missing_total = token_event()
    del missing_total["payload"]["info"]["total_token_usage"]
    missing_cache = token_event()
    del missing_cache["payload"]["info"]["total_token_usage"]["cached_input_tokens"]
    path.write_bytes(b"".join(line(item) for item in [first, missing_total, missing_cache, token_event()]))
    monitor = SessionMonitor(Settings(sessions_dir=tmp_path))
    monitor.scan()
    assert len(monitor.threads(details=True)[0]["evolution"]) == 1
