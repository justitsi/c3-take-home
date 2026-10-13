"""Behavioral regression guards and rollback using generic simulated contracts."""

import ast
from copy import deepcopy
from itertools import count
import json
from pathlib import Path
import time

import pytest

import fix as harness_module
from fix import Harness


@pytest.fixture
def guarded_harness(tmp_path, monkeypatch):
    workspace, corpus = tmp_path / "workspace", tmp_path / "corpus"
    (workspace / "src").mkdir(parents=True)
    (workspace / "scenarios/faults").mkdir(parents=True)
    corpus.mkdir()
    (workspace / "src/service.py").write_text("STATE = 0\nSECOND = 0\n")
    (workspace / "case.json").write_text(json.dumps({"public_seeds": [2, 5, 9, 12]}))
    (workspace / "scenarios/recovery.yaml").write_text("name: recovery\n")
    for name in ("drop", "clocks"):
        (workspace / f"scenarios/faults/{name}.yaml").write_text("network: {}\n")
    for name, value in {
        "C3_WORKSPACE": workspace, "C3_CORPUS": corpus,
        "C3_DEADLINE": time.time() + 900, "C3_BUDGET_USD": 9,
        "OPENAI_BASE_URL": "http://fixture.invalid/v1", "OPENAI_API_KEY": "fixture-token",
        "ANTHROPIC_MODEL": "anthropic/claude-sonnet-4.6",
    }.items():
        monkeypatch.setenv(name, str(value))
    harness = Harness()
    calls = []
    artifact_sequence = count(1)
    behavior = {"evaluate": lambda values, spec: [] if values["STATE"] == 1 else ["I_original"]}

    def replay(seed, scenario="public", faults=None, timeout_s=40):
        source = workspace / "src/service.py"
        values = {node.targets[0].id: ast.literal_eval(node.value)
                  for node in ast.parse(source.read_text()).body if isinstance(node, ast.Assign)}
        spec = {"seed": int(seed), "scenario": scenario, "faults": faults}
        calls.append(deepcopy(spec))
        invariants = behavior["evaluate"](values, spec)
        directory = harness.scratch / "artifacts" / f"fixture-{next(artifact_sequence)}"
        directory.mkdir(parents=True)
        trace = directory / "trace.jsonl"
        trace.write_text(json.dumps({"spec": spec, "source": source.read_text()}, sort_keys=True) + "\n")
        violations = [{"invariant": inv, "detail": f"fixture {inv}"} for inv in invariants]
        return {"ok": not violations, "seed": int(seed), "spec": spec,
                "replay_exit": 0, "check_exit": 1 if violations else 0,
                "violations": violations, "violation_count": len(violations),
                "trace_path": str(trace), "summary": {}, "output": "fixture replay/check",
                "elapsed_s": 0.001, "timed_out": False, "cancelled": False}

    monkeypatch.setattr(harness.validation, "compile_source", lambda: {"ok": True, "elapsed_s": 0.001})
    monkeypatch.setattr(harness.validation, "run_tests", lambda **_: {"ok": True, "elapsed_s": 0.001})
    monkeypatch.setattr(harness.validation, "replay_check", replay)
    return harness, behavior, calls


def _baseline(harness):
    harness.baseline = harness.checks(harness.seeds)
    for result in harness.baseline["replays"]:
        harness.observe_check(result)


def _edit(harness, old, new, second=None):
    edits = [{"path": "src/service.py", "old": old, "new": new}]
    if second is not None:
        edits.append({"path": "src/service.py", "old": second[0], "new": second[1]})
    return harness.apply_candidate({"edits": edits})


def test_all_configured_public_seeds_are_retained(guarded_harness):
    harness, _, _ = guarded_harness
    assert harness.seeds == [2, 5, 9, 12]


def test_check_identity_distinguishes_scenario_and_fault_profile():
    key = harness_module.check_key
    assert key({"seed": 7}) == key({"seed": 7, "scenario": "public", "faults": None})
    identities = [
        {"seed": 7},
        {"seed": 7, "scenario": "recovery"},
        {"seed": 7, "scenario": "recovery", "faults": "scenarios/faults/drop.yaml"},
        {"seed": 7, "scenario": "recovery", "faults": "scenarios/faults/clocks.yaml"},
        {"seed": 8},
    ]
    assert len({key(spec) for spec in identities}) == len(identities)


def test_observing_same_seed_in_other_scenario_does_not_overwrite_pass(guarded_harness):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, spec: [] if spec["scenario"] == "recovery" else ["I_original"]
    passed = harness.validation.replay_check(7, scenario="recovery")
    failed = harness.validation.replay_check(7)
    harness.observe_check(passed)
    harness.observe_check(failed)
    passed_key = harness_module.check_key(passed["spec"])
    failed_key = harness_module.check_key(failed["spec"])
    assert passed_key in harness.passing_checks
    assert failed_key not in harness.passing_checks
    assert harness.check_results[passed_key]["ok"]
    assert not harness.check_results[failed_key]["ok"]


