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


def test_all_terms_match_separate_fields_without_changing_literal_queries(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [
        {"t": 1, "payload": {"entity": "request-a"}, "event": "committed"},
        {"t": 2, "payload": {"entity": "request-b"}, "event": "committed"},
        {"t": 3, "payload": {"entity": "request-a"}, "event": "started"},
    ])
    literal = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", query="request-a committed")
    assert literal["ok"] and literal["returned_events"] == literal["matched_events"] == 0
    assert literal["query_mode"] == "literal" and "all_terms" in literal["hint"]
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", all_terms=["REQUEST-A", "committed"])
    assert result["ok"] and result["query_mode"] == "all_terms"
    assert [row["line"] for row in result["events"]] == [1]
    assert result["returned_time_range"] == [1, 1]


def test_literal_query_all_terms_and_time_filter_are_conjunctive(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [
        {"t": 1, "entity": "request-a", "event": "commit accepted", "tenant": "east"},
        {"t": 5, "entity": "request-a", "event": "commit accepted", "tenant": "east"},
        {"t": 5, "entity": "request-a", "event": "commit rejected", "tenant": "east"},
        {"t": 5, "entity": "request-b", "event": "commit accepted", "tenant": "east"},
    ])
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", query="commit accepted",
                                 all_terms=["request-a", "east"], center_t=5, window_s=0)
    assert result["ok"] and result["query_mode"] == "literal+all_terms"
    assert [row["line"] for row in result["events"]] == [2]
    assert result["returned_events"] == 1
    assert result["next_line"] is None


def test_event_limit_pagination_reaches_late_rows_without_duplicates(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": index, "entity": "request-a", "event": "progress"} for index in range(7)])
    lines = []
    cursor = 1
    for _ in range(8):
        result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", all_terms=["request-a", "progress"], limit=2, start_line=cursor)
        assert result["ok"] and result["returned_events"] == len(result["events"])
        lines.extend(row["line"] for row in result["events"])
        if result["next_line"] is None:
            assert not result["truncated"]
            break
        assert result["next_line"] > cursor
        assert "start_line=next_line" in result["hint"]
        cursor = result["next_line"]
    assert lines == list(range(1, 8))


def test_output_cap_pagination_resumes_first_unreturned_matching_row(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": index, "payload": "x" * 1000 + "target" + "y" * 3000} for index in range(40)])
    lines = []
    cursor = 1
    for _ in range(40):
        result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", query="target", limit=100, start_line=cursor)
        assert result["ok"]
        assert len(json.dumps(result, ensure_ascii=False)) <= artifact_module.MAX_TRACE_OUTPUT
        lines.extend(row["line"] for row in result["events"])
        if result["next_line"] is None:
            break
        assert result["next_line"] > cursor
        assert result["next_line"] == result["events"][-1]["line"] + 1
        cursor = result["next_line"]
    assert lines == list(range(1, 41))


def test_returned_time_range_handles_unsorted_times_and_cursor_skips_prefix(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": time, "event": "same"} for time in (8, 1, 4)])
    first = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", limit=2)
    assert first["returned_time_range"] == [1, 8]
    second = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", start_line=first["next_line"])
    assert second["returned_time_range"] == [4, 4]
    assert second["events"][0]["line"] == 3 and second["next_line"] is None


def test_pagination_preserves_line_provenance_after_skipped_malformed_rows(artifact_tools):
    tools = artifact_tools
    trace = tools.artifacts_root / "replay-unit/trace.jsonl"
    trace.write_text('bad\n{"t": 1}\nnot json\n{"t": 3}\n')
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", start_line=4)
    assert result["ok"] and result["scanned_lines"] == 4
    assert result["malformed_lines"] == 0
    assert result["events"][0]["line"] == 4


def test_scan_limit_includes_skipped_prefix_and_does_not_claim_eof(artifact_tools, monkeypatch):
    tools = artifact_tools
    write_trace(tools, [{"t": index, "event": "noise"} for index in range(100)])
    monkeypatch.setattr(artifact_module, "MAX_TRACE_BYTES", 128)
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", start_line=90)
    assert result["ok"] and result["scan_limit_reached"] and result["truncated"]
    assert result["scanned_bytes"] <= 128 and result["returned_events"] == 0
    assert "scan limit" in result["hint"]


def test_all_terms_support_unicode_and_keep_clipped_term_evidence(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": 1, "tenant": "Zürich", "payload": "x" * 1000 + "request-a" + "y" * 3000 + "complete-token"}])
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", all_terms=["ZÜRICH", "request-a", "complete-token"])
    assert result["ok"] and result["returned_events"] == 1
    row = result["events"][0]
    assert row["event_truncated"]
    excerpts = {item["term"]: item["text"] for item in row["term_excerpts"]}
    assert "request-a" in excerpts["request-a"]
    assert "complete-token" in excerpts["complete-token"]


@pytest.mark.parametrize("all_terms", [[], "entity", [" "] , [1], ["x"] * 9, ["x" * 257]])
def test_all_terms_reject_invalid_or_unbounded_lists(artifact_tools, all_terms):
    tools = artifact_tools
    write_trace(tools, [{"t": 1, "event": "valid"}])
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", all_terms=all_terms)
    assert not result["ok"] and "all_terms" in result["error"]


@pytest.mark.parametrize("start_line", [0, -1, True, 1.5, None])
def test_pagination_rejects_invalid_line_numbers(artifact_tools, start_line):
    tools = artifact_tools
    write_trace(tools, [{"t": 1, "event": "valid"}])
    assert not tools.inspect_trace("artifacts/replay-unit/trace.jsonl", start_line=start_line)["ok"]


def test_all_terms_and_pagination_preserve_cancellation(artifact_tools):
    tools = artifact_tools
    write_trace(tools, [{"t": index, "event": "progress"} for index in range(100)])
    tools.stop = threading.Event()
    tools.stop.set()
    result = tools.inspect_trace("artifacts/replay-unit/trace.jsonl", all_terms=["progress"], start_line=50)
    assert not result["ok"] and result["cancelled"]
    assert result["scanned_bytes"] == 0 and result["returned_events"] == 0
    assert result["next_line"] == 50


def test_original_positional_parser_api_remains_compatible(artifact_tools):
    tools = artifact_tools
    path = write_trace(tools, [{"t": 1, "event": "exact phrase"}])
    result = artifact_module.inspect_jsonl(path, "artifacts/replay-unit/trace.jsonl", "exact phrase", 1, 0, 30, threading.Event())
    assert result["ok"] and result["returned_events"] == 1
