"""Independent repair-loop tests with deterministic fake model responses."""

from copy import deepcopy
import json
import time

import pytest

import model as model_module
from model import ModelUnavailable
from test_v2_guards import guarded_harness, _baseline, _edit


def _assistant(name=None, args=None, content="", identifier="fixture-call"):
    response = {"role": "assistant", "content": content, "finish_reason": "tool_calls" if name else "stop"}
    if name:
        response["tool_calls"] = [{"id": identifier, "type": "function", "function": {
            "name": name, "arguments": json.dumps(args or {}),
        }}]
    return response


def _patch(old, new):
    return {"edits": [{"path": "src/service.py", "old": old, "new": new}]}


def test_useful_repairs_continue_beyond_v1_fourteen_round_limit(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, spec: [f"I_component_{number}" for number in range(values["STATE"], 16)]
    _baseline(harness)
    calls = []

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        assert len(calls) < 30, "completed fixture must not spin indefinitely"
        if len(calls) <= 16:
            before = len(calls) - 1
            return _assistant("apply_edits", _patch(f"STATE = {before}\n", f"STATE = {before + 1}\n"),
                              content=f"Repair independently verified component {before}.",
                              identifier=f"component-{before}")
        return _assistant(content="All fixture components repaired; review coverage.")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture with sixteen independent failing components.")
    assert len(calls) >= 16
    assert harness.patch_count == 16
    assert "STATE = 16\n" in (harness.workspace / "src/service.py").read_text()
    assert all(result["ok"] for result in harness.check_results.values())


def test_two_unsupported_completion_claims_do_not_end_known_failing_case(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    _baseline(harness)
    calls = []

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        assert len(calls) < 15
        if len(calls) <= 2:
            return _assistant(content="Everything is complete.")
        if len(calls) == 3:
            return _assistant("apply_edits", _patch("STATE = 0", "STATE = 1"), identifier="actual-repair")
        return _assistant(content="Fixture is checked and complete.")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture with an unresolved original invariant.")
    assert len(calls) >= 3
    assert harness.patch_count == 1
    assert "STATE = 1" in (harness.workspace / "src/service.py").read_text()


def test_fresh_diagnosis_drops_stale_model_anchor_but_preserves_validated_source(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, spec: (["I_original", "I_remaining"] if values["STATE"] == 0 else
                                              ([] if values["SECOND"] == 1 else ["I_remaining"]))
    _baseline(harness)
    anchor = "DISCARDED_HYPOTHESIS_ANCHOR_4b31"
    calls = []
    restarted = []
    patched = False

    def complete(messages, tools, **kwargs):
        nonlocal patched
        calls.append(deepcopy(messages))
        assert len(calls) < 25, "fixture must restart instead of repeating forever"
        if len(calls) == 1:
            return _assistant("apply_edits", _patch("STATE = 0", "STATE = 1"), content=anchor,
                              identifier="supported-first-repair")
        flattened = json.dumps(messages)
        if len(calls) > 3 and anchor not in flattened and not patched:
            assert "STATE = 1" in (harness.workspace / "src/service.py").read_text()
            restarted.append(deepcopy(messages))
            patched = True
            return _assistant("apply_edits", _patch("SECOND = 0", "SECOND = 1"), identifier="independent-followup")
        if patched:
            return _assistant(content="Both generic repairs are checked.")
        return _assistant("read_file", {"path": "src/service.py"}, content="Repeat unchanged evidence.",
                          identifier=f"stagnant-read-{len(calls)}")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture; preserve earlier supported repairs during independent diagnosis.")
    assert restarted, "stagnation must rebuild context without the abandoned assistant theory"
    assert harness.patch_count == 2
    assert (harness.workspace / "src/service.py").read_text() == "STATE = 1\nSECOND = 1\n"
    assert all(result["ok"] for result in harness.check_results.values())


def test_stagnant_repeated_reads_are_bounded_without_source_changes(guarded_harness, monkeypatch, capsys):
    harness, _, _ = guarded_harness
    _baseline(harness)
    calls = []
    before = (harness.workspace / "src/service.py").read_bytes()

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        assert len(calls) <= 80, "safety ceiling must bound a no-progress fake model"
        return _assistant("read_file", {"path": "src/service.py"}, identifier=f"repeat-{len(calls)}")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture with intentionally unproductive repeated inspection.")
    assert calls
    assert (harness.workspace / "src/service.py").read_bytes() == before
    assert harness.patch_count == 0
    events = capsys.readouterr().out
    assert "stagnation" in events.lower() or "no-progress" in events.lower() or "no progress" in events.lower()


def test_truncated_reply_can_recover_without_mutating_from_partial_data(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    _baseline(harness)
    calls = []
    before = (harness.workspace / "src/service.py").read_bytes()

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        assert len(calls) < 15
        if len(calls) == 1:
            raise model_module.ModelTruncated("fixture truncated response; partial mutation must not execute")
        if len(calls) == 2:
            assert (harness.workspace / "src/service.py").read_bytes() == before
            return _assistant("apply_edits", _patch("STATE = 0", "STATE = 1"), identifier="complete-retry")
        return _assistant(content="Complete fixture repair.")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture with one truncated provider response.")
    assert len(calls) >= 2
    assert harness.patch_count == 1
    assert "STATE = 1" in (harness.workspace / "src/service.py").read_text()


def test_editor_respects_final_validation_time_reserve(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    harness.deadline = time.time() + harness.reserve_s + 1
    before = (harness.workspace / "src/service.py").read_bytes()

    def unexpected(*_args, **_kwargs):
        pytest.fail("editor must leave its final validation reserve intact")

    monkeypatch.setattr(harness.client, "complete", unexpected)
    harness.edit("Generic fixture with only its shutdown/validation allowance left.")
    assert (harness.workspace / "src/service.py").read_bytes() == before


def test_budget_exhaustion_stops_additional_editor_requests(guarded_harness, monkeypatch):
    harness, _, _ = guarded_harness
    _baseline(harness)
    calls = []

    def complete(messages, tools, **kwargs):
        calls.append(deepcopy(messages))
        assert len(calls) == 1, "exhausted shared budget must prevent another model request"
        harness.budget.spent = harness.budget.limit
        return _assistant("read_file", {"path": "src/service.py"}, identifier="last-affordable-call")

    monkeypatch.setattr(harness.client, "complete", complete)
    harness.edit("Generic fixture with budget exhausted after a final read.")
    assert len(calls) == 1
    assert harness.patch_count == 0


def test_model_unavailable_retains_prior_validated_partial_repair(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, spec: ["I_remaining"] if values["STATE"] == 1 else ["I_original", "I_remaining"]
    _baseline(harness)
    assert _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    before = (harness.workspace / "src/service.py").read_bytes()

    def unavailable(*_args, **_kwargs):
        raise ModelUnavailable("fixture proxy unavailable")

    monkeypatch.setattr(harness.client, "complete", unavailable)
    harness.edit("Generic fixture with a retained partial repair and unavailable proxy.")
    assert harness.patch_count == 1
    assert (harness.workspace / "src/service.py").read_bytes() == before
