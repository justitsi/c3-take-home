"""Structured diagnostic evidence must stay attributable, bounded, and redacted."""

import json
import os

from model import ModelUnavailable
from test_v2_guards import guarded_harness, _baseline
from test_v2_iteration import _assistant


def test_tool_events_link_actor_call_outcome_timing_and_source(guarded_harness, capsys):
    harness, _, _ = guarded_harness
    call = {"id": "read-counterexample-03", "function": {
        "name": "inspect_trace", "arguments": json.dumps({"path": "artifacts/replay/trace.jsonl", "query": "job-17"}),
    }}
    harness.tool_event("editor", call, {"ok": True, "truncated": True, "seed": 17}, elapsed=0.125)
    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "tool_result"
    assert event["actor"] == "editor"
    assert event["call_id"] == "read-counterexample-03"
    assert event["tool"] == "inspect_trace"
    assert event["source_revision"] == harness.patch_count
    assert event["ok"] is True
    assert event["elapsed_s"] == 0.125
    assert len(event["result_sha256"]) == 64
    assert "job-17" in event["arguments"]
    assert "truncated" in event["result_preview"]


def test_tool_event_logs_are_bounded_redacted_and_distinguish_results(guarded_harness, capsys):
    harness, _, _ = guarded_harness
    secret = os.environ["OPENAI_API_KEY"]
    call = {"id": "fixture-bounded-call", "function": {
        "name": "read_file", "arguments": json.dumps({"path": "x" * 30_000, "fixture_secret": secret}),
    }}
    result = {"ok": False, "error": f"fixture rejection {secret}",
              "violations": [{"invariant": "I_fixture", "detail": "d" * 4_000}] * 100,
              "content": "original tool evidence"}
    harness.tool_event("editor", call, result)
    first_output = capsys.readouterr().out
    first = json.loads(first_output)
    assert secret not in first_output
    assert "[REDACTED]" in first_output
    assert len(first_output) < 12_000
    result["content"] = "different tool evidence"
    harness.tool_event("editor", call, result)
    second = json.loads(capsys.readouterr().out)
    assert first["result_sha256"] != second["result_sha256"]


def test_editor_records_provider_finish_reason_and_tool_outcome(guarded_harness, monkeypatch, capsys):
    harness, _, _ = guarded_harness
    _baseline(harness)
    calls = 0

    def complete(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _assistant("read_file", {"path": "src/service.py"}, identifier="fixture-read-1")
        raise ModelUnavailable("fixture proxy unavailable")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture used to inspect structured observations.")
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    response = next(event for event in events if event["event"] == "model_response")
    result = next(event for event in events if event["event"] == "tool_result")
    stopped = next(event for event in events if event["event"] == "editor_complete")
    assert response["actor"] == "editor" and response["finish_reason"] == "tool_calls"
    assert result["call_id"] == "fixture-read-1" and result["ok"]
    assert stopped["reason"] == "fixture proxy unavailable"