@pytest.mark.parametrize("args", [
    {"seed": 17, "scenario": "typo-scenario-does-not-exist"},
    {"seed": 17, "faults": "scenarios/faults/missing.yaml"},
])
def test_invalid_probe_paths_do_not_poison_registry_or_launch_replay(guarded_harness, args):
    harness, _, calls = guarded_harness
    _baseline(harness)
    before = deepcopy(harness.check_specs)
    calls.clear()
    result = harness.replay_tool(args)
    assert not result["ok"]
    assert result.get("error")
    assert harness.check_specs == before
    assert calls == []


@pytest.mark.parametrize("exit_code,expected_registered", [(2, False), (3, True)])
def test_configuration_errors_and_genuine_runtime_failures_are_distinguished(guarded_harness, monkeypatch, exit_code, expected_registered):
    harness, _, _ = guarded_harness
    spec = {"seed": 17, "scenario": "recovery"}
    key = harness_module.check_key(spec)
    monkeypatch.setattr(harness.validation, "replay_check", lambda **_: {
        "ok": False, "seed": 17, "spec": spec, "replay_exit": exit_code, "check_exit": None,
        "violations": [], "output": "fixture configuration error" if exit_code == 2 else "fixture runtime failure",
        "timed_out": False, "cancelled": False,
    })
    result = harness.replay_tool(spec)
    assert not result["ok"]
    assert (key in harness.check_specs) is expected_registered
    if expected_registered:
        assert harness.check_results[key]["replay_exit"] == 3
        assert key not in harness.passing_checks
    else:
        assert result.get("error")


