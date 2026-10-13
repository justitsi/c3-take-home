"""Independent authored-counterexample and skeptical-review integration tests."""

from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

import fix as harness_module
import model as model_module
from test_probes import BASE
from test_v2_guards import guarded_harness, _baseline
from test_v2_iteration import _assistant


def _provided_probe(harness):
    (harness.workspace / "scenarios/public.yaml").write_text(BASE)
    (harness.workspace / "scenarios/faults/calm.yaml").write_text("network: {drop: 0}\n")
    result = harness.tools.create_probe(overrides={}, name="generic-ordering", seed=77)
    assert result["ok"], result
    return result


def _tamper(probe):
    path = Path(probe["scenario_path"])
    path.chmod(0o644)
    path.write_text(path.read_text().replace('"seed": 77', '"seed": 78'))


def test_authored_alias_and_path_share_one_canonical_guard_identity(guarded_harness):
    harness, behavior, calls = guarded_harness
    behavior["evaluate"] = lambda _values, _spec: []
    _baseline(harness)
    probe = _provided_probe(harness)
    first = harness.replay_tool({"seed": 77, "scenario": probe["scenario_artifact"]})
    second = harness.replay_tool({"seed": 77, "scenario": probe["scenario_path"]})
    assert first["ok"] and second["ok"]
    key = harness_module.check_key({"seed": 77, "scenario": probe["scenario_path"]})
    assert key in harness.check_specs and key in harness.passing_checks
    assert all(call["scenario"] == probe["scenario_path"] for call in calls[-2:])
    assert sum(spec["scenario"] == probe["scenario_path"] for spec in harness.required_specs()) == 1
    checks = harness.checks(harness.seeds, repeat=True)
    harness.extra_checks(checks)
    authored = [row for row in checks["replays"] if row["spec"]["scenario"] == probe["scenario_path"]]
    assert len(authored) == 1 and authored[0]["ok"]
    assert harness.coverage_complete(checks)


def test_create_probe_dispatch_immediately_replays_and_registers_its_counterexample(guarded_harness):
    harness, _, calls = guarded_harness
    (harness.workspace / "scenarios/public.yaml").write_text(BASE)
    (harness.workspace / "scenarios/faults/calm.yaml").write_text("network: {drop: 0}\n")
    result = harness.dispatch("create_probe", {"overrides": {}, "name": "generic-probe", "seed": 78})
    assert result["ok"] is False  # The fixture's original invariant must not be hidden by successful authoring.
    assert result["replay_exit"] == 0 and result["check_exit"] == 1
    assert len(calls) == 1 and calls[0]["scenario"] == result["scenario_path"]
    key = harness_module.check_key({"seed": 78, "scenario": result["scenario_path"]})
    assert key in harness.check_specs and not harness.check_results[key]["ok"]
    assert result["probe_sha256"] == harness.tools.authored_probes[result["scenario_artifact"]]["sha256"]


@pytest.mark.parametrize("entrypoint", ["replay", "extra-checks"])
def test_tampered_authored_probe_is_not_replayed_or_forgotten(guarded_harness, entrypoint):
    harness, behavior, calls = guarded_harness
    behavior["evaluate"] = lambda _values, _spec: []
    _baseline(harness)
    probe = _provided_probe(harness)
    assert harness.replay_tool({"seed": 77, "scenario": probe["scenario_artifact"]})["ok"]
    key = harness_module.check_key({"seed": 77, "scenario": probe["scenario_path"]})
    prior_specs, prior_passes = deepcopy(harness.check_specs), set(harness.passing_checks)
    checks = harness.checks(harness.seeds, repeat=True)
    calls.clear()
    _tamper(probe)
    try:
        if entrypoint == "replay":
            result = harness.replay_tool({"seed": 77, "scenario": probe["scenario_artifact"]})
            assert not result["ok"] and result.get("error")
        else:
            harness.extra_checks(checks)
            assert not harness.coverage_complete(checks)
            failed = [row for row in checks["replays"] if row.get("spec", {}).get("scenario") == probe["scenario_path"]]
            assert failed and all(not row["ok"] for row in failed)
    except ValueError as error:
        assert "changed" in str(error) or "immutable" in str(error) or "hash" in str(error)
    assert calls == [], "tampered scenario content must not reach the replay process"
    assert harness.check_specs == prior_specs
    assert harness.passing_checks == prior_passes and key in harness.passing_checks


