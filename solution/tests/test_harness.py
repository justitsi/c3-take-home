"""Exercise controller plumbing with deterministic local HTTP, never paid models."""

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

import fix as harness_module
from fix import Harness, PROFILES


FIXER_DIR = Path(__file__).resolve().parents[1] / "fixer"


@pytest.fixture
def fixture_case(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    corpus = tmp_path / "corpus"
    for path in (workspace / "src/processor", workspace / "tests", workspace / "sim", corpus):
        path.mkdir(parents=True)
    (workspace / "case.json").write_text(json.dumps({"public_seeds": [11, 22]}))
    (workspace / "src/processor/__init__.py").write_text("")
    (workspace / "src/processor/service.py").write_text("VALUE = 1\n")
    (workspace / "README.md").write_text("processor fixture service; repair VALUE with public replay evidence.")
    (workspace / "SYMPTOM.md").write_text("Fixture service has an incorrect transition.")
    (workspace / "INVARIANTS.md").write_text("I_fixture: VALUE must equal 2.")
    (corpus / "INDEX.md").write_text("Fixture documentation index.")
    (workspace / "tests/test_service.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
        "from processor.service import VALUE\n"
        "def test_supported_public_interface():\n    assert VALUE in (1, 2)\n"
    )
    (workspace / "sim/__init__.py").write_text("")
    (workspace / "sim/__main__.py").write_text(
        "import argparse, json\nfrom pathlib import Path\n"
        "p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command')\n"
        "r=sub.add_parser('replay'); r.add_argument('--scenario'); r.add_argument('--seed', type=int); r.add_argument('--out')\n"
        "c=sub.add_parser('check'); c.add_argument('--trace'); a=p.parse_args()\n"
        "if a.command=='replay':\n"
        "    scope={}; exec(Path('src/processor/service.py').read_text(), scope)\n"
        "    out=Path(a.out); out.mkdir(parents=True, exist_ok=True)\n"
        "    (out/'trace.jsonl').write_text(json.dumps({'value':scope['VALUE'],'seed':a.seed})+'\\n')\n"
        "    (out/'summary.json').write_text('{}')\n"
        "else:\n"
        "    trace=Path(a.trace); value=json.loads(trace.read_text())['value']\n"
        "    violations=[] if value==2 else [{'invariant':'I_fixture','detail':'original fixture bug'}]\n"
        "    (trace.parent/'summary.json').write_text(json.dumps({'invariants':violations}))\n"
        "    raise SystemExit(1 if violations else 0)\n"
    )
    monkeypatch.setenv("C3_WORKSPACE", str(workspace))
    monkeypatch.setenv("C3_CORPUS", str(corpus))
    monkeypatch.setenv("C3_BUDGET_USD", "3")
    monkeypatch.setenv("C3_DEADLINE", str(time.time() + 180))
    monkeypatch.setenv("OPENAI_API_KEY", "local-fixture-token")
    monkeypatch.setenv("ANTHROPIC_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    return workspace, corpus


def start_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def send_reply(handler, content="", tool_calls=None):
    data = json.dumps({
        "choices": [{"message": {"role": "assistant", "content": content, "tool_calls": tool_calls or []}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.001},
    }).encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def test_hypothesis_register_and_experiment_journal_are_structured(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    hypotheses = Harness._parse_hypotheses(
        'Hypotheses: {"hypotheses":[{"id":"lease-race","scope":["src/processor/service.py:renew"],'
        '"cause":"renewal races release","evidence":[{"path":"src/processor/service.py","line":2}],'
        '"prediction":"stale epoch accepted","test":"replay delayed renewal"}]}',
        "leases-membership",
    )
    assert hypotheses[0]["id"] == "lease-race"
    assert hypotheses[0]["agent"] == "leases-membership"

    harness = Harness()
    result = harness.experiment_tool("replay_check", {
        "seed": 11, "hypothesis_id": "lease-race",
    }, "test-agent")
    assert result["trace_path"]
    assert harness.experiments[0]["hypothesis_id"] == "lease-race"
    assert harness.experiments[0]["violations"][0]["invariant"] == "I_fixture"
    assessment = harness.assess_hypothesis({
        "hypothesis_id": "lease-race",
        "verdict": "weakened",
        "explanation": "The check failed on the original invariant, but did not show stale-epoch acceptance.",
    }, "test-agent")
    assert assessment["ok"]
    assert harness.hypothesis_assessments[0]["verdict"] == "weakened"


def test_candidate_seed_selection_prioritizes_failures_guards_then_exploration(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    (workspace / "case.json").write_text(json.dumps({"public_seeds": [11, 22, 33, 44]}))
    harness = Harness()
    harness.baseline = {"replays": [
        {"seed": 11, "ok": False},
        {"seed": 22, "ok": True},
    ]}
    harness.passing_seeds = {22}
    harness.known_failing_seeds = {11}
    harness.explored_seeds = {11, 22}
    selected, roles = harness.candidate_seeds()
    assert selected == [11, 22, 33]
    assert roles == {
        11: "known-failing reproducer",
        22: "retained regression guard",
        33: "exploration seed",
    }


def test_followup_routing_responds_to_failure_class(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    harness.records = [{"rejection_reasons": ["previously passing seed regressed"]}]
    assert "regressed" in harness.followup_directive(2)
    harness.records = [{"rejection_reasons": [
        "new invariant categories appeared; combine prerequisite repairs if needed",
    ]}]
    assert "new counterexample" in harness.followup_directive(2)


def test_resource_release_investigator_is_added_for_capacity_services(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    modules = workspace / "src/processor"
    (modules / "capacity.py").write_text("class CapacityLedger: pass\n")
    (modules / "releaser.py").write_text("class ReleaseManager: pass\n")

    harness = Harness()

    assert harness.profiles[-1][0] == "resource-release-lifecycle"
    assert "ReleaseComplete" in harness.profiles[-1][1]


def test_followup_audits_supported_hypotheses_not_in_accepted_candidate(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    harness.hypotheses = [
        {"id": "lease-fence", "agent": "leases", "cause": "late report", "scope": ["executor"]},
        {"id": "release-ack", "agent": "resources", "cause": "free before release completion",
         "scope": ["releaser"]},
    ]
    harness.hypothesis_assessments = [{
        "hypothesis_id": "release-ack", "verdict": "supported", "explanation": "contract mismatch",
    }]
    harness.records = [{"accepted": True, "hypothesis_ids": ["lease-fence"]}]

    directive = harness.followup_directive(2)

    assert "not included in an accepted candidate" in directive
    assert "release-ack" in directive
    assert "lease-fence" not in directive


def test_numbered_ticket_reports_get_dedicated_investigators(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    (workspace / "SYMPTOM.md").write_text(
        "Intro paragraph.\n\n1. **Billing.** Cancelled jobs were billed.\n\n"
        "2. **Stuck.** Big jobs never start after restart.\n\n3. **Flood.** Registration spam.\n"
    )
    harness = Harness()
    names = [name for name, _ in harness.profiles]
    assert names[-3:] == ["ticket-report-1", "ticket-report-2", "ticket-report-3"]
    assert "Big jobs never start" in harness.profiles[-2][1]
    assert "ONLY this reported issue" in harness.profiles[-1][1]
    assert "Registration spam" in harness.followup_directive(1)

    (workspace / "SYMPTOM.md").write_text("1. **Only one.** Single report.\n")
    assert Harness().ticket_items == []


def test_investigator_without_json_is_asked_to_conclude(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    harness.investigation_until = time.time() + 600
    replies = [
        {"role": "assistant", "content": "Long narrative cut off {\"hypotheses\": [{\"id\": "},
        {"role": "assistant", "content": json.dumps({"hypotheses": [
            {"id": "H1", "scope": ["src/a.py:f"], "cause": "c"}], "finding": "f"})},
    ]
    calls = []

    class FakeClient:
        def complete(self, messages, tools, **kwargs):
            calls.append(tools)
            return replies.pop(0)

    harness.client = FakeClient()
    result = harness.investigate(("probe", "focus"), "context")
    assert [h["id"] for h in result["hypotheses"]] == ["H1"]
    assert calls[-1] == []


def test_b1_selects_speculation_and_commit_investigator(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    (workspace / "case.json").write_text(json.dumps({
        "id": "B1", "public_seeds": [12, 14, 20],
    }))
    harness = Harness()
    assert len(harness.profiles) == len(PROFILES) + 1
    assert harness.profiles[-1][0] == "speculation-commit-coordination"
    assert "task identity" in harness.profiles[-1][1]


def test_new_failure_category_is_compared_to_that_seeds_baseline(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    (workspace / "case.json").write_text(json.dumps({
        "id": "A2", "public_seeds": [11, 22, 33],
    }))
    harness = Harness()
    harness.baseline = {"replays": [
        {"seed": 11, "ok": False, "violations": [{"invariant": "I_fixture"}]},
        {"seed": 22, "ok": True, "violations": []},
    ]}
    harness.seed_results = {item["seed"]: item for item in harness.baseline["replays"]}
    harness.known_failing_seeds = {11}
    harness.passing_seeds = {22}
    harness.explored_seeds = {11, 22}

    original_replay = harness.validation.replay_check

    def replay_baseline(seed, **kwargs):
        if seed == 33:
            return {"ok": False, "seed": seed, "violations": [{"invariant": "I_EXTRA"}],
                    "trace_path": "", "replay_exit": 0, "check_exit": 1}
        return original_replay(seed, **kwargs)

    monkeypatch.setattr(harness.validation, "replay_check", replay_baseline)
    monkeypatch.setattr(harness, "checks", lambda seeds, repeat=False: {
        "syntax": {"ok": True},
        "tests": {"ok": True},
        "replays": [
            {"seed": seed, "ok": seed != 33,
             "violations": ([{"invariant": "I_EXTRA"}] if seed == 33 else []),
             "replay_exit": 0, "check_exit": 1 if seed == 33 else 0,
             "deterministic": True}
            for seed in seeds
        ],
    })
    result = harness.apply_candidate({"hypothesis_ids": ["hyp-a"],
        "edits": [{"path": "src/processor/service.py", "old": "VALUE = 1", "new": "VALUE = 2"}]})
    assert result["ok"]
    record = harness.records[-1]
    assert record["seed_roles"]["33"] == "newly measured failing reproducer"
    assert record["new_invariant_categories"] == []


def test_rejected_candidate_retains_edit_and_validation_evidence(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    harness.baseline = {"replays": [
        {"seed": 11, "ok": False, "violations": [{"invariant": "I_fixture"}],
         "trace_path": "/scratch/baseline-11.jsonl"},
        {"seed": 22, "ok": True, "violations": []},
    ]}
    harness.seed_results = {item["seed"]: item for item in harness.baseline["replays"]}
    harness.known_failing_seeds = {11}
    harness.passing_seeds = {22}
    harness.explored_seeds = {11, 22}
    monkeypatch.setattr(harness, "checks", lambda seeds, repeat=False: {
        "syntax": {"ok": True},
        "tests": {"ok": True, "output": "3 passed"},
        "replays": [
            {"seed": 11, "ok": False, "violations": [{"invariant": "I_fixture"}],
             "replay_exit": 0, "check_exit": 1, "deterministic": True,
             "trace_path": "/scratch/candidate-11.jsonl"},
            {"seed": 22, "ok": True, "violations": [],
             "replay_exit": 0, "check_exit": 0},
        ],
    })

    edits = [{"path": "src/processor/service.py", "old": "VALUE = 1", "new": "VALUE = 3"}]
    result = harness.apply_candidate({"hypothesis_ids": ["hyp-a"], "edits": edits})

    assert not result["ok"]
    record = harness.records[-1]
    assert record["outcome"] == "original_failure_persists"
    assert record["candidate_edits"] == edits
    assert record["validation_summary"]["seeds"][0]["violations"][0]["invariant"] == "I_fixture"
    assert harness.latest_candidate_evidence()["candidate_edits"] == edits
    assert harness.latest_candidate_evidence()["validation"]["seeds"][0]["baseline_trace_path"] == "/scratch/baseline-11.jsonl"
    assert harness.latest_candidate_evidence()["validation"]["seeds"][0]["candidate_trace_path"] == "/scratch/candidate-11.jsonl"
    assert (fixture_case[0] / "src/processor/service.py").read_text() == "VALUE = 1\n"


def test_editor_retries_once_after_narrative_only_round(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    monkeypatch.setattr(harness, "enough_time", lambda seconds=0: True)
    monkeypatch.setattr(harness, "experiment_tool", lambda *args: {
        "ok": False, "violations": [{"invariant": "I_fixture"}],
    })
    requests = []

    def complete(messages, tools, **kwargs):
        requests.append([dict(message) for message in messages])
        if len(requests) == 1:
            return {"role": "assistant", "content": "The code may have a recovery issue."}
        if len(requests) == 2:
            return {"role": "assistant", "content": "", "tool_calls": [{
                "id": "editor-replay",
                "type": "function",
                "function": {"name": "replay_check", "arguments": json.dumps({
                    "seed": 11, "hypothesis_id": "recovery",
                })},
            }]}
        return {"role": "assistant", "content": "No further supported change."}

    monkeypatch.setattr(harness.client, "complete", complete)

    harness.edit("Fixture context")

    assert "This round has not run an experiment" in requests[1][-1]["content"]
    assert len(harness.experiments) == 0
    assert len(harness.diagnosis_rounds) == 3
    assert len(requests) >= 5


def test_editor_escalates_after_two_read_only_batches(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    monkeypatch.setattr(harness, "enough_time", lambda seconds=0: True)
    monkeypatch.setattr(harness, "read_tool", lambda *args: {"ok": True})
    monkeypatch.setattr(harness, "experiment_tool", lambda *args: {
        "ok": False, "violations": [{"invariant": "I_fixture"}],
    })
    requests = []
    toolsets = []
    choices = []
    experiment_calls = []

    def call(name, call_id):
        return {"role": "assistant", "content": "", "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps({"path": "src/processor/service.py"})
                         if name == "read_file" else json.dumps({"seed": 11})},
        }]}

    def complete(messages, tools, **kwargs):
        requests.append([dict(message) for message in messages])
        toolsets.append(tools)
        choices.append(kwargs.get("tool_choice"))
        if len(requests) in (1, 2):
            return call("read_file", f"read-{len(requests)}")
        if len(requests) == 3:
            return call("replay_check", "replay")
        return {"role": "assistant", "content": "No further supported change."}

    monkeypatch.setattr(harness.client, "complete", complete)
    original_experiment_tool = harness.experiment_tool

    def record_experiment(*args):
        experiment_calls.append(args)
        return original_experiment_tool(*args)

    monkeypatch.setattr(harness, "experiment_tool", record_experiment)

    harness.edit("Fixture context")

    assert {"apply_edits", "replay_check"} <= {tool["function"]["name"] for tool in toolsets[2]}
    assert "read_file" not in {tool["function"]["name"] for tool in toolsets[2]}
    assert choices[2] == "required"
    assert "two read-only tool batches" in requests[2][-1]["content"]
    assert len(experiment_calls) == 1


def test_editor_retries_after_rejected_candidate_even_if_round_had_action(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    monkeypatch.setattr(harness, "enough_time", lambda seconds=0: True)
    attempted_edits = [{"path": "src/processor/service.py", "old": "VALUE = 1", "new": "VALUE = 2"}]

    def reject_candidate(_args):
        harness.records.append({
            "round": harness.current_round,
            "accepted": False,
            "outcome": "new_counterexample",
            "candidate_edits": attempted_edits,
            "experiment_count_at_candidate": len(harness.experiments),
            "remaining_invariants": {"11": ["I_capacity"]},
            "rejection_reasons": ["new invariant categories appeared"],
            "validation_summary": {"seeds": [{
                "seed": 11,
                "baseline_trace_path": "/scratch/baseline.jsonl",
                "candidate_trace_path": "/scratch/candidate.jsonl",
                "baseline_violations": [],
                "violations": [{"invariant": "I_capacity"}],
            }]},
        })
        return {"ok": False, "retained": False, "rejection_reasons": ["new counterexample"]}

    monkeypatch.setattr(harness, "apply_candidate", reject_candidate)

    def record_experiment(name, args, agent):
        harness.experiments.append({"round": harness.current_round, "tool": name})
        return {"ok": True, "identical": False}

    monkeypatch.setattr(harness, "experiment_tool", record_experiment)
    requests = []
    toolsets = []

    def complete(messages, tools, **kwargs):
        requests.append([dict(message) for message in messages])
        toolsets.append(tools)
        if len(requests) == 1:
            return {"role": "assistant", "content": "", "tool_calls": [{
                "id": "editor-edit",
                "type": "function",
                "function": {"name": "apply_edits", "arguments": json.dumps({"edits": attempted_edits})},
            }]}
        if len(requests) in (2, 3):
            return {"role": "assistant", "content": "", "tool_calls": [{
                "id": f"editor-read-{len(requests)}",
                "type": "function",
                "function": {"name": "read_file", "arguments": json.dumps({
                    "path": "src/processor/service.py",
                })},
            }]}
        if len(requests) in (4, 5):
            name, call_id = (
                ("compare_traces", "editor-compare") if len(requests) == 4
                else ("replay_check", "editor-replay")
            )
            arguments = ({
                "first": "/scratch/baseline.jsonl", "second": "/scratch/candidate.jsonl",
                "hypothesis_id": "capacity",
            } if name == "compare_traces" else {"seed": 11, "hypothesis_id": "capacity"})
            return {"role": "assistant", "content": "", "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }]}
        if len(requests) == 6:
            return {"role": "assistant", "content": "", "tool_calls": [{
                "id": "editor-revised-edit",
                "type": "function",
                "function": {"name": "apply_edits", "arguments": json.dumps({"edits": attempted_edits})},
            }]}
        return {"role": "assistant", "content": "The candidate needs a capacity-safe retry."}

    monkeypatch.setattr(harness.client, "complete", complete)

    harness.edit("Fixture context")

    names = {tool["function"]["name"] for tool in toolsets[3]}
    assert "read_file" not in names and "apply_edits" in names and "compare_traces" in names
    assert "Stop broad reads" in requests[3][-1]["content"]
    assert {tool["function"]["name"] for tool in toolsets[5]} == {"apply_edits"}
    assert "Two targeted experiments" in requests[5][-1]["content"]
    assert len(harness.diagnosis_rounds) == 3


def test_accepted_repair_keeps_source_reads_available_after_later_rejection(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    monkeypatch.setattr(harness, "enough_time", lambda seconds=0: True)
    attempted_edits = [{"path": "src/processor/service.py", "old": "VALUE = 1", "new": "VALUE = 2"}]

    candidate_results = iter((True, False))

    def candidate(_args):
        accepted = next(candidate_results)
        harness.records.append({
            "round": harness.current_round,
            "accepted": accepted,
            "outcome": "baseline_improved" if accepted else "original_failure_persists",
            "candidate_edits": attempted_edits,
            "experiment_count_at_candidate": len(harness.experiments),
            "remaining_invariants": {"11": ["I_secondary"]},
        })
        return {"ok": accepted, "accepted": accepted}

    monkeypatch.setattr(harness, "apply_candidate", candidate)
    monkeypatch.setattr(harness, "read_tool", lambda *args: {"ok": True})

    def record_experiment(*_args):
        harness.experiments.append({"round": harness.current_round, "tool": "replay_check"})
        return {"ok": True, "violations": [{"invariant": "I_secondary"}]}

    monkeypatch.setattr(harness, "experiment_tool", record_experiment)
    requests = []
    toolsets = []

    def tool_call(name, call_id):
        args = {"edits": attempted_edits} if name == "apply_edits" else (
            {"seed": 11} if name == "replay_check" else {"path": "src/processor/service.py"}
        )
        return {"role": "assistant", "content": "", "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }]}

    def complete(messages, tools, **kwargs):
        requests.append([dict(message) for message in messages])
        toolsets.append(tools)
        if len(requests) == 1:
            return tool_call("apply_edits", "accepted-edit")
        if len(requests) == 2:
            return tool_call("apply_edits", "rejected-edit")
        if len(requests) in (3, 4):
            return tool_call("replay_check", f"experiment-{len(requests)}")
        if len(requests) == 5:
            return tool_call("read_file", "source-read")
        return {"role": "assistant", "content": "No further supported change."}

    monkeypatch.setattr(harness.client, "complete", complete)

    harness.edit("Fixture context")

    fifth_toolset = {tool["function"]["name"] for tool in toolsets[4]}
    assert "read_file" in fifth_toolset
    assert "apply_edits" in fifth_toolset
    assert "Two targeted experiments" not in requests[4][-1]["content"]


def test_final_round_requires_a_candidate_after_two_experiments(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    monkeypatch.setattr(harness, "enough_time", lambda seconds=0: True)
    harness.records.append({
        "round": 1,
        "accepted": True,
        "outcome": "baseline_improved",
        "candidate_edits": [],
        "experiment_count_at_candidate": 0,
        "remaining_invariants": {"11": ["I_secondary"]},
    })
    monkeypatch.setattr(harness, "experiment_tool", lambda name, args, agent: (
        harness.experiments.append({"round": harness.current_round, "tool": name})
        or {"ok": True, "violations": [{"invariant": "I_secondary"}]}
    ))

    def apply_candidate(_args):
        harness.records.append({
            "round": harness.current_round,
            "accepted": True,
            "outcome": "baseline_improved",
            "candidate_edits": [],
            "experiment_count_at_candidate": len(harness.experiments),
            "remaining_invariants": {},
        })
        return {"ok": True, "accepted": True}

    monkeypatch.setattr(harness, "apply_candidate", apply_candidate)
    requests = []
    round_three_toolsets = []
    round_three_choices = []

    def complete(messages, tools, **kwargs):
        requests.append([dict(message) for message in messages])
        if harness.current_round == 3:
            round_three_toolsets.append(tools)
            round_three_choices.append(kwargs.get("tool_choice"))
            if len(round_three_toolsets) <= 2:
                return {"role": "assistant", "content": "", "tool_calls": [{
                    "id": f"replay-{len(round_three_toolsets)}",
                    "type": "function",
                    "function": {"name": "replay_check", "arguments": json.dumps({"seed": 11})},
                }]}
            if len(round_three_toolsets) == 3:
                return {"role": "assistant", "content": "", "tool_calls": [{
                    "id": "final-edit",
                    "type": "function",
                    "function": {"name": "apply_edits", "arguments": json.dumps({"edits": []})},
                }]}
        return {"role": "assistant", "content": "No further supported change."}

    monkeypatch.setattr(harness.client, "complete", complete)

    harness.edit("Fixture context")

    assert len(round_three_toolsets) >= 3
    assert {tool["function"]["name"] for tool in round_three_toolsets[2]} == {"apply_edits"}
    assert round_three_choices[2] == "required"
    assert len(harness.experiments) == 2
    assert len(harness.records) == 2


@pytest.mark.parametrize("candidate_value,expected_accept", [(2, True), (3, False)])
def test_three_parallel_investigators_then_checked_serial_editor(fixture_case, monkeypatch, candidate_value, expected_accept):
    """Real client HTTP, source tools, pytest, replay/check, snapshots and rollback."""
    arrived = threading.Barrier(len(PROFILES))
    lock = threading.Lock()
    counts = {}
    requests = []
    failures = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert self.path == "/v1/chat/completions"
                assert body["model"] == "anthropic/claude-sonnet-4.6"
                prompt = "\n".join(message.get("content", "") or "" for message in body["messages"])
                actor = next((name for name, _ in PROFILES if f"You are the {name} specialist" in prompt), "editor")
                with lock:
                    turn = counts.get(actor, 0)
                    counts[actor] = turn + 1
                    requests.append((actor, body))
                if actor != "editor":
                    assert all(tool["function"]["name"] != "apply_edits" for tool in body.get("tools", []))
                    if turn == 0:
                        # Fails unless all three specialists really overlap.
                        arrived.wait(timeout=10)
                        send_reply(self, tool_calls=[{"id": actor + "-read", "type": "function", "function": {
                            "name": "read_file", "arguments": json.dumps({"path": "src/processor/service.py"})}}])
                    else:
                        send_reply(self, content="Evidence: service.py line 1; change VALUE = 1 to VALUE = 2, then replay/check.")
                elif turn == 0:
                    assert all(counts.get(name, 0) >= 2 for name, _ in PROFILES)
                    send_reply(self, tool_calls=[{"id": "editor-edit", "type": "function", "function": {
                        "name": "apply_edits", "arguments": json.dumps({"edits": [{
                            "path": "src/processor/service.py", "old": "VALUE = 1", "new": f"VALUE = {candidate_value}"}]})}}])
                else:
                    send_reply(self, content="Fixture repair attempt complete.")
            except Exception as error:
                failures.append(str(error))
                self.send_error(500)

        def log_message(self, *_):
            pass

    server = start_server(Handler)
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    previous_handlers = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        harness = Harness()
        assert harness.run() == 0
        assert not failures
        assert set(counts) == {name for name, _ in PROFILES} | {"editor"}
        assert len(harness.findings) == len(PROFILES)
        assert len(harness.records) == 1
        assert [item["round"] for item in harness.diagnosis_rounds] == [1, 2, 3]
        assert harness.records[0]["accepted"] is expected_accept
        assert harness.patch_count == int(expected_accept)
        report = json.loads((fixture_case[0] / ".c3-fixer-report.json").read_text())
        assert len(report["diagnosis_rounds"]) == 3
        assert "hypotheses" in report and "experiments" in report
        assert "hypothesis_assessments" in report
        assert harness.budget.calls == len(requests)
        expected = candidate_value if expected_accept else 1
        assert (fixture_case[0] / "src/processor/service.py").read_text() == f"VALUE = {expected}\n"
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)
        server.shutdown()
        server.server_close()


def test_candidate_mutations_are_serialized(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    (workspace / "src/first.py").write_text("FIRST = 0\n")
    (workspace / "src/second.py").write_text("SECOND = 0\n")
    harness = Harness()
    actual_apply = harness.tools.apply_edits
    lock = threading.Lock()
    active = maximum = 0

    def measured_apply(**args):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(active, maximum)
        try:
            time.sleep(0.05)
            return actual_apply(**args)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(harness.tools, "apply_edits", measured_apply)
    harness.baseline = {"replays": [
        {"seed": 11, "ok": False, "violations": [{"invariant": "I_first"}]},
        {"seed": 22, "ok": False, "violations": [{"invariant": "I_second"}]},
    ]}
    harness.known_failing_seeds = {11, 22}
    harness.passing_seeds = set()
    harness.explored_seeds = {11, 22}
    harness.seed_results = {item["seed"]: item for item in harness.baseline["replays"]}

    def checks(*args, **kwargs):
        first_fixed = "FIRST = 1" in (workspace / "src/first.py").read_text()
        second_fixed = "SECOND = 1" in (workspace / "src/second.py").read_text()
        violations = {
            11: [] if first_fixed else [{"invariant": "I_first"}],
            22: [] if second_fixed else [{"invariant": "I_second"}],
        }
        return {
            "syntax": {"ok": True},
            "tests": {"ok": True},
            "replays": [{
                "seed": seed, "ok": not violations[seed], "violations": violations[seed],
                "replay_exit": 0, "check_exit": 0 if not violations[seed] else 1,
                "deterministic": True,
            } for seed in (11, 22)],
        }

    monkeypatch.setattr(harness, "checks", checks)
    edits = [{"edits": [{"path": f"src/{name.lower()}.py", "old": f"{name} = 0", "new": f"{name} = 1"}]} for name in ("FIRST", "SECOND")]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(harness.apply_candidate, edits))
    assert all(result["ok"] for result in results)
    assert maximum == 1
    assert harness.patch_count == 2


def test_failed_tool_transaction_restores_checkpoint_after_rollback_failure(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    source = workspace / "src/processor/service.py"
    original = source.read_bytes()
    harness = Harness()

    def partially_failed_transaction(**_):
        source.write_text("VALUE = 999\n")
        return {"ok": False, "error": "candidate install failed", "rollback_errors": ["first file rollback failed"]}

    monkeypatch.setattr(harness.tools, "apply_edits", partially_failed_transaction)
    result = harness.apply_candidate({"edits": []})
    assert not result["ok"]
    assert source.read_bytes() == original
    assert harness.active_snapshot is None
    assert harness.patch_count == 0


@pytest.mark.parametrize("incomplete", ["missing_determinism", "incomplete_seed_set", "duplicate_seed_set"])
def test_candidate_requires_complete_seeds_and_positive_determinism(fixture_case, monkeypatch, incomplete):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    source = workspace / "src/processor/service.py"
    original = source.read_bytes()
    harness = Harness()
    harness.baseline = {"replays": [
        {"seed": 11, "ok": False, "violations": [{"invariant": "I_fixture"}]},
        {"seed": 22, "ok": True, "violations": []},
    ]}
    harness.seed_results = {item["seed"]: item for item in harness.baseline["replays"]}
    harness.known_failing_seeds = {11}
    harness.passing_seeds = {22}
    harness.explored_seeds = {11, 22}
    replays = [{"seed": seed, "ok": True, "replay_exit": 0, "check_exit": 0,
                "violations": [], "deterministic": True} for seed in (11, 22)]
    if incomplete == "missing_determinism":
        del replays[0]["deterministic"]
    elif incomplete == "incomplete_seed_set":
        replays = replays[:1]
    else:
        replays[1]["seed"] = 11
    monkeypatch.setattr(harness, "checks", lambda *args, **kwargs: {
        "syntax": {"ok": True}, "tests": {"ok": True}, "replays": replays,
    })
    result = harness.apply_candidate({"edits": [{
        "path": "src/processor/service.py", "old": "VALUE = 1", "new": "VALUE = 2"}]})
    assert not result["ok"]
    assert source.read_bytes() == original
    assert harness.patch_count == 0


@pytest.mark.parametrize("shutdown", ["deadline", "SIGTERM"])
def test_shutdown_interrupts_blocked_model_calls(fixture_case, monkeypatch, shutdown):
    """A real child controller must exit while HTTP workers are still blocked."""
    release = threading.Event()
    all_arrived = threading.Event()
    lock = threading.Lock()
    arrived = 0

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            nonlocal arrived
            self.rfile.read(int(self.headers["Content-Length"]))
            with lock:
                arrived += 1
                if arrived == len(PROFILES):
                    all_arrived.set()
            release.wait(timeout=20)
            try:
                send_reply(self, content="Late fixture response.")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_):
            pass

    server = start_server(Handler)
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    deadline = time.time() + (12 if shutdown == "deadline" else 90)
    monkeypatch.setenv("C3_DEADLINE", str(deadline))
    env = dict(os.environ, PYTHONPATH=str(FIXER_DIR))
    script = (
        "import time\nfrom fix import Harness\n"
        "h=Harness(); h.reserve_s=0; h.client.reserve_s=0\n"
        "h.investigation_until=h.deadline\n"
        "h.enough_time=lambda seconds=0: not h.stop.is_set() and time.time()+0.1<h.deadline\n"
        "raise SystemExit(h.run())\n"
    )
    process = subprocess.Popen([sys.executable, "-c", script], cwd=fixture_case[0], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert all_arrived.wait(timeout=8), "three model requests did not start before shutdown"
        if shutdown == "SIGTERM":
            process.send_signal(signal.SIGTERM)
        output, _ = process.communicate(timeout=14)
        assert process.returncode == 0, output
        assert time.time() < deadline
        assert f'"status": "{shutdown}"' in output, output
        assert (fixture_case[0] / "src/processor/service.py").read_text() == "VALUE = 1\n"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=2)
        release.set()
        server.shutdown()
        server.server_close()


def test_probe_baselines_are_kept_once_and_compared_after_candidate(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    harness.remember_probe({"seed": 1}, {"violation_count": 0, "log_signatures": {"x": 1}})
    assert harness.probes == {}
    args = {"seed": 3, "scenario": "public", "faults": "scenarios/faults/network.yaml"}
    harness.remember_probe(args, {"violation_count": 2, "log_signatures": {"lost": 5, "same": 1}})
    harness.remember_probe(args, {"violation_count": 0, "log_signatures": {"lost": 0}})
    assert harness.probes["3|public|scenarios/faults/network.yaml"]["log_signatures"]["lost"] == 5

    harness._checked_replay = lambda a: {"violation_count": 0, "log_signatures": {"lost": 1, "same": 1}}
    [delta] = harness.probe_deltas()
    assert delta["log_signature_changes_before_after"] == {"lost": [5, 1]}
    assert (delta["violations_before"], delta["violations_after"]) == (2, 0)


def test_ticket_signatures_and_focus_rounds(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    (workspace / "SYMPTOM.md").write_text(
        "1. **A.** Jobs hang.\n\n2. **B.** coord logs `task_finished outcome=missing_from_heartbeat` too often.\n\n"
        "3. **C.** Loss hangs jobs.\n"
    )
    harness = Harness()
    assert harness.symptom_targets == ["outcome=missing_from_heartbeat"]
    assert harness.total_rounds == 5
    assert "ROUND FOCUS: repair ONLY ticket report 2" in harness.followup_directive(2)
    assert "ROUND FOCUS" not in harness.followup_directive(4)
    assert harness.remaining_violation_note() == ""


def test_remaining_violations_reach_later_directives_with_stuck_timeline(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    harness = Harness()
    harness.records.append({"accepted": True, "paths": ["a.py"], "probe_deltas": [
        {"seed": 1, "scenario": "public", "faults": "scenarios/faults/p.yaml", "violations_before": 2,
         "violations_after": 2, "anomaly_signatures_unchanged_by_candidate": {},
         "stuck_entity_timeline": [{"unresolved": "A:q1", "events": [{"event": "batch_report_abandoned"}]}]},
        {"seed": 1, "scenario": "public", "faults": "scenarios/faults/ok.yaml", "violations_before": 3,
         "violations_after": 0, "anomaly_signatures_unchanged_by_candidate": {}, "stuck_entity_timeline": []}]})
    note = harness.followup_directive(1)
    assert "STILL VIOLATING" in note and "p.yaml" in note and "batch_report_abandoned" in note
    assert "ok.yaml" not in note


def test_probe_symptom_pins_symptomatic_and_violating_profiles(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    (workspace / "SYMPTOM.md").write_text("Logs show `outcome=missing_from_heartbeat`.\n")
    faults = workspace / "scenarios/faults"
    faults.mkdir(parents=True)
    for name in ("a", "b", "c"):
        (faults / f"{name}.yaml").write_text("x: 1\n")
    results = {
        "a": {"summary": {"x": 1}, "replay_exit": 0, "violation_count": 0, "trace_path": "/nonexistent",
              "log_signatures": {"task_finished|outcome=missing_from_heartbeat": 4}},
        "b": {"summary": {"x": 1}, "replay_exit": 0, "violation_count": 2, "trace_path": "/nonexistent",
              "violations": [], "unresolved_entities": [], "log_signatures": {}},
        "c": {"summary": {"x": 1}, "replay_exit": 0, "violation_count": 0, "trace_path": "/nonexistent",
              "log_signatures": {}},
    }
    harness = Harness()
    harness._checked_replay = lambda args: results[Path(args["faults"]).stem]
    text = harness.probe_symptom()
    assert "missing_from_heartbeat" in text and "latent failures" in text
    pinned = {key.split("|")[-1] for key, p in harness.probes.items() if p["pinned"]}
    assert pinned == {"scenarios/faults/a.yaml", "scenarios/faults/b.yaml"}


def test_residual_forcing_only_for_multi_report_tickets(fixture_case, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    workspace, _ = fixture_case
    harness = Harness()
    assert harness.ticket_items == [] and harness.residual_start > harness.total_rounds
    (workspace / "SYMPTOM.md").write_text("1. **A.** One.\n\n2. **B.** Two.\n\n3. **C.** Three.\n")
    harness = Harness()
    assert harness.residual_start == 4 and harness.total_rounds == 5