def test_configuration_error_cannot_forget_a_previously_passing_probe(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, spec: []
    spec = {"seed": 17, "scenario": "recovery"}
    key = harness_module.check_key(spec)
    assert harness.replay_tool(spec)["ok"]
    monkeypatch.setattr(harness.validation, "replay_check", lambda **_: {
        "ok": False, "seed": 17, "spec": spec, "replay_exit": 2, "check_exit": None,
        "violations": [], "output": "fixture transient configuration error",
        "timed_out": False, "cancelled": False,
    })
    assert not harness.replay_tool(spec)["ok"]
    assert key in harness.check_specs and key in harness.passing_checks


def test_ad_hoc_passing_scenario_is_guarded_against_later_public_improvement(guarded_harness):
    harness, behavior, calls = guarded_harness

    def evaluate(values, spec):
        if spec["scenario"] == "recovery":
            return [] if values["STATE"] == 0 else ["I_recovery"]
        return [] if values["STATE"] == 1 else ["I_original"]

    behavior["evaluate"] = evaluate
    _baseline(harness)
    spec = {"seed": 91, "scenario": "recovery", "faults": "scenarios/faults/drop.yaml"}
    assert harness.replay_tool(spec)["ok"]
    guard = harness_module.check_key(spec)
    assert guard in harness.passing_checks
    before = (harness.workspace / "src/service.py").read_bytes()
    calls.clear()
    candidate = _edit(harness, "STATE = 0", "STATE = 1")
    assert not candidate["ok"]
    assert guard in {harness_module.check_key(spec) for spec in calls}
    assert guard in harness.passing_checks
    assert (harness.workspace / "src/service.py").read_bytes() == before
    assert harness.patch_count == 0


def test_failed_candidate_cannot_poison_retained_guard_registry(guarded_harness):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, spec: (["I_new"] if spec["seed"] == 12 else []) if values["STATE"] == 1 else ["I_original"]
    _baseline(harness)
    previous_results = deepcopy(harness.check_results)
    previous_passes = set(harness.passing_checks)
    assert not _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    assert harness.check_results == previous_results
    assert harness.passing_checks == previous_passes
    assert "STATE = 0" in (harness.workspace / "src/service.py").read_text()


def test_prerequisite_rejection_allows_coherent_combined_retry(guarded_harness):
    harness, behavior, _ = guarded_harness

    def evaluate(values, spec):
        if values["STATE"] == 0:
            return ["I_original"]
        return [] if values["SECOND"] == 1 else ["I_followup"]

    behavior["evaluate"] = evaluate
    _baseline(harness)
    original = (harness.workspace / "src/service.py").read_bytes()
    first = _edit(harness, "STATE = 0", "STATE = 1")
    assert not first["ok"]
    assert (harness.workspace / "src/service.py").read_bytes() == original
    combined = _edit(harness, "STATE = 0", "STATE = 1", ("SECOND = 0", "SECOND = 1"))
    assert combined["ok"]
    assert harness.patch_count == 1
    assert all(result["ok"] for result in harness.check_results.values())


def test_later_rejected_candidate_preserves_earlier_supported_partial_repair(guarded_harness):
    harness, behavior, _ = guarded_harness

    def evaluate(values, spec):
        if values["STATE"] == 0:
            return ["I_original", "I_remaining"]
        if values["SECOND"] == 0:
            return ["I_remaining"]
        return [] if values["STATE"] == 2 else ["I_new"]

    behavior["evaluate"] = evaluate
    _baseline(harness)
    assert _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    supported = (harness.workspace / "src/service.py").read_bytes()
    assert not _edit(harness, "SECOND = 0", "SECOND = 1")["ok"]
    assert (harness.workspace / "src/service.py").read_bytes() == supported
    assert harness.patch_count == 1
    assert _edit(harness, "STATE = 1", "STATE = 2", ("SECOND = 0", "SECOND = 1"))["ok"]
    assert harness.patch_count == 2


def test_missing_extra_guard_cannot_be_mistaken_for_complete_candidate(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    _baseline(harness)
    behavior["evaluate"] = lambda values, spec: []
    spec = {"seed": 91, "scenario": "recovery"}
    harness.observe_check(harness.validation.replay_check(**spec), spec)
    actual_checks = harness.checks

    def omit_extra(*args, **kwargs):
        result = actual_checks(*args, **kwargs)
        result["replays"] = [record for record in result["replays"] if record["spec"]["seed"] != 91]
        return result

    monkeypatch.setattr(harness, "checks", omit_extra)
    monkeypatch.setattr(harness, "extra_checks", lambda *_args, **_kwargs: None)
    before = (harness.workspace / "src/service.py").read_bytes()
    result = _edit(harness, "STATE = 0", "STATE = 1")
    assert not result["ok"]
    assert (harness.workspace / "src/service.py").read_bytes() == before


def test_final_validation_automatically_covers_public_and_extra_checks(guarded_harness):
    harness, behavior, calls = guarded_harness
    behavior["evaluate"] = lambda values, spec: []
    spec = {"seed": 91, "scenario": "recovery", "faults": "scenarios/faults/drop.yaml"}
    harness.observe_check(harness.validation.replay_check(**spec), spec)
    calls.clear()
    result = harness.final_validation()
    observed = {harness_module.check_key(spec) for spec in calls}
    required = {harness_module.check_key({"seed": seed}) for seed in (2, 5, 9, 12)}
    assert observed >= required | {harness_module.check_key(spec)}
    assert result["coverage_complete"]
    assert result["all_passed"]


def test_interrupted_final_coverage_is_reported_as_incomplete(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, spec: []
    actual_replay = harness.validation.replay_check

    def cancel_during_sweep(*args, **kwargs):
        result = actual_replay(*args, **kwargs)
        harness.stop.set()
        return result

    monkeypatch.setattr(harness.validation, "replay_check", cancel_during_sweep)
    result = harness.final_validation()
    assert not result["coverage_complete"]
    assert not result["all_passed"]
    assert (harness.workspace / "src/service.py").read_text() == "STATE = 0\nSECOND = 0\n"


def test_final_regression_restores_previous_supported_candidate_and_rechecks(guarded_harness):
    harness, behavior, calls = guarded_harness
    _baseline(harness)
    assert _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    supported = (harness.workspace / "src/service.py").read_bytes()
    behavior["evaluate"] = lambda values, spec: [] if values["STATE"] in (1, 2) else ["I_original"]
    assert _edit(harness, "STATE = 1", "STATE = 2")["ok"]
    # A broad final check exposes a latent failure in the newest candidate.
    behavior["evaluate"] = lambda values, spec: [] if values["STATE"] == 1 else ["I_new"]
    calls.clear()
    result = harness.final_validation()
    assert result["restored"]
    assert (harness.workspace / "src/service.py").read_bytes() == supported
    assert result["coverage_complete"]
    assert result["all_passed"]
    assert len(calls) >= 5  # Detect a regression, then recheck all four restored seeds.


def test_final_rollback_does_not_forget_later_discovered_scenario_guard(guarded_harness):
    harness, behavior, calls = guarded_harness
    _baseline(harness)
    assert _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    behavior["evaluate"] = lambda values, spec: [] if values["STATE"] in (1, 2) else ["I_original"]
    assert _edit(harness, "STATE = 1", "STATE = 2")["ok"]
    extra = {"seed": 91, "scenario": "recovery", "faults": "scenarios/faults/drop.yaml"}
    assert harness.replay_tool(extra)["ok"]
    key = harness_module.check_key(extra)
    assert key in harness.passing_checks
    behavior["evaluate"] = lambda values, spec: (["I_new"] if values["STATE"] == 2 and spec["scenario"] == "public" else [])
    calls.clear()
    result = harness.final_validation()
    assert result["restored"] and result["all_passed"]
    assert key in harness.check_specs and key in harness.passing_checks
    assert harness.check_results[key]["ok"]
    assert sum(harness_module.check_key(spec) == key for spec in calls) >= 2


@pytest.mark.parametrize("stop", ["cancelled", "deadline"])
def test_stop_conditions_prevent_new_source_candidates(guarded_harness, stop):
    harness, _, _ = guarded_harness
    before = (harness.workspace / "src/service.py").read_bytes()
    if stop == "cancelled":
        harness.stop.set()
    else:
        harness.deadline = time.time() + 1
    assert not _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    assert (harness.workspace / "src/service.py").read_bytes() == before
    assert harness.active_snapshot is None