def test_contract_reviewer_is_fresh_read_only_and_final_call_is_tool_free(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    harness.findings = [{"agent": "fixture", "finding": "DO_NOT_ANCHOR_REVIEW_SPECIALIST"}]
    source = harness.workspace / "src/service.py"
    before = source.read_bytes()
    requests = []

    def complete(messages, tools, **_kwargs):
        requests.append(deepcopy(messages))
        assert "DO_NOT_ANCHOR_REVIEW_SPECIALIST" not in json.dumps(messages)
        if len(requests) < 5:
            names = {tool["function"]["name"] for tool in tools}
            assert "source_diff" in names
            assert names.isdisjoint({"apply_edits", "create_probe", "update_issues"})
            if len(requests) > 1:
                delivered = next(message for message in reversed(messages) if message["role"] == "tool")
                assert json.loads(delivered["content"])["ok"]
            return _assistant("source_diff", identifier=f"review-diff-{len(requests)}")
        assert tools == []
        return _assistant(content="INDEPENDENT_CONTRACT_CONCERN: cite service.py and a generic allowed-fault ordering probe.")

    monkeypatch.setattr(harness.client, "complete", complete)
    finding = harness.review_contracts("Generic fixture contract text.")
    assert len(requests) == 5
    assert "INDEPENDENT_CONTRACT_CONCERN" in finding
    assert source.read_bytes() == before
    assert not harness.tools.authored_probes


@pytest.mark.parametrize("name,args", [
    ("apply_edits", {"edits": [{"path": "src/service.py", "old": "STATE = 0", "new": "STATE = 9"}]}),
    ("create_probe", {"overrides": {}}),
])
def test_review_rejects_mutating_tools_even_if_model_ignores_schema(guarded_harness, monkeypatch, name, args):
    harness, _, _ = guarded_harness
    before = (harness.workspace / "src/service.py").read_bytes()
    calls = []

    def complete(messages, _tools, **_kwargs):
        calls.append(True)
        if len(calls) == 1:
            return _assistant(name, args, identifier="untrusted-review-mutation")
        result = next(message for message in messages if message.get("tool_call_id") == "untrusted-review-mutation")
        assert not json.loads(result["content"])["ok"]
        return _assistant(content="Mutation was denied; no supported fixture concern.")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.review_contracts("Generic review context.")
    assert len(calls) == 2
    assert (harness.workspace / "src/service.py").read_bytes() == before
    assert not harness.tools.authored_probes


def test_review_findings_reopen_editor_with_normal_final_reserve(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    normal_reserve = harness.reserve_s
    phases = []
    marker = "REVIEW_TO_SECOND_EDITOR_MARKER"
    monkeypatch.setattr(harness_module, "build_context", lambda *_args, **_kwargs: "Generic fixture context.")
    monkeypatch.setattr(harness_module.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(harness, "investigate", lambda profile, _context: {"agent": profile[0], "finding": "Generic fixture finding."})

    def edit(context):
        phases.append((harness.reserve_s, json.dumps(harness.editor_messages(context))))

    def review(_context):
        assert harness.reserve_s == normal_reserve
        return marker

    monkeypatch.setattr(harness, "edit", edit)
    monkeypatch.setattr(harness, "review_contracts", review)
    assert harness.run() == 0
    assert len(phases) == 2
    assert phases[0][0] >= normal_reserve + 130
    assert phases[1][0] == normal_reserve
    assert marker not in phases[0][1] and marker in phases[1][1]
    assert harness.contract_review == marker
    assert harness.finished.is_set()


def test_editor_round_ceiling_is_shared_across_review_phases(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    _baseline(harness)
    harness.editor_rounds = 79
    calls = []

    def complete(_messages, _tools, **_kwargs):
        calls.append(True)
        return _assistant("read_file", {"path": "src/service.py"})

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("First editor phase.")
    harness.contract_review = "A supported concern requires follow-up within the same budget."
    harness.edit("Second editor phase.")
    assert calls == [True]
    assert harness.editor_rounds == 80


@pytest.mark.parametrize("resource", ["deadline", "cancelled", "budget"])
def test_review_respects_stop_deadline_and_shared_model_budget(guarded_harness, monkeypatch, resource):
    harness, _, _ = guarded_harness
    if resource == "deadline":
        harness.deadline = time.time() + harness.reserve_s + 20
    elif resource == "cancelled":
        harness.stop.set()
    else:
        harness.budget.spent = harness.budget.limit
    monkeypatch.setattr(model_module.urllib.request, "urlopen", lambda *_args, **_kwargs: pytest.fail("resource-exhausted review must not issue HTTP"))
    assert harness.review_contracts("Generic bounded review.") == ""
    assert harness.patch_count == 0
