import json
from pathlib import Path
import threading

import pytest

import fixer.artifacts as artifact_module
from fixer.tools import READ_TOOL_SCHEMAS, Tools


@pytest.fixture
def artifact_tools(tmp_path):
    workspace = tmp_path / "workspace"
    corpus = tmp_path / "corpus"
    scratch = tmp_path / "scratch"
    (workspace / "src").mkdir(parents=True)
    corpus.mkdir()
    (scratch / "artifacts/replay-unit").mkdir(parents=True)
    tools = Tools(workspace, corpus, scratch)
    return tools


def write_trace(tools, events):
    trace = tools.artifacts_root / "replay-unit/trace.jsonl"
    trace.write_text("".join(json.dumps(event) + "\n" for event in events))
    return trace


def test_artifact_aliases_support_list_read_search_and_safe_absolute_paths(artifact_tools):
    tools = artifact_tools
    trace = write_trace(tools, [{"t": 1, "event": "lease_expired", "job": "job-x"}])
    summary = trace.parent / "summary.json"
    summary.write_text('{"invariants": [{"invariant": "lease-safety"}]}\n')
    assert set(tools.list_files(root="artifacts")["files"]) == {
        "artifacts/replay-unit/trace.jsonl", "artifacts/replay-unit/summary.json"}
    read = tools.read_file("artifacts/replay-unit/summary.json")
    assert read["ok"] and "lease-safety" in read["content"]
    assert tools.read_file(str(summary))["path"] == "artifacts/replay-unit/summary.json"
    result = tools.search("LEASE_EXPIRED", root="artifacts")
    assert result["ok"] and result["matches"][0]["path"] == "artifacts/replay-unit/trace.jsonl"
    assert tools.search("lease-safety", root=str(summary))["ok"]
    assert tools.inspect_trace(str(trace))["events"][0]["line"] == 1
    assert any(tool["function"]["name"] == "inspect_trace" for tool in READ_TOOL_SCHEMAS)


def test_artifacts_are_read_only_and_do_not_allow_other_absolute_paths(artifact_tools):
    tools = artifact_tools
    trace = write_trace(tools, [{"t": 1, "event": "before"}])
    original = trace.read_bytes()
    for path in ("artifacts/replay-unit/trace.jsonl", str(trace)):
        result = tools.apply_edits([{"path": path, "old": "before", "new": "after"}])
        assert not result["ok"]
    for path in (str(tools.workspace / "src/code.py"), str(tools.corpus / "INDEX.md"), str(tools.scratch / "private.json")):
        assert not tools.read_file(path)["ok"]
        assert not tools.inspect_trace(path)["ok"]
    assert trace.read_bytes() == original


def test_artifact_symlink_and_parent_traversal_containment(artifact_tools, tmp_path):
    tools = artifact_tools
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.jsonl").write_text('{"secret": true}\n')
    (tools.artifacts_root / "escaped.jsonl").symlink_to(outside / "secret.jsonl")
    (tools.artifacts_root / "escaped-dir").symlink_to(outside, target_is_directory=True)
    for path in ("artifacts/../private.json", "artifacts/escaped.jsonl", "artifacts/escaped-dir/secret.jsonl"):
        assert not tools.read_file(path)["ok"]
        assert not tools.inspect_trace(path)["ok"]
    assert tools.list_files(root="artifacts")["files"] == []
    other = Tools(tools.workspace, tools.corpus, tmp_path / "other-scratch")
    other.scratch.mkdir()
    other.artifacts_root.symlink_to(outside, target_is_directory=True)
    assert not other.read_file("artifacts/secret.jsonl")["ok"]
    assert not other.list_files(root="artifacts")["ok"]


