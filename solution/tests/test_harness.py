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
                    assert all(tool["function"]["name"] != "apply_edits" for tool in body["tools"])
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
        assert harness.records[0]["accepted"] is expected_accept
        assert harness.patch_count == int(expected_accept)
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
    monkeypatch.setattr(harness, "checks", lambda *args, **kwargs: {
        "syntax": {"ok": True}, "tests": {"ok": True},
        "replays": [{"seed": seed, "ok": True, "replay_exit": 0, "check_exit": 0,
                     "deterministic": True} for seed in (11, 22)],
    })
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
