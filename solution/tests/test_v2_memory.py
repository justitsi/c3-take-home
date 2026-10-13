"""Independent r2 evidence, compaction, issue-claim, and progress contracts."""

from copy import deepcopy
import json
import os

import pytest

from model import ModelUnavailable
from test_v2_guards import guarded_harness, _baseline
from test_v2_iteration import _assistant
from test_v2_artifacts import artifact_tools, _trace


def _source_fact(marker="SOURCE_FACT_MARKER"):
    return {"ok": True, "path": "src/service.py", "start_line": 1, "end_line": 2,
            "content": f"1: STATE = 0  # {marker}\n2: SECOND = 0", "truncated": False}


def _issue(identifier="symptom-alpha", status="open"):
    return {"id": identifier, "symptom": f"Observable fixture failure {identifier}",
            "hypothesis": "Unverified transition hypothesis", "status": status,
            "evidence": ["src/service.py:1"], "check_specs": [{"seed": 2, "scenario": "public"}]}


@pytest.mark.parametrize("name,args,result", [
    ("read_file", {"path": "src/service.py"}, {"ok": True, "content": ""}),
    ("list_files", {"root": "src"}, {"ok": True, "files": []}),
    ("search", {"query": "no-match"}, {"ok": True, "matches": []}),
    ("inspect_trace", {"path": "artifacts/a/trace.jsonl"}, {"ok": True, "events": [], "matched_events": 0}),
    ("search", {"query": "error"}, {"ok": False, "error": "fixture rejected query"}),
])
def test_empty_or_failed_inspection_is_not_progress(guarded_harness, name, args, result):
    harness, _, _ = guarded_harness
    assert harness.progress_key(name, args, result) is None


def test_same_nonempty_evidence_is_not_novel_because_arguments_or_paths_change(guarded_harness):
    harness, _, _ = guarded_harness
    first = harness.progress_key("read_file", {"path": "src/service.py", "end_line": 160}, _source_fact())
    second = harness.progress_key("read_file", {"path": "src/service.py", "end_line": 400}, _source_fact())
    assert isinstance(first, str) and first == second
    event = {"line": 42, "t": 4, "event": {"kind": "log", "job": "fixture-job", "event": "accepted"}}
    first_result = {"ok": True, "path": "artifacts/run-one/trace.jsonl", "events": [event], "matched_events": 1, "elapsed_s": 0.1}
    second_result = {**first_result, "path": "artifacts/run-two/trace.jsonl", "elapsed_s": 0.9}
    first = harness.progress_key("inspect_trace", {"path": first_result["path"], "query": "fixture-job"}, first_result)
    second = harness.progress_key("inspect_trace", {"path": second_result["path"], "query": "accepted"}, second_result)
    assert isinstance(first, str) and first == second


def test_replay_progress_ignores_trace_paths_and_timing_noise(guarded_harness):
    harness, _, _ = guarded_harness
    spec = {"seed": 2, "scenario": "public"}
    common = {"ok": False, "seed": 2, "spec": spec, "replay_exit": 0, "check_exit": 1,
              "violations": [{"invariant": "I_fixture", "detail": "operation never resolved"}]}
    first = {**common, "trace_path": "/tmp/run-first/trace.jsonl", "summary_path": "/tmp/run-first/summary.json", "elapsed_s": 0.2,
             "output": "trace written to /tmp/run-first; wall_s=0.2"}
    second = {**common, "trace_path": "/tmp/run-second/trace.jsonl", "summary_path": "/tmp/run-second/summary.json", "elapsed_s": 0.9,
              "output": "trace written to /tmp/run-second; wall_s=0.9"}
    first_key = harness.progress_key("replay_check", spec, first)
    second_key = harness.progress_key("replay_check", spec, second)
    assert isinstance(first_key, str) and first_key == second_key


def test_fresh_diagnosis_preserves_cited_facts_and_ledger_but_omits_specialist_hypotheses(guarded_harness):
    harness, _, _ = guarded_harness
    _baseline(harness)
    harness.findings = [{"agent": "fixture-specialist", "finding": "UNSUPPORTED_SPECIALIST_ANCHOR"}]
    harness.remember_evidence("read_file", {"path": "src/service.py"}, _source_fact())
    harness.update_issues([_issue()])
    before = (harness.workspace / "src/service.py").read_bytes()
    normal = json.dumps(harness.editor_messages("Generic fixture context."))
    fresh = json.dumps(harness.editor_messages("Generic fixture context.", fresh=True))
    assert "UNSUPPORTED_SPECIALIST_ANCHOR" in normal
    assert "UNSUPPORTED_SPECIALIST_ANCHOR" not in fresh
    assert "Unverified transition hypothesis" in normal
    assert "Unverified transition hypothesis" not in fresh
    assert "SOURCE_FACT_MARKER" in fresh and "src/service.py" in fresh
    assert "symptom-alpha" in fresh
    assert "I_original" in fresh
    assert (harness.workspace / "src/service.py").read_bytes() == before