def test_trace_query_and_time_window_keep_original_line_numbers(artifact_tools):
    tools = artifact_tools
    trace = tools.artifacts_root / "replay-unit/trace.jsonl"
    trace.write_text(
        '{"t": 0, "job": "job-x", "event": "start"}\n'
        'not json\n\n[]\n'
        '{"t": 1, "job": "other", "event": "unrelated"}\n'
        '{"t": 2, "payload": {"job": "job-x"}, "event": "timeout"}\n'
        '{"t": 3, "job": "job-x", "event": "retry"}\n'
    )
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", query="JOB-X", center_t=2, window_s=0.5)
    assert result["ok"] and not result["truncated"]
    assert [row["line"] for row in result["events"]] == [6]
    assert result["events"][0]["event"]["event"] == "timeout"
    assert result["malformed_lines"] == 2
    assert result["malformed_line_numbers"] == [2, 4]
    assert result["scanned_lines"] == 7


def test_trace_malformed_utf8_and_oversized_rows_are_bounded(artifact_tools):
    tools = artifact_tools
    trace = tools.artifacts_root / "replay-unit/trace.jsonl"
    trace.write_bytes(b"x" * (artifact_module.MAX_LINE_BYTES + 50) + b'\n\xff\n{"t": 5, "event": "valid"}\n')
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl")
    assert result["ok"]
    assert result["malformed_lines"] == 2
    assert result["oversized_lines"] == 1 and result["truncated"]
    assert result["events"][0]["line"] == 3
    assert result["events"][0]["event"]["event"] == "valid"
    assert result["scanned_bytes"] == trace.stat().st_size


def test_trace_scan_limit_is_explicit_and_never_exceeded(artifact_tools, monkeypatch):
    tools = artifact_tools
    trace = write_trace(tools, [{"t": index, "event": "noise"} for index in range(100)])
    monkeypatch.setattr(artifact_module, "MAX_TRACE_BYTES", 128)
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", query="absent")
    assert result["ok"] and result["truncated"]
    assert result["scanned_bytes"] <= 128 < trace.stat().st_size
    assert result["events"] == []


def test_trace_output_limit_and_clipped_entity_evidence(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": index, "payload": "x" * 1000 + "target-entity" + "y" * 3000} for index in range(150)])
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", query="target-entity", limit=100)
    assert result["ok"] and result["truncated"]
    assert len(json.dumps(result, ensure_ascii=False)) <= artifact_module.MAX_TRACE_OUTPUT
    assert len(result["events"]) < 100
    assert all("target-entity" in row["excerpt"] and row["event_truncated"] for row in result["events"])


def test_trace_unicode_query_uses_decoded_event_values(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": 1, "tenant": "Zürich"}])
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", query="ZÜRICH")
    assert result["ok"] and len(result["events"]) == 1


def test_trace_cancellation_before_and_during_scan(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": index, "event": "noise"} for index in range(100)])
    tools.stop = threading.Event()
    tools.stop.set()
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl")
    assert not result["ok"] and result["cancelled"] and result["scanned_bytes"] == 0

    class CancelsDuringScan:
        def __init__(self):
            self.polls = 0

        def is_set(self):
            self.polls += 1
            return self.polls >= 3

    tools.stop = CancelsDuringScan()
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", limit=100)
    assert not result["ok"] and result["cancelled"]
    assert len(result["events"]) == 2


@pytest.mark.parametrize("arguments", [{"center_t": float("nan")}, {"window_s": -1}, {"window_s": float("inf")}, {"query": " "}])
def test_trace_rejects_invalid_filters(artifact_tools, arguments):
    tools = artifact_tools
    write_trace(tools, [{"t": 1, "event": "valid"}])
    assert not tools.inspect_trace("artifacts/replay-unit/trace.jsonl", **arguments)["ok"]


def test_trace_without_trailing_newline_and_invalid_time_remains_readable(artifact_tools):
    tools = artifact_tools
    trace = tools.artifacts_root / "replay-unit/trace.jsonl"
    trace.write_text(json.dumps({"t": 10 ** 500, "event": "odd time"}) + '\n{"t": 2, "event": "last row"}')
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl")
    assert result["ok"] and len(result["events"]) == 2
    assert result["events"][0]["t"] is None
    assert result["events"][1]["event"]["event"] == "last row"
