"""Independent generated-evidence tests: readable, bounded, and never writable."""

import json
from pathlib import Path
import threading

import pytest

from tools import Tools


@pytest.fixture
def artifact_tools(tmp_path):
    workspace, corpus, scratch = (tmp_path / name for name in ("workspace", "corpus", "scratch"))
    (workspace / "src").mkdir(parents=True)
    corpus.mkdir()
    run = scratch / "artifacts" / "replay-example"
    run.mkdir(parents=True)
    (workspace / "src/service.py").write_text("VALIDATED = True\n")
    (run / "summary.json").write_text(json.dumps({"invariants": [], "seed": 7}))
    return Tools(workspace, corpus, scratch), run


def _trace(run: Path, events) -> Path:
    path = run / "trace.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events))
    return path


def test_generated_absolute_paths_and_aliases_are_both_readable(artifact_tools):
    tools, run = artifact_tools
    alias = "artifacts/replay-example/summary.json"
    by_alias = tools.read_file(alias)
    by_absolute = tools.read_file(str(run / "summary.json"))
    assert by_alias["ok"] and by_absolute["ok"]
    assert by_alias["content"] == by_absolute["content"]
    assert "invariants" in by_alias["content"]
    assert by_alias["path"] == alias == by_absolute["path"]
    assert tools.list_files(root="artifacts")["files"] == [alias]
    found = tools.search("invariants", root="artifacts")
    assert found["ok"] and found["matches"][0]["path"] == alias
    assert not tools.read_file(str(tools.workspace / "src/service.py"))["ok"]
    assert (tools.workspace / "src/service.py").read_text() == "VALIDATED = True\n"


@pytest.mark.parametrize("accessor", ["read_file", "search", "inspect_trace"])
def test_artifact_escape_and_sibling_prefix_are_rejected(artifact_tools, tmp_path, accessor):
    tools, run = artifact_tools
    outside = tmp_path / "private.jsonl"
    outside.write_text('{"secret":"fixture-do-not-expose"}\n')
    sibling = tools.scratch / "artifacts-other"
    sibling.mkdir()
    (sibling / "trace.jsonl").write_text(outside.read_text())
    (run / "escape.jsonl").symlink_to(outside)
    attempts = [
        "artifacts/../private.jsonl", str(outside),
        str(sibling / "trace.jsonl"), "artifacts/replay-example/escape.jsonl",
        str(run / "escape.jsonl"),
    ]
    for path in attempts:
        if accessor == "search":
            result = tools.search("fixture-do-not-expose", root=path)
        else:
            result = getattr(tools, accessor)(path)
        assert not result["ok"], (accessor, path, result)
        assert "fixture-do-not-expose" not in json.dumps(result)


def test_artifact_root_symlink_cannot_expand_allowed_roots(tmp_path):
    workspace, corpus, scratch, outside = (tmp_path / name for name in ("workspace", "corpus", "scratch", "outside"))
    for directory in (workspace, corpus, scratch, outside):
        directory.mkdir()
    (outside / "private.json").write_text('{"secret":"fixture-do-not-expose"}')
    (scratch / "artifacts").symlink_to(outside, target_is_directory=True)
    try:
        tools = Tools(workspace, corpus, scratch)
    except ValueError:
        return  # Refusing the unsafe configuration is also a safe outcome.
    result = tools.read_file("artifacts/private.json")
    assert not result["ok"]
    assert "fixture-do-not-expose" not in json.dumps(result)


def test_inspection_artifacts_cannot_be_mutated(artifact_tools):
    tools, run = artifact_tools
    path = run / "summary.json"
    original = path.read_bytes()
    for candidate in ("artifacts/replay-example/summary.json", str(path)):
        result = tools.apply_edits([{"path": candidate, "old": "\"seed\": 7", "new": "\"seed\": 99"}])
        assert not result["ok"]
        assert path.read_bytes() == original


def test_trace_query_and_time_window_do_not_mix_entities(artifact_tools):
    tools, run = artifact_tools
    path = _trace(run, [
        {"t": 0, "kind": "log", "job": "other", "event": "commit"},
        {"t": 1, "kind": "log", "job": "TARGET", "event": "accepted"},
        {"t": 2.9, "kind": "log", "job": "other", "event": "committed"},
        {"t": 3, "kind": "log", "job": "target", "event": "committed"},
        {"t": 4, "kind": "log", "job": "target", "event": "retry"},
    ])
    result = tools.inspect_trace(str(path), query="target", center_t=3, window_s=0.2)
    assert result["ok"]
    assert len(result["events"]) == 1
    assert result["events"][0]["line"] == 4
    assert result["events"][0]["event"]["job"] == "target"
    assert result["events"][0]["t"] == 3


def test_trace_inspection_reports_malformed_records_and_preserves_line_numbers(artifact_tools):
    tools, run = artifact_tools
    path = run / "trace.jsonl"
    path.write_text('{broken-json\n[]\n{"kind":"log","t":2,"event":"literal [. match"}\n')
    result = tools.inspect_trace(str(path), query="[.")
    assert result["ok"]
    assert result["malformed_lines"] == 2
    assert result["malformed_line_numbers"] == [1, 2]
    assert result["events"][0]["line"] == 3
    assert result["events"][0]["event"]["event"] == "literal [. match"


def test_trace_result_and_oversized_records_are_bounded(artifact_tools):
    tools, run = artifact_tools
    path = _trace(run, [
        {"t": 1, "kind": "log", "detail": "x" * 300_000},
        {"t": 2, "kind": "log", "detail": "evidence-after-oversized-record"},
    ])
    result = tools.inspect_trace(str(path), query="evidence-after-oversized-record")
    assert result["ok"]
    assert result["events"][0]["line"] == 2
    assert len(json.dumps(result)) < 20_000
    assert result["malformed_lines"] >= 1 or result["truncated"]
    path = _trace(run, [{"t": number, "kind": "log", "detail": "d" * 8_000} for number in range(30)])
    result = tools.inspect_trace(str(path), limit=30)
    assert result["ok"] and result["truncated"]
    assert len(json.dumps(result)) < 20_000


def test_cancelled_trace_scan_does_not_claim_complete_evidence(artifact_tools):
    tools, run = artifact_tools
    path = _trace(run, [{"t": 1, "kind": "log", "event": "accepted"}])
    tools.stop = threading.Event()
    tools.stop.set()
    result = tools.inspect_trace(str(path))
    assert not result["ok"]
    assert result["cancelled"]
    assert result["events"] == []