def test_context_compaction_keeps_facts_and_hypotheses_without_becoming_diagnosis_restart(guarded_harness, monkeypatch, capsys):
    harness, _, _ = guarded_harness
    _baseline(harness)
    harness.findings = [{"agent": "fixture-specialist", "finding": "COMPACTION_SPECIALIST_MARKER"}]
    harness.update_issues([_issue("compaction-issue")])
    calls = []

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        if len(calls) == 1:
            return _assistant("read_file", {"path": "src/service.py"},
                              content="DISCARD_RAW_TRANSCRIPT_MARKER" + "x" * 190_000,
                              identifier="fact-before-compaction")
        text = json.dumps(messages)
        assert "DISCARD_RAW_TRANSCRIPT_MARKER" not in text
        assert "COMPACTION_SPECIALIST_MARKER" in text
        assert "compaction-issue" in text
        assert "src/service.py" in text and "STATE = 0" in text
        raise ModelUnavailable("fixture compaction verified")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic long-context fixture.")
    assert len(calls) == 2
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert any(event["event"] == "context_compaction" for event in events)
    assert not any(event["event"] == "diagnosis_restart" for event in events)


def test_varying_empty_queries_trigger_fresh_diagnosis_without_forgetting_evidence(guarded_harness, monkeypatch, capsys):
    harness, _, _ = guarded_harness
    _baseline(harness)
    harness.findings = [{"agent": "fixture-specialist", "finding": "DROP_ON_TRUE_STAGNATION"}]
    harness.remember_evidence("read_file", {"path": "src/service.py"}, _source_fact("KEEP_VERIFIABLE_FACT"))
    harness.update_issues([_issue("stagnant-issue")])
    monkeypatch.setattr(harness.tools, "search", lambda query, **_: {"ok": True, "matches": [], "query": query})
    calls = []
    restarted = []

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        assert len(calls) <= 8, "new query arguments must not disguise empty-result stagnation"
        text = json.dumps(messages)
        if len(calls) > 3 and "DROP_ON_TRUE_STAGNATION" not in text:
            assert "KEEP_VERIFIABLE_FACT" in text
            assert "stagnant-issue" in text
            restarted.append(True)
            raise ModelUnavailable("fixture restart verified")
        return _assistant("search", {"query": f"different-empty-query-{len(calls)}"}, identifier=f"empty-{len(calls)}")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic zero-match fixture.")
    assert restarted == [True]
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert any(event["event"] == "diagnosis_restart" for event in events)
    assert not any(event["event"] == "context_compaction" for event in events)
    assert harness.patch_count == 0


def test_source_facts_are_not_presented_as_current_after_revision_change(guarded_harness):
    harness, _, _ = guarded_harness
    harness.remember_evidence("read_file", {"path": "src/service.py"}, _source_fact("OLD_SOURCE_FACT"))
    harness.remember_evidence("read_file", {"path": "corpus/platform/contract.md"}, {
        "ok": True, "path": "corpus/platform/contract.md", "start_line": 9, "end_line": 9,
        "content": "9: CURRENT_CONTRACT_FACT", "truncated": False,
    })
    harness.remember_evidence("inspect_trace", {"path": "artifacts/replay/trace.jsonl"}, {
        "ok": True, "path": "artifacts/replay/trace.jsonl", "events": [
            {"line": 37, "t": 4, "event": {"kind": "log", "event": "HISTORICAL_TRACE_FACT"}}],
    })
    harness.patch_count += 1
    (harness.workspace / "src/service.py").write_text("STATE = 1\nSECOND = 0\n")
    context = harness.evidence_context()
    assert "CURRENT_CONTRACT_FACT" in context
    assert "HISTORICAL_TRACE_FACT" in context and "37" in context
    assert "OLD_SOURCE_FACT" not in context or "historical" in context.lower() or "stale" in context.lower()


def test_rereading_unchanged_source_refreshes_provenance_without_inventing_progress(guarded_harness):
    harness, _, _ = guarded_harness
    args, fact = {"path": "src/service.py"}, _source_fact("RECHECKED_SOURCE_FACT")
    before_key = harness.progress_key("read_file", args, fact)
    harness.remember_evidence("read_file", args, fact)
    # An accepted change in another file advances the case revision.
    (harness.workspace / "src/other.py").write_text("UNRELATED_REPAIR = True\n")
    harness.patch_count += 1
    harness.remember_evidence("read_file", args, fact)
    context = json.loads(harness.evidence_context())
    row = next(row for row in context["observations"] if "RECHECKED_SOURCE_FACT" in row["data"])
    assert row["source_revision"] == harness.patch_count
    assert row["observed_revision"] == harness.patch_count
    assert not row["historical"]
    assert harness.progress_key("read_file", args, fact) == before_key


