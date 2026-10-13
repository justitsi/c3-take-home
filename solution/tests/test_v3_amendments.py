"""Small R4 fixes for confirmed R3 review/iteration evidence gaps."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from model import ModelTruncated, ModelUnavailable
from test_v2_guards import guarded_harness, _baseline, _edit
from test_v2_iteration import _assistant


def test_truncated_final_review_retries_tool_free_and_records_real_completion(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    before = (harness.workspace / "src/service.py").read_bytes()
    requests = []

    def complete(messages, tools, **kwargs):
        requests.append(deepcopy(messages))
        if len(requests) < 5:
            return _assistant("read_file", {"path": "src/service.py"}, content="PRIOR_REVIEW_THINKING_NOT_A_FINDING")
        assert tools == []
        if len(requests) == 5:
            raise ModelTruncated("fixture incomplete synthesis; do not apply partial edits")
        assert len(requests) == 6
        assert kwargs["max_tokens"] == 3200
        retry = str(messages[-1].get("content", "")).lower()
        assert "truncated" in retry and ("1000" in retry or "concise" in retry)
        return _assistant(content="COMPLETED_REVIEW_FINDING: cite current source and contract; use a generic ordering counterexample.")

    monkeypatch.setattr(harness.client, "complete", complete)
    finding = harness.review_contracts("Generic current fixture contracts.")
    assert len(requests) == 6
    assert "COMPLETED_REVIEW_FINDING" in finding
    assert "PRIOR_REVIEW_THINKING_NOT_A_FINDING" not in finding
    assert harness.review_complete is True
    assert (harness.workspace / "src/service.py").read_bytes() == before


def test_repeated_truncation_returns_explicit_incomplete_not_prior_utterance(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    calls = []

    def complete(_messages, tools, **_kwargs):
        calls.append(True)
        if len(calls) < 5:
            return _assistant("read_file", {"path": "src/service.py"}, content="I will inspect more source; this is not a completed audit.")
        assert tools == [] and len(calls) <= 6
        raise ModelTruncated("fixture output token limit")

    monkeypatch.setattr(harness.client, "complete", complete)
    assert harness.review_contracts("Generic current fixture contracts.") == ""
    assert len(calls) == 6
    assert harness.review_complete is False
    assert harness.patch_count == 0 and harness.active_snapshot is None


def test_only_actual_tool_free_review_response_is_marked_complete(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    monkeypatch.setattr(harness.client, "complete", lambda *_args, **_kwargs: _assistant(content="No supported fixture concern after the supplied source diff and contracts."))
    finding = harness.review_contracts("Generic fixture review.")
    assert finding and harness.review_complete is True
    assert harness.patch_count == 0


def test_rejected_counterexample_artifact_citations_survive_context_rebuild(guarded_harness):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, _spec: ["I_original"] if values["STATE"] == 0 else ["I_prerequisite"]
    _baseline(harness)
    candidate = _edit(harness, "STATE = 0", "STATE = 1")
    assert not candidate["ok"]
    for row in candidate["checks"]["replays"]:
        trace = Path(row["trace_path"])
        summary = trace.with_name("summary.json")
        summary.write_text(json.dumps({"seed": row["seed"], "violations": row["violations"]}))
        row["trace_artifact"] = "artifacts/" + trace.relative_to(harness.tools.artifacts_root).as_posix()
        row["summary_artifact"] = "artifacts/" + summary.relative_to(harness.tools.artifacts_root).as_posix()
    harness.remember_evidence("apply_edits", {"edits": []}, candidate)
    first = candidate["checks"]["replays"][0]
    evidence = harness.evidence_context()
    fresh = json.dumps(harness.editor_messages("Generic context after rejection.", fresh=True))
    assert first["trace_artifact"] in evidence and first["summary_artifact"] in evidence
    assert first["trace_artifact"] in fresh and first["summary_artifact"] in fresh
    assert "I_prerequisite" in fresh
    assert (harness.workspace / "src/service.py").read_text() == "STATE = 0\nSECOND = 0\n"
    assert harness.patch_count == 0


def test_early_read_only_handoff_preserves_partial_repair_and_passing_guards(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness

    def evaluate(values, spec):
        if spec["scenario"] == "recovery":
            return [] if values["STATE"] <= 1 else ["I_guard"]
        return ["I_original", "I_remaining"] if values["STATE"] == 0 else ["I_remaining"]

    behavior["evaluate"] = evaluate
    _baseline(harness)
    assert harness.replay_tool({"seed": 91, "scenario": "recovery"})["ok"]
    assert _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    before = (harness.workspace / "src/service.py").read_bytes()
    registries = deepcopy((harness.check_specs, harness.check_results, harness.passing_checks))
    harness.editor_phase_limit = 55  # Match run()'s initial phase, not the default direct-edit allowance.
    calls = []

    def complete(_messages, _tools, **_kwargs):
        calls.append(True)
        assert len(calls) <= 12, "read-only diagnosis must hand off within the configured initial inspection allowance"
        return _assistant("read_file", {"path": "src/service.py"}, identifier=f"handoff-read-{len(calls)}")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic remaining fixture symptom.")
    assert len(calls) == 12
    assert harness.stop_reason == "diagnosis-needs-independent-review"
    assert harness.patch_count == 1
    assert (harness.workspace / "src/service.py").read_bytes() == before
    assert (harness.check_specs, harness.check_results, harness.passing_checks) == registries
    assert harness.active_snapshot is None


def _ready_for_audit(harness):
    _baseline(harness)
    assert _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    for seed in harness.probe_seeds:
        assert harness.replay_tool({"seed": seed})["ok"]
    harness.probes_done = True
    harness.issues = {"ticket": {"id": "ticket", "status": "claimed-resolved",
        "evidence": ["src/service.py:1 and all fixture checks"], "revision": harness.patch_count}}


def test_completed_cited_audit_ends_after_last_tool_without_prose_restart(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    _ready_for_audit(harness)
    before = (harness.workspace / "src/service.py").read_bytes()
    calls = []

    def complete(_messages, _tools, **_kwargs):
        calls.append(True)
        if len(calls) == 1:
            return _assistant(content="All fixture checks pass; perform the controller's final audit.")
        assert len(calls) == 2, "a completed audited tools turn must not require another prose completion"
        return _assistant("read_file", {"path": "src/service.py"}, identifier="final-audit-read")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture completion audit.")
    assert len(calls) == 2
    assert harness.stop_reason == "public-and-additional-checks-passed"
    assert harness.restarts == 0 and harness.all_known_verified()
    assert (harness.workspace / "src/service.py").read_bytes() == before


@pytest.mark.parametrize("defect", ["stale", "uncited", "unresolved"])
def test_tool_turn_cannot_finish_with_incomplete_issue_audit(guarded_harness, monkeypatch, defect):
    harness, _, _ = guarded_harness
    _ready_for_audit(harness)
    issue = harness.issues["ticket"]
    if defect == "stale":
        issue["revision"] -= 1
    elif defect == "uncited":
        issue["evidence"] = []
    else:
        issue["status"] = "open"
    calls = []

    def complete(_messages, _tools, **_kwargs):
        calls.append(True)
        if len(calls) == 1:
            return _assistant(content="Public fixture checks pass; audit claims still need verification.")
        if len(calls) == 2:
            return _assistant("read_file", {"path": "src/service.py"})
        raise ModelUnavailable("fixture proves unfinished audit was not certified")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic incomplete fixture audit.")
    assert len(calls) == 3
    assert harness.stop_reason != "public-and-additional-checks-passed"