def test_issue_resolution_claim_cannot_override_unresolved_checks(guarded_harness):
    harness, _, _ = guarded_harness
    _baseline(harness)
    checks_before = deepcopy(harness.check_results)
    passes_before = set(harness.passing_checks)
    harness.update_issues([_issue("issue-a", "resolved"), _issue("issue-b", "open")])
    rendered = harness.issue_context()
    assert "issue-a" in rendered and "issue-b" in rendered
    assert "revision" in rendered.lower()
    assert not harness.all_known_verified()
    assert harness.check_results == checks_before
    assert harness.passing_checks == passes_before


def test_evidence_and_issue_memory_are_bounded_and_redacted(guarded_harness):
    harness, _, _ = guarded_harness
    secret = os.environ["OPENAI_API_KEY"]
    for number in range(80):
        harness.remember_evidence("read_file", {"path": f"src/module-{number}.py"}, {
            "ok": True, "path": f"src/module-{number}.py", "start_line": 1, "end_line": 2,
            "content": f"1: bounded evidence {number} {secret}\n2: " + "x" * 10_000,
        })
    issues = [_issue(f"bounded-issue-{number}") for number in range(8)]
    for issue in issues:
        issue["hypothesis"] = secret + "x" * 10_000
    harness.update_issues(issues)
    facts = harness.evidence_context()
    ledger = harness.issue_context()
    # Keep rebuilt context comfortably below the overall compaction threshold.
    assert len(facts) < 40_000
    assert len(ledger) < 20_000
    assert secret not in facts and secret not in ledger


def test_term_query_results_keep_same_record_and_pagination_provenance(artifact_tools):
    tools, run = artifact_tools
    path = _trace(run, [
        {"t": 1, "kind": "log", "job": "alpha", "event": "accepted"},
        {"t": 2, "kind": "log", "job": "beta", "event": "committed"},
        {"t": 3, "kind": "log", "job": "alpha", "event": "committed"},
        {"t": 4, "kind": "log", "job": "alpha", "event": "committed"},
    ])
    first = tools.inspect_trace(str(path), all_terms=["alpha", "committed"], limit=1)
    assert first["ok"] and first["events"][0]["line"] == 3
    assert first["returned_events"] == 1 and first["next_line"] == 4
    second = tools.inspect_trace(str(path), all_terms=["alpha", "committed"], start_line=first["next_line"], limit=1)
    assert second["ok"] and second["events"][0]["line"] == 4
    assert second["returned_time_range"] == [4, 4]


def test_final_investigator_call_requires_actual_tool_free_findings(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    harness.investigation_until = harness.deadline
    before = (harness.workspace / "src/service.py").read_bytes()
    requests = []

    def complete(messages, tools, **kwargs):
        requests.append(deepcopy(tools))
        if len(requests) < 6:
            assert any(tool["function"]["name"] == "read_file" for tool in tools)
            assert all(tool["function"]["name"] != "apply_edits" for tool in tools)
            return _assistant("read_file", {"path": "src/service.py"}, identifier=f"specialist-read-{len(requests)}")
        assert tools == [], "last specialist call must enforce synthesis, not merely request it in prose"
        return _assistant(content="FINAL_EVIDENCED_FINDING_MARKER: source service.py line 1; verify via original seed.")

    monkeypatch.setattr(harness.client, "complete", complete)
    result = harness.investigate(("independent-fixture", "Generic durability evidence"), "Generic case context.")
    assert len(requests) == 6
    assert "FINAL_EVIDENCED_FINDING_MARKER" in result["finding"]
    assert (harness.workspace / "src/service.py").read_bytes() == before


def test_full_bounded_trace_metadata_reaches_next_model_turn_unclipped(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    _baseline(harness)
    payload = {"ok": True, "path": "artifacts/fixture/trace.jsonl", "events": [
        {"line": number + 1, "t": number, "event": {"kind": "log", "detail": "v" * 700}}
        for number in range(20)], "truncated": True, "next_line": 21,
        "returned_events": 20, "returned_time_range": [0, 19], "scan_limit_reached": False}
    assert 13_000 < len(json.dumps(payload)) < 18_000
    monkeypatch.setattr(harness.tools, "inspect_trace", lambda **_: deepcopy(payload))
    calls = []

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        if len(calls) == 1:
            return _assistant("inspect_trace", {"path": payload["path"]}, identifier="paginated-trace-read")
        tool = next(message for message in messages if message.get("tool_call_id") == "paginated-trace-read")
        delivered = json.loads(tool["content"])
        assert delivered["next_line"] == 21
        assert delivered["returned_events"] == 20
        assert delivered["returned_time_range"] == [0, 19]
        assert delivered["scan_limit_reached"] is False
        assert len(delivered["events"]) == 20
        raise ModelUnavailable("fixture full trace transport verified")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic pagination metadata transport fixture.")
    assert len(calls) == 2
